#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
从备份数据库中恢复被误删的笔记条目。

恢复策略：从备份中筛选出那些在当前数据库中父条目仍然可见，
但笔记本身已被删除的笔记，精确恢复它们（不涉及父条目和其他数据）。
"""
import sqlite3
import sys
import string
import random
import time
import os
from pathlib import Path

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")
BACKUP_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite.bak")
LIBRARY_ID = 1


def generate_item_key(length=8):
    chars = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
    return ''.join(random.choices(chars, k=length))


def wrap_zotero_note(inner_html):
    return f'<div class="zotero-note znv1"><div data-schema-version="9">{inner_html}</div></div>'


def main():
    print("=" * 60)
    print("  从备份恢复被误删的笔记")
    print("=" * 60)

    # 连接当前数据库，ATTACH 备份库
    cur_conn = sqlite3.connect(DB_PATH, timeout=30)
    cur_conn.execute("PRAGMA journal_mode=WAL")
    cur_conn.execute("PRAGMA busy_timeout=10000")
    cur_cur = cur_conn.cursor()

    # ATTACH 备份库
    cur_cur.execute(f"ATTACH '{BACKUP_PATH}' AS bak")

    # 找出备份中有、当前 DB 中没有，且父条目在当前 DB 中仍可见的笔记
    cur_cur.execute("""
        SELECT n.itemID, n.parentItemID, n.note, n.title
        FROM bak.itemNotes n
        JOIN bak.items i ON n.itemID = i.itemID
        WHERE i.itemTypeID = 28
          AND n.parentItemID IN (SELECT itemID FROM main.items)
          AND NOT EXISTS (SELECT 1 FROM main.items WHERE itemID = n.itemID)
    """)
    lost_notes = cur_cur.fetchall()

    if not lost_notes:
        print("未找到需要恢复的笔记。")
        cur_conn.close()
        return

    print(f"\n找到 {len(lost_notes)} 条需要恢复的笔记:\n")

    restored = 0
    skipped = 0

    for row in lost_notes:
        note_id = row[0]
        parent_id = row[1]
        note_html = row[2]
        note_title = row[3]

        # 确认父条目确实在当前 DB 中
        cur_cur.execute("SELECT COUNT(*) FROM items WHERE itemID = ?", (parent_id,))
        if cur_cur.fetchone()[0] == 0:
            print(f"  ⚠️  父条目 {parent_id} 已不存在，跳过笔记 {note_id}")
            skipped += 1
            continue

        # 检查是否已有同名笔记（防止重复恢复）
        cur_cur.execute(
            "SELECT COUNT(*) FROM itemNotes WHERE parentItemID = ? AND title = ?",
            (parent_id, note_title)
        )
        if cur_cur.fetchone()[0] > 0:
            print(f"  ⚠️  同名笔记已存在，跳过: {note_title[:50]}")
            skipped += 1
            continue

        # 创建新的 item 记录
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        new_key = generate_item_key()

        cur_cur.execute("SELECT MAX(version) FROM items")
        max_ver = cur_cur.fetchone()[0]
        version = (max_ver or 0) + 1

        cur_cur.execute(
            """INSERT INTO items (itemTypeID, dateAdded, dateModified,
               clientDateModified, libraryID, key, version, synced)
               VALUES (28, ?, ?, ?, ?, ?, ?, 0)""",
            (now, now, now, LIBRARY_ID, new_key, version)
        )
        new_id = cur_cur.lastrowid

        wrapped_html = wrap_zotero_note(note_html)

        cur_cur.execute(
            """INSERT INTO itemNotes (itemID, parentItemID, note, title)
               VALUES (?, ?, ?, ?)""",
            (new_id, parent_id, wrapped_html, note_title)
        )

        # 获取父条目标题用于显示
        cur_cur.execute("""
            SELECT v.value FROM itemData d
            JOIN itemDataValues v ON d.valueID = v.valueID
            WHERE d.itemID = ? AND d.fieldID = 1 LIMIT 1
        """, (parent_id,))
        ptitle_row = cur_cur.fetchone()
        parent_title = ptitle_row[0][:40] if ptitle_row else f"itemID={parent_id}"

        print(f"  ✅ {note_title[:55]}")
        print(f"     所属: {parent_title}  | 新ID: {new_id}")
        restored += 1

    cur_conn.commit()
    print(f"\n{'=' * 60}")
    print(f"  恢复完成: 成功 {restored} 条，跳过 {skipped} 条")

    cur_cur.execute("DETACH bak")
    cur_conn.close()


if __name__ == "__main__":
    main()
