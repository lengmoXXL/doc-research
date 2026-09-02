#!/usr/bin/env python3
"""doc-research：文档处理 CLI——PDF/EPUB 转 Markdown、网页正文提取、PDF 页面导出、Markdown 渲染 HTML 站点。"""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="doc-research", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse", help="用 DocMind 转换本地文档（PDF、EPUB 等）为 Markdown"
    )
    parse_parser.add_argument("file_path", help="本地文档路径")
    parse_parser.add_argument("-o", "--output", help="输出目录（默认 ./<文件名>）")

    fetch_parser = subparsers.add_parser(
        "fetch", help="抓取网页，提取正文转换为 Markdown（图片下载到本地）"
    )
    fetch_parser.add_argument("url", help="网页 URL")
    fetch_parser.add_argument("-o", "--output", help="输出目录（默认 ./<从 URL 推导的名称>）")

    export_parser = subparsers.add_parser(
        "export-page", help="导出 PDF 页面（或相对坐标裁剪的局部）为图片"
    )
    export_parser.add_argument("file_path", help="PDF 路径")
    export_parser.add_argument("page", type=int, help="页索引（0 基）")
    export_parser.add_argument("-o", "--output", required=True, help="输出图片路径")
    export_parser.add_argument("--dpi", type=int, default=100, help="渲染 DPI（默认 100）")
    export_parser.add_argument("--clip", help="局部裁剪，相对坐标 x0,y0,x1,y1（0~1）")

    build_parser = subparsers.add_parser(
        "build", help="把目录中的 Markdown 渲染为 HTML 站点"
    )
    build_parser.add_argument("md_dir", help="Markdown 目录")
    build_parser.add_argument("-o", "--output", required=True, help="输出目录")
    build_parser.add_argument("--title", default="文档索引", help="首页标题")
    build_parser.add_argument("--desc", help="首页标题下的简介（默认只显示篇数）")
    build_parser.add_argument(
        "--base", help="首页 <base href>（站点发布在子路径且经根路径访问时使用）"
    )

    args = parser.parse_args()
    # 重依赖（alibabacloud、trafilatura 等）延迟导入，help 等路径保持轻量
    if args.command == "parse":
        from . import parse

        return parse.run(args)
    if args.command == "fetch":
        from . import web

        return web.run(args)
    if args.command == "export-page":
        from . import export

        return export.run(args)
    from . import build

    return build.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
