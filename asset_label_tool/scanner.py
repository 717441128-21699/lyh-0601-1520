import os
import sys
import csv
from typing import List, Optional
from .store import Store


def _read_ids_from_file(file_path: str) -> List[str]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ids = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            has_header = "资产编号" in sample or "asset_id" in sample.lower()
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if has_header and i == 0:
                    continue
                for cell in row:
                    val = (cell or "").strip()
                    if val:
                        ids.append(val)
    else:
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                parts = line.replace(",", " ").replace(";", " ").replace("\t", " ").split()
                for p in parts:
                    p = p.strip()
                    if p:
                        ids.append(p)
    return ids


def _read_ids_from_stdin() -> List[str]:
    ids = []
    for line in sys.stdin:
        parts = line.replace(",", " ").replace(";", " ").replace("\t", " ").split()
        for p in parts:
            p = p.strip()
            if p:
                ids.append(p)
    return ids


def run_scan(args):
    store = Store(args.data_dir)
    inv_name = getattr(args, "inventory", None)
    if not inv_name:
        print("[错误] 请用 --inventory 指定盘点批次名。可用 --list-inventories 查看。")
        return

    ids: List[str] = []
    input_file = getattr(args, "file", None)
    if input_file:
        try:
            ids = _read_ids_from_file(input_file)
        except FileNotFoundError as e:
            print(f"[错误] {e}")
            return
        except Exception as e:
            print(f"[错误] 读取文件失败: {e}")
            return
        if not ids:
            print("[提示] 文件为空或未找到有效编号")
            return
    else:
        if sys.stdin.isatty():
            print("[提示] 请从标准输入输入编号（每行一个，Ctrl+Z 结束），或使用 --file 指定文件：")
        try:
            ids = _read_ids_from_stdin()
        except Exception as e:
            print(f"[错误] 读取标准输入失败: {e}")
            return

    if not ids:
        print("[提示] 没有输入任何编号")
        return

    result = store.add_scan_results(inv_name, ids)

    if "error" in result:
        print(f"[错误] {result['error']}")
        return

    new_checked = result["new_checked"]
    new_extraneous = result["new_extraneous"]

    print(f"[扫码完成] 批次: {inv_name}")
    print(f"  本次输入编号总数: {len(ids)}")
    print(f"  新核对通过: {len(new_checked)}")
    for n in new_checked[:10]:
        print(f"    + {n}")
    if len(new_checked) > 10:
        print(f"    ... 及其他 {len(new_checked) - 10} 条")

    if new_extraneous:
        print(f"  ⚠ 清单外编号: {len(new_extraneous)}（扫到的编号不在当前盘点批次内）")
        for n in new_extraneous[:10]:
            print(f"    ? {n}")
        if len(new_extraneous) > 10:
            print(f"    ... 及其他 {len(new_extraneous) - 10} 条")

    total = len(new_checked) + len(new_extraneous)
    dup = len(ids) - total
    if dup > 0:
        print(f"  重复扫码: {dup} 条（已自动去重）")

    progress = store.get_inventory_progress(inv_name)
    if progress:
        print("")
        print(f"[进度] 已核对 {progress['checked_count']}/{progress['total']}"
              f"  已打印未贴 {progress['printed_not_checked_count']}"
              f"  未打印 {progress['unprinted_count']}"
              f"  清单外 {progress['extraneous_count']}")
