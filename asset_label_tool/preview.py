from typing import List, Optional
from .models import Asset
from .store import Store


def _format_row(asset: Asset, idx: int, show_missing: bool = True) -> str:
    missing = asset.missing_fields() if show_missing else []
    fields = [
        f"{idx:>4}",
        asset.asset_id[:20].ljust(20),
        asset.name[:16].ljust(16),
        asset.location[:16].ljust(16),
        asset.responsible[:10].ljust(10),
        asset.category[:10].ljust(10),
        "✔" if asset.printed else "✘",
    ]
    line = " | ".join(fields)
    if missing:
        line += f"  ⚠ 缺失: {', '.join(missing)}"
    return line


def preview_assets(store: Store, category: Optional[str] = None,
                   unprinted_only: bool = False, show_missing: bool = True) -> List[Asset]:
    if category:
        assets = store.get_assets_by_category(category)
    elif unprinted_only:
        assets = store.get_unprinted_assets()
    else:
        assets = store.get_all_assets()
    return assets


def run_preview(args):
    store = Store(args.data_dir)
    assets = preview_assets(
        store,
        category=args.category,
        unprinted_only=args.unprinted,
        show_missing=not args.hide_missing,
    )

    if not assets:
        print("[提示] 没有找到匹配的资产记录")
        return

    header = "  #  | " + " | ".join([
        "资产编号".ljust(20),
        "名称".ljust(16),
        "位置".ljust(16),
        "责任人".ljust(10),
        "类别".ljust(10),
        "已打印",
    ])
    sep = "-" * len(header)

    print(sep)
    print(header)
    print(sep)

    missing_count = 0
    for i, asset in enumerate(assets, 1):
        print(_format_row(asset, i, show_missing=not args.hide_missing))
        if asset.missing_fields():
            missing_count += 1

    print(sep)
    print(f"共 {len(assets)} 条记录", end="")
    if missing_count:
        print(f"  |  ⚠ {missing_count} 条缺失必填字段")
    else:
        print("  |  所有记录字段完整")

    categories = store.get_categories()
    if categories:
        print(f"\n可用类别: {', '.join(categories)}")
