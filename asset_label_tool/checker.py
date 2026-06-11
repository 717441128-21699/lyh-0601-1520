import os
from typing import List, Optional
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


def _format_inventory_progress(progress: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"  盘点批次进度: {progress['name']}")
    lines.append("=" * 60)
    group_cn = "位置" if progress["group_by"] == "location" else "责任人"
    lines.append(f"  分组方式: 按{group_cn}")
    lines.append(f"  {group_cn}:  {progress['group_value']}")
    lines.append(f"  创建时间: {progress['created_at']}")
    lines.append("-" * 60)
    total = progress["total"]
    printed = progress["printed"]
    unprinted = progress["unprinted"]
    pct = (printed / total * 100) if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * printed / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    lines.append(f"  进度:   |{bar}| {printed}/{total} ({pct:.1f}%)")
    lines.append(f"  已打印: {printed}")
    lines.append(f"  未打印: {unprinted}")
    if unprinted:
        lines.append("")
        lines.append("  待补打资产:")
        for aid in progress["unprinted_ids"][:20]:
            lines.append(f"    - {aid}")
        if len(progress["unprinted_ids"]) > 20:
            lines.append(f"    ... 及其他 {len(progress['unprinted_ids']) - 20} 条")
    lines.append("=" * 60)
    return "\n".join(lines)


def run_check(args):
    store = Store(args.data_dir)

    if getattr(args, "list_inventories", False):
        invs = store.get_all_inventories()
        if not invs:
            print("[提示] 暂无盘点批次")
            return
        print("[盘点批次列表]")
        print("-" * 70)
        print(f"{'批次名':<30} {'分组':<10} {'分组值':<20} {'资产数':<8} {'创建时间'}")
        print("-" * 70)
        for inv in invs:
            prog = store.get_inventory_progress(inv.name)
            total = prog["total"] if prog else len(inv.asset_ids)
            printed = prog["printed"] if prog else 0
            group_cn = "位置" if inv.group_by == "location" else "责任人"
            print(f"{inv.name:<30} {group_cn:<10} {inv.group_value[:18]:<20} {f'{printed}/{total}':<8} {inv.created_at}")
        print("-" * 70)
        print(f"共 {len(invs)} 个盘点批次")
        return

    if getattr(args, "inventory", None):
        progress = store.get_inventory_progress(args.inventory)
        if not progress:
            print(f"[错误] 盘点批次 '{args.inventory}' 不存在")
            return
        print(_format_inventory_progress(progress))
        return

    if getattr(args, "inventory_detail", None):
        progress = store.get_inventory_progress(args.inventory_detail)
        if not progress:
            print(f"[错误] 盘点批次 '{args.inventory_detail}' 不存在")
            return
        print(_format_inventory_progress(progress))
        print("")
        print("[资产明细]")
        print("-" * 90)
        print(f"{'状态':<6} {'资产编号':<20} {'名称':<18} {'位置':<22} {'责任人':<10} {'打印批次'}")
        print("-" * 90)
        all_ids = progress["printed_ids"] + progress["unprinted_ids"]
        printed_set = set(progress["printed_ids"])
        for aid in all_ids:
            asset = store.get_asset(aid)
            if not asset:
                continue
            status = "✔已打" if aid in printed_set else "✘未打"
            print(f"{status:<6} {asset.asset_id:<20} {asset.name[:16]:<18} {asset.location[:20]:<22} {asset.responsible[:10]:<10} {asset.print_batch or '-'}")
        print("-" * 90)
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
