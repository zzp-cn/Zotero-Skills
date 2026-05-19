---
name: zotero-backup
description: Zotero 数据库自动备份——每日自动备份，手动备份，备份状态查询，保留最近3份
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<!-- Copyright (c) 2026 Chokpun -->

# Zotero 数据库备份

## 用户对话示例

用户通过以下方式触发本工作流：

| 功能 | 用户对话示例 |
|------|-------------|
| 手动备份 | "备份一下 Zotero 数据库" |
| 查看状态 | "查看当前备份状态" |

## 自动备份

每次提交 prompt 时自动检查备份（通过 `.claude/settings.local.json` 的 `UserPromptSubmit` hook 触发）：
- 同一天已备份过则跳过
- 备份文件保存至 `$ZOTERO_DATA_DIR/zotero_backups/`
- 保留最近 **3 份**备份，超出自动清理最旧的

## 工具脚本

`tools/backup_zotero_db.py`

## 手动操作

### 执行备份

```bash
python3 tools/backup_zotero_db.py
```

### 查看备份状态

```bash
python3 tools/backup_zotero_db.py --status
```

### 指定保留份数

```bash
python3 tools/backup_zotero_db.py --keep 3
```

## 备份文件

- 命名格式：`zotero_YYYYMMDD_HHMMSS.bak`
- 存储在 `$ZOTERO_DATA_DIR/zotero_backups/`
- 可手动恢复：停止 Zotero → 复制备份覆盖 `zotero.sqlite` → 重启 Zotero

## License

This project is licensed under the GNU Affero General Public License v3.0.
See the [LICENSE](../../LICENSE) file for details.
