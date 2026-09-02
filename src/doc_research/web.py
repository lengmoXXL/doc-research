#!/usr/bin/env python3
"""收集网页：抓取 URL，提取正文转换为 Markdown，图片下载到本地 images/，并记录来源链接。"""

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

import trafilatura

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as resp:
        return resp.read()


def derive_slug(url: str) -> str:
    # 取 URL 路径末段作为 slug，取不到则用域名
    parts = [p for p in urlsplit(url).path.split("/") if p]
    base = parts[-1] if parts else urlsplit(url).netloc
    base = re.sub(r"\.(html?|php|aspx?)$", "", base, flags=re.I)
    slug = re.sub(r"[^a-z0-9一-鿿]+", "-", base.lower()).strip("-")
    return slug or "page"


def localize_images(markdown: str, page_url: str, images_dir: Path) -> tuple[str, list[str]]:
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
                failures.append(f"{abs_url} ({error})")
                return match.group(0)
        return f"![{alt}](images/{localized[abs_url]})"

    return IMAGE_RE.sub(replace, markdown), failures


def run(args) -> int:
    output_dir = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path.cwd() / derive_slug(args.url)
    )

    print(f"Fetching {args.url} ...")
    html = fetch(args.url).decode("utf-8", errors="replace")
    markdown = trafilatura.extract(
        html, output_format="markdown", include_images=True, url=args.url
    )
    if not markdown:
        print("正文提取失败：页面可能没有足够的正文内容", file=sys.stderr)
        return 1

    markdown, failures = localize_images(markdown, args.url, output_dir / "images")
    for failure in failures:
        print(f"图片下载失败，保留原链接: {failure}", file=sys.stderr)

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "raw.md"
    raw_path.write_text(
        f"<!-- source: {args.url} -->\n\n{markdown.strip()}\n", encoding="utf-8"
    )
    images_dir = output_dir / "images"
    image_count = len(list(images_dir.glob("*")))

    print(f"Saved local results to {output_dir}")
    print(f"- Markdown: {raw_path}")
    print(f"- Images: {images_dir} ({image_count})")
    return 0
