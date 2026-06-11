import os
from typing import List, Optional, Dict
from .models import Asset, BatchRecord, LABEL_SIZES, CODE_STYLES, PAPER_SIZES, PrintTask
from .store import Store
from .printer import _create_label_image


def _export_as_pdf(assets: List[Asset], output_path: str, label_size: str, code_style: str,
                   paper_size: str = "A4", cols: Optional[int] = None, rows: Optional[int] = None,
                   margin_mm: float = 10.0, gap_mm: float = 3.0) -> Dict:
    from reportlab.lib.pagesizes import A4, A5, LETTER
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from PIL import Image
    import tempfile

    paper_map = {
        "A4": A4,
        "A5": A5,
        "letter": LETTER,
    }

    if paper_size in paper_map:
        page_w, page_h = paper_map[paper_size]
    elif paper_size in PAPER_SIZES:
        ps = PAPER_SIZES[paper_size]
        page_w, page_h = ps["width"] * mm, ps["height"] * mm
    else:
        page_w, page_h = A4

    size_config = LABEL_SIZES.get(label_size, LABEL_SIZES["medium"])
    px_label_w = size_config["width"]
    px_label_h = size_config["height"]

    label_w_mm = px_label_w * 0.3
    label_h_mm = px_label_h * 0.3

    margin = margin_mm * mm
    gap = gap_mm * mm

    available_w = page_w - 2 * margin
    available_h = page_h - 2 * margin

    if cols is None:
        cols = max(1, int((available_w + gap) / (label_w_mm + gap)))
    if rows is None:
        rows = max(1, int((available_h + gap) / (label_h_mm + gap)))

    labels_per_page = cols * rows
    total_pages = max(1, (len(assets) + labels_per_page - 1) // labels_per_page)

    label_w = label_w_mm * mm
    label_h = label_h_mm * mm

    total_w = cols * label_w + (cols - 1) * gap
    total_h = rows * label_h + (rows - 1) * gap
    x_start = (page_w - total_w) / 2
    y_start = page_h - (page_h - total_h) / 2

    c = canvas.Canvas(output_path, pagesize=(page_w, page_h))

    with tempfile.TemporaryDirectory() as tmpdir:
        page_idx = 0
        for i, asset in enumerate(assets):
            idx_in_page = i % labels_per_page
            if idx_in_page == 0 and i > 0:
                c.showPage()
                page_idx += 1

            label_img = _create_label_image(asset, label_size, code_style)
            tmp_path = os.path.join(tmpdir, f"{asset.asset_id}.png")
            label_img.save(tmp_path, "PNG")

            col = idx_in_page % cols
            row = idx_in_page // cols

            x = x_start + col * (label_w + gap)
            y = y_start - (row + 1) * label_h - row * gap

            c.drawImage(tmp_path, x, y, width=label_w, height=label_h)

    c.save()

    summary = {
        "paper_size": paper_size,
        "page_width_mm": round(page_w / mm, 1),
        "page_height_mm": round(page_h / mm, 1),
        "cols": cols,
        "rows": rows,
        "labels_per_page": labels_per_page,
        "total_labels": len(assets),
        "total_pages": total_pages,
        "label_width_mm": round(label_w_mm, 1),
        "label_height_mm": round(label_h_mm, 1),
        "margin_mm": margin_mm,
        "gap_mm": gap_mm,
        "output_path": output_path,
    }
    return summary


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


def _resolve_export_assets(store: Store, args) -> List[Asset]:
    if getattr(args, "task", None):
        task = store.get_task(args.task)
        if not task:
            raise ValueError(f"打印任务 '{args.task}' 不存在")
        return store.filter_assets(
            category=task.category or None,
            location=task.location or None,
            responsible=task.responsible or None,
            unprinted_only=False,
        )

    if getattr(args, "batch_id", None):
        return store.get_assets_by_batch(args.batch_id)

    if getattr(args, "asset_ids", None):
        assets = []
        for aid in args.asset_ids:
            a = store.get_asset(aid)
            if a:
                assets.append(a)
        return assets

    category = getattr(args, "category", None)
    location = getattr(args, "location", None)
    responsible = getattr(args, "responsible", None)

    if category or location or responsible:
        return store.filter_assets(
            category=category or None,
            location=location or None,
            responsible=responsible or None,
            unprinted_only=False,
        )

    return store.get_all_assets()


def format_pdf_summary(summary: Dict) -> str:
    lines = []
    lines.append("=" * 50)
    lines.append("  PDF 排版摘要")
    lines.append("=" * 50)
    lines.append(f"  纸张规格:      {summary['paper_size']} ({summary['page_width_mm']}×{summary['page_height_mm']}mm)")
    lines.append(f"  每页列数:      {summary['cols']}")
    lines.append(f"  每页行数:      {summary['rows']}")
    lines.append(f"  每页标签数:    {summary['labels_per_page']}")
    lines.append(f"  标签尺寸:      {summary['label_width_mm']}×{summary['label_height_mm']}mm")
    lines.append(f"  页边距:        {summary['margin_mm']}mm")
    lines.append(f"  标签间距:      {summary['gap_mm']}mm")
    lines.append("-" * 50)
    lines.append(f"  标签总数:      {summary['total_labels']}")
    lines.append(f"  总页数:        {summary['total_pages']}")
    lines.append(f"  输出文件:      {summary['output_path']}")
    lines.append("=" * 50)
    return "\n".join(lines)


def run_export(args):
    store = Store(args.data_dir)

    label_size = getattr(args, "label_size", None)
    code_style = getattr(args, "code_style", None)

    if getattr(args, "task", None):
        task = store.get_task(args.task)
        if not task:
            print(f"[错误] 打印任务 '{args.task}' 不存在")
            return
        if label_size is None:
            label_size = task.label_size
        if code_style is None:
            code_style = task.code_style

    if label_size is None:
        label_size = "medium"
    if code_style is None:
        code_style = "barcode"

    if label_size not in LABEL_SIZES:
        print(f"[错误] 无效的标签尺寸: {label_size}")
        print(f"  可选: {', '.join(LABEL_SIZES.keys())}")
        return

    if code_style not in CODE_STYLES:
        print(f"[错误] 无效的码样式: {code_style}")
        print(f"  可选: {', '.join(CODE_STYLES)}")
        return

    try:
        assets = _resolve_export_assets(store, args)
    except ValueError as e:
        print(f"[错误] {e}")
        return

    if not assets:
        print("[提示] 没有找到匹配的资产记录")
        return

    fmt = getattr(args, "format", "pdf")
    output = getattr(args, "output", None)

    if fmt == "pdf":
        if not output:
            output = "labels_export.pdf"
        if not output.endswith(".pdf"):
            output += ".pdf"

        paper_size = getattr(args, "paper", "A4")
        cols = getattr(args, "cols", None)
        rows = getattr(args, "rows", None)
        margin = getattr(args, "margin", 10.0)
        gap = getattr(args, "gap", 3.0)

        summary = _export_as_pdf(
            assets, output, label_size, code_style,
            paper_size=paper_size, cols=cols, rows=rows,
            margin_mm=margin, gap_mm=gap,
        )
        print(format_pdf_summary(summary))
    else:
        if not output:
            output = "labels_export"
        files = _export_as_pngs(assets, output, label_size, code_style)
        print(f"[导出完成] PNG 文件目录: {os.path.abspath(output)}")
        print(f"  标签数量: {len(files)}")
