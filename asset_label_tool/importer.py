import csv
import os
from typing import List, Optional, Dict, Tuple
from .models import Asset
from .store import Store


FIELD_MAPPING = {
    "asset_id": ["asset_id", "资产编号", "编号", "id", "asset_id"],
    "name": ["name", "资产名称", "名称", "asset_name"],
    "location": ["location", "位置", "存放位置", "位置信息"],
    "responsible": ["responsible", "责任人", "负责人", "保管人"],
    "category": ["category", "类别", "分类", "资产类别"],
}


def _normalize_header(header: str) -> str:
    h = header.strip()
    for canonical, aliases in FIELD_MAPPING.items():
        if h.lower() in [a.lower() for a in aliases]:
            return canonical
    return h


def _read_rows(file_path: str, sheet: Optional[str] = None) -> Tuple[List[dict], str, List[str]]:
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".csv",):
        rows = []
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = [h for h in (reader.fieldnames or []) if h is not None]
            normalized = {h: _normalize_header(h) for h in headers}
            for idx, row in enumerate(reader, start=2):
                mapped = {"_row": idx}
                try:
                    for orig, norm in normalized.items():
                        val = row.get(orig, "")
                        mapped[norm] = "" if val is None else str(val).strip()
                except Exception:
                    pass
                rows.append(mapped)
            present = set(normalized.values())
            missing = [c for c in FIELD_MAPPING.keys() if c not in present]
        return rows, "csv", missing

    elif ext in (".xlsx", ".xls"):
        try:
            import openpyxl
        except ImportError:
            raise ImportError("需要安装 openpyxl 库来读取 Excel 文件: pip install openpyxl")

        wb = openpyxl.load_workbook(file_path, read_only=True)
        ws = wb[sheet] if sheet else wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if not raw_rows:
            return [], "xlsx", list(FIELD_MAPPING.keys())

        headers = [str(h or "") for h in raw_rows[0]]
        normalized = {h: _normalize_header(h) for h in headers}

        rows = []
        for idx, row in enumerate(raw_rows[1:], start=2):
            row_data = {"_row": idx}
            try:
                for i, orig in enumerate(headers):
                    norm = normalized.get(orig, orig)
                    val = row[i] if i < len(row) else ""
                    row_data[norm] = "" if val is None else str(val).strip()
            except Exception:
                pass
            rows.append(row_data)
        present = set(normalized.values())
        missing = [c for c in FIELD_MAPPING.keys() if c not in present]
        return rows, "xlsx", missing
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def validate_assets(rows: List[dict], store: Store, category: Optional[str] = None,
                    auto_id: bool = False, id_prefix: str = "AST",
                    missing_columns: Optional[List[str]] = None) -> dict:
    report = {
        "total_rows": len(rows),
        "empty_id_rows": [],
        "duplicate_rows": [],
        "missing_field_rows": [],
        "auto_generated_ids": [],
        "valid_assets": [],
        "will_be_skipped": [],
        "missing_columns": missing_columns or [],
    }

    seen_ids = set()

    db_max_num = store.get_next_sequential_number(id_prefix) - 1
    file_max_num = 0
    for row_data in rows:
        asset_id = row_data.get("asset_id", "").strip()
        if asset_id and asset_id.startswith(id_prefix):
            try:
                num = int(asset_id[len(id_prefix):])
                if num > file_max_num:
                    file_max_num = num
            except ValueError:
                pass

    next_num = max(db_max_num, file_max_num) + 1

    for row_data in rows:
        row_num = row_data.get("_row", "?")
        asset_id = row_data.get("asset_id", "").strip()

        if category:
            row_data["category"] = category

        if not asset_id:
            if auto_id:
                asset_id = f"{id_prefix}{next_num:06d}"
                next_num += 1
                report["auto_generated_ids"].append({"row": row_num, "asset_id": asset_id})
            else:
                report["empty_id_rows"].append(row_num)
                report["will_be_skipped"].append({"row": row_num, "reason": "空编号"})
                continue

        if asset_id in seen_ids:
            report["duplicate_rows"].append({"row": row_num, "asset_id": asset_id, "type": "文件内重复"})
            report["will_be_skipped"].append({"row": row_num, "reason": f"编号 {asset_id} 在文件内重复"})
            continue

        if store.get_asset(asset_id):
            report["duplicate_rows"].append({"row": row_num, "asset_id": asset_id, "type": "与数据库重复"})
            report["will_be_skipped"].append({"row": row_num, "reason": f"编号 {asset_id} 已存在"})
            continue

        seen_ids.add(asset_id)

        asset = Asset.from_dict({**row_data, "asset_id": asset_id})
        missing = asset.missing_fields()
        if missing:
            report["missing_field_rows"].append({
                "row": row_num,
                "asset_id": asset_id,
                "missing": missing,
            })

        report["valid_assets"].append(asset)

    report["new_count"] = len(report["valid_assets"])
    return report


def import_file(file_path: str, store: Store, category: Optional[str] = None,
                auto_id: bool = False, id_prefix: str = "AST",
                sheet: Optional[str] = None, dry_run: bool = True) -> dict:
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    try:
        rows, _, missing_cols = _read_rows(file_path, sheet)
    except ImportError as e:
        return {"error": str(e)}
    except ValueError as e:
        return {"error": str(e)}

    if not rows:
        report = {
            "total_rows": 0,
            "new_count": 0,
            "will_be_skipped": [],
            "auto_generated_ids": [],
            "duplicate_rows": [],
            "empty_id_rows": [],
            "missing_field_rows": [],
            "valid_assets": [],
            "missing_columns": missing_cols,
        }
        report["applied"] = False if dry_run else True
        report["added"] = []
        report["skipped"] = []
        report["db_duplicates"] = []
        return report

    report = validate_assets(rows, store, category=category, auto_id=auto_id,
                             id_prefix=id_prefix, missing_columns=missing_cols)

    if dry_run:
        report["applied"] = False
        return report

    if report["valid_assets"]:
        result = store.add_assets(report["valid_assets"], skip_duplicates=True)
        report["added"] = result["added"]
        report["skipped"] = result["skipped"]
        report["db_duplicates"] = result["duplicates"]
    else:
        report["added"] = []
        report["skipped"] = []
        report["db_duplicates"] = []

    report["applied"] = True
    return report


def format_validation_report(report: dict) -> str:
    CHINESE_COL = {
        "asset_id": "资产编号",
        "name": "资产名称",
        "location": "位置",
        "responsible": "责任人",
        "category": "类别",
    }
    lines = []
    lines.append("=" * 60)
    lines.append("  导入校验报告")
    lines.append("=" * 60)
    lines.append(f"  文件总行数:    {report['total_rows']}")
    lines.append(f"  可新增数量:    {report['new_count']}")
    lines.append(f"  将跳过数量:    {len(report['will_be_skipped'])}")

    if report.get("missing_columns"):
        missing_cn = [CHINESE_COL.get(c, c) for c in report["missing_columns"]]
        lines.append(f"  ⚠ 表头缺少列: {', '.join(missing_cn)} (相关字段将全部视为空)")

    lines.append("-" * 60)

    if report["auto_generated_ids"]:
        lines.append(f"  ▶ 自动生成编号: {len(report['auto_generated_ids'])} 条")
        for item in report["auto_generated_ids"][:10]:
            lines.append(f"     第{item['row']}行 → {item['asset_id']}")
        if len(report["auto_generated_ids"]) > 10:
            lines.append(f"     ... 及其他 {len(report['auto_generated_ids']) - 10} 条")
        lines.append("")

    if report["duplicate_rows"]:
        lines.append(f"  ⚠ 重复编号: {len(report['duplicate_rows'])} 条")
        for item in report["duplicate_rows"][:10]:
            lines.append(f"     第{item['row']}行 - {item['asset_id']} ({item['type']})")
        if len(report["duplicate_rows"]) > 10:
            lines.append(f"     ... 及其他 {len(report['duplicate_rows']) - 10} 条")
        lines.append("")

    if report["empty_id_rows"]:
        lines.append(f"  ⚠ 空编号: {len(report['empty_id_rows'])} 条")
        for r in report["empty_id_rows"][:10]:
            lines.append(f"     第{r}行")
        if len(report["empty_id_rows"]) > 10:
            lines.append(f"     ... 及其他 {len(report['empty_id_rows']) - 10} 条")
        lines.append("")

    if report["missing_field_rows"]:
        lines.append(f"  ⚠ 缺失必填字段: {len(report['missing_field_rows'])} 条")
        for item in report["missing_field_rows"][:10]:
            lines.append(f"     第{item['row']}行 - {item['asset_id']} 缺: {', '.join(item['missing'])}")
        if len(report["missing_field_rows"]) > 10:
            lines.append(f"     ... 及其他 {len(report['missing_field_rows']) - 10} 条")
        lines.append("")

    if report.get("applied"):
        lines.append("-" * 60)
        lines.append(f"  ✔ 已写入数据库: {len(report['added'])} 条")
    else:
        lines.append("-" * 60)
        lines.append("  (预览模式，尚未写入数据库。使用 --apply 确认导入)")

    lines.append("=" * 60)
    return "\n".join(lines)


def run_import(args):
    store = Store(args.data_dir)
    file_path = args.file

    dry_run = not getattr(args, "apply", False)

    result = import_file(
        file_path, store,
        category=args.category,
        auto_id=args.auto_id,
        id_prefix=args.prefix,
        sheet=args.sheet,
        dry_run=dry_run,
    )

    if "error" in result:
        print(f"[错误] {result['error']}")
        return

    print(format_validation_report(result))

    if result.get("applied"):
        total = len(store.get_all_assets())
        print(f"  数据库总计: {total} 条资产")
    else:
        print(f"\n提示: 确认无误后，加上 --apply 选项正式导入")
