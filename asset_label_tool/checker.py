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


def run_check(args):
    store = Store(args.data_dir)

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
