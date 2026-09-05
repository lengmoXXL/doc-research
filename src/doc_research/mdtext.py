"""Markdown 文本的共享定义。"""

import re

IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
