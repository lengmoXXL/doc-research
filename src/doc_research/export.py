#!/usr/bin/env python3
"""导出 PDF 页面（或相对坐标裁剪的局部）为图片，供校对时核对公式、图表细节。"""

import sys
from pathlib import Path


def run(args) -> int:
    import pymupdf

    pdf_path = Path(args.file_path).expanduser().resolve()
    if not pdf_path.is_file():
        print(f"File not found: {pdf_path}", file=sys.stderr)
        return 1

    doc = pymupdf.open(pdf_path)
    page = doc[args.page]
    clip = None
    if args.clip:
        rect = page.rect
        x0, y0, x1, y1 = (float(v) for v in args.clip.split(","))
        clip = pymupdf.Rect(
            rect.width * x0, rect.height * y0, rect.width * x1, rect.height * y1
        )
    page.get_pixmap(dpi=args.dpi, clip=clip).save(args.output)
    print(f"Saved {args.output}")
    return 0
