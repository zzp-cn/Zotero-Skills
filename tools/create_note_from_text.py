#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
将指定文本内容创建为 Zotero 条目笔记（自动处理标准 HTML 包装）。

用法:
  python3 create_note_from_text.py <父条目ID> --title "笔记标题" --content-file content.html
  python3 create_note_from_text.py <父条目ID> --title "笔记标题" --content "笔记正文 HTML"
  python3 create_note_from_text.py <父条目ID> --title "笔记标题" --stdin

可选:
  --update             如果已存在同名笔记则更新（按标题匹配）
  --dry-run           仅打印将写入的内容，不实际写入
  --verbose           打印详细信息
"""
import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from zotero_utils import get_connection, generate_item_key, _get_next_version, LIBRARY_ID
from zotero_utils import wrap_zotero_note
import time


def find_note_by_title(cursor, parent_item_id, title):
    """查找上级条目下是否有同名笔记。返回 (itemID,) 或 None。"""
    cursor.execute("""
        SELECT n.itemID FROM itemNotes n
        JOIN items i ON n.itemID = i.itemID
        WHERE n.parentItemID = ? AND n.title = ?
    """, (parent_item_id, title))
    row = cursor.fetchone()
    return row['itemID'] if row else None


def update_note_content(cursor, note_item_id, new_content_html):
    """更新已有笔记的内容。"""
    wrapped = wrap_zotero_note(new_content_html)
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE items SET dateModified = ?, clientDateModified = ? WHERE itemID = ?",
                   (now, now, note_item_id))
    cursor.execute("UPDATE itemNotes SET note = ? WHERE itemID = ?",
                   (wrapped, note_item_id))
    return note_item_id


def create_note_from_text(parent_item_id, title, content_html, update=False, dry_run=False):
    """
    创建或更新 Zotero 笔记。

    Args:
        parent_item_id: 目标文献条目ID
        title: 笔记标题
        content_html: 笔记内容（内层 HTML，无需外层 Zotero 包装）
        update: 若已有同名笔记则更新，否则创建新笔记
        dry_run: 仅预览，不写入

    Returns:
        int or None: 笔记的 itemID
    """
    conn = get_connection()
    cursor = conn.cursor()

    existing_id = find_note_by_title(cursor, parent_item_id, title)

    if existing_id:
        if update:
            if dry_run:
                print(f"[DRY RUN] 将更新笔记 itemID={existing_id}（{title}）")
                return existing_id
            note_id = update_note_content(cursor, existing_id, content_html)
            conn.commit()
            print(f"已更新笔记: itemID={note_id}（{title}）")
            conn.close()
            return note_id
        else:
            print(f"已存在同名笔记 itemID={existing_id}（{title}），跳过。使用 --update 可更新。")
            conn.close()
            return existing_id

    if dry_run:
        print(f"[DRY RUN] 将创建新笔记，上级条目ID={parent_item_id}，标题={title}")
        conn.close()
        return None

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    key = generate_item_key()

    cursor.execute("SELECT MAX(version) FROM items")
    max_ver = cursor.fetchone()[0]
    version = (max_ver or 0) + 1

    cursor.execute(
        """INSERT INTO items (itemTypeID, dateAdded, dateModified,
           clientDateModified, libraryID, key, version, synced)
           VALUES (28, ?, ?, ?, ?, ?, ?, 0)""",
        (now, now, now, LIBRARY_ID, key, version)
    )
    new_id = cursor.lastrowid

    wrapped = wrap_zotero_note(content_html)
    cursor.execute(
        "INSERT INTO itemNotes (itemID, parentItemID, note, title) VALUES (?, ?, ?, ?)",
        (new_id, parent_item_id, wrapped, title)
    )
    conn.commit()

    print(f"已创建笔记: itemID={new_id}, key={key}（{title}）")
    conn.close()
    return new_id


def main():
    parser = argparse.ArgumentParser(description="将文本内容创建为 Zotero 条目笔记")
    parser.add_argument("parent_id", type=int, help="目标文献条目ID")
    parser.add_argument("--title", "-t", required=True, help="笔记标题")
    parser.add_argument("--content", "-c", help="笔记正文 HTML（内层，无需 Zotero 包装）")
    parser.add_argument("--content-file", "-f", type=Path, help="从文件读取笔记正文 HTML")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取正文 HTML")
    parser.add_argument("--update", "-u", action="store_true", help="若已有同名笔记则更新")
    parser.add_argument("--dry-run", "-n", action="store_true", help="仅预览，不写入")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印详细信息")

    args = parser.parse_args()

    # 读取内容
    content = None
    if args.content:
        content = args.content
    elif args.content_file and args.content_file.exists():
        content = args.content_file.read_text(encoding="utf-8")
    elif args.stdin:
        content = sys.stdin.read()
    else:
        parser.error("请通过 --content、--content-file 或 --stdin 提供笔记内容")

    if args.verbose:
        print(f"上级条目ID: {args.parent_id}")
        print(f"笔记标题: {args.title}")
        print(f"内容长度: {len(content)} 字符")
        print(f"模式: {'更新' if args.update else '新建'}")
        if args.dry_run:
            print("模式: DRY RUN（不会写入数据库）")

    create_note_from_text(
        parent_item_id=args.parent_id,
        title=args.title,
        content_html=content,
        update=args.update,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
