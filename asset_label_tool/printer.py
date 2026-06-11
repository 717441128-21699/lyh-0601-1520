import os
from typing import List, Optional, Tuple
from io import BytesIO

from .models import Asset, BatchRecord, LABEL_SIZES, CODE_STYLES
from .store import Store


def _generate_barcode_image(data: str, width: int, height: int) -> "PIL.Image.Image":
    from barcode import Code128
    from barcode.writer import ImageWriter

    writer = ImageWriter()
    writer.set_options({
        "module_width": 0.2,
        "module_height": height * 0.4 / 10,
        "font_size": int(height * 0.08),
        "text_distance": 2,
        "quiet_zone": 2,
    })
    code = Code128(data, writer=writer)
    buf = BytesIO()
    code.write(buf, text=data)
    buf.seek(0)

    from PIL import Image
    img = Image.open(buf)
    return img


def _generate_qrcode_image(data: str, size: int) -> "PIL.Image.Image":
    import qrcode
    from PIL import Image

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=max(4, size // 50),
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")


def _create_label_image(asset: Asset, label_size: str, code_style: str) -> "PIL.Image.Image":
    from PIL import Image, ImageDraw, ImageFont

    size_config = LABEL_SIZES.get(label_size, LABEL_SIZES["medium"])
    w, h = size_config["width"], size_config["height"]

    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_path = None
        font_dirs = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for fp in font_dirs:
            if os.path.exists(fp):
                font_path = fp
                break

        font_small = ImageFont.truetype(font_path, max(10, h // 16)) if font_path else ImageFont.load_default()
        font_medium = ImageFont.truetype(font_path, max(12, h // 12)) if font_path else ImageFont.load_default()
        font_large = ImageFont.truetype(font_path, max(14, h // 10)) if font_path else ImageFont.load_default()
    except Exception:
        font_small = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_large = ImageFont.load_default()

    margin = 8
    text_x = margin
    text_y = margin

    draw.text((text_x, text_y), f"编号: {asset.asset_id}", fill="black", font=font_large)
    text_y += h // 5

    draw.text((text_x, text_y), f"名称: {asset.name or '(未填)'}", fill="black", font=font_medium)
    text_y += h // 6

    draw.text((text_x, text_y), f"位置: {asset.location or '(未填)'}", fill="black", font=font_small)
    text_y += h // 7

    draw.text((text_x, text_y), f"责任人: {asset.responsible or '(未填)'}", fill="black", font=font_small)
    text_y += h // 7

    code_area_top = text_y + 4
    code_area_height = h - code_area_top - margin
    code_area_width = w - 2 * margin

    code_data = asset.asset_id

    if code_style == "barcode":
        try:
            barcode_img = _generate_barcode_image(code_data, code_area_width, code_area_height)
            bw, bh = barcode_img.size
            scale = min(code_area_width / bw, code_area_height / bh, 1.0)
            new_w = int(bw * scale)
            new_h = int(bh * scale)
            barcode_img = barcode_img.resize((new_w, new_h))
            code_x = (w - new_w) // 2
            code_y = code_area_top + (code_area_height - new_h) // 2
            img.paste(barcode_img, (code_x, code_y))
        except Exception as e:
            draw.text((text_x, code_area_top), f"[条形码生成失败: {e}]", fill="red", font=font_small)
    elif code_style == "qrcode":
        try:
            qr_size = min(code_area_width, code_area_height)
            qr_img = _generate_qrcode_image(code_data, qr_size)
            qw, qh = qr_img.size
            scale = min(qr_size / qw, qr_size / qh, 1.0)
            new_w = int(qw * scale)
            new_h = int(qh * scale)
            qr_img = qr_img.resize((new_w, new_h))
            code_x = (w - new_w) // 2
            code_y = code_area_top + (code_area_height - new_h) // 2
            img.paste(qr_img, (code_x, code_y))
        except Exception as e:
            draw.text((text_x, code_area_top), f"[二维码生成失败: {e}]", fill="red", font=font_small)

    draw.rectangle([0, 0, w - 1, h - 1], outline="black", width=1)

    return img


def print_labels(store: Store, assets: List[Asset], label_size: str,
                 code_style: str, output_dir: str) -> Tuple[BatchRecord, List[str]]:
    os.makedirs(output_dir, exist_ok=True)

    batch = BatchRecord(
        label_size=label_size,
        code_style=code_style,
        output_path=os.path.abspath(output_dir),
        asset_ids=[a.asset_id for a in assets],
        count=len(assets),
    )

    generated_files = []
    for asset in assets:
        label_img = _create_label_image(asset, label_size, code_style)
        filename = f"{asset.asset_id}_{label_size}_{code_style}.png"
        filepath = os.path.join(output_dir, filename)
        label_img.save(filepath, "PNG")
        generated_files.append(filepath)

    store.mark_printed([a.asset_id for a in assets], batch.batch_id)
    store.add_batch(batch)

    return batch, generated_files


def run_print(args):
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
        if not assets:
            print(f"[提示] 类别 '{args.category}' 下没有资产")
            return
    elif args.asset_ids:
        for aid in args.asset_ids:
            a = store.get_asset(aid)
            if a:
                assets.append(a)
            else:
                print(f"[警告] 资产编号 '{aid}' 不存在，已跳过")
        if not assets:
            print("[错误] 没有找到指定的资产")
            return
    else:
        assets = store.get_unprinted_assets()
        if not assets:
            print("[提示] 没有未打印的资产")
            return

    skip_missing = args.skip_missing
    valid_assets = []
    for a in assets:
        missing = a.missing_fields()
        if missing and skip_missing:
            print(f"[跳过] {a.asset_id} 缺失字段: {', '.join(missing)}")
        else:
            valid_assets.append(a)

    if not valid_assets:
        print("[错误] 没有可打印的资产（所有记录均缺失必填字段）")
        return

    output_dir = args.output or os.path.join(".", "labels_output")
    batch, files = print_labels(store, valid_assets, args.label_size, args.code_style, output_dir)

    print(f"[打印完成] 批次号: {batch.batch_id}")
    print(f"  标签尺寸: {args.label_size} ({LABEL_SIZES[args.label_size]['width']}x{LABEL_SIZES[args.label_size]['height']}px)")
    print(f"  码样式: {args.code_style}")
    print(f"  打印数量: {len(files)}")
    print(f"  输出目录: {os.path.abspath(output_dir)}")
    for f in files[:5]:
        print(f"    - {os.path.basename(f)}")
    if len(files) > 5:
        print(f"    ... 及其他 {len(files) - 5} 个文件")
