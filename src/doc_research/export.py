"""导出 PDF 页面（或相对坐标裁剪的局部）为图片。"""

import sys
from pathlib import Path

import pymupdf


def run(args) -> int:
    pdf_path = Path(args.file_path).expanduser().resolve()
    if not pdf_path.is_file():
        print(f"文件不存在：{pdf_path}", file=sys.stderr)
        return 1

    doc = pymupdf.open(pdf_path)
    page = doc[args.page]
    clip = None
    if args.clip:
        rect = page.rect
        x0, y0, x1, y1 = (float(v) for v in args.clip.split(","))
        clip = pymupdf.Rect(rect.width * x0, rect.height * y0, rect.width * x1, rect.height * y1)
    page.get_pixmap(dpi=args.dpi, clip=clip).save(args.output)
    print(f"已保存到 {args.output}")
    return 0
