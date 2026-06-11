import os
from typing import List, Optional
from .models import Asset, BatchRecord, LABEL_SIZES, CODE_STYLES
from .store import Store
from .printer import _create_label_image


def _export_as_pdf(assets: List[Asset], output_path: str, label_size: str, code_style: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from PIL import Image
    import tempfile

    page_w, page_h = A4
    size_config = LABEL_SIZES.get(label_size, LABEL_SIZES["medium"])
    label_w = size_config["width"]
    label_h = size_config["height"]

    margin = 10 * mm
    gap = 5 * mm
    cols = max(1, int((page_w - 2 * margin) / (label_w + gap)))
    x_start = margin
    y_start = page_h - margin

    c = canvas.Canvas(output_path, pagesize=A4)

    with tempfile.TemporaryDirectory() as tmpdir:
        row = 0
        col = 0
        for asset in assets:
            label_img = _create_label_image(asset, label_size, code_style)
            tmp_path = os.path.join(tmpdir, f"{asset.asset_id}.png")
            label_img.save(tmp_path, "PNG")

            x = x_start + col * (label_w + gap)
            y = y_start - row * (label_h + gap) - label_h

            if y < margin:
                c.showPage()
                row = 0
                col = 0
                y = y_start - label_h

            c.drawImage(tmp_path, x, y, width=label_w, height=label_h)

            col += 1
            if col >= cols:
                col = 0
                row += 1

    c.save()


def _export_as_pngs(assets: List[Asset], output_dir: str, label_size: str, code_style: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    files = []
    for asset in assets:
        label_img = _create_label_image(asset, label_size, code_style)
        filename = f"{asset.asset_id}_{label_size}_{code_style}.png"
        filepath = os.path.join(output_dir, filename)
        label_img.save(filepath, "PNG")
        files.append(filepath)
    return files


def export_labels(store: Store, assets: List[Asset], label_size: str,
                  code_style: str, output_path: str, fmt: str = "pdf") -> str:
    if fmt == "pdf":
        _export_as_pdf(assets, output_path, label_size, code_style)
        return output_path
    else:
        files = _export_as_pngs(assets, output_path, label_size, code_style)
        return output_path


def run_export(args):
    store = Store(args.data_dir)

    if args.label_size not in LABEL_SIZES:
        print(f"[错误] 无效的标签尺寸: {args.label_size}")
        print(f"  可选: {', '.join(LABEL_SIZES.keys())}")
        return

    if args.code_style not in CODE_STYLES:
        print(f"[错误] 无效的码样式: {args.code_style}")
        print(f"  可选: {', '.join(CODE_STYLES)}")
        return

    assets = []
    if args.category:
        assets = store.get_assets_by_category(args.category)
    elif args.asset_ids:
        for aid in args.asset_ids:
            a = store.get_asset(aid)
            if a:
                assets.append(a)
            else:
                print(f"[警告] 资产编号 '{aid}' 不存在，已跳过")
    elif args.batch_id:
        assets = store.get_assets_by_batch(args.batch_id)
        if not assets:
            print(f"[提示] 批次 '{args.batch_id}' 未找到")
            return
    else:
        assets = store.get_all_assets()

    if not assets:
        print("[提示] 没有找到匹配的资产记录")
        return

    fmt = args.format or "pdf"
    output = args.output or "labels_export"

    if fmt == "pdf":
        if not output.endswith(".pdf"):
            output += ".pdf"
        result_path = export_labels(store, assets, args.label_size, args.code_style, output, fmt)
        print(f"[导出完成] PDF 文件: {os.path.abspath(result_path)}")
        print(f"  标签数量: {len(assets)}")
    else:
        result_path = export_labels(store, assets, args.label_size, args.code_style, output, fmt)
        print(f"[导出完成] PNG 文件目录: {os.path.abspath(result_path)}")
        print(f"  标签数量: {len(assets)}")
