---
name: zotero-note-cleanup
description: Zotero 条目笔记去重与清理——列出条目下所有笔记的创建时间、修改时间、字符数，由用户决定保留/删除条件，再执行清理
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<!-- Copyright (c) 2026 Chokpun -->

# Zotero 笔记去重与清理

## 用户对话示例

用户通过以下方式触发本工作流（`{{文献标题或关键词}}` 由用户替换为具体文献信息）：

| 功能 | 用户对话示例 |
|------|-------------|
| 列出笔记 | "列出 `{{文献标题或关键词}}` 下的所有笔记" |
| 删除笔记 | "删除 `{{文献标题或关键词}}` 下多余的笔记" |

## 快速命令

```bash
# 列出条目下所有笔记
python3 tools/note_cleanup.py list <条目ID>

# 删除指定笔记
python3 tools/note_cleanup.py delete <笔记ID> [笔记ID ...]

# 清理临时文件
python3 tools/cleanup.py --dry-run --all   # 预览
python3 tools/cleanup.py --all             # 执行
```

## 工作流

### Step 1：列出条目下所有笔记

```bash
python3 tools/note_cleanup.py list <条目ID>
```

输出示例：
```
条目 [父条目ID] 下的笔记：
    ID  创建时间                修改时间                字符数  标题
  ─────────────────────────────────────────────────────────────────
   100  2026-01-15 10:30:00  2026-01-15 10:30:00   1164  （简单总结）...
   101  2026-01-20 14:——:——  2026-01-20 14:——:——  18926  （全文翻译）...
```

### Step 2：向用户展示信息

展示笔记 ID、标题、创建时间、修改时间、字符数。

### Step 3：询问用户删除条件

例如：
- "保留最早创建的那个，删除其他的"
- "保留字符数最多的那个"
- "保留简单总结，删除其他全文翻译"
- "每个类型只保留一篇，多余的删掉"
- 或直接指定要删除的 itemID

### Step 4：执行删除

```bash
python3 tools/note_cleanup.py delete <笔记ID> [笔记ID ...]
```

## License

This project is licensed under the GNU Affero General Public License v3.0.
See the [LICENSE](../../LICENSE) file for details.
