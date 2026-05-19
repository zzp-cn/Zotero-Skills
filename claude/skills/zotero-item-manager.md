---
name: zotero-item-manager
description: Zotero 条目删除状态检查与管理——查看条目详情（含创建时间、附件数、笔记数）、真正删除条目、恢复条目
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<!-- Copyright (c) 2026 Chokpun -->

# Zotero 条目管理器

## 用户对话示例

用户通过以下方式触发本工作流（`{{文献标题或关键词}}` 由用户替换为具体文献信息）：

| 功能 | 用户对话示例 |
|------|-------------|
| 查看状态 | "查看 `{{文献标题或关键词}}` 的删除状态" |
| 彻底删除 | "彻底删除 `{{文献标题或关键词}}`" |
| 恢复条目 | "恢复这个已删除条目" |

## 工具脚本

`tools/zotero_item_manager.py`

## 工作流

### Step 1：列出条目详细信息

按关键词搜索并显示每个条目的创建时间、修改时间、附件数量、笔记数量：

```bash
python3 tools/zotero_item_manager.py list-all <关键词>
```

或指定具体 itemID：

```bash
python3 tools/zotero_item_manager.py list <itemID> [itemID ...]
```

输出包括：ItemID、Key、类型、状态、创建时间、附件数、笔记数、标题。

### Step 2：用户指定删除条件

例如：
- "删除 240 和 279，保留 176"
- "删除所有名义删除的条目"
- "删除没有附件也没有笔记的条目"

### Step 3：执行删除

```bash
python3 tools/zotero_item_manager.py delete <itemID> [itemID ...]
```

会同时清理：
- `items` 表
- `syncCache` 表（防止 Zotero 自动重建）
- 关联的 PDF 物理文件

### Step 4：恢复条目

```bash
python3 tools/zotero_item_manager.py restore <itemID>
```

清除 `deletedItems` 标记，使条目在 Zotero UI 重新可见。

## 全盘扫描

仅在用户明确要求时执行：

```bash
python3 tools/zotero_item_manager.py audit
python3 tools/zotero_item_manager.py cleanup
```

## 删除状态说明

| 状态 | 含义 |
|------|------|
| 正常 | 在 items 表，不在 deletedItems，UI 可见 |
| 名义删除 | 在 items 表，也在 deletedItems，UI 不可见 |
| 缓存残留 | 不在 items 表，但在 syncCache 中，会被自动重建 |
| 彻底删除 | items 和 syncCache 均已清理，不会重建 |

## License

This project is licensed under the GNU Affero General Public License v3.0.
See the [LICENSE](../../LICENSE) file for details.
