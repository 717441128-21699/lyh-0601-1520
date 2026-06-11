import argparse
import sys

from .models import LABEL_SIZES, CODE_STYLES, PAPER_SIZES
from .importer import run_import
from .preview import run_preview
from .printer import run_print
from .exporter import run_export
from .checker import run_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asset-label",
        description="企业资产标签打印命令行工具 - 批量生成条码和标签文件",
    )
    parser.add_argument("--data-dir", default=".asset_data", help="数据存储目录 (默认: .asset_data)")

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # ---- import ----
    p_import = sub.add_parser("import", help="从清单文件导入资产数据")
    p_import.add_argument("file", help="资产清单文件路径 (.csv 或 .xlsx)")
    p_import.add_argument("--category", help="统一设置资产类别")
    p_import.add_argument("--auto-id", action="store_true", help="为无编号的资产生成连续编号")
    p_import.add_argument("--prefix", default="AST", help="自动编号前缀 (默认: AST)")
    p_import.add_argument("--sheet", help="Excel 工作表名称 (仅 .xlsx)")
    p_import.add_argument("--apply", action="store_true", help="确认并写入数据库 (不加则仅预览校验报告)")

    # ---- preview ----
    p_preview = sub.add_parser("preview", help="预览资产数据及缺失字段")
    p_preview.add_argument("--category", help="按类别筛选")
    p_preview.add_argument("--location", help="按位置模糊筛选")
    p_preview.add_argument("--responsible", help="按责任人模糊筛选")
    p_preview.add_argument("--unprinted", action="store_true", help="仅显示未打印记录")
    p_preview.add_argument("--hide-missing", action="store_true", help="隐藏缺失字段提示")

    # ---- print ----
    p_print = sub.add_parser("print", help="生成标签图片并记录打印批次")
    p_print.add_argument("--category", help="按类别筛选打印范围")
    p_print.add_argument("--location", help="按位置模糊筛选")
    p_print.add_argument("--responsible", help="按责任人模糊筛选")
    p_print.add_argument("--ids", nargs="+", dest="asset_ids", help="指定资产编号列表")
    p_print.add_argument("--task", help="使用保存的打印任务 (优先使用任务的筛选条件)")
    p_print.add_argument("--all", action="store_true", help="打印全部 (包括已打印)")
    p_print.add_argument("--label-size", choices=list(LABEL_SIZES.keys()), help="标签尺寸 (默认: medium)")
    p_print.add_argument("--code-style", choices=list(CODE_STYLES), help="码样式: barcode/qrcode (默认: barcode)")
    p_print.add_argument("--skip-missing", action="store_true", help="自动跳过缺失必填字段的记录")
    p_print.add_argument("--output", help="输出目录 (默认: ./labels_output)")
    p_print.add_argument("--save-task", metavar="NAME", help="将当前筛选条件保存为常用打印任务")
    p_print.add_argument("--list-tasks", action="store_true", help="列出所有常用打印任务")
    p_print.add_argument("--delete-task", metavar="NAME", help="删除指定打印任务")

    # ---- export ----
    p_export = sub.add_parser("export", help="导出标签文件 (PDF/PNG)")
    p_export.add_argument("--category", help="按类别筛选")
    p_export.add_argument("--location", help="按位置模糊筛选")
    p_export.add_argument("--responsible", help="按责任人模糊筛选")
    p_export.add_argument("--ids", nargs="+", dest="asset_ids", help="指定资产编号列表")
    p_export.add_argument("--batch-id", help="按批次号导出")
    p_export.add_argument("--task", help="使用保存的打印任务的筛选条件")
    p_export.add_argument("--label-size", choices=list(LABEL_SIZES.keys()), help="标签尺寸 (默认: medium)")
    p_export.add_argument("--code-style", choices=list(CODE_STYLES), help="码样式 (默认: barcode)")
    p_export.add_argument("--format", choices=["pdf", "png"], default="pdf", help="输出格式 (默认: pdf)")
    p_export.add_argument("--output", help="输出路径 (PDF 为文件名, PNG 为目录)")
    p_export.add_argument("--paper", default="A4", choices=list(PAPER_SIZES.keys()), help="纸张规格 (默认: A4)")
    p_export.add_argument("--cols", type=int, help="每页列数 (自动计算)")
    p_export.add_argument("--rows", type=int, help="每页行数 (自动计算)")
    p_export.add_argument("--margin", type=float, default=10.0, help="页边距 (mm, 默认: 10)")
    p_export.add_argument("--gap", type=float, default=3.0, help="标签间距 (mm, 默认: 3)")

    # ---- check ----
    p_check = sub.add_parser("check", help="查看打印记录、资产状态及补打")
    p_check.add_argument("--status", metavar="ASSET_ID", help="查看指定资产状态")
    p_check.add_argument("--reprint", metavar="ASSET_ID", help="按资产编号补打单张标签")
    p_check.add_argument("--reprint-batch", metavar="BATCH_ID", help="按批次号整组补打")
    p_check.add_argument("--label-size", choices=list(LABEL_SIZES.keys()), help="补打标签尺寸")
    p_check.add_argument("--code-style", choices=list(CODE_STYLES), help="补打码样式")
    p_check.add_argument("--output", help="补打输出目录")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "import": run_import,
        "preview": run_preview,
        "print": run_print,
        "export": run_export,
        "check": run_check,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
