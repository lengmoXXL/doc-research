"""把目录中的 Markdown 渲染为 HTML 站点（含首页、目录栏与正文图片）。"""

import html
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

import markdown
import yaml
from markdown.extensions.toc import slugify_unicode
from pygments.formatters import HtmlFormatter

from .mdtext import IMAGE_RE

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

TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.DOTALL)

LINK_RE = re.compile(r"\]\(([^)\s/]+?\.md)(#[^)\s]*)?\)")

ENTRY_LINE = r"[-*] \[[^]]*\]\(([^)\s/]+?)\.md(?:#[^)\s]*)?\)"

ENTRY_LINK_RE = re.compile(rf"^{ENTRY_LINE}[ \t]*$", re.MULTILINE)

ENTRY_BLOCK_RE = re.compile(rf"(?:^{ENTRY_LINE}[ \t]*\n?)+", re.MULTILINE)

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
__BASE__
<script>
var t = localStorage.getItem("theme");
if (t) document.documentElement.dataset.theme = t;
</script>
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

.index-content {
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
.pin {
  flex: none;
  align-self: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: none;
  color: var(--muted);
  cursor: pointer;
  opacity: 0.35;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s ease, color 0.15s ease;
}
.entry:hover .pin { opacity: 0.8; }
.pin:hover { color: var(--accent); }
.pin.on { opacity: 1; color: var(--accent); }
.tag-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px 12px 12px;
}
.tag {
  padding: 2px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--muted);
  font-size: 13px;
  cursor: pointer;
}
.tag.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
.entry-tag {
  flex: none;
  color: var(--muted);
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0 8px;
}
.entry.hide { display: none; }

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
<svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
<svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="4"/>
<path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2"/>
<path d="M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4M4.9 14.9l1.4 1.4"/></svg>
</button>
</div></header>
__BODY__
<button id="to-top" class="icon-btn" type="button" aria-label="回到顶部">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg></button>
<script>
(function () {
  var root = document.documentElement;
  var media = matchMedia("(prefers-color-scheme: dark)");
  var themeBtn = document.getElementById("theme-toggle");
  function isDark() {
    return root.dataset.theme ? root.dataset.theme === "dark" : media.matches;
  }
  function update() {
    var dark = isDark();
    themeBtn.setAttribute("aria-label", dark ? "切换到浅色模式" : "切换到深色模式");
    themeBtn.querySelector(".icon-sun").style.display = dark ? "" : "none";
    themeBtn.querySelector(".icon-moon").style.display = dark ? "none" : "";
  }
  themeBtn.addEventListener("click", function () {
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

  var progressKey = "progress:" + location.pathname;
  if (!location.hash) {
    var savedY = Number(localStorage.getItem(progressKey));
    if (savedY) addEventListener("load", function () {
      scrollTo({ top: savedY, behavior: "instant" });
    });
  }
  var saveTimer;
  function saveProgress() {
    localStorage.setItem(progressKey, String(Math.round(scrollY)));
  }
  addEventListener("scroll", function () {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveProgress, 200);
  }, { passive: true });
  addEventListener("pagehide", saveProgress);

  var toc = document.getElementById("toc");
  var tocToggle = document.getElementById("toc-toggle");
  if (toc && tocToggle) {
    // 展开目录时定位到当前阅读的目录项：目录链接与正文标题成对收集，二分找视口内最后一个标题
    var tocItems = [];
    toc.querySelectorAll('a[href^="#"]').forEach(function (a) {
      var h = document.getElementById(a.getAttribute("href").slice(1));
      if (h) tocItems.push([h, a]);
    });
    function locateCurrent() {
      // 标题锚点定位后停在视口顶部 68px（scroll-margin-top），判定窗口略放宽
      var lo = 0, hi = tocItems.length - 1, idx = -1;
      while (lo <= hi) {
        var mid = (lo + hi) >> 1;
        if (tocItems[mid][0].getBoundingClientRect().top <= 90) { idx = mid; lo = mid + 1; }
        else hi = mid - 1;
      }
      // 滚到底时末节标题可能永远到不了顶部，直接取最后一条
      if (scrollY > 0 && scrollY + innerHeight >= document.documentElement.scrollHeight - 2)
        idx = tocItems.length - 1;
      if (idx < 0) return;
      var a = tocItems[idx][1];
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

  // 置顶：条目可能分成多个 .entry-list 容器，图钉在各自容器内重排，按页持久化
  var entryRows = [];
  var rowsBySlug = {};
  var entryBoxes = [];
  document.querySelectorAll(".entry-list").forEach(function (box) {
    var rows = [];
    box.querySelectorAll(".entry").forEach(function (el) {
      rowsBySlug[el.dataset.slug] = el;
      rows.push(el);
      entryRows.push(el);
    });
    entryBoxes.push({ box: box, rows: rows });
  });
  if (entryRows.length) {
    var pinsKey = "pins:" + location.pathname;
    var pins = [];
    try {
      var savedPins = JSON.parse(localStorage.getItem(pinsKey));
      if (Array.isArray(savedPins)) pins = savedPins;
    } catch (e) {}
    function applyPins() {
      pins = pins.filter(function (s) { return rowsBySlug[s]; });
      entryBoxes.forEach(function (b) {
        var order = [];
        pins.forEach(function (s) {
          if (b.rows.indexOf(rowsBySlug[s]) >= 0) order.push(rowsBySlug[s]);
        });
        b.rows.forEach(function (el) {
          var on = pins.indexOf(el.dataset.slug) >= 0;
          var pinBtn = el.querySelector(".pin");
          pinBtn.classList.toggle("on", on);
          pinBtn.setAttribute("aria-pressed", String(on));
          if (!on) order.push(el);
        });
        order.forEach(function (el) { b.box.appendChild(el); });
      });
    }
    entryRows.forEach(function (el) {
      el.querySelector(".pin").addEventListener("click", function () {
        var slug = el.dataset.slug;
        var i = pins.indexOf(slug);
        if (i >= 0) pins.splice(i, 1); else pins.unshift(slug);
        localStorage.setItem(pinsKey, JSON.stringify(pins));
        applyPins();
      });
    });
    applyPins();
  }

  // 标签过滤：chips 多选，条目须含全部选中标签；再次点击取消选中（作用于全部容器）
  var filter = document.querySelector(".tag-filter");
  if (filter && entryRows.length) {
    var selected = [];
    filter.querySelectorAll(".tag").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var tag = chip.dataset.tag;
        var i = selected.indexOf(tag);
        if (i >= 0) selected.splice(i, 1); else selected.push(tag);
        chip.classList.toggle("on", i < 0);
        entryRows.forEach(function (el) {
          var tags = JSON.parse(el.dataset.tags);
          var show = selected.every(function (t) { return tags.indexOf(t) >= 0; });
          el.classList.toggle("hide", !show);
        });
      });
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
<button id="toc-toggle" class="icon-btn" type="button" aria-label="目录">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round">
<path d="M4 6h16M8 12h12M12 18h8"/></svg></button>
"""

PIN_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 '
    "15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 "
    '0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1z"/></svg>'
)

INDEX_BODY = """<section class="hero">
<h1>__TITLE__</h1>
<p>__DESC__</p>
</section>
<section class="index-content">
__CONTENT__
</section>
"""


def render_page(md_text: str) -> tuple[str, str, str]:
    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS)
    content = md.convert(md_text)
    title_match = TITLE_RE.search(md_text)
    title = title_match.group(1) if title_match else ""
    return content, title, md.toc  # toc 扩展在 convert 时动态挂载该属性


def split_frontmatter(text: str) -> tuple[str, list[str]]:
    # Obsidian 风格 YAML 头；只取 tags（列表或单个标量），整块剥离不参与渲染
    match = FRONTMATTER_RE.match(text)
    if not match:
        return text, []
    meta = yaml.safe_load(match.group(1)) or {}
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return text[match.end() :], tags


def localize_images(text: str, md_dir: Path, out_dir: Path) -> tuple[str, int]:
    # 相对路径引用的本地图片复制进输出目录，保持相对结构（去掉开头的 ../）并改写引用
    count = 0

    def copy(match: re.Match) -> str:
        nonlocal count
        alt, src = match.group(1), match.group(2)
        if re.match(r"[a-z]+:", src, re.IGNORECASE):  # http:、data: 等绝对地址不处理
            return match.group(0)
        src_path = (md_dir / src).resolve()
        rel = os.path.relpath(src_path, md_dir)
        while rel.startswith("../"):
            rel = rel[3:]
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst)
        count += 1
        return f"![{alt}]({rel})"

    return IMAGE_RE.sub(copy, text), count


def localize_links(text: str, slugs: set[str], source: str) -> str:
    # 站内互链 [文字](other.md) 改写为 .html；仅处理同目录裸文件名，目标缺失时警告
    def rewrite(match: re.Match) -> str:
        slug, anchor = match.group(1)[:-3], match.group(2) or ""
        if slug not in slugs:
            print(f"{source}：内链目标不存在：{slug}.md", file=sys.stderr)
        return f"]({slug}.html{anchor})"

    return LINK_RE.sub(rewrite, text)


def entry_year(slug: str) -> int:
    m = re.search(r"-(\d{4})$", slug)
    return int(m.group(1)) if m else 0


def entry_row(slug: str, title: str, tags: list[str]) -> str:
    tag_spans = "".join(f'<span class="entry-tag">{html.escape(t)}</span>' for t in tags)
    data_tags = html.escape(json.dumps(tags, ensure_ascii=False), quote=True)
    return (
        f'<div class="entry" data-slug="{html.escape(slug, quote=True)}"'
        f' data-tags="{data_tags}">'
        f'<span class="entry-year">{entry_year(slug) or ""}</span>'
        f'<a class="entry-slug" href="{quote(slug)}.html">{html.escape(slug)}</a>'
        f'<a class="entry-title" href="{quote(slug)}.html">{html.escape(title)}</a>{tag_spans}'
        f'<button class="pin" type="button" aria-label="置顶" aria-pressed="false">'
        f"{PIN_SVG}</button></div>"
    )


def enhance_entries(text: str, articles: dict[str, tuple[str, list[str]]]) -> tuple[str, list[str]]:
    # index.md 中「整个列表项为单个 .md 内链」的行是首页条目：连续条目行合并为
    # entry-list 容器（首个容器带标签过滤栏）；指向不存在文章的条目警告并跳过
    found = [m.group(1) for m in ENTRY_LINK_RE.finditer(text)]
    for slug in found:
        if slug not in articles:
            print(f"index.md：条目指向不存在的文章：{slug}.md", file=sys.stderr)
    entry_slugs = [slug for slug in found if slug in articles]

    all_tags = set()
    for slug in entry_slugs:
        _, tags = articles[slug]
        all_tags.update(tags)
    chips = "".join(
        f'<button class="tag" type="button" data-tag="{html.escape(t, quote=True)}">'
        f"{html.escape(t)}</button>"
        for t in sorted(all_tags)
    )
    tag_filter = f'<div class="tag-filter">{chips}</div>\n' if chips else ""
    first = True

    def block(match: re.Match) -> str:
        nonlocal first
        rows = []
        for line in ENTRY_LINK_RE.finditer(match.group(0)):
            slug = line.group(1)
            if slug not in articles:
                continue
            title, tags = articles[slug]
            rows.append(entry_row(slug, title, tags))
        if not rows:
            return ""
        head = tag_filter if first else ""
        first = False
        return f'<div class="entry-list">\n{head}' + "\n".join(rows) + "\n</div>\n"

    return ENTRY_BLOCK_RE.sub(block, text), entry_slugs


def render_html(
    title: str, body: str, styles: tuple[str, str, str], base_tag: str = "", nav_extra: str = ""
) -> str:
    light, dark_system, dark_forced = styles
    return (
        PAGE_TEMPLATE.replace("__PYGMENTS_LIGHT__", light)
        .replace("__PYGMENTS_DARK_SYSTEM__", dark_system)
        .replace("__PYGMENTS_DARK_FORCED__", dark_forced)
        .replace("__DARK_VARS__", DARK_VARS)
        .replace("__TITLE__", html.escape(title))
        .replace("__BASE__", base_tag)
        .replace("__NAV_EXTRA__", nav_extra)
        .replace("__BODY__", body)
    )


def run(args) -> int:
    md_dir = Path(args.md_dir).resolve()
    out_dir = Path(args.output).resolve()
    if not md_dir.is_dir():
        print(f"{md_dir} 不存在", file=sys.stderr)
        return 1

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()

    def style_defs(style: str, selector: str) -> str:
        defs = HtmlFormatter(style=style).get_style_defs(selector)
        # 代码块容器底色统一由模板的 --code-bg 控制，去掉主题自带的背景
        return re.sub(r"\{ background: [^;}]+; ", "{ ", defs)

    pygments_light = style_defs("default", ".highlight")
    dark_system = style_defs("github-dark", ':root:not([data-theme="light"]) .highlight')
    dark_forced = style_defs("github-dark", '[data-theme="dark"] .highlight')
    styles = (pygments_light, dark_system, dark_forced)

    md_paths = [p for p in sorted(md_dir.glob("*.md")) if p.name != "index.md"]
    slugs = {p.stem for p in md_paths}
    articles = {}
    for md_path in md_paths:
        text = md_path.read_text(encoding="utf-8")
        text, tags = split_frontmatter(text)
        text, images = localize_images(text, md_dir, out_dir)
        text = localize_links(text, slugs, md_path.name)

        content, title, toc = render_page(text)
        title = title or md_path.stem
        page = render_html(
            title,
            ARTICLE_BODY.replace("__CONTENT__", content).replace("__TOC__", toc),
            styles,
            nav_extra='<a class="back" href="index.html">← 返回首页</a>',
        )
        (out_dir / f"{md_path.stem}.html").write_text(page, encoding="utf-8")
        articles[md_path.stem] = (title, tags)
        print(f"已构建 {md_path.stem}.html（{images} 张图片）")

    # 首页：index.md 走与文章相同的管线；其中「整项为单个 .md 内链」的列表行增强为条目行
    content_html = ""
    entry_slugs = []
    index_md = md_dir / "index.md"
    if index_md.is_file():
        text, _ = split_frontmatter(index_md.read_text(encoding="utf-8"))
        text, _ = localize_images(text, md_dir, out_dir)
        text, entry_slugs = enhance_entries(text, articles)
        text = localize_links(text, slugs, "index.md")
        content_html, _, _ = render_page(text)

    count = len(entry_slugs)
    desc = f"{args.desc}，共 {count} 个条目。" if args.desc else f"共 {count} 个条目。"
    base_tag = f'<base href="{html.escape(args.base, quote=True)}">' if args.base else ""
    index = render_html(
        args.title,
        INDEX_BODY.replace("__TITLE__", html.escape(args.title))
        .replace("__DESC__", html.escape(desc))
        .replace("__CONTENT__", content_html),
        styles,
        base_tag=base_tag,
    )
    (out_dir / "index.html").write_text(index, encoding="utf-8")
    print(f"已构建 index.html（{len(articles)} 篇文章，{count} 个条目）")
    return 0
