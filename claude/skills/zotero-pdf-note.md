---
name: zotero-pdf-note
description: Zotero 文献处理全流程——检索未处理条目 → 读取 PDF/Abstract → 用户选择笔记类型（简单总结/详细总结/全文翻译）→ 生成对应内容 → 写入 Zotero 条目笔记 → 进度标记
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<!-- Copyright (c) 2026 Chokpun -->

# Zotero 全流程工作流

## 用户对话示例

用户通过以下方式触发本工作流（`{{文献标题或关键词}}` 由用户替换为具体文献信息）：

| 功能 | 用户对话示例 |
|------|-------------|
| 简单总结 | "帮我对 `{{文献标题或关键词}}` 做一个简单总结" |
| 详细总结 | "给 `{{文献标题或关键词}}` 做一个详细总结" |
| 全文翻译 | "帮我把 `{{文献标题或关键词}}` 全文翻译成中文" |
| 批量处理 | "把最近一周添加的文献全部做详细总结" |

## 项目文件结构

| 文件 | 用途 |
|------|------|
| `tools/zotero_utils.py` | 核心工具库——数据库连接、PDF 路径查找、元数据查询、note 创建、增量标记 |
| `tools/create_notes.py` | 批量创建详细总结笔记的模板脚本（需要每次重写 `generate_summary()`） |
| `tools/create_note_from_text.py` | 通用笔记写入脚本——将文本内容创建/更新为 Zotero 条目笔记 |
| `tools/zotero_item_manager.py` | 条目删除状态检查与管理工具 |
| `CLAUDE.md` | Zotero Item Key 格式规则见该文件末尾 |

## 工作流步骤

### Step 1：查询待处理文献

使用 `zotero_utils.find_items_without_notes()` 查找没有笔记的文献条目（默认增量模式）。

```python
from zotero_utils import get_connection, find_items_without_notes, get_pdf_path, get_item_metadata

conn = get_connection()
cursor = conn.cursor()
items = find_items_without_notes(cursor)  # 默认增量
# 或全量: find_items_without_notes(cursor, since='all')
```

### Step 2：读取文献内容

```python
for item in items:
    meta = get_item_metadata(cursor, item['itemID'])
    pdf = get_pdf_path(cursor, item['itemID'])
    # 读取 PDF 全文或使用 abstract
```

**PDF 提取**: 使用 `pymupdf` (fitz) 提取全文：

```python
import fitz
doc = fitz.open(pdf_path)
text = ""
for page in doc:
    text += page.get_text()
doc.close()
```

### Step 3：询问用户笔记类型

向用户展示待处理文献列表，询问需要生成哪种笔记：

- **简单总结** — 高度概括，不要求保留所有章节层级（中英文均可）
- **详细总结** — 保留全文框架，压缩章节内容，章节编号不可省略（中英文均可）
- **全文翻译** — 逐句翻译，保留原文结构，参考文献默认不翻译

用户确认后，根据所选类型读取 PDF 全文或 abstract 并生成对应内容。

#### 全文翻译的语言检测

当用户选择**全文翻译**时，必须调用 `is_chinese_paper()` 判断文献语言：

```python
from zotero_utils import is_chinese_paper, get_pdf_path, get_item_metadata

text = extract_pdf_text(pdf_path)  # 先提取全文
if is_chinese_paper(text):  # 中文字符占比 >= 30%
    print("⚠️  该文献为中文文献，跳过全文翻译。")
    # 可询问用户是否改为生成简单总结或详细总结
else:
    # 正常执行全文翻译
```

- 阈值 30% 经过实测验证，能清晰区分纯中文论文（>60%）和含中文引用的英文论文（<10%）
- 简单总结和详细总结不区分中英文，不受此限制
- `is_chinese_paper()` 函数定义在 `tools/zotero_utils.py` 中

### Step 4：写入 Zotero 笔记

所有笔记内容使用标准 HTML 标签（`<h1>` `<h2>` `<h3>` `<p>` `<strong>` 等），**不需要手动添加 Zotero 外层包装**。

**方式 A——使用 `create_note_from_text.py`（推荐）：**

```bash
# 从文件读取内容创建笔记
python3 tools/create_note_from_text.py <父条目ID> \
    --title "（任务类型）文献标题中文翻译" \
    --content-file note_content.html

# 已有同名笔记则更新
python3 tools/create_note_from_text.py <父条目ID> \
    --title "（任务类型）文献标题中文翻译" \
    --content-file note_content.html --update

# 预览模式
python3 tools/create_note_from_text.py <父条目ID> \
    --title "xxx" --content "<p>内容</p>" --dry-run
```

**方式 B——代码中调用 `create_note()`：**

```python
from zotero_utils import create_note
note_id = create_note(cursor, parent_item_id, title, note_html)
# 注意: note_html 是内层 HTML，create_note 会自动添加 Zotero 外层包装
```

### Step 5：标记已处理

```python
from zotero_utils import mark_processed
mark_processed(item_ids)  # int 或 list of int
```

## 笔记标题规则

格式：`（任务定义）文献标题中文翻译`

示例：
- `（简单总结）连续碳酸盐沉淀法制备小粒径高密度碳酸钴及其生长机制研究`
- `（详细总结）硼诱导晶格稳定化实现超高镍NCM正极在高电压下的长循环`
- `（全文翻译）硼诱导晶格稳定化实现超高镍NCM正极在高电压下的长循环`

## 总结来源标注

所有笔记内容中必须标注来源：

```html
<p><strong>来源：PDF 全文</strong></p>
```
或
```html
<p><strong>来源：元数据 + Abstract</strong></p>
<p>本内容基于 Zotero 元数据和 abstract 生成，未读取 PDF 全文。</p>
```

## Zotero Note HTML 格式要点

- 内容使用标准 HTML 标签：`<h1>` `<h2>` `<h3>` `<p>` `<strong>` 等
- **不需要**手动加 `<div class="zotero-note znv1">` 包装——`create_note()` 和 `create_note_from_text.py` 会自动处理
- 不要使用 HTML 实体转义标签字符（不要写成 `&lt;h1&gt;`）

## Zotero Item Key 规则

- 8 字符，大写
- 字符集：`23456789ABCDEFGHIJKLMNPQRSTUVWXYZ`
- **排除** `0`、`1`、`O`（防视觉混淆）
- 正则：`^[A-Z2-9]{8}$`
- 详见 `CLAUDE.md` 中「Zotero Item Key 格式规则」

## 批量处理规则

1. 先处理 1–3 篇样本文献
2. 检查输出是否符合要求
3. 再继续批量处理
4. 每次报告：输入数量、成功数、失败数、失败原因、是否已写入笔记

## License

This project is licensed under the GNU Affero General Public License v3.0.
See the [LICENSE](../../LICENSE) file for details.
