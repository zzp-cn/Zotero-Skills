#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
Zotero 笔记去重与清理工具。

用法：
  python3 tools/note_cleanup.py list <条目ID>         # 列出条目下所有笔记
  python3 tools/note_cleanup.py delete <笔记ID> [...]  # 删除指定笔记

示例：
  python3 tools/note_cleanup.py list 176
  python3 tools/note_cleanup.py delete 596 965 966
"""

import sqlite3
import os
import sys
from pathlib import Path

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")


def cmd_list(cursor, parent_id):
    """列出指定条目下的所有笔记。"""
    cursor.execute("""
        SELECT n.itemID, n.title, i.dateAdded, i.dateModified, LENGTH(n.note) AS char_count
        FROM itemNotes n
        JOIN items i ON n.itemID = i.itemID
        WHERE n.parentItemID = ?
        ORDER BY i.dateAdded
    """, (parent_id,))
    rows = cursor.fetchall()
    if not rows:
        print(f"条目 {parent_id} 下没有笔记")
        return

    print(f"\n条目 {parent_id} 下的笔记：")
    print(f"{'ID':>6}  {'创建时间':<20} {'修改时间':<20} {'字符数':>6}  标题")
    print("-" * 100)
    for row in rows:
        print(f"{row[0]:>6}  {row[2]:<20} {row[3]:<20} {row[4]:>6}  {row[1][:40]}")
    print()


def cmd_delete(cursor, note_ids):
    """删除指定笔记。"""
    for note_id in note_ids:
        cursor.execute("SELECT COUNT(*) FROM items WHERE itemID = ?", (note_id,))
        if cursor.fetchone()[0] == 0:
            print(f"笔记 {note_id}: 不存在，跳过")
            continue
        for tbl in ("itemNotes", "itemData", "itemTags", "itemRelations",
                    "collectionItems", "itemCreators", "fulltextItemWords", "fulltextItems"):
            cursor.execute(f"DELETE FROM {tbl} WHERE itemID = ?", (note_id,))
        cursor.execute("INSERT OR IGNORE INTO deletedItems(itemID) VALUES (?)", (note_id,))
        cursor.execute("DELETE FROM items WHERE itemID = ?", (note_id,))
        print(f"已删除笔记 {note_id}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        if command == "list":
            cmd_list(cursor, int(args[0]))
        elif command == "delete":
            note_ids = [int(a) for a in args]
            confirm = input(f"确认删除 {len(note_ids)} 条笔记 (IDs: {note_ids})? (y/N): ")
            if confirm.lower() == 'y':
                cmd_delete(cursor, note_ids)
                conn.commit()
            else:
                print("取消")
        else:
            print(f"未知命令: {command}")
            print(__doc__)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
