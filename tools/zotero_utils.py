#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
Zotero 工具模块 — 可复用的 Zotero 数据库操作函数
提供：查询无笔记条目、查找PDF路径、创建笔记、连接数据库等基础功能

增量追踪：自动记录上次处理时间点，后续只查询增量，避免全量扫描。
"""
import sqlite3
import string
import random
import time
import json
from pathlib import Path

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")
STORAGE_PATH = ZOTERO_DATA_DIR / "storage"
PROJECT_DIR = Path(__file__).parent
STATE_FILE = PROJECT_DIR / "processed_state.json"
LIBRARY_ID = 1


def _load_state():
    """加载处理状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_checked": None, "processed_item_ids": []}


def _save_state(state):
    """保存处理状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_last_checked():
    """获取上次处理的时间点"""
    state = _load_state()
    return state.get("last_checked")


def mark_processed(item_ids):
    """
    将指定条目标记为已处理。

    Args:
        item_ids: int 或 list of int，已处理的条目ID
    """
    state = _load_state()
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    if isinstance(item_ids, int):
        item_ids = [item_ids]

    existing = set(state.get("processed_item_ids", []))
    existing.update(item_ids)
    state["processed_item_ids"] = sorted(existing)
    state["last_checked"] = now
    _save_state(state)


def reset_processed_state():
    """重置处理记录（下次将全量扫描）"""
    _save_state({"last_checked": None, "processed_item_ids": []})
    print("已重置处理记录，下次将全量扫描。")


def get_connection():
    """获取 Zotero 数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_items_without_notes(cursor, since=None, only_with_pdf=True):
    """
    查找没有笔记的文献条目。默认只查上次处理后的增量。

    Args:
        cursor: 数据库游标
        since: 时间起点 (str, ISO格式如 '2026-05-14 00:00:00')
               若为 None 则从上次记录的时间点开始查
               传入 'all' 则全量扫描
        only_with_pdf: 是否仅返回有PDF附件的条目

    Returns:
        list of dict: [{'itemID': int, 'title': str, 'dateAdded': str, 'key': str}, ...]
    """
    # 确定查询起点
    if since is None:
        last = get_last_checked()
        if last:
            since = last
            mode = "增量"
        else:
            since = "1970-01-01 00:00:00"
            mode = "全量（首次或无记录）"
    elif since == 'all':
        since = "1970-01-01 00:00:00"
        mode = "全量（用户指定）"
    else:
        mode = f"从 {since} 起"

    # 获取已处理条目ID，排除它们
    state = _load_state()
    processed_ids = state.get("processed_item_ids", [])

    query = """
        SELECT i.itemID, i.key, i.dateAdded
        FROM items i
        WHERE i.itemTypeID NOT IN (1, 2, 3, 28)
          AND i.dateAdded >= ?
          AND i.itemID NOT IN (
              SELECT DISTINCT parentItemID FROM itemNotes WHERE parentItemID IS NOT NULL
          )
    """
    params = [since]

    if only_with_pdf:
        query += """
          AND i.itemID IN (
              SELECT parentItemID FROM itemAttachments WHERE contentType LIKE '%pdf%'
          )
        """

    query += " ORDER BY i.dateAdded DESC;"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        item_id = row['itemID']

        # 跳过已处理的条目
        if item_id in processed_ids:
            continue

        # 获取标题
        cursor.execute("""
            SELECT v.value FROM itemData d
            JOIN itemDataValues v ON d.valueID = v.valueID
            WHERE d.itemID = ? AND d.fieldID = 1
        """, (item_id,))
        title_row = cursor.fetchone()
        title = title_row['value'] if title_row else "(无标题)"

        results.append({
            'itemID': item_id,
            'key': row['key'],
            'title': title,
            'dateAdded': row['dateAdded'],
        })

    print(f"查询模式: {mode}，找到 {len(results)} 篇未处理的新文献（含PDF附件）")
    return results


def get_pdf_path(cursor, parent_item_id):
    """
    获取文献条目关联的PDF文件路径。

    Args:
        cursor: 数据库游标
        parent_item_id: 文献条目ID

    Returns:
        Path or None: PDF文件的绝对路径
    """
    cursor.execute("""
        SELECT ia.itemID, ia.path FROM itemAttachments ia
        WHERE ia.parentItemID = ? AND ia.contentType LIKE '%pdf%'
        LIMIT 1
    """, (parent_item_id,))
    row = cursor.fetchone()

    if not row:
        return None

    # storage:filename.pdf 格式 → 需要找到对应的存储目录
    path_str = row['path']
    if path_str.startswith('storage:'):
        filename = path_str[8:]

        # 根据附件条目的key查找存储子目录
        cursor.execute("SELECT key FROM items WHERE itemID = ?", (row['itemID'],))
        key_row = cursor.fetchone()
        if key_row:
            pdf_path = STORAGE_PATH / key_row['key'] / filename
            if pdf_path.exists():
                return pdf_path

    return None


def get_item_metadata(cursor, item_id):
    """
    获取文献条目的元数据。

    Args:
        cursor: 数据库游标
        item_id: 文献条目ID

    Returns:
        dict: 包含标题、期刊、年份、DOI等信息的字典
    """
    cursor.execute("""
        SELECT d.fieldID, v.value FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        WHERE d.itemID = ?
    """, (item_id,))

    fields = {}
    for row in cursor.fetchall():
        fields[row['fieldID']] = row['value']

    # fieldID: 1=title, 6=date, 8=DOI, 10=url, 41=journal, 44=ISSN, 22=issue, 35=pages, 67=volume
    field_names = {1: 'title', 6: 'date', 8: 'DOI', 10: 'url', 41: 'journal',
                   44: 'issn', 22: 'issue', 35: 'pages', 67: 'volume', 85: 'abbrev_journal',
                   15: 'language', 16: 'library_catalog', 11: 'dateAdded'}

    metadata = {}
    for fid, fname in field_names.items():
        if fid in fields:
            metadata[fname] = fields[fid]

    return metadata


def generate_item_key(length=8):
    """生成随机 Zotero 条目 key（排除 0、1、O 以符合 Zotero 规范）"""
    chars = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
    return ''.join(random.choices(chars, k=length))


def _get_next_version(cursor):
    """获取下一个版本号"""
    cursor.execute("SELECT MAX(version) FROM items")
    max_ver = cursor.fetchone()[0]
    return (max_ver or 0) + 1


def wrap_zotero_note(inner_html):
    """用 Zotero 标准包装结构包裹笔记内容 HTML，确保格式正确渲染。"""
    return f'<div class="zotero-note znv1"><div data-schema-version="9">{inner_html}</div></div>'


def create_note(cursor, parent_item_id, title, note_content_html):
    """
    为指定文献条目创建笔记（自动添加 Zotero 标准 HTML 包装）。

    Args:
        cursor: 数据库游标
        parent_item_id: 目标文献条目的ID
        title: 笔记标题
        note_content_html: 笔记内容（HTML格式，无需手动添加外层包装）

    Returns:
        int: 新创建的笔记条目ID
    """
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    key = generate_item_key()
    version = _get_next_version(cursor)

    cursor.execute(
        """INSERT INTO items (itemTypeID, dateAdded, dateModified,
           clientDateModified, libraryID, key, version, synced)
           VALUES (28, ?, ?, ?, ?, ?, ?, 0)""",
        (now, now, now, LIBRARY_ID, key, version)
    )
    new_id = cursor.lastrowid

    wrapped_html = wrap_zotero_note(note_content_html)

    cursor.execute(
        """INSERT INTO itemNotes (itemID, parentItemID, note, title)
           VALUES (?, ?, ?, ?)""",
        (new_id, parent_item_id, wrapped_html, title)
    )
    return new_id


def is_chinese_paper(text, threshold=0.30):
    """
    判断文献是否为中文文献（基于中文字符占比）。

    用于全文翻译前判断：中文文献跳过翻译，外文文献正常翻译。
    不适用于简单总结和详细总结——两者不区分中英文。

    判断逻辑：
      - 统计文本中中文字符（CJK统一表意文字）占总字符数（不含空白）的比例
      - 比例 >= threshold（默认 30%）判断为中文文献
      - 比例 < threshold 判断为外文文献

    注意：
      - 英文文献中可能夹杂中文参考文献、作者名、机构名等
      - 此类文献中文字符占比通常低于 10%
      - 阈值 30% 能较好区分"纯中文论文"和"含中文引用的英文论文"

    Args:
        text: 文献全文文本
        threshold: 中文字符占比阈值，默认 0.30（30%）

    Returns:
        bool: True 为中文文献，False 为外文文献
    """
    import re
    if not text or not text.strip():
        return False
    text = text.strip()
    total = len(text)
    if total == 0:
        return False
    zh_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    ratio = zh_chars / total
    return ratio >= threshold


def main():
    """命令行入口：显示未处理的无笔记文献列表"""
    import argparse

    parser = argparse.ArgumentParser(description="Zotero 工具模块")
    parser.add_argument("--all", action="store_true", help="全量扫描（忽略增量记录）")
    parser.add_argument("--since", help="从指定时间开始查 (ISO格式)")
    parser.add_argument("--reset", action="store_true", help="重置处理记录")
    args = parser.parse_args()

    if args.reset:
        reset_processed_state()
        return

    conn = get_connection()
    cursor = conn.cursor()

    if args.all:
        items = find_items_without_notes(cursor, since='all')
    elif args.since:
        items = find_items_without_notes(cursor, since=args.since)
    else:
        items = find_items_without_notes(cursor)

    if items:
        print("\n待处理文献：")
        for item in items:
            print(f"  itemID={item['itemID']} | {item['dateAdded']}")
            print(f"  标题: {item['title'][:80]}...")
            print()

    conn.close()


if __name__ == "__main__":
    main()
