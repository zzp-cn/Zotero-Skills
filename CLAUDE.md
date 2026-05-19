# CLAUDE.md

## 项目定位

本项目主要用于处理 Zotero 文献库中的文献条目、PDF、摘要、全文总结、全文翻译和条目笔记生成。

默认工作对象包括：

- Zotero 文献条目；
- Zotero 条目元数据；
- Zotero 条目的 abstract；
- Zotero 条目关联的 PDF；
- 从 PDF 中提取出的正文文本；
- 生成并写入 Zotero 的条目笔记。

除非用户明确要求，不要修改原始 PDF、原始附件文件、Zotero 数据库文件或已有重要笔记内容。

---

## 语言要求

- 默认使用中文进行解释、总结、翻译、注释和文档编写。
- 只有在用户明确要求英文时，才使用英文。
- 输出应保持严谨、清晰、结构化，避免无关内容和模糊表述。
- 不要把总结、翻译或分析内容写成空泛评价，应基于文献实际内容。

---

## Zotero 路径信息

本项目使用的 Zotero 数据目录绝对路径为：

```text
${ZOTERO_DATA_DIR}

```md
除非用户明确授权，`${ZOTERO_DATA_DIR}/zotero.sqlite` 默认只读，不得直接执行写入型 SQL。

所有 Zotero SQLite 查询必须使用 `sqlite3 -readonly ${ZOTERO_DATA_DIR}/zotero.sqlite ...`。禁止使用普通 `sqlite3 ${ZOTERO_DATA_DIR}/zotero.sqlite ...` 访问 Zotero 数据库。

Zotero 笔记写入原则上仅使用本地 Zotero SQLite 数据库和本地 PDF 文件，无需 Zotero API。不使用 macOS Keychain 或第三方 API 服务。

## Zotero 条目关系定义

在 Zotero 中：

- PDF 附件条目不是最终保存笔记的位置；
- PDF 附件对应的上级条目，指的是该 PDF 所属的文献条目；
- Zotero 的 collection / 分类不属于“上级条目”；
- 生成的总结或翻译笔记应保存到 PDF 附件所属的文献条目下。

因此，当根据某个 PDF 生成笔记时，应先识别该 PDF 附件对应的文献条目，再把生成内容保存为该文献条目下的子笔记。

---

## Zotero 数据安全规则

### 默认只读对象

以下内容默认视为只读：

- Zotero 原始 PDF；
- Zotero SQLite 数据库；
- Zotero 原始附件目录；
- Zotero 条目原始元数据；
- 用户未明确授权修改的已有笔记。

### 禁止行为

除非用户明确授权并确认影响范围，不要执行：

- 删除 Zotero PDF；
- 删除 Zotero 条目；
- 删除 Zotero 笔记；
- 直接修改 `zotero.sqlite`；
- 批量覆盖已有条目笔记；
- 批量删除 summary / translation / note 文件；
- 对 Zotero 数据库执行 `UPDATE`、`DELETE`、`INSERT`、`DROP`、`ALTER` 等写入型 SQL。

### 写入 Zotero 条目笔记的原则

当用户要求生成“简单总结”“详细总结”或“全文翻译”时，最终内容应保存为对应文献条目下的 Zotero 条目笔记。

保存位置要求：

- 笔记应保存至 PDF 附件对应的文献条目下；
- 不应保存到 PDF 附件条目本身；
- 不应保存到 Zotero collection / 分类下；
- 不应只保存为孤立的本地 Markdown 文件，除非用户要求先生成本地预览；
- 如需先生成本地预览文件，应在用户确认后再写入 Zotero 条目笔记。

写入前应尽量确认：

- 目标 PDF 附件；
- PDF 附件对应的文献条目；
- 将创建还是更新笔记；
- 笔记标题；
- 是否会覆盖已有同名笔记；
- 本次处理的文献数量。

---

## 笔记标题规则

生成的 Zotero 笔记标题统一采用：

```text
（任务定义）文献标题中文翻译
```

其中：

- 任务定义包括：`简单总结`、`详细总结`、`全文翻译`；
- 文献标题中文翻译应根据原文标题准确翻译；
- 标题中不需要额外添加 DOI、年份、作者等信息，除非用户明确要求。

示例：

```text
（全文翻译）连续碳酸盐沉淀法制备小粒径高密度碳酸钴及其生长机制研究
```

```text
（详细总结）连续碳酸盐沉淀法制备小粒径高密度碳酸钴及其生长机制研究
```

```text
（简单总结）连续碳酸盐沉淀法制备小粒径高密度碳酸钴及其生长机制研究
```

---

## 三类任务定义

### 1. 简单总结

“简单总结”是指：

- 以较少字数高度概括全文内容；
- 不要求完整保留全文所有章节层级；
- 重点提炼研究对象、研究方法、关键结果、主要结论和与本项目相关的信息；
- 适合作为快速浏览用条目笔记。

简单总结不等于只总结 abstract。

如果 PDF 可用，应优先基于 PDF 全文内容总结；如果只能基于标题、元数据和 abstract，应明确标注总结来源。

---

### 2. 详细总结

“详细总结”是指：

- 在保留全文原始框架的条件下进行内容概括；
- 原文中的章节编号和层级结构不可省略；
- 包括但不限于 `1`、`1.1`、`2.1.3`、`3.1.4.2` 等所有可识别章节框架；
- 每个章节标题和编号都应保留；
- 每个章节内部内容可以进行概括总结；
- 不应把多个原文章节随意合并；
- 不应省略原文已有的小节层级。

详细总结的核心要求是：

```text
保留全文框架，压缩章节内容。
```

---

### 3. 全文翻译

“全文翻译”是指：

- 对全文内容逐字逐句翻译；
- 不是总结；
- 不是概括；
- 不应压缩原文内容；
- 不应省略正文段落；
- 原文中的标题、章节、小节、图表标题、表格标题、正文段落均应翻译；
- 参考文献部分默认不翻译，除非用户明确要求；
- 公式、单位、变量名、化学式、材料名称、图表编号应保持准确。

#### 语言检测

执行全文翻译前，必须先判断文献是否为中文文献：

- 使用 `zotero_utils.is_chinese_paper(text)` 检测中文字符占比
- 中文字符占比 >= **30%** 判定为中文文献
- 中文文献直接跳过全文翻译，并向用户说明原因
  - 例："该文献为中文文献，跳过全文翻译。"
- 外文文献正常执行全文翻译
- 英文文献中夹杂的中文参考文献引用（作者名、机构名等通常占比 < 10%）不影响判定
- 简单总结和详细总结不受此限制，中英文文献均可执行

全文翻译应尽量保留原文结构，包括：

- 标题；
- 摘要；
- 关键词；
- 一级标题；
- 二级标题；
- 三级及更低级标题；
- 图注；
- 表注；
- 正文段落。

---

## 总结来源标注

每一份生成内容都应标注来源类型，避免混淆。

可使用以下标记：

```text
来源：元数据 + Abstract
来源：PDF 全文
来源：PDF 全文 + 图表信息
来源：用户提供文本
```

如果没有读取 PDF 正文，只基于 Zotero 元数据和 abstract 生成，应明确写：

```text
本内容基于 Zotero 元数据和 abstract 生成，未读取 PDF 全文。
```

如果读取了 PDF 全文，应明确写：

```text
本内容基于 PDF 全文生成。
```

---

## 批量处理规则

批量处理文献时，应优先采用分批策略：

- 先处理 1–3 篇样本文献；
- 检查输出是否符合用户要求；
- 再继续批量处理；
- 不要一次性对大量 PDF 执行不可逆写入操作。

每次批量处理后应报告：

- 输入文献数量；
- 成功处理数量；
- 失败数量；
- 失败原因；
- 是否已写入 Zotero 文献条目笔记；
- 是否仅生成了本地预览文件。

---

## 文件与路径规则

- 使用绝对路径处理 Zotero 目录时，应明确说明读取路径和输出路径。
- 搜索 Zotero 相关文件时，应限制在 `${ZOTERO_DATA_DIR}` 或 `${ZOTERO_PROFILE_DIR}` 目录内，例如：
  - `find "${ZOTERO_DATA_DIR}" -maxdepth 5 -name "prefs.js" 2>/dev/null | head -5`
  - `find "${ZOTERO_PROFILE_DIR}" -maxdepth 5 -name "prefs.js" 2>/dev/null | head -5`
  禁止搜索系统全局范围或 macOS Keychain。
- 生成的中间文件应保存到当前项目目录下的 `output/`、`tmp/`、`summaries/` 或 `translations/` 中。
- 不要覆盖原始 PDF。
- 不要覆盖已有重要结果文件。
- 如果要覆盖已有同名输出文件，应先说明并请求确认。

---

## Python 脚本规则

- 默认使用 Python。
- 路径处理优先使用 `pathlib.Path`。
- 批处理脚本应支持命令行参数，例如：

```bash
python3 script.py --input INPUT --output OUTPUT --mode detailed
```

- 脚本应尽量区分：
  - metadata-only summary；
  - abstract-level summary；
  - PDF fulltext summary；
  - full translation。

- 对 PDF 解析失败的文献，应记录失败原因，不要静默跳过。
- 写入 Zotero 笔记时，应定位 PDF 附件对应的文献条目，而不是附件条目本身。

---

## Python 命令规则

- 不要使用很长的多行 `python3 -c` 执行复杂逻辑。
- 如果 Python 代码超过 5 行，应写入当前项目的 `tmp/scripts/` 或 `tools/` 目录为 `.py` 脚本，再运行脚本。
- 读取、检查、提取文本类脚本可以放在 `tmp/scripts/`；真正写入 Zotero 笔记的脚本必须单独请求确认。

---

## Zotero 条目删除与恢复规则

由于 Zotero 存在 `syncCache` 机制，直接 SQL 删除 items 表中的条目会被自动重建。

### 真正删除条目的必要条件

必须同时清理：

1. `items` 表 — 条目主数据
2. `syncCache` 表（`DELETE FROM syncCache WHERE key = '<ITEM_KEY>'`）— 防止自动重建
3. 关联的物理 PDF 文件（`${ZOTERO_DATA_DIR}/storage/<ATTACHMENT_KEY>/`）

### 删除状态分类

正常：items 存在、deletedItems 不存在 → UI 可见
名义删除：items 存在、deletedItems 存在 → UI 不可见
缓存残留：items 不存在、syncCache 存在 → 会被自动重建
彻底删除：items 不存在、syncCache 已清理 → 不会再出现

### 管理工具

`tools/zotero_item_manager.py` 提供统一管理：

- `list <itemID>` — 查看指定条目删除状态（处理单条目时用这个）
- `list-all <关键词>` — 搜索后查看多条目的删除状态
- `delete <itemID>` — 真正删除条目（含 syncCache + 物理文件）
- `restore <itemID>` — 恢复条目（清除 deletedItems 标记）
- `audit` — 仅当用户明确要求全盘扫描时才使用
- `cleanup` — 仅当用户明确要求全盘整理时才使用
- `purge-cache` — 仅当用户明确要求时使用

使用规则：
- 处理具体条目（如写入笔记、查询信息）前，用 `list <itemID>` 检查该条目是否在 `deletedItems` 中，不在才继续操作。
- `audit` / `cleanup` / `purge-cache` 只在用户主动要求进行时才执行，不主动触发。
- `delete` 命令需逐条确认。

---

## 权限与确认规则

执行以下操作前必须明确说明影响范围并等待用户确认：

- 删除文件；
- 覆盖文件；
- 写入 Zotero 条目笔记；
- 修改 Zotero 数据库；
- 批量创建或更新笔记；
- 安装 Python 包；
- 运行会批量处理 PDF 或批量写文件的脚本。

以下操作可以视为低风险：

- 查询当前路径；
- 检查 Python 版本；
- 检查 Python 包是否安装；
- 读取 PDF 文本；
- 读取 Zotero 元数据；
- 读取临时 JSON / Markdown / HTML 文件；
- 生成本地预览文件。

---

## 工作流程建议

### 简单总结

```text
读取文献元数据 → 读取 PDF 全文或 abstract → 生成短总结 → 保存为 PDF 附件对应文献条目下的 Zotero 笔记
```

### 详细总结

```text
读取 PDF 全文 → 识别原文章节框架 → 保留所有章节编号 → 概括各节内容 → 保存为 PDF 附件对应文献条目下的 Zotero 笔记
```

### 全文翻译

```text
读取 PDF 全文 → 按原文顺序逐段翻译 → 保留章节结构 → 参考文献默认不翻译 → 保存为 PDF 附件对应文献条目下的 Zotero 笔记
```

### 任务后清理

每次笔记写入完成后执行两步：

```bash
python3 tools/cleanup.py --dry-run --all   # 预览
python3 tools/cleanup.py --all             # 确认后清理
```

清理 `tmp/` 中的中间文件以及笔记已写入的翻译文件（`translations/`），保留目录结构。

---

## Zotero Item Key 格式规则

- 长度：**8 个字符**，**仅大写**
- 字符集：`23456789ABCDEFGHIJKLMNPQRSTUVWXYZ`
- 排除字符：`0`（数字零）、`1`（数字一）、`O`（字母 O）——因视觉混淆
- 注意：`I`（字母 I）**是允许的**
- 正则：`^[A-Z2-9]{8}$` 或 `^[23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]{8}$`
- 生成：`random.choices("23456789ABCDEFGHIJKLMNPQRSTUVWXYZ", k=8)`
