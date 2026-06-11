import os
import csv
from typing import List, Optional
from collections import defaultdict
from .models import Asset, BatchRecord, LABEL_SIZES, CODE_STYLES
from .store import Store
from .printer import print_labels, _create_label_image


def check_batches(store: Store) -> List[BatchRecord]:
    return store.get_batches()


def check_asset_status(store: Store, asset_id: str) -> Optional[Asset]:
    return store.get_asset(asset_id)


def reprint_single(store: Store, asset_id: str, label_size: str,
                   code_style: str, output_dir: str) -> Optional[str]:
    asset = store.get_asset(asset_id)
    if not asset:
        return None

    os.makedirs(output_dir, exist_ok=True)
    label_img = _create_label_image(asset, label_size, code_style)
    filename = f"{asset.asset_id}_reprint_{label_size}_{code_style}.png"
    filepath = os.path.join(output_dir, filename)
    label_img.save(filepath, "PNG")

    return filepath


def reprint_batch(store: Store, batch_id: str, output_dir: str) -> Optional[List[str]]:
    batch = store.get_batch(batch_id)
    if not batch:
        return None

    assets = store.get_assets_by_batch(batch_id)
    if not assets:
        return None

    _, files = print_labels(store, assets, batch.label_size, batch.code_style, output_dir)
    return files


STATUS_LABELS = {
    "checked": "已贴",
    "printed_not_checked": "已打印未贴",
    "unprinted_not_checked": "未打印未贴",
    "extraneous": "清单外",
}


def _format_inventory_progress(progress: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"  盘点批次进度: {progress['name']}")
    lines.append("=" * 70)
    group_cn = "位置" if progress["group_by"] == "location" else "责任人"
    lines.append(f"  分组方式: 按{group_cn}")
    lines.append(f"  {group_cn}:  {progress['group_value']}")
    lines.append(f"  创建时间: {progress['created_at']}")
    lines.append("-" * 70)
    total = progress["total"]
    lines.append(f"  批次内资产总数: {total}")
    lines.append(f"  ✔ 已贴 (核对通过):    {progress['checked_count']}")
    lines.append(f"  ⚠ 已打印未贴 (待现场): {progress['printed_not_checked_count']}")
    lines.append(f"  ✘ 未打印未贴 (需补打): {progress['unprinted_not_checked_count']}")
    lines.append(f"  ? 清单外扫码 (异常):  {progress['extraneous_count']}")
    lines.append("-" * 70)

    def _bar(curr, total, length=30):
        if total == 0:
            return "░" * length
        filled = int(length * curr / total)
        return "█" * filled + "░" * (length - filled)

    pct = (progress["checked_count"] / total * 100) if total > 0 else 0
    lines.append(f"  已贴进度: |{_bar(progress['checked_count'], total)}| {progress['checked_count']}/{total} ({pct:.1f}%)")
    pct2 = (progress["printed_count"] / total * 100) if total > 0 else 0
    lines.append(f"  打印进度: |{_bar(progress['printed_count'], total)}| {progress['printed_count']}/{total} ({pct2:.1f}%)")
    lines.append("=" * 70)
    return "\n".join(lines)


def _export_diff_csv(store: Store, progress: dict, output_path: str, group_summary: bool = True):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    rows = []
    checked_set = set(progress["checked_ids"])
    extraneous_set = set(progress["extraneous_ids"])
    unprinted_set = set(progress["unprinted_ids"])

    all_augmented_ids = progress["all_ids"] + list(extraneous_set - set(progress["all_ids"]))

    for aid in all_augmented_ids:
        asset = store.get_asset(aid)
        if aid in extraneous_set and aid not in set(progress["all_ids"]):
            status = "清单外扫码"
        elif aid in checked_set:
            status = "已贴"
        elif aid in unprinted_set:
            status = "未打印未贴"
        else:
            status = "已打印未贴"
        row = {
            "asset_id": aid,
            "name": asset.name if asset else "",
            "location": asset.location if asset else "",
            "responsible": asset.responsible if asset else "",
            "category": asset.category if asset else "",
            "status": status,
            "print_batch": asset.print_batch if asset else "",
            "printed": "是" if asset and asset.printed else ("未知" if not asset else "否"),
            "checked": "是" if aid in checked_set else "否",
            "note": "",
        }
        if status == "清单外扫码":
            row["note"] = "不属于当前盘点批次，请确认资产归属"
        elif status == "未打印未贴":
            if asset:
                mf = asset.missing_fields()
                if mf:
                    row["note"] = f"打印时被跳过，缺字段: {', '.join(mf)}"
                else:
                    row["note"] = "需要补打标签"
        rows.append(row)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        headers_cn = {
            "asset_id": "资产编号",
            "name": "资产名称",
            "location": "位置",
            "responsible": "责任人",
            "category": "类别",
            "status": "状态",
            "print_batch": "打印批次",
            "printed": "是否已打印",
            "checked": "是否已贴",
            "note": "备注",
        }
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(headers_cn)
        for r in rows:
            writer.writerow(r)

    if group_summary:
        summary_path = os.path.splitext(output_path)[0] + "_summary.csv"
        _export_summary_csv(store, rows, summary_path, progress["group_by"])


def _export_summary_csv(store: Store, rows: list, output_path: str, group_by: str):
    group_key_cn = "责任人" if group_by == "responsible" else "位置"

    by_status = defaultdict(int)
    by_group_status = defaultdict(lambda: defaultdict(int))

    for r in rows:
        status = r["status"]
        by_status[status] += 1
        gkey = r["responsible"] if group_by == "responsible" else r["location"]
        if not gkey:
            gkey = "(未设置)"
        by_group_status[gkey][status] += 1

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        all_statuses = ["已贴", "已打印未贴", "未打印未贴", "清单外扫码"]

        f.write(f"差异汇总表（按{group_key_cn}）\n".encode("utf-8-sig").decode("utf-8-sig"))
        f.seek(0, os.SEEK_END)
        writer.writerow([group_key_cn] + all_statuses + ["合计"])
        grand = {s: 0 for s in all_statuses}
        for gkey in sorted(by_group_status.keys()):
            rec = by_group_status[gkey]
            line = [gkey]
            total = 0
            for s in all_statuses:
                v = rec.get(s, 0)
                grand[s] += v
                total += v
                line.append(v)
            line.append(total)
            writer.writerow(line)
        writer.writerow(["合计"] + [grand[s] for s in all_statuses] + [sum(grand.values())])


def run_check(args):
    store = Store(args.data_dir)

    if getattr(args, "list_inventories", False):
        invs = store.get_all_inventories()
        if not invs:
            print("[提示] 暂无盘点批次")
            return
        print("[盘点批次列表]")
        print("-" * 90)
        print(f"{'批次名':<25} {'分组':<6} {'分组值':<18} {'总计':<7} {'已贴':<6} {'已打印未贴':<10} {'未打印':<8} {'清单外':<8} {'创建时间'}")
        print("-" * 90)
        for inv in invs:
            prog = store.get_inventory_progress(inv.name)
            group_cn = "位置" if inv.group_by == "location" else "责任人"
            if prog:
                print(f"{inv.name:<25} {group_cn:<6} {prog['group_value'][:16]:<18}"
                      f" {prog['total']:<7} {prog['checked_count']:<6}"
                      f" {prog['printed_not_checked_count']:<10}"
                      f" {prog['unprinted_count']:<8}"
                      f" {prog['extraneous_count']:<8}"
                      f" {inv.created_at}")
            else:
                print(f"{inv.name:<25} {group_cn:<6} {inv.group_value[:16]:<18}"
                      f" {len(inv.asset_ids):<7} - - - - {inv.created_at}")
        print("-" * 90)
        print(f"共 {len(invs)} 个盘点批次")
        return

    inv_name = getattr(args, "inventory", None)
    inv_detail_name = getattr(args, "inventory_detail", None)
    diff_name = getattr(args, "export_diff", None)

    target_inv = inv_name or inv_detail_name or diff_name

    if target_inv:
        progress = store.get_inventory_progress(target_inv)
        if not progress:
            print(f"[错误] 盘点批次 '{target_inv}' 不存在")
            return

        if diff_name:
            out_path = args.export_diff
            if not out_path.endswith(".csv"):
                out_path += ".csv"
            _export_diff_csv(store, progress, out_path, group_summary=True)
            print(f"[差异表已导出] {os.path.abspath(out_path)}")
            print(f"  含 {len(progress['all_ids']) + len(progress['extraneous_ids'])} 条明细 + 按分组汇总")
            summary_path = os.path.splitext(out_path)[0] + "_summary.csv"
            if os.path.exists(summary_path):
                print(f"  汇总表: {os.path.abspath(summary_path)}")
            return

        print(_format_inventory_progress(progress))

        if inv_detail_name:
            print("")
            print("[资产明细]")
            print("-" * 120)
            print(f"{'状态':<12} {'资产编号':<20} {'名称':<18} {'位置':<22} {'责任人':<12} {'打印批次':<10} {'备注'}")
            print("-" * 120)
            all_ids = progress["all_ids"] + [e for e in progress["extraneous_ids"] if e not in set(progress["all_ids"])]
            checked_set = set(progress["checked_ids"])
            extraneous_set = set(progress["extraneous_ids"])
            unprinted_set = set(progress["unprinted_ids"])
            for aid in all_ids:
                asset = store.get_asset(aid)
                if aid in extraneous_set and aid not in set(progress["all_ids"]):
                    status = "? 清单外"
                    note = "不属于本批次"
                elif aid in checked_set:
                    status = "✔ 已贴"
                    note = ""
                elif aid in unprinted_set:
                    status = "✘ 未打印"
                    if asset:
                        mf = asset.missing_fields()
                        note = f"缺字段: {', '.join(mf)}" if mf else "需补打"
                    else:
                        note = "资产不存在"
                else:
                    status = "⚠ 已打印未贴"
                    note = ""
                print(f"{status:<12} {aid:<20}"
                      f" {(asset.name[:16] if asset else ''):<18}"
                      f" {(asset.location[:20] if asset else ''):<22}"
                      f" {(asset.responsible[:10] if asset else ''):<12}"
                      f" {(asset.print_batch[:8] if asset and asset.print_batch else '-'):<10}"
                      f" {note}")
            print("-" * 120)
        return

    if getattr(args, "delete_inventory", None):
        if store.delete_inventory(args.delete_inventory):
            print(f"[已删除] 盘点批次 '{args.delete_inventory}'")
        else:
            print(f"[错误] 盘点批次 '{args.delete_inventory}' 不存在")
        return

    if args.reprint:
        asset_id = args.reprint
        label_size = args.label_size or "medium"
        code_style = args.code_style or "barcode"
        output_dir = args.output or os.path.join(".", "reprint_output")

        result = reprint_single(store, asset_id, label_size, code_style, output_dir)
        if result:
            print(f"[补打完成] 单张标签: {os.path.abspath(result)}")
        else:
            print(f"[错误] 资产编号 '{asset_id}' 不存在")

    elif args.reprint_batch:
        batch_id = args.reprint_batch
        output_dir = args.output or os.path.join(".", "reprint_output")

        result = reprint_batch(store, batch_id, output_dir)
        if result:
            print(f"[整组补打完成] 批次号: {batch_id}")
            print(f"  补打数量: {len(result)}")
            print(f"  输出目录: {os.path.abspath(output_dir)}")
        else:
            print(f"[错误] 批次 '{batch_id}' 不存在或无关联资产")

    elif args.status:
        asset_id = args.status
        asset = check_asset_status(store, asset_id)
        if asset:
            print(f"[资产状态]")
            print(f"  编号:   {asset.asset_id}")
            print(f"  名称:   {asset.name or '(未填)'}")
            print(f"  位置:   {asset.location or '(未填)'}")
            print(f"  责任人: {asset.responsible or '(未填)'}")
            print(f"  类别:   {asset.category or '(未填)'}")
            print(f"  已打印: {'是' if asset.printed else '否'}")
            if asset.print_batch:
                print(f"  打印批次: {asset.print_batch}")
            missing = asset.missing_fields()
            if missing:
                print(f"  ⚠ 缺失字段: {', '.join(missing)}")
        else:
            print(f"[错误] 资产编号 '{asset_id}' 不存在")

    else:
        batches = check_batches(store)
        if not batches:
            print("[提示] 暂无打印批次记录")
            return

        print("[打印批次记录]")
        print("-" * 80)
        print(f"{'批次号':<10} {'时间':<20} {'数量':<8} {'尺寸':<8} {'样式':<10} {'输出路径'}")
        print("-" * 80)
        for b in batches:
            print(f"{b.batch_id:<10} {b.timestamp:<20} {b.count:<8} {b.label_size:<8} {b.code_style:<10} {b.output_path}")
        print("-" * 80)
        print(f"共 {len(batches)} 个批次")
