#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
全盘扫描 Zotero 数据库中的重复条目。

重复检测策略：
  1. DOI 相同（最可靠的重复指标）
  2. 标题完全匹配（同一类型下的相同标题）
  3. 标题近似匹配（可选，默认关闭）

用法：
  python3 tools/find_duplicates.py                  # 默认：按 DOI + 标题精确匹配
  python3 tools/find_duplicates.py --fuzzy          # 启用标题模糊匹配
  python3 tools/find_duplicates.py --min-score 80   # 模糊匹配阈值（默认85）
  python3 tools/find_duplicates.py --type journalArticle  # 仅限特定类型
"""

import sqlite3
import sys
import re
import os
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")

# 排除的 itemTypeID：annotation(1), artwork(2), attachment(3), note(28)
EXCLUDED_TYPES = {1, 2, 3, 28}

FIELD_TITLE = 1
FIELD_DOI = 8


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_item_type_map(cursor):
    cursor.execute("SELECT itemTypeID, typeName FROM itemTypes")
    return {r["itemTypeID"]: r["typeName"] for r in cursor.fetchall()}


def get_field_value(cursor, item_id, field_id):
    cursor.execute("""
        SELECT v.value FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        WHERE d.itemID = ? AND d.fieldID = ?
        LIMIT 1
    """, (item_id, field_id))
    r = cursor.fetchone()
    return r[0] if r else None


def get_item_key(cursor, item_id):
    cursor.execute("SELECT key FROM items WHERE itemID = ?", (item_id,))
    r = cursor.fetchone()
    return r[0] if r else None


def get_date_added(cursor, item_id):
    cursor.execute("SELECT dateAdded FROM items WHERE itemID = ?", (item_id,))
    r = cursor.fetchone()
    return r[0][:19] if r else "—"


def is_deleted(cursor, item_id):
    cursor.execute("SELECT COUNT(*) FROM deletedItems WHERE itemID = ?", (item_id,))
    return cursor.fetchone()[0] > 0


def get_attachment_count(cursor, item_id):
    cursor.execute("SELECT COUNT(*) FROM itemAttachments WHERE parentItemID = ?", (item_id,))
    return cursor.fetchone()[0]


def get_note_count(cursor, item_id):
    cursor.execute("SELECT COUNT(*) FROM itemNotes WHERE parentItemID = ?", (item_id,))
    return cursor.fetchone()[0]


def load_all_items(cursor, type_filter=None):
    """加载所有符合条件的文献条目（排除附件/笔记/注解等非文献类型）。"""
    query = """
        SELECT i.itemID, i.key, i.dateAdded, t.typeName AS itemType
        FROM items i
        JOIN itemTypes t ON i.itemTypeID = t.itemTypeID
        WHERE i.itemTypeID NOT IN (1, 2, 3, 28)
    """
    params = []
    if type_filter:
        query += " AND t.typeName = ?"
        params.append(type_filter)
    query += " ORDER BY i.dateAdded DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    items = []
    for r in rows:
        item_id = r["itemID"]
        title = get_field_value(cursor, item_id, FIELD_TITLE) or "(无标题)"
        doi = get_field_value(cursor, item_id, FIELD_DOI) or ""
        deleted = is_deleted(cursor, item_id)
        attachments = get_attachment_count(cursor, item_id)
        notes = get_note_count(cursor, item_id)

        items.append({
            "itemID": item_id,
            "key": r["key"],
            "itemType": r["itemType"],
            "title": title,
            "doi": doi,
            "dateAdded": r["dateAdded"][:19],
            "deleted": deleted,
            "attachments": attachments,
            "notes": notes,
        })

    return items


def normalize_title(title):
    """标准化标题：去空格、标点、小写，便于比较。"""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)  # 去标点
    t = re.sub(r'\s+', ' ', t)     # 合并空白
    return t.strip()


def find_doi_duplicates(items):
    """按 DOI 分组，找出 DOI 不为空的重复组。"""
    doi_groups = defaultdict(list)
    for item in items:
        if item["doi"]:
            doi_groups[item["doi"].strip().lower()].append(item)

    return {doi: group for doi, group in doi_groups.items() if len(group) > 1}


def find_title_exact_duplicates(items):
    """按类型+标准化标题分组，找出完全匹配的重复组。"""
    title_groups = defaultdict(list)
    for item in items:
        key = (item["itemType"], normalize_title(item["title"]))
        title_groups[key].append(item)

    return {k: group for k, group in title_groups.items() if len(group) > 1}


def find_title_fuzzy_duplicates(items, min_score=85):
    """基于标准化标题的模糊匹配，找近似重复。"""
    normalized = [(i, normalize_title(i["title"])) for i in items]
    visited = set()
    groups = []

    for i in range(len(normalized)):
        if i in visited:
            continue
        group = [normalized[i][0]]
        visited.add(i)
        for j in range(i + 1, len(normalized)):
            if j in visited:
                continue
            score = SequenceMatcher(None, normalized[i][1], normalized[j][1]).ratio() * 100
            if score >= min_score:
                group.append(normalized[j][0])
                visited.add(j)
        if len(group) > 1:
            groups.append(group)

    return groups


def print_results(doi_dups, title_dups, fuzzy_groups, items_map, all_items_count):
    """打印重复条目报告。"""
    total_dup_items = set()

    print("\n" + "=" * 80)
    print("  Zotero 重复条目扫描报告")
    print("=" * 80)

    # ── DOI 重复 ──
    if doi_dups:
        print(f"\n\n▶【DOI 重复】共 {len(doi_dups)} 组")
        print("-" * 80)
        for doi, group in sorted(doi_dups.items()):
            for item in group:
                total_dup_items.add(item["itemID"])
            status_icons = []
            for item in group:
                if item["deleted"]:
                    status_icons.append("⚠️  (已删除)")
                else:
                    status_icons.append("✅  (可见)")
            print(f"\n  DOI: {doi}")
            print(f"  {'ItemID':>7} {'Key':<10} {'类型':<16} {'日期':<20} {'附件':>3} {'笔记':>3}  标题")
            print(f"  {'-'*7} {'-'*10} {'-'*16} {'-'*20} {'-'*3} {'-'*3}  {'-'*40}")
            for i, item in enumerate(group):
                print(f"  {item['itemID']:>7} {item['key']:<10} {item['itemType']:<16} "
                      f"{item['dateAdded']:<20} {item['attachments']:>3} {item['notes']:>3}  "
                      f"{item['title'][:50]}  {status_icons[i]}")
    else:
        print("\n\n▶【DOI 重复】未发现 DOI 重复条目。")

    # ── 标题精确重复 ──
    if title_dups:
        print(f"\n\n▶【标题精确匹配重复】共 {len(title_dups)} 组")
        print("-" * 80)
        for (item_type, norm_title), group in sorted(title_dups.items()):
            for item in group:
                total_dup_items.add(item["itemID"])
            status_icons = []
            for item in group:
                if item["deleted"]:
                    status_icons.append("⚠️  (已删除)")
                else:
                    status_icons.append("✅  (可见)")
            print(f"\n  类型: {item_type}")
            print(f"  标题: {group[0]['title'][:70]}")
            print(f"  {'ItemID':>7} {'Key':<10} {'DOI':<32} {'日期':<20} {'附件':>3} {'笔记':>3}")
            print(f"  {'-'*7} {'-'*10} {'-'*32} {'-'*20} {'-'*3} {'-'*3}")
            for i, item in enumerate(group):
                doi_short = item["doi"][:30] if item["doi"] else "—"
                print(f"  {item['itemID']:>7} {item['key']:<10} {doi_short:<32} "
                      f"{item['dateAdded']:<20} {item['attachments']:>3} {item['notes']:>3}  {status_icons[i]}")
    else:
        print(f"\n\n▶【标题精确匹配重复】未发现标题完全匹配的重复条目。")

    # ── 标题模糊重复 ──
    if fuzzy_groups:
        print(f"\n\n▶【标题近似匹配重复】共 {len(fuzzy_groups)} 组")
        print("-" * 80)
        for group in fuzzy_groups:
            for item in group:
                total_dup_items.add(item["itemID"])
            status_icons = []
            for item in group:
                if item["deleted"]:
                    status_icons.append("⚠️  (已删除)")
                else:
                    status_icons.append("✅  (可见)")
            print(f"\n  近似标题组:")
            print(f"  {'ItemID':>7} {'Key':<10} {'类型':<16} {'DOI':<32} {'附件':>3} {'笔记':>3}  标题")
            print(f"  {'-'*7} {'-'*10} {'-'*16} {'-'*32} {'-'*3} {'-'*3}  {'-'*50}")
            for i, item in enumerate(group):
                doi_short = item["doi"][:30] if item["doi"] else "—"
                print(f"  {item['itemID']:>7} {item['key']:<10} {item['itemType']:<16} "
                      f"{doi_short:<32} {item['attachments']:>3} {item['notes']:>3}  "
                      f"{item['title'][:60]}  {status_icons[i]}")
    elif fuzzy_groups is not None:
        print(f"\n\n▶【标题近似匹配重复】未发现标题近似匹配的重复条目。")

    # ── 汇总 ──
    non_deleted_dup = sum(1 for iid in total_dup_items if not items_map[iid]["deleted"])
    deleted_dup = len(total_dup_items) - non_deleted_dup
    groups_count = len(doi_dups) + len(title_dups) + (len(fuzzy_groups) if fuzzy_groups else 0)

    print(f"\n\n{'=' * 80}")
    print(f"  汇总")
    print(f"{'=' * 80}")
    print(f"  数据库全部文献条目:     {all_items_count}")
    print(f"  涉及重复的条目总数:     {len(total_dup_items)}")
    print(f"    ├─ 可见重复条目:      {non_deleted_dup}")
    print(f"    └─ 已删除条目:        {deleted_dup}")
    print(f"  重复组数:               {groups_count}")
    print(f"  检测策略:               DOI 匹配 + 标题精确匹配" +
          (f" + 标题模糊匹配(≥{args.min_score})" if fuzzy_groups is not None else ""))
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="全盘扫描 Zotero 数据库中的重复条目")
    parser.add_argument("--fuzzy", action="store_true", help="启用标题模糊匹配")
    parser.add_argument("--min-score", type=int, default=85,
                        help="模糊匹配阈值（0-100），默认85")
    parser.add_argument("--type", dest="type_filter", help="仅限特定条目类型（如 journalArticle）")
    args = parser.parse_args()

    conn = get_conn()
    cursor = conn.cursor()

    type_map = get_item_type_map(cursor)

    print("正在加载条目数据...", end=" ", flush=True)
    items = load_all_items(cursor, type_filter=args.type_filter)
    print(f"加载 {len(items)} 条文献条目。")
    items_map = {item["itemID"]: item for item in items}

    if not items:
        print("数据库中没有可扫描的文献条目。")
        conn.close()
        sys.exit(0)

    # 1) DOI 重复
    print("正在检测 DOI 重复...", end=" ", flush=True)
    doi_duplicates = find_doi_duplicates(items)
    print(f"完成。发现 {len(doi_duplicates)} 组。")

    # 2) 标题精确匹配
    print("正在检测标题精确重复...", end=" ", flush=True)
    title_duplicates = find_title_exact_duplicates(items)
    # 排除已在 DOI 组中的条目，避免重复报告
    doi_item_ids = {item["itemID"] for group in doi_duplicates.values() for item in group}
    filtered_title_dups = {}
    for key, group in title_duplicates.items():
        new_group = [item for item in group if item["itemID"] not in doi_item_ids]
        if len(new_group) > 1:
            filtered_title_dups[key] = new_group
    print(f"完成。发现 {len(filtered_title_dups)} 组（已排除 DOI 重复中的条目）。")

    # 3) 标题模糊匹配（可选）
    fuzzy_groups = None
    if args.fuzzy:
        print(f"正在检测标题近似重复（阈值 ≥{args.min_score}）...", end=" ", flush=True)
        all_dup_ids = doi_item_ids | {item["itemID"] for group in filtered_title_dups.values() for item in group}
        remaining_items = [item for item in items if item["itemID"] not in all_dup_ids]
        raw_fuzzy = find_title_fuzzy_duplicates(remaining_items, min_score=args.min_score)
        fuzzy_groups = []
        for group_ids in raw_fuzzy:
            group_items = [items_map[iid] for iid in group_ids]
            fuzzy_groups.append(group_items)
        print(f"完成。发现 {len(fuzzy_groups)} 组。")
    else:
        print("标题模糊匹配：跳过（启用请加 --fuzzy）。")

    # 输出报告
    print_results(doi_duplicates, filtered_title_dups, fuzzy_groups, items_map, len(items))

    conn.close()
