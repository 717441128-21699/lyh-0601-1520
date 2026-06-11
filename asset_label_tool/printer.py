import os
from typing import List, Optional, Tuple, Dict
from io import BytesIO
from collections import defaultdict

from .models import Asset, BatchRecord, LABEL_SIZES, CODE_STYLES, PrintTask, InventoryBatch
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


def _resolve_assets(store: Store, args) -> List[Asset]:
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
    unprinted = not getattr(args, "all", False)

    if category or location or responsible:
        return store.filter_assets(
            category=category or None,
            location=location or None,
            responsible=responsible or None,
            unprinted_only=unprinted,
        )

    if unprinted:
        return store.get_unprinted_assets()
    return store.get_all_assets()


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


def save_print_task(store: Store, name: str, args) -> PrintTask:
    task = PrintTask(
        name=name,
        category=getattr(args, "category", "") or "",
        location=getattr(args, "location", "") or "",
        responsible=getattr(args, "responsible", "") or "",
        label_size=getattr(args, "label_size", None) or "medium",
        code_style=getattr(args, "code_style", None) or "barcode",
        skip_missing=getattr(args, "skip_missing", False),
    )
    store.save_task(task)
    return task


def run_print(args):
    store = Store(args.data_dir)

    if getattr(args, "save_task", None):
        task = save_print_task(store, args.save_task, args)
        print(f"[任务已保存] {task.name}")
        print(f"  类别: {task.category or '(全部)'}")
        print(f"  位置: {task.location or '(全部)'}")
        print(f"  责任人: {task.responsible or '(全部)'}")
        print(f"  标签尺寸: {task.label_size}")
        print(f"  码样式: {task.code_style}")
        return

    if getattr(args, "list_tasks", False):
        tasks = store.get_all_tasks()
        if not tasks:
            print("[提示] 暂无保存的打印任务")
            return
        print("[常用打印任务]")
        print("-" * 70)
        for t in tasks:
            filters = []
            if t.category: filters.append(f"类别={t.category}")
            if t.location: filters.append(f"位置~{t.location}")
            if t.responsible: filters.append(f"责任人~{t.responsible}")
            filter_str = ", ".join(filters) if filters else "(全部资产)"
            print(f"  {t.name:<15} {t.label_size:<8} {t.code_style:<10} {filter_str}")
        print("-" * 70)
        print(f"共 {len(tasks)} 个任务")
        return

    if getattr(args, "delete_task", None):
        if store.delete_task(args.delete_task):
            print(f"[已删除] 任务 '{args.delete_task}'")
        else:
            print(f"[错误] 任务 '{args.delete_task}' 不存在")
        return

    label_size = getattr(args, "label_size", None)
    code_style = getattr(args, "code_style", None)
    skip_missing = getattr(args, "skip_missing", False)

    if getattr(args, "task", None):
        task = store.get_task(args.task)
        if not task:
            print(f"[错误] 打印任务 '{args.task}' 不存在")
            return
        if label_size is None:
            label_size = task.label_size
        if code_style is None:
            code_style = task.code_style
        if not args.skip_missing:
            skip_missing = task.skip_missing

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

    inv_group = getattr(args, "inventory_group", None)

    try:
        assets = _resolve_assets(store, args)
    except ValueError as e:
        print(f"[错误] {e}")
        return

    if not assets:
        print("[提示] 没有找到匹配的资产记录")
        return

    if inv_group:
        if inv_group == "location":
            groups: Dict[str, List[Asset]] = defaultdict(list)
            for a in assets:
                gkey = a.location or "(未设置位置)"
                groups[gkey].append(a)
            group_display = "位置"
        elif inv_group == "responsible":
            groups = defaultdict(list)
            for a in assets:
                gkey = a.responsible or "(未设置责任人)"
                groups[gkey].append(a)
            group_display = "责任人"
        else:
            print(f"[错误] --inventory-group 只能是 'location' 或 'responsible'")
            return

        if not groups:
            print("[提示] 没有可分组的资产")
            return

        inv_prefix = getattr(args, "inventory_prefix", "INV")
        base_name = getattr(args, "inventory_name", None)
        output_root = getattr(args, "output", None) or os.path.join(".", "labels_output")

        print(f"[盘点批次模式] 按 {group_display} 分组，共 {len(groups)} 组")
        print("-" * 60)

        inv_counter = 1
        skip_missing = getattr(args, "skip_missing", False)
        for gvalue in sorted(groups.keys()):
            group_assets = sorted(groups[gvalue], key=lambda a: a.asset_id)
            all_ids = [a.asset_id for a in group_assets]

            valid = []
            skipped = []
            for a in group_assets:
                missing = a.missing_fields()
                if missing and skip_missing:
                    skipped.append(a)
                else:
                    valid.append(a)
            if not valid and not skipped:
                continue

            if base_name:
                inv_name = f"{base_name}_{inv_counter:02d}"
            else:
                safe_gv = gvalue.replace("/", "_").replace("\\", "_").replace(" ", "_")[:20]
                inv_name = f"{inv_prefix}_{safe_gv}"

            inv = InventoryBatch(
                name=inv_name,
                group_by=inv_group,
                group_value=gvalue,
                asset_ids=all_ids,
            )
            store.save_inventory(inv)

            printed_msg = ""
            if valid:
                group_dir = os.path.join(output_root, inv_name)
                batch, files = print_labels(store, valid, label_size, code_style, group_dir)
                printed_msg = (f"    已打印: {len(valid)} 张，批次号: {batch.batch_id}\n"
                               f"    目录: {os.path.abspath(group_dir)}")
            else:
                printed_msg = "    已打印: 0（全部因缺字段跳过，保留于盘点批次内，补齐字段后可补打）"

            skipped_msg = ""
            if skipped:
                skipped_msg = f"    未打印（缺字段）: {len(skipped)} 张 [{', '.join(a.asset_id for a in skipped[:5])}"
                if len(skipped) > 5:
                    skipped_msg += f" ...]"
                else:
                    skipped_msg += "]"

            print(f"  [{inv_name}] {group_display}={gvalue}  总计{len(all_ids)}张")
            if printed_msg:
                print(printed_msg)
            if skipped_msg:
                print(skipped_msg)
            inv_counter += 1

        print("-" * 60)
        print(f"[完成] 共生成 {inv_counter - 1} 个盘点批次")
        return

    valid_assets = []
    skipped_count = 0
    for a in assets:
        missing = a.missing_fields()
        if missing and skip_missing:
            skipped_count += 1
            print(f"  [跳过] {a.asset_id} 缺失字段: {', '.join(missing)}")
        else:
            valid_assets.append(a)

    if not valid_assets:
        print("[错误] 没有可打印的资产（所有记录均缺失必填字段）")
        return

    output_dir = getattr(args, "output", None) or os.path.join(".", "labels_output")

    task_name = getattr(args, "task", None)
    if task_name:
        print(f"[使用任务] {task_name}")

    batch, files = print_labels(store, valid_assets, label_size, code_style, output_dir)

    print(f"[打印完成] 批次号: {batch.batch_id}")
    print(f"  标签尺寸: {label_size} ({LABEL_SIZES[label_size]['width']}x{LABEL_SIZES[label_size]['height']}px)")
    print(f"  码样式: {code_style}")
    if skipped_count:
        print(f"  跳过缺失字段: {skipped_count} 条")
    print(f"  打印数量: {len(files)}")
    print(f"  输出目录: {os.path.abspath(output_dir)}")
    for f in files[:5]:
        print(f"    - {os.path.basename(f)}")
    if len(files) > 5:
        print(f"    ... 及其他 {len(files) - 5} 个文件")
