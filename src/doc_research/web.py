"""抓取网页，提取正文转换为 Markdown，图片下载到本地，并记录来源链接。"""

import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import trafilatura
from curl_cffi import requests

from .mdtext import IMAGE_RE

ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}


def fetch(url: str) -> bytes:
    # impersonate 模拟真实浏览器的 TLS 指纹，绕过常见的机器人检测
    resp = requests.get(url, impersonate="chrome", timeout=60)
    resp.raise_for_status()
    return resp.content


def derive_slug(url: str) -> str:
    # 取 URL 路径末段作为 slug，取不到则用域名
    parts = [p for p in urlsplit(url).path.split("/") if p]
    base = parts[-1] if parts else urlsplit(url).netloc
    base = re.sub(r"\.(html?|php|aspx?)$", "", base, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9一-鿿]+", "-", base.lower()).strip("-")
    return slug or "page"


def localize_images(text: str, page_url: str, images_dir: Path) -> tuple[str, list[str]]:
    # 把正文中的图片下载到 images/ 并改写为相对路径；下载失败保留原链接
    localized = {}
    failures = []

    def replace(match: re.Match) -> str:
        alt, src = match.group(1), match.group(2)
        if src.startswith("data:"):
            return match.group(0)
        abs_url = urljoin(page_url, src)
        if abs_url not in localized:
            suffix = Path(urlsplit(abs_url).path).suffix.lower()
            if suffix not in ALLOWED_IMAGE_SUFFIXES:
                suffix = ".png"
            name = f"image-{len(localized) + 1:04d}{suffix}"
            try:
                images_dir.mkdir(parents=True, exist_ok=True)
                (images_dir / name).write_bytes(fetch(abs_url))
                localized[abs_url] = name
            except Exception as error:
                failures.append(f"{abs_url}（{error}）")
                return match.group(0)
        return f"![{alt}](images/{localized[abs_url]})"

    return IMAGE_RE.sub(replace, text), failures


def run(args) -> int:
    output_dir = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path.cwd() / derive_slug(args.url)
    )

    print(f"抓取 {args.url} ...")
    page_html = fetch(args.url).decode("utf-8", errors="replace")
    text = trafilatura.extract(
        page_html, output_format="markdown", include_images=True, url=args.url
    )
    if not text:
        print("正文提取失败：页面可能没有足够的正文内容", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    # 只覆盖脚本产物（raw.md、images/），输出目录下的其它文件不动
    raw_path = output_dir / "raw.md"
    images_dir = output_dir / "images"
    if raw_path.exists():
        raw_path.unlink()
    if images_dir.exists():
        shutil.rmtree(images_dir)

    text, failures = localize_images(text, args.url, images_dir)
    for failure in failures:
        print(f"图片下载失败，保留原链接：{failure}", file=sys.stderr)

    raw_path.write_text(f"<!-- source: {args.url} -->\n\n{text.strip()}\n", encoding="utf-8")
    image_count = len(list(images_dir.glob("*"))) if images_dir.exists() else 0

    print(f"已保存到 {output_dir}")
    print(f"- Markdown：{raw_path}")
    print(f"- 图片：{images_dir}（{image_count} 张）")
    return 0
