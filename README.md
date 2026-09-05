# doc-research

文档处理 CLI：PDF/EPUB 转 Markdown（阿里云 DocMind）、网页正文提取、PDF 页面导出、Markdown 渲染 HTML 站点。

## 安装

```bash
uv tool install .      # 或 pipx install .
```

## 命令

```bash
doc-research parse <file> -o <dir>          # 本地 PDF/EPUB 转 raw.md + images/（DocMind）
doc-research fetch <url> -o <dir>           # 网页正文转 raw.md，图片下载到本地
doc-research export-page <pdf> <页索引> -o <img> [--dpi N] [--clip x0,y0,x1,y1]
doc-research build <md目录> -o <输出> [--title T] [--desc D] [--base U]
```

- `parse` 凭据读环境变量 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`，
  或当前目录的 `.env`；`-o` 省略时输出到 `./<文件名>`
- `fetch` 用 curl_cffi 模拟浏览器 TLS 指纹抓取；`raw.md` 首行记录 `<!-- source: <url> -->`；
  `-o` 省略时输出到 `./<从 URL 推导的名称>`
- `build` 把目录中的 Markdown 渲染为 HTML 站点：每篇一个 `<slug>.html`，外加生成的
  `index.html` 首页（源文件为目录下的 `index.md`，可选）

## Markdown 格式

全站只有一种文档协议：**每个 `.md` 都是一篇文章**，首页（`index.md`）也走同一套格式
（仅标题取值有一处例外，见「标题」一节）。

### 文件

- UTF-8 编码；文件名（去扩展名）即 slug，输出 `<slug>.html`
- `index.md` 是首页源文件，不作为文章列入条目；不存在时首页只有标题区

### YAML frontmatter（可选）

```markdown
---
tags: [分布式, 论文]
---
```

- 仅取 `tags`（字符串列表或单个标量），其它字段忽略；整块剥离不参与渲染
- YAML 语法错误会导致构建报错

### 标题

首个 `# H1` 为文章标题（用于页面标题与首页条目）；无 H1 时用文件名。
`index.md` 例外：首页标题由 `--title` 指定，其 H1 只作为正文内容渲染。

### 正文

- CommonMark + 表格 + 脚注 + `attr_list`
- 强调用 `*斜体*`、`**粗体**`；下划线 `_…_` 紧贴中文时不解析，**不要使用**
- 围栏代码块需显式标注语言（不自动猜测）
- 数学：行内 `\(...\)`、块级 `\[...\]`（MathJax 渲染）
- 嵌套列表按标记宽度识别（2/3 空格缩进不会被拉平）

### 锚点

- 标题自动生成保留中文的 slug（GitHub 风格，如 `#acid-的含义`）
- 用 `{#custom-id}` 自定义锚点；标题悬停可见 ¶ 永久链接
- 支持内联 HTML（如 `<a id="..."></a>`）

### 图片

`![alt](相对路径)`：构建时复制进输出目录，保持相对结构（去掉开头的 `../`），引用同步改写；
`http(s)`、`data:` 外链不动。`alt` 保持单行。

### 内链

站内互链写源文件相对链接，构建时改写为 `.html`：

```markdown
[设计数据密集型应用](ddia-2026.md)
[事务的隔离性](ddia-2026.md#事务)
```

目标文章不存在时构建会警告（不中断）。外链与 `#锚点` 链接原样保留。

### 首页条目

首页条目由 `index.md` **手动维护**：整个列表项就是一个指向文章的内链，即视为一个条目：

```markdown
## 文章

- [DDIA](ddia-2026.md)
- [Kafka 论文](kafka-2011.md)
```

构建时每个条目增强为条目行：年份（取自 slug 尾缀）、slug 链接、文章 H1 标题
（替换手写文字，以文章为准）、标签胶囊（取自文章 frontmatter）、置顶按钮；
首个条目前自动插入标签过滤栏。条目的顺序与取舍完全由手写决定，未列出的文章不上首页；
指向不存在文章的条目会警告并跳过。
