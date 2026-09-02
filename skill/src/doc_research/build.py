#!/usr/bin/env python3
"""报告构建：把 tr/*.md 渲染为 HTML 站点，写入 dist/（含首页与正文图片）。"""

import html
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

import markdown
from markdown.extensions.toc import slugify_unicode
from pygments.formatters import HtmlFormatter

MD_EXTENSIONS = [
    "tables",
    "footnotes",
    # 按列表标记宽度识别嵌套（默认渲染器要求子列表缩进 4 空格，2/3 空格会被拉平）
    "mdx_truly_sane_lists",
    "toc",
    "attr_list",
    "pymdownx.superfences",
    "pymdownx.arithmatex",
]
# 译文保留原文的 GitHub 风格锚点链接（如 #acid-的含义），slugify 须保留中文
MD_EXTENSION_CONFIGS = {
    "toc": {"slugify": slugify_unicode, "permalink": " ¶", "permalink_class": "headerlink"},
    "pymdownx.highlight": {"guess_lang": False},
    "pymdownx.arithmatex": {"generic": True},
}


IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\.\./raw/([^)]+)\)")
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
SOURCE_RE = re.compile(r"^<!--\s*source:\s*(\S+)\s*-->", re.MULTILINE)

# 暗色变量：@media 内（跟随系统且未手动指定浅色）与 [data-theme="dark"]（手动指定暗色）各展开一次
DARK_VARS = """    --bg: #0d1117;
    --fg: #e6edf3;
    --muted: #8b949e;
    --card: #161b22;
    --border: #2d333b;
    --accent: #58a6ff;
    --accent-soft: #12233d;
    --code-bg: #161b22;
    --shadow: 0 1px 2px rgb(0 0 0 / 30%), 0 4px 16px rgb(0 0 0 / 40%);"""
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<script>var t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t;</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
__PYGMENTS_LIGHT__
@media (prefers-color-scheme: dark) {
__PYGMENTS_DARK_SYSTEM__
}
__PYGMENTS_DARK_FORCED__
:root {
  --bg: #fafbfc;
  --fg: #1f2328;
  --muted: #656d76;
  --card: #ffffff;
  --border: #e5e7eb;
  --accent: #2563eb;
  --accent-soft: #eff6ff;
  --code-bg: #f6f8fa;
  --shadow: 0 1px 2px rgb(0 0 0 / 4%), 0 4px 16px rgb(0 0 0 / 6%);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
__DARK_VARS__
  }
}
:root[data-theme="dark"] {
__DARK_VARS__
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.75 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Source Han Sans SC", "Noto Sans CJK SC", "Microsoft YaHei",
    system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.topnav {
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: saturate(180%) blur(12px);
  background: color-mix(in srgb, var(--bg) 82%, transparent);
  border-bottom: 1px solid var(--border);
}
.topnav-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
}
.topnav .back { color: var(--muted); }
.topnav .back:hover { color: var(--accent); text-decoration: none; }

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  color: var(--muted);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, opacity 0.2s ease, transform 0.2s ease;
}
.icon-btn:hover { color: var(--accent); border-color: var(--accent); }
#theme-toggle { margin-left: auto; }
#to-top {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 20;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  box-shadow: var(--shadow);
  opacity: 0;
  pointer-events: none;
  transform: translateY(8px);
}
#to-top.visible { opacity: 1; pointer-events: auto; transform: none; }
#toc-toggle {
  display: none;
  position: fixed;
  right: 24px;
  bottom: 78px;
  z-index: 20;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  box-shadow: var(--shadow);
}

.hero {
  max-width: 1080px;
  margin: 0 auto;
  padding: 48px 24px 24px;
}
.hero h1 {
  margin: 0 0 8px;
  font-size: 34px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  background: linear-gradient(120deg, var(--accent), #a855f7);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero p { margin: 0; color: var(--muted); font-size: 15px; }

.entries {
  max-width: 1080px;
  margin: 0 auto;
  padding: 4px 24px 48px;
}
.entry {
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 7px 12px;
  color: var(--fg);
  border-bottom: 1px solid var(--border);
  border-radius: 6px;
}
.entry:hover { background: var(--accent-soft); text-decoration: none; }
.entry:hover .entry-slug { color: var(--accent); }
.entry-year {
  flex: none;
  width: 4ch;
  color: var(--muted);
  font: 13px ui-monospace, SFMono-Regular, Menlo, monospace;
}
.entry-slug {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font: 600 14.5px ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: nowrap;
  color: var(--fg);
}
.entry-slug:hover { color: var(--accent); text-decoration: none; }
.entry-title {
  flex: 1;
  min-width: 0;
  color: var(--muted);
  font-size: 13.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.entry-title:hover { color: var(--accent); text-decoration: none; }
.entry-src {
  flex: none;
  color: var(--muted);
  font: 12.5px ui-monospace, SFMono-Regular, Menlo, monospace;
}
.entry-src:hover { color: var(--accent); text-decoration: none; }

.layout {
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 24px 96px;
  display: grid;
  grid-template-columns: 260px minmax(0, 760px);
  gap: 48px;
  justify-content: center;
}

/* 同一个 #toc 元素：桌面端为左侧 sticky 栏，窄屏变为左侧滑出面板，由 #toc-toggle 控制 */
#toc {
  position: sticky;
  top: 76px;
  max-height: calc(100vh - 100px);
  overflow: auto;
  overscroll-behavior: contain;  /* 目录滚到底后不继续滚正文 */
  padding: 16px 18px;
  font-size: 13.5px;
  line-height: 1.6;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
}
/* 桌面浏览器下目录滚动条收窄，悬停时加宽便于拖拽 */
#toc::-webkit-scrollbar { width: 4px; }
#toc:hover::-webkit-scrollbar { width: 10px; }
#toc::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 3px; }
/* Firefox 不支持 ::-webkit-scrollbar，用标准属性收窄（最窄 thin） */
@supports (-moz-appearance: none) {
  #toc { scrollbar-width: thin; scrollbar-color: var(--muted) transparent; }
}
@media (max-width: 1100px) {
  .layout { grid-template-columns: minmax(0, 760px); }
  #toc-toggle { display: inline-flex; }
  #toc {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 30;
    width: 300px;
    max-width: 85vw;
    max-height: none;
    border: none;
    border-right: 1px solid var(--border);
    border-radius: 0;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }
  #toc.open { transform: none; }
}
.toc ul { list-style: none; margin: 0; padding-left: 14px; }
.toc > ul { padding-left: 0; }
.toc li { margin: 2px 0; }
.toc a { color: var(--muted); display: block; padding: 2px 0; }
.toc a:hover { color: var(--accent); text-decoration: none; }
.toc a.active { color: var(--accent); }


article { min-width: 0; }
article > h1:first-child {
  margin-top: 0;
  font-size: 32px;
  line-height: 1.3;
  letter-spacing: -0.01em;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.4; margin: 1.8em 0 0.7em; scroll-margin-top: 68px; }
article img[id] { scroll-margin-top: 68px; }
h2 { padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.headerlink { color: var(--muted); opacity: 0; font-size: 0.8em; }
h1:hover .headerlink, h2:hover .headerlink, h3:hover .headerlink,
h4:hover .headerlink, h5:hover .headerlink, h6:hover .headerlink { opacity: 1; }
.headerlink:hover { text-decoration: none; color: var(--accent); }

p, li { overflow-wrap: break-word; }
img {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  display: block;
  margin: 12px auto;
}
blockquote {
  margin: 16px 0;
  padding: 2px 18px;
  color: var(--muted);
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 8px 8px 0;
  font-size: 14.5px;
}
code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.88em;
}
p code, li code, td code, blockquote code {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.15em 0.4em;
}
.highlight {
  background: var(--code-bg);
  border-radius: 12px;
  border: 1px solid var(--border);
  overflow: hidden;
  margin: 16px 0;
  box-shadow: var(--shadow);
}
.highlight pre {
  margin: 0;
  padding: 16px 18px;
  overflow-x: auto;
  font-size: 13.5px;
  line-height: 1.65;
}
.highlight code { background: none; border: none; padding: 0; font-size: inherit; }
table {
  display: block;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14.5px;
}
th, td { border: 1px solid var(--border); padding: 8px 14px; }
th { background: var(--code-bg); font-weight: 600; }
tr:nth-child(even) td { background: color-mix(in srgb, var(--code-bg) 55%, transparent); }
hr { border: none; border-top: 1px solid var(--border); margin: 40px 0; }
.footnote { font-size: 13.5px; color: var(--muted); }
mjx-container { color: inherit; overflow-x: auto; overflow-y: hidden; }
</style>
<script>
window.MathJax = {
  tex: {
    inlineMath: [["\\\\(", "\\\\)"]],
    displayMath: [["\\\\[", "\\\\]"]]
  },
  options: { skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"] }
};
</script>
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
</head>
<body>
<header class="topnav"><div class="topnav-inner">
__NAV_EXTRA__
<button id="theme-toggle" class="icon-btn" type="button" aria-label="切换主题">
<svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
<svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4M4.9 14.9l1.4 1.4"/></svg>
</button>
</div></header>
__BODY__
<button id="to-top" class="icon-btn" type="button" aria-label="回到顶部"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg></button>
<script>
(function () {
  var root = document.documentElement;
  var media = matchMedia("(prefers-color-scheme: dark)");
  var btn = document.getElementById("theme-toggle");
  function isDark() {
    return root.dataset.theme ? root.dataset.theme === "dark" : media.matches;
  }
  function update() {
    var dark = isDark();
    btn.setAttribute("aria-label", dark ? "切换到浅色模式" : "切换到深色模式");
    btn.querySelector(".icon-sun").style.display = dark ? "" : "none";
    btn.querySelector(".icon-moon").style.display = dark ? "none" : "";
  }
  btn.addEventListener("click", function () {
    root.dataset.theme = isDark() ? "light" : "dark";
    localStorage.setItem("theme", root.dataset.theme);
    update();
  });
  media.addEventListener("change", update);
  update();

  var toTop = document.getElementById("to-top");
  addEventListener("scroll", function () {
    toTop.classList.toggle("visible", scrollY > 400);
  }, { passive: true });
  toTop.addEventListener("click", function () { scrollTo(0, 0); });

  var toc = document.getElementById("toc");
  var tocToggle = document.getElementById("toc-toggle");
  if (toc && tocToggle) {
    // 展开目录时定位到当前阅读的条目：目录链接与正文标题成对收集，二分找视口内最后一个标题
    var entries = [];
    toc.querySelectorAll('a[href^="#"]').forEach(function (a) {
      var h = document.getElementById(a.getAttribute("href").slice(1));
      if (h) entries.push([h, a]);
    });
    function locateCurrent() {
      // 标题锚点定位后停在视口顶部 68px（scroll-margin-top），判定窗口略放宽
      var lo = 0, hi = entries.length - 1, idx = -1;
      while (lo <= hi) {
        var mid = (lo + hi) >> 1;
        if (entries[mid][0].getBoundingClientRect().top <= 90) { idx = mid; lo = mid + 1; }
        else hi = mid - 1;
      }
      // 滚到底时末节标题可能永远到不了顶部，直接取最后一条
      if (scrollY > 0 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2)
        idx = entries.length - 1;
      if (idx < 0) return;
      var a = entries[idx][1];
      var prev = toc.querySelector("a.active");
      if (prev) prev.classList.remove("active");
      a.classList.add("active");
      toc.scrollTop = a.offsetTop + a.offsetHeight / 2 - toc.clientHeight / 2;
    }
    tocToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      if (toc.classList.toggle("open")) locateCurrent();
    });
    toc.addEventListener("click", function (e) {
      if (e.target.closest("a")) toc.classList.remove("open");
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#toc")) toc.classList.remove("open");
    });
  }
})();
</script>
</body>
</html>
"""

ARTICLE_BODY = """<div class="layout">
<nav id="toc">__TOC__</nav>
<article>
__CONTENT__
</article>
</div>
<button id="toc-toggle" class="icon-btn" type="button" aria-label="目录"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M8 12h12M12 18h8"/></svg></button>
"""

INDEX_BODY = """<section class="hero">
<h1>调研报告</h1>
<p>文献调研的中文报告，共 __COUNT__ 篇。</p>
</section>
<section class="entries">
__ENTRIES__
</section>
"""


def render_page(md_text: str) -> tuple[str, str, str]:
    md = markdown.Markdown(
        extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS
    )
    content = md.convert(md_text)
    title_match = TITLE_RE.search(md_text)
    title = title_match.group(1) if title_match else ""
    return content, title, md.toc  # toc 扩展在 convert 时动态挂载该属性


def find_source(project: Path, slug: str) -> str:
    # 网页来源的 raw.md 首行有 <!-- source: <url> --> 注释，用作首页「原文」入口
    raw_path = project / "raw" / slug / "raw.md"
    if not raw_path.is_file():
        return ""
    match = SOURCE_RE.search(raw_path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def run(args) -> int:
    project = Path(args.dir).resolve()
    tr_dir = project / "tr"
    dist_dir = project / "dist"
    if not tr_dir.is_dir():
        print(f"{tr_dir} 不存在，先完成收集与整理", file=sys.stderr)
        return 1

    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()

    def style_defs(style: str, selector: str) -> str:
        defs = HtmlFormatter(style=style).get_style_defs(selector)
        # 代码块容器底色统一由模板的 --code-bg 控制，去掉主题自带的背景
        return re.sub(r"\{ background: [^;}]+; ", "{ ", defs)

    pygments_light = style_defs("default", ".highlight")
    dark_system = style_defs("github-dark", ':root:not([data-theme="light"]) .highlight')
    dark_forced = style_defs("github-dark", '[data-theme="dark"] .highlight')

    entries = []
    for md_path in sorted(tr_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        images = IMAGE_RE.findall(text)
        text = IMAGE_RE.sub(r"![](raw/\1)", text)

        for rel in images:
            src = project / "raw" / rel
            dst = dist_dir / "raw" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        content, title, toc = render_page(text)
        title = title or md_path.stem
        page = (
            PAGE_TEMPLATE.replace("__PYGMENTS_LIGHT__", pygments_light)
            .replace("__PYGMENTS_DARK_SYSTEM__", dark_system)
            .replace("__PYGMENTS_DARK_FORCED__", dark_forced)
            .replace("__DARK_VARS__", DARK_VARS)
            .replace("__TITLE__", html.escape(title))
            .replace("__NAV_EXTRA__", '<a class="back" href="index.html">← 返回首页</a>')
            .replace(
                "__BODY__",
                ARTICLE_BODY.replace("__CONTENT__", content).replace("__TOC__", toc),
            )
        )
        (dist_dir / f"{md_path.stem}.html").write_text(page, encoding="utf-8")
        entries.append((md_path.stem, title, find_source(project, md_path.stem)))
        print(f"built {md_path.stem}.html ({len(images)} images)")

    # 按 slug 尾缀年份倒序（最新在前），同年按 slug 字典序
    entries = [
        (int(m.group(1)) if (m := re.search(r"-(\d{4})$", slug)) else 0, slug, title, source)
        for slug, title, source in entries
    ]
    entries.sort(key=lambda e: (-e[0], e[1]))

    def entry_row(year: int, slug: str, title: str, source: str) -> str:
        source_link = (
            f'<a class="entry-src" href="{html.escape(source, quote=True)}"'
            f' target="_blank" rel="noopener">原文 ↗</a>'
            if source
            else ""
        )
        return (
            f'<div class="entry">'
            f'<span class="entry-year">{year}</span>'
            f'<a class="entry-slug" href="{quote(slug)}.html">{html.escape(slug)}</a>'
            f'<a class="entry-title" href="{quote(slug)}.html">{html.escape(title)}</a>'
            f"{source_link}</div>"
        )

    rows = "\n".join(entry_row(*entry) for entry in entries)
    index = (
        PAGE_TEMPLATE.replace("__PYGMENTS_LIGHT__", pygments_light)
        .replace("__PYGMENTS_DARK_SYSTEM__", dark_system)
        .replace("__PYGMENTS_DARK_FORCED__", dark_forced)
        .replace("__DARK_VARS__", DARK_VARS)
        .replace("__TITLE__", "调研报告")
        .replace("__NAV_EXTRA__", "")
        .replace(
            "__BODY__",
            INDEX_BODY.replace("__COUNT__", str(len(entries))).replace("__ENTRIES__", rows),
        )
    )
    (dist_dir / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(entries)} articles)")
    return 0
