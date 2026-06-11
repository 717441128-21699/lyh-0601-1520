import csv
import os
from typing import List, Optional
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


def import_csv(file_path: str, store: Store, category: Optional[str] = None,
               auto_id: bool = False, id_prefix: str = "AST") -> dict:
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    assets = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        normalized = {h: _normalize_header(h) for h in headers}

        for row in reader:
            mapped = {}
            for orig, norm in normalized.items():
                mapped[norm] = row.get(orig, "").strip()

            if category:
                mapped["category"] = category

            if auto_id and not mapped.get("asset_id"):
                mapped["asset_id"] = store.get_next_sequential_id(id_prefix)

            if not mapped.get("asset_id"):
                continue

            assets.append(Asset.from_dict(mapped))

    if not assets:
        return {"error": "未找到有效的资产数据，请检查文件格式和表头"}

    result = store.add_assets(assets, skip_duplicates=True)
    return result


def import_excel(file_path: str, store: Store, category: Optional[str] = None,
                 auto_id: bool = False, id_prefix: str = "AST", sheet: Optional[str] = None) -> dict:
    try:
        import openpyxl
    except ImportError:
        return {"error": "需要安装 openpyxl 库来读取 Excel 文件: pip install openpyxl"}

    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb[sheet] if sheet else wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        wb.close()
        return {"error": "Excel 文件为空或只有表头"}

    headers = [str(h or "") for h in rows[0]]
    normalized = {h: _normalize_header(h) for h in headers}

    assets = []
    for row in rows[1:]:
        row_data = {}
        for i, orig in enumerate(headers):
            norm = normalized.get(orig, orig)
            val = row[i] if i < len(row) else ""
            row_data[norm] = str(val or "").strip()

        if category:
            row_data["category"] = category

        if auto_id and not row_data.get("asset_id"):
            row_data["asset_id"] = store.get_next_sequential_id(id_prefix)

        if not row_data.get("asset_id"):
            continue

        assets.append(Asset.from_dict(row_data))

    wb.close()

    if not assets:
        return {"error": "未找到有效的资产数据，请检查文件格式和表头"}

    result = store.add_assets(assets, skip_duplicates=True)
    return result


def run_import(args):
    store = Store(args.data_dir)
    file_path = args.file
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".xlsx", ".xls"):
        result = import_excel(
            file_path, store,
            category=args.category,
            auto_id=args.auto_id,
            id_prefix=args.prefix,
            sheet=args.sheet,
        )
    elif ext in (".csv",):
        result = import_csv(
            file_path, store,
            category=args.category,
            auto_id=args.auto_id,
            id_prefix=args.prefix,
        )
    else:
        print(f"[错误] 不支持的文件格式: {ext}，请使用 .csv 或 .xlsx 文件")
        return

    if "error" in result:
        print(f"[错误] {result['error']}")
        return

    print(f"[导入完成]")
    print(f"  新增: {len(result['added'])} 条")
    if result['duplicates']:
        print(f"  跳过重复编号: {len(result['duplicates'])} 条")
        for did in result['duplicates'][:10]:
            print(f"    - {did}")
        if len(result['duplicates']) > 10:
            print(f"    ... 及其他 {len(result['duplicates']) - 10} 条")
    if result['skipped']:
        print(f"  覆盖更新: {len(result['skipped'])} 条")

    total = len(store.get_all_assets())
    print(f"  数据库总计: {total} 条资产")
