---
name: doc-research
description: >-
  文献调研工作流——收集 PDF/EPUB 原文与网页并转换为 Markdown（raw/），对照原文校对、翻译整理为中文（tr/），
  渲染为 HTML 报告（dist/）。Use when doing research/investigation that involves collecting papers,
  books or web articles, converting PDF/EPUB/HTML to markdown, organizing source material with
  extracted figures, translating documents into Chinese, proofreading against the original,
  or building Chinese HTML reading reports from markdown.
---

# 文献调研：收集、整理、报告

围绕一份文献的调研流程分三步：**收集**（本地 PDF/EPUB 原文或网页转换为 Markdown 底稿与图片，
存入 `raw/`，并记录来源链接）、**整理**（对照原文逐段校对，翻译为中文，写入 `tr/`）、
**报告**（`tr/` 渲染为 HTML 站点，写入 `dist/`，并做格式检查）。

## 目录约定

```text
.
├── raw/
│   └── <slug>/
│       ├── raw.md          # 转换脚本的原始输出，不做任何修改
│       └── images/         # 脚本裁剪的原始图片，不应修改
│           ├── figure-0001.png
│           └── ...
└── tr/
    └── <slug>.md           # 校对/翻译结果，文件名沿用 raw/ 子目录名

dist/                       # doc-research build 产物（HTML 站点），不手工修改
```

`<slug>` 命名为 `<短名>-<年份>`，如 `kafka-2011`。脚本重跑时会覆盖 `raw.md` 和 `images/`，
但不会触碰 `tr/` 下的译文。

## 1. 前置检查

本 skill 假设 `doc-research` 已安装、当前项目已初始化。开始前先检查：

```bash
command -v doc-research   # CLI 可用
doc-research check        # 项目已初始化（.env 凭据 + .venv 依赖）
```

任一不满足时**停止操作并向用户报错**，不要代为安装；提示用户先执行：

```bash
uv tool install <skill目录>      # 或 pipx install <skill目录>
doc-research init                # 在项目根目录执行，交互式填写凭据
```

## 2. 收集：转 Markdown 底稿

### 本地文档（PDF、EPUB）

用 `doc-research parse`（阿里云 DocMind）转换**本地**文档：

```bash
doc-research parse /path/to/kafka-2011.pdf
```

结果为 `raw/kafka-2011/raw.md` 和 `raw/kafka-2011/images/figure-XXXX.png`。

### 网页（HTML）

用 `doc-research fetch` 抓取网页，提取正文转为 Markdown，正文图片下载到本地：

```bash
doc-research fetch <url>                    # slug 从 URL 推导
doc-research fetch <url> --slug kafka-notes # 或显式指定
```

结果为 `raw/<slug>/raw.md` 和 `raw/<slug>/images/image-XXXX.png`。
`raw.md` 首行以注释记录来源链接（`<!-- source: <url> -->`），后续报告据此注明出处。

转换结果有问题时在 `tr/` 译文中修正。

## 3. 整理：校对并翻译

校对翻译委派给子代理执行（fork context），主代理只抽查验收，问题反馈子代理修正。

以 `raw/<slug>/raw.md` 为底稿，对照原文逐段校对，将译文写入 `tr/<slug>.md`。
中文原著不需要翻译，但仍需对照原文校对，结果同样写入 `tr/<slug>.md`。
译文以 `../raw/<slug>/images/figure-XXXX.png`（网页来源为 `image-XXXX.png`）引用需要的图片。
网页来源的报告须在开头注明原文链接（取自 `raw.md` 首行的 `source` 注释）。

段落换行由翻译时手工控制：中文字符按 1.5 计、其余字符按 1 计，每行总宽度不超过 100。

### 术语

- 专业术语直接使用英文，除非中文译法已广泛使用（如"三模冗余""快照隔离"）。除缩写引入外，术语不以括注附另一种语言的译名。
- 缩写首次出现时须给出英文全名，写作"英文全名（缩写）"，之后直接使用缩写：

  > 从历史上看，队列代理限制了记录在队列中存储的 time-to-live（TTL）。

- 中文译法已广泛使用的术语，引入缩写时写作"中文译名（缩写）"，如"变更数据捕获（CDC）""物联网（IoT）"。
- 直接使用英文的术语示例：mercurial core、CEE、SDC、fail-stop、hyperscaler。
- 通行译法直接用中文，如 Kafka 的"主题""代理节点""消费者"。
- 代码中的类名和方法名保持不变。

### 名称不翻译

文档标题保留英文原名；正文中引用该书/论文名时同样使用英文原名（可保留《》等原有标点）。
例如标题写作 `# Kafka: a Distributed Messaging System for Log Processing`，
书名引用写作《Designing Data-Intensive Applications》。

### 图片

- 无语义的图片说明要补充完整，`![figure](../raw/kafka-2011/images/figure-0001.png)`
  改为 `![图 1：Kafka 架构](../raw/kafka-2011/images/figure-0001.png)`。
- 正文中的图号应能对应到图，如"Kafka 的整体架构如图 1 所示"对应 `图 1：Kafka 架构`。
- 每张图片除引用行 `![alt](url)` 外，**下方还须紧跟一行图注** `> 图 N：<完整描述>。`（blockquote 形式）。
  `alt` 渲染时不可见，图注才是图片正下方读者能看到的说明；`alt` 写简短图名，图注写完整描述，
  二者图号须一致：

  ```markdown
  ![图 1：一个用于存储网页的示例表切片](../raw/bigtable-2006/images/figure-0001.png)

  > 图 1：一个用于存储网页的示例表切片。行名是反转后的 URL。`contents` 列族保存页面内容，
  > `anchor` 列族保存所有指向该页面的锚文本……
  ```

- 原书中编号为 Figure 但实际内容是表格的，标注为 `表 X-Y` 而非 `图 X-Y`。
- 图片引用行 `![alt](url)` 的 alt 须保持单行，便于 git diff 逐行查看。

### 目录与交叉引用

- 书的目录（Table of Contents）应从点线加页码的形式改为指向标题的 Markdown 锚点链接：

  ```markdown
  **[第一部分 数据系统基础](#第一部分-数据系统基础)**

  1. **[第 1 章 数据系统架构中的权衡](#第-1-章-数据系统架构中的权衡)**
     - [事务处理系统与分析系统](#事务处理系统与分析系统)
  ```

  处理重名标题时，在目标标题前插入 `<a id="..."></a>` 锚点，目录链接指向该锚点：

  ```markdown
  - [小结](#chapter-1-summary)
  ```

  ```markdown
  <a id="chapter-1-summary"></a>
  ```

- 原书中的页码交叉引用（如"参见第 84 页的……"）在 Markdown 中没有意义，改为指向对应标题的锚点链接，或直接引用章节名：

  ```markdown
  参见[识别并确定组件大小模式](#识别并确定组件大小模式)。
  ```

### O'Reilly 书籍的校对要点

O'Reilly 图书（如 DDIA）的"提示/注意/警告"小图标会在正文中反复出现（DocMind 可能将其识别为重复的图片），
应统一转换为 GitHub 风格告警块：

```markdown
> [!NOTE]
> **术语：前端与后端**
>
> ...
```

- `> [!TIP]` — 提示
- `> [!NOTE]` — 注意/说明
- `> [!WARNING]` — 警告

### 导出 PDF 页面图片核对

校对公式、图表细节时，把本地 PDF 对应页导出为图片直接查看：

1. 确定页码偏移：扫描版 PDF 没有文本层，且 PDF 页索引与书页码存在固定偏移（前置页所致）。
   先用一个已知地标确定偏移量，例如某公式在书页 13、在 PDF 第 32 页（0 基索引 31），偏移即 +18；
   之后「0 基页索引 = 书页码 + 偏移 - 1」。不知道书页码时，可按译文行号占全文的比例估算大致范围，
   再用第 3 步的拼图快速扫页定位。
2. 用 pymupdf 导出整页或裁剪局部：

   ```bash
   .venv/bin/python - <<'EOF'
   import fitz
   doc = fitz.open("/path/to/book.pdf")
   page = doc[31]  # 0 基页索引
   page.get_pixmap(dpi=100).save("/tmp/page.png")  # 整页
   r = page.rect
   clip = fitz.Rect(r.width*0.25, r.height*0.55, r.width*0.85, r.height*0.80)
   page.get_pixmap(dpi=200, clip=clip).save("/tmp/crop.png")  # 局部放大
   EOF
   ```

3. 连续扫页时用 ImageMagick 拼图（每行 4 页，两行 8 页一屏）：

   ```bash
   convert p030.png p031.png p032.png p033.png +append row1.png
   convert p034.png p035.png p036.png p037.png +append row2.png
   convert row1.png row2.png -append montage.png
   ```

核对时先用整页图确认章节位置，再用 200 dpi 裁剪图逐项核对上下标、分数线和符号方向。

## 4. 报告：构建 HTML

```bash
doc-research build   # tr/*.md → dist/（含 index.html，引用图片复制到 dist/raw/）
```

要改内容就改 `tr/` 后重新构建。
首页按 slug 尾缀年份倒序列出各篇报告；网页来源（`raw.md` 首行有 `source` 注释）的条目带「原文 ↗」链接。

## 5. 检查改动

```bash
git diff --check
git diff
```
