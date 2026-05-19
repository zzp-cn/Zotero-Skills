#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
Zotero 数据库备份工具。

用法：
  python3 tools/backup_zotero_db.py              # 执行备份
  python3 tools/backup_zotero_db.py --status     # 仅查看备份状态，不备份
  python3 tools/backup_zotero_db.py --keep 7     # 保留最近 7 份备份（默认 14）

备份文件保存到 $ZOTERO_DATA_DIR/zotero_backups/，按时间戳命名。
"""
import shutil
import sqlite3
import os
import sys
import re
import time
from pathlib import Path
from datetime import datetime

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")
BACKUP_DIR = ZOTERO_DATA_DIR / "zotero_backups"
MAX_KEEP = 3


def get_db_size():
    """获取当前数据库大小"""
    try:
        return os.path.getsize(DB_PATH)
    except OSError:
        return 0


def count_items(db_path):
    """获取条目总数"""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items")
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return None


def get_db_stats(db_path):
    """获取数据库详细统计（仅统计正常可见条目，排除回收站中的）。"""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items WHERE NOT EXISTS (SELECT 1 FROM deletedItems WHERE itemID = items.itemID)")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM items WHERE itemTypeID = 3 AND NOT EXISTS (SELECT 1 FROM deletedItems WHERE itemID = items.itemID)")
        attachments = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM items WHERE itemTypeID = 28 AND NOT EXISTS (SELECT 1 FROM deletedItems WHERE itemID = items.itemID)")
        notes = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM items WHERE itemTypeID NOT IN (1,2,3,28) AND NOT EXISTS (SELECT 1 FROM deletedItems WHERE itemID = items.itemID)")
        items = c.fetchone()[0]
        conn.close()
        return items, attachments, notes, total
    except Exception:
        return None, None, None, None


def list_backups():
    """列出所有备份文件"""
    if not BACKUP_DIR.exists():
        return []
    backups = []
    for f in sorted(BACKUP_DIR.iterdir()):
        if f.name.endswith(".bak") and f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            size = f.stat().st_size
            backups.append((f.name, mtime, size))
    return backups


def format_size(n):
    if n >= 1e9:
        return f"{n/1e9:.2f} GB"
    elif n >= 1e6:
        return f"{n/1e6:.2f} MB"
    elif n >= 1e3:
        return f"{n/1e3:.2f} KB"
    return f"{n} B"


def do_backup():
    """执行备份（如果今天已备份过则跳过）"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # 检查今日是否已备份
    today = datetime.now().strftime("%Y%m%d")
    backups = list_backups()
    for name, _, _ in backups:
        if name.startswith(f"zotero_{today}"):
            print(f"⏭️  今日已备份 ({name[:17]}...)，跳过")
            print(f"   备份目录: {BACKUP_DIR}")
            print(f"   最新: {name}")
            # 显示当前数据库状态
            items, attachments, notes, total = get_db_stats(DB_PATH)
            if total is not None:
                db_size = get_db_size()
                print(f"   当前数据库: {format_size(db_size)}")
                print(f"   条目总数:   {total}")
                print(f"   ├─ 文献条目: {items}")
                print(f"   ├─ 附件:     {attachments}")
                print(f"   └─ 笔记:     {notes}")
            return True

    # 获取当前数据库状态
    db_size = get_db_size()
    items, attachments, notes, total = get_db_stats(DB_PATH)

    if db_size == 0:
        print("❌ 错误: 数据库文件不存在或无法访问")
        return False

    if total is None:
        print("❌ 错误: 无法读取数据库内容")
        return False

    # 生成备份文件名
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_name = f"zotero_{ts}.bak"
    bak_path = BACKUP_DIR / bak_name

    # 执行备份
    try:
        shutil.copy2(DB_PATH, bak_path)
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return False

    # 验证备份文件
    bak_size = bak_path.stat().st_size

    print("✅ Zotero 数据库备份完成")
    print(f"   备份文件: {bak_path}")
    print(f"   数据库大小: {format_size(db_size)}")
    print(f"   条目总数:    {total}")
    print(f"   ├─ 文献条目: {items}")
    print(f"   ├─ 附件:     {attachments}")
    print(f"   └─ 笔记:     {notes}")
    print(f"   备份大小: {format_size(bak_size)}")

    # 清理旧备份
    backups = list_backups()
    if len(backups) > MAX_KEEP:
        to_remove = len(backups) - MAX_KEEP
        removed_size = 0
        for name, _, _ in backups[:to_remove]:
            fpath = BACKUP_DIR / name
            removed_size += fpath.stat().st_size
            fpath.unlink()
        print(f"\n   已清理 {to_remove} 份旧备份（保留最近 {MAX_KEEP} 份，释放 {format_size(removed_size)}）")

    return True


def show_status():
    """仅显示备份状态"""
    db_size = get_db_size()
    items, attachments, notes, total = get_db_stats(DB_PATH)

    print("=" * 50)
    print("  Zotero 数据库状态")
    print("=" * 50)
    print(f"  数据库路径: {DB_PATH}")
    print(f"  当前大小:   {format_size(db_size) if db_size else '—'}")
    print(f"  条目总数:    {total if total is not None else '—'}")
    if total:
        print(f"   ├─ 文献条目: {items}")
        print(f"   ├─ 附件:     {attachments}")
        print(f"   └─ 笔记:     {notes}")
    print()

    backups = list_backups()
    if not backups:
        print("  暂无备份")
    else:
        print(f"  备份目录: {BACKUP_DIR}")
        print(f"  备份总数: {len(backups)} 份")
        print()

        # 最近的 5 份
        print(f"  {'文件名':<30} {'时间':<20} {'大小'}")
        print(f"  {'-'*28}  {'-'*18}  {'-'*8}")
        for name, mtime, size in backups[-5:]:
            print(f"  {name:<30} {mtime.strftime('%Y-%m-%d %H:%M'):<20} {format_size(size)}")
        if len(backups) > 5:
            print(f"  ... 还有 {len(backups) - 5} 份更早的备份")

    # 最新备份距今时间
    if backups:
        latest_mtime = backups[-1][1]
        hours_ago = (datetime.now() - latest_mtime).total_seconds() / 3600
        print(f"\n  最近备份距今: {hours_ago:.1f} 小时前")


def main():
    global MAX_KEEP

    if "--status" in sys.argv:
        show_status()
        return

    if "--keep" in sys.argv:
        idx = sys.argv.index("--keep")
        if idx + 1 < len(sys.argv):
            try:
                MAX_KEEP = int(sys.argv[idx + 1])
            except ValueError:
                pass

    do_backup()


if __name__ == "__main__":
    main()
