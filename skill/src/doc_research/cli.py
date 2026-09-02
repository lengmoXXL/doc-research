#!/usr/bin/env python3
"""doc-research：文献调研 CLI——收集（PDF/EPUB 转 Markdown）、整理、报告（校对翻译为中文）。"""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="doc-research", description=__doc__)
    parser.add_argument("--dir", default=".", help="项目目录（默认当前目录）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse", help="用 DocMind 转换本地文档（PDF、EPUB 等）为 Markdown"
    )
    parse_parser.add_argument("file_path", help="本地文档路径")

    fetch_parser = subparsers.add_parser(
        "fetch", help="抓取网页，提取正文转换为 Markdown（图片下载到本地）"
    )
    fetch_parser.add_argument("url", help="网页 URL")
    fetch_parser.add_argument("--slug", help="raw/ 下的子目录名（默认从 URL 推导）")

    subparsers.add_parser("env", help="交互式填写 .env 凭据")
    subparsers.add_parser("check", help="检查项目是否已初始化（.env 凭据 + .venv 依赖）")

    subparsers.add_parser(
        "build", help="报告构建：tr/*.md 渲染为 HTML 站点，写入 dist/"
    )

    init_parser = subparsers.add_parser(
        "init", help="初始化项目：凭据 + .venv"
    )
    init_parser.add_argument("--skip-deps", action="store_true", help="跳过 pip install")

    args = parser.parse_args()
    # 重依赖（alibabacloud、trafilatura 等）延迟导入，env/init 保持轻量
    if args.command == "parse":
        from . import parse

        return parse.run(args)
    if args.command == "fetch":
        from . import web

        return web.run(args)
    if args.command == "build":
        from . import build

        return build.run(args)
    from . import project

    if args.command == "env":
        return project.cmd_env(args)
    if args.command == "check":
        return project.cmd_check(args)
    return project.cmd_init(args)


if __name__ == "__main__":
    raise SystemExit(main())
