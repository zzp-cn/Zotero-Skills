> **推荐使用搭载于 Claude Code 的 DeepSeek 运行，DeepSeek 选择 flash 模型即可。**
>
> **注意：** 由于 GitHub 不支持上传隐藏文件夹，本仓库中的 `claude/` 文件夹复制到本地后，需重命名为 `.claude/` 才能被 Claude Code 正常读取。

## 推荐用法

### 场景一：首次使用 AI 管理 Zotero 文献库

1. 将本文件夹复制到你的电脑中，并重命名为 `Zotero-AI`
2. 根据 DeepSeek 官方文档下载并配置 Claude Code
3. 通过终端（macOS/Linux）或命令提示符（Windows）进入 `Zotero-AI` 目录
4. 在目录中运行 `claude` 即可直接使用

配置完成后，直接与 AI Agent 对话即可管理你的 Zotero 文献库。

### 场景二：已使用 AI Agent 管理 Zotero 文献库

1. 将 `CLAUDE.md` 中的项目规则内容整合到你已有的 `.md` 配置文件中
2. 将 `claude/settings.local.json` 中与 `/permissions` 相关的指令添加到你的配置文件中
3. 将 `tools/` 文件夹以及 `claude/skills/` 文件夹复制到你运行 AI Agent 的项目目录中

配置完成后，直接与 AI Agent 对话即可管理你的 Zotero 文献库。

---

# Zotero Skills — 文献处理工作流

Zotero 文献库自动化处理工具集：读取 PDF → 生成简单总结 / 详细总结 / 全文翻译 → 写入 Zotero 条目笔记。

## 功能与提示词

配置完成后，直接与 AI Agent 对话即可调用以下功能。提示词中的 `{{文献标题或关键词}}` 请替换为你要处理的具体文献信息。

### 笔记生成（核心功能）

#### 简单总结
对文献内容进行高度概括，提炼研究对象、方法、关键结果和主要结论。适合快速浏览。

**对话示例：**
> "帮我对 `{{文献标题或关键词}}` 做一个简单总结"
> "简单总结昨天导入的文献"

#### 详细总结
保留原文完整章节框架，对各节内容进行概括压缩。适合深入了解文献全貌。

**对话示例：**
> "给 `{{文献标题或关键词}}` 做一个详细总结"
> "详细总结 `{{文献标题或关键词}}`"

#### 全文翻译
将外文文献逐段翻译为中文，保留原文标题、章节、图表编号等结构（中文文献自动跳过）。

**对话示例：**
> "帮我把 `{{文献标题或关键词}}` 全文翻译成中文"
> "全文翻译最近导入的文献"

#### 批量笔记生成
一次性对多篇文献执行相同的笔记生成任务。

**对话示例：**
> "把最近一周添加的文献全部做详细总结"
> "对 `{{文献标题或关键词}}` 和 `{{文献标题或关键词}}` 生成简单总结"

---

### 文献检索与查询

按关键词搜索文献，查看条目类型、创建时间、附件和笔记数量等详细信息。

**对话示例：**
> "帮我查一下标题包含 `{{关键词}}` 的文献"
> "列出最近添加的文献"
> "搜索作者为 `{{作者名}}` 的条目"

---

### 条目管理

查看条目删除状态、彻底删除条目、恢复已删除条目。彻底删除时会同时清理数据库记录和关联的 PDF 文件。

**对话示例：**
> "查看 `{{文献标题或关键词}}` 的删除状态"
> "彻底删除 `{{文献标题或关键词}}`"
> "恢复刚刚删除的条目"

---

### 笔记管理

列出某篇文献下的所有笔记，查看笔记字数、创建时间，删除不需要的笔记。

**对话示例：**
> "列出 `{{文献标题或关键词}}` 下的所有笔记"
> "删除 `{{文献标题或关键词}}` 下多余的笔记"

---

### 笔记恢复

从 Zotero 数据库备份中恢复被误删的笔记，仅恢复那些父条目仍然可见的笔记。

**对话示例：**
> "恢复被误删的笔记"
> "从备份中恢复 `{{文献标题或关键词}}` 的笔记"

---

### 重复条目检测

按 DOI 或标题精确/模糊匹配，检测 Zotero 库中的重复文献条目。

**对话示例：**
> "检测库中的重复条目"
> "查找标题相似的重复文献"

---

### 数据库备份

备份 Zotero 数据库（`zotero.sqlite`），备份文件保存到指定目录并自动管理保留份数。

**对话示例：**
> "备份一下 Zotero 数据库"
> "查看当前备份状态"

---

### 磁盘空间统计

统计已删除条目和 syncCache 残留条目占用的磁盘空间。

**对话示例：**
> "统计已删除条目占用了多少空间"
> "查看可清理的磁盘空间"

---

### PDF 文本提取

从文献关联的 PDF 中提取全文文本，保存为本地文件供后续处理使用。

**对话示例：**
> "提取 `{{文献标题或关键词}}` 的 PDF 全文"
> "把最近文献的 PDF 文本都提取出来"

---

### 临时文件清理

清理项目运行过程中产生的临时脚本、PDF 提取文本、Python 缓存等中间文件。

**对话示例：**
> "清理一下临时文件"
> "清理所有临时文件和翻译缓存"

---

### 增量处理追踪

自动记录已处理的文献，下次只处理新增文献，避免重复。支持重置记录以重新全量处理。

**对话示例：**
> "重置处理记录，我要重新处理所有文献"

## 目录结构

```
Zotero-Skills-Release/
├── CLAUDE.md                    # Claude Code 项目规则（核心文档）
├── claude/
│   ├── settings.local.json      # 权限配置模板
│   └── skills/
│       ├── zotero-pdf-note.md         # 笔记生成工作流 skill
│       ├── zotero-item-manager.md     # 条目删除管理 skill
│       ├── zotero-note-cleanup.md     # 笔记清理 skill
│       └── zotero-backup.md           # 数据库备份 skill
├── tools/
│   ├── zotero_utils.py                 # 核心工具库（数据库连接、PDF 路径、增量追踪）
│   ├── create_note_from_text.py        # 通用笔记写入脚本
│   ├── create_notes.py                 # 批量笔记模板
│   ├── save_extracted_texts.py         # PDF 文本提取与保存
│   ├── zotero_item_manager.py          # 条目删除状态管理
│   ├── find_duplicates.py              # 重复条目检测
│   ├── backup_zotero_db.py             # 数据库备份
│   ├── restore_notes.py                # 笔记恢复
│   ├── note_cleanup.py                 # 笔记列表与删除
│   ├── calc_dup_space.py               # 磁盘空间统计
│   └── cleanup.py                      # 临时文件清理
└── tmp/                            # 中间文件目录（自动生成）
```

## 环境要求

- Python 3.8+
- PyMuPDF（`pip install pymupdf`）
- 本地 Zotero 客户端
- Claude Code（推荐）或其他 AI 辅助工具

## 配置步骤

### 1. 设置 Zotero 路径

根据你的操作系统和 Zotero 安装路径，配置以下环境变量：

```bash
# Zotero 数据目录（含 zotero.sqlite 和 storage/ 的目录）
export ZOTERO_DATA_DIR=/path/to/your/Zotero

# Zotero 配置文件目录
# macOS: ~/Library/Application Support/Zotero
# Linux: ~/.zotero
# Windows: %APPDATA%/Zotero
export ZOTERO_PROFILE_DIR=/path/to/Zotero/profile
```

Claude Code 用户可写入 `claude/settings.json`（复制后需重命名为 `.claude/settings.json`）的 `env` 字段或项目根目录的 `.env` 文件。

### 2. 配置 Claude Code（可选）

`claude/settings.local.json`（复制后重命名为 `.claude/settings.local.json`）为权限规则模板，与用户自行创建的 `.claude/settings.json`（API Key / 模型配置）可并存使用。如使用其他 AI 工具，需确保工具具有：

- 对 `zotero.sqlite` 的**只读**查询权限
- 对 `tools/` 目录脚本的执行权限
- 对 `tmp/`、`translations/` 目录的读写权限

### 3. 安装 Python 依赖

```bash
pip install pymupdf
```

## 使用方式

### 通过 Claude Code（推荐）

将 `CLAUDE.md` 和 `claude/` 目录（复制后重命名为 `.claude/`）放入项目根目录，Claude Code 会自动加载配置。启动后即可：

1. 搜索需要处理的文献
2. 选择笔记类型（简单总结 / 详细总结 / 全文翻译）
3. 确认后自动写入 Zotero 条目笔记

### 直接使用脚本

```bash
# 查看条目删除状态
python3 tools/zotero_item_manager.py list <itemID>

# 写入笔记
python3 tools/create_note_from_text.py <条目ID> \
    --title "笔记标题" \
    --content-file content.html

# 清理临时文件
python3 tools/cleanup.py --dry-run --all   # 预览
python3 tools/cleanup.py --all             # 执行清理
```

## 注意事项

- **Zotero 数据库默认为只读**，写入笔记通过 Zotero 标准接口
- 删除条目时需同时清理 `syncCache`，否则 Zotero 会自动重建
- PDF 文本提取优先使用 PyMuPDF（fitz）
- 批量操作前建议先测试 1–3 篇样本文献

## 原作者

Chokpun · 基于搭载在 Claude Code 的 DeepSeek 生成

## License

This project is licensed under the GNU Affero General Public License v3.0.
See the [LICENSE](LICENSE) file for details.
