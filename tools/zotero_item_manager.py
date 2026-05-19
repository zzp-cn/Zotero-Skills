#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
Zotero 条目删除状态检查与管理工具。

功能：
  - audit       全盘扫描所有条目删除状态，给出统计摘要
  - list        查看指定条目的删除状态
  - list-all    按关键词搜索并查看状态
  - delete      真正删除条目（清理 items + syncCache + 物理文件）
  - restore     恢复条目（清除 deletedItems 标记，使条目在 UI 重新可见）
  - purge-cache 清理所有 syncCache 中的条目缓存（防止自动重建）
  - purge-ditems 清理所有孤立的 deletedItems 记录（条目已不存在的残留）
  - cleanup     批量清理：删除所有名义删除条目 + 清理 syncCache 残留 + 清理孤立 deletedItems

用法：
  python3 tools/zotero_item_manager.py audit
  python3 tools/zotero_item_manager.py list <itemID> [itemID ...]
  python3 tools/zotero_item_manager.py list-all <keyword>
  python3 tools/zotero_item_manager.py delete <itemID> [itemID ...]
  python3 tools/zotero_item_manager.py restore <itemID> [itemID ...]
  python3 tools/zotero_item_manager.py purge-cache
  python3 tools/zotero_item_manager.py cleanup
"""

import sqlite3
import os
import shutil
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calc_dup_space import calc_dup_space, fmt_size

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")
STORAGE_PATH = str(ZOTERO_DATA_DIR / "storage")

STATUS_NORMAL = "正常（可见）"
STATUS_NOMINAL_DEL = "名义删除（deletedItems 中，UI 不可见）"
STATUS_SYNC_CACHE = "缓存残留（不在 items 表，但 syncCache 会重建）"
STATUS_DELETED = "已彻底删除"


def get_title(cursor, item_id):
    cursor.execute("""
        SELECT v.value FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        JOIN fields f ON d.fieldID = f.fieldID
        WHERE d.itemID = ? AND f.fieldName = 'title' LIMIT 1
    """, (item_id,))
    r = cursor.fetchone()
    return r[0][:80] + "..." if r and len(r[0]) > 80 else (r[0] if r else "—")


def get_key(cursor, item_id):
    cursor.execute("SELECT key FROM items WHERE itemID = ?", (item_id,))
    r = cursor.fetchone()
    return r[0] if r else None


def get_type_name(cursor, item_id):
    cursor.execute("""
        SELECT t.typeName FROM items i
        JOIN itemTypes t ON i.itemTypeID = t.itemTypeID
        WHERE i.itemID = ?
    """, (item_id,))
    r = cursor.fetchone()
    return r[0] if r else "—"


def get_item_ids_from_keyword(cursor, keyword):
    cursor.execute("""
        SELECT DISTINCT d.itemID FROM itemData d
        JOIN itemDataValues v ON d.valueID = v.valueID
        JOIN fields f ON d.fieldID = f.fieldID
        WHERE f.fieldName = 'title' AND v.value LIKE ?
    """, (f"%{keyword}%",))
    return [r[0] for r in cursor.fetchall()]


def _item_status(cursor, item_id, key=None):
    """Return (in_items, in_deleted, in_cache) for an item_id."""
    cursor.execute("SELECT COUNT(*) FROM items WHERE itemID = ?", (item_id,))
    in_items = cursor.fetchone()[0] > 0

    cursor.execute("SELECT COUNT(*) FROM deletedItems WHERE itemID = ?", (item_id,))
    in_deleted = cursor.fetchone()[0] > 0

    if key is None:
        key = get_key(cursor, item_id)

    in_cache = False
    if key:
        cursor.execute(
            "SELECT COUNT(*) FROM syncCache WHERE libraryID = 1 AND key = ? AND syncObjectTypeID = 3",
            (key,)
        )
        in_cache = cursor.fetchone()[0] > 0

    return in_items, in_deleted, in_cache


def display_status(cursor, item_ids):
    """Print detailed status table for given item_ids."""
    print(f"\n{'ItemID':>7} {'Key':<10} {'类型':<14} {'创建时间':<20} {'附件':>4} {'笔记':>4} {'状态':<34} 标题")
    print("-" * 140)
    for item_id in item_ids:
        key = get_key(cursor, item_id)
        type_name = get_type_name(cursor, item_id)
        title = get_title(cursor, item_id)
        in_items, in_del, in_cache = _item_status(cursor, item_id, key)

        # 创建时间
        cursor.execute("SELECT dateAdded FROM items WHERE itemID = ?", (item_id,))
        row = cursor.fetchone()
        added = row[0][:19] if row else "—"

        # 附件数、笔记数
        cursor.execute("SELECT COUNT(*) FROM itemAttachments WHERE parentItemID = ?", (item_id,))
        att_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM itemNotes WHERE parentItemID = ?", (item_id,))
        note_count = cursor.fetchone()[0]

        if in_items and not in_del:
            status = "✅ " + STATUS_NORMAL
        elif in_items and in_del:
            status = "⚠️  " + STATUS_NOMINAL_DEL
        elif not in_items and in_cache:
            status = "🔄 " + STATUS_SYNC_CACHE
        elif not in_items and not in_cache:
            status = "❌ " + STATUS_DELETED
        else:
            status = "—"

        print(f"{item_id:>7} {(key or '—'):<10} {type_name:<14} {added:<20} {att_count:>4} {note_count:>4} {status:<34} {title[:55]}")
    print()


# ─── 命令实现 ─────────────────────────────────────────────

def cmd_audit(cursor):
    """全盘扫描所有条目，按状态分类汇总。"""
    print("\n===== 全盘扫描：items 表中所有条目 =====")
    cursor.execute("SELECT itemID FROM items ORDER BY itemID")
    all_item_ids = [r[0] for r in cursor.fetchall()]

    normal, nom_del, revived = [], [], []
    for item_id in all_item_ids:
        in_items, in_del, in_cache = _item_status(cursor, item_id)
        if in_items and not in_del:
            normal.append(item_id)
        elif in_items and in_del:
            nom_del.append(item_id)

    # 检查 syncCache 中但 items 中不存在的条目
    cursor.execute("""
        SELECT sc.key, sc.version FROM syncCache sc
        WHERE sc.libraryID = 1 AND sc.syncObjectTypeID = 3
        AND NOT EXISTS (SELECT 1 FROM items i WHERE i.key = sc.key)
        ORDER BY sc.version
    """)
    cache_only = cursor.fetchall()

    # 尝试从 cache data 中提取标题
    cache_items = []
    for (ck, cv) in cache_only:
        cursor.execute(
            "SELECT data FROM syncCache WHERE libraryID = 1 AND key = ? AND syncObjectTypeID = 3 AND version = ?",
            (ck, cv)
        )
        row = cursor.fetchone()
        title = ck
        if row:
            try:
                data = json.loads(row[0])
                title = data.get("data", {}).get("title", ck)
            except json.JSONDecodeError:
                pass
        cache_items.append((ck, title))

    # 输出报告
    print(f"\n📊  扫描完成\n")
    print(f"  ✅  正常（可见）:         {len(normal)} 条")
    print(f"  ⚠️   名义删除（UI 不可见）: {len(nom_del)} 条")
    print(f"  🔄  缓存残留（将被重建）:  {len(cache_only)} 条")
    print(f"  📦  数据库全部条目:       {len(all_item_ids)} 条")
    print()

    if nom_del:
        print("── 名义删除条目 ──")
        display_status(cursor, nom_del)

        # 检查这些条目是否曾经被重建过（有对应的 syncCache 残留）
        for item_id in nom_del:
            key = get_key(cursor, item_id)
            if key:
                cursor.execute(
                    "SELECT COUNT(*) FROM syncCache WHERE libraryID = 1 AND key = ? AND syncObjectTypeID = 3",
                    (key,)
                )
                if cursor.fetchone()[0] > 0:
                    print(f"  ⚠️  注意: {item_id} ({key}) 的 syncCache 仍然存在，如果被删除会自动重建")
        print()

    if cache_only:
        print("── 缓存残留（将被自动重建）──")
        print(f"{'Key':<12} 版本     标题")
        print("-" * 80)
        for (ck, title) in cache_items:
            cv = next((v for k, v in cache_only if k == ck), "?")
            print(f"{ck:<12} v{cv:<7} {title[:60]}")
        print()


def cmd_list(cursor, item_ids):
    display_status(cursor, item_ids)


def cmd_list_all(cursor, keyword):
    item_ids = get_item_ids_from_keyword(cursor, keyword)
    if not item_ids:
        print(f"未找到标题包含 '{keyword}' 的条目")
    else:
        print(f"找到 {len(item_ids)} 个标题包含 '{keyword}' 的条目:")
        display_status(cursor, item_ids)

    # Also check syncCache-only entries with matching keyword
    cursor.execute("""
        SELECT sc.key FROM syncCache sc
        WHERE sc.libraryID = 1 AND sc.syncObjectTypeID = 3
        AND sc.data LIKE ?
        AND NOT EXISTS (SELECT 1 FROM items i WHERE i.key = sc.key)
    """, (f"%{keyword}%",))
    cache_keys = [r[0] for r in cursor.fetchall()]
    if cache_keys:
        print(f"以下 key 在 syncCache 中但不在 items 表（将被重建）:")
        for ck in cache_keys:
            print(f"  🔄 {ck}")
    print()


def _delete_one_item(cursor, item_id):
    """Delete a single item from all tables (not syncCache)."""
    for tbl in ("itemNotes", "itemAttachments", "itemData", "itemTags",
                "itemRelations", "collectionItems", "itemCreators",
                "fulltextItemWords", "fulltextItems"):
        cursor.execute(f"DELETE FROM {tbl} WHERE itemID = ?", (item_id,))
    cursor.execute("INSERT OR IGNORE INTO deletedItems(itemID) VALUES (?)", (item_id,))
    cursor.execute("DELETE FROM items WHERE itemID = ?", (item_id,))


def _delete_one_item_with_synccache(cursor, item_id):
    """删除单一条目自身 + 清理 syncCache，不涉及任何子条目。"""
    key = None
    cursor.execute("SELECT key FROM items WHERE itemID = ?", (item_id,))
    row = cursor.fetchone()
    if row:
        key = row[0]
    _delete_one_item(cursor, item_id)
    if key:
        cursor.execute(
            "DELETE FROM syncCache WHERE libraryID = 1 AND key = ? AND syncObjectTypeID = 3",
            (key,)
        )
    return 1


def _delete_with_children(cursor, item_id):
    """Delete an item and all its children, returns deleted count."""
    count = 0
    # Delete physical storage for attachments
    cursor.execute("SELECT itemID FROM itemAttachments WHERE parentItemID = ?", (item_id,))
    for (att_id,) in cursor.fetchall():
        cursor.execute("SELECT key FROM items WHERE itemID = ?", (att_id,))
        row = cursor.fetchone()
        if row:
            dir_path = os.path.join(STORAGE_PATH, row[0])
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)

    # Delete child items recursively
    for tbl in ("itemAttachments", "itemNotes"):
        cursor.execute(f"SELECT itemID FROM {tbl} WHERE parentItemID = ?", (item_id,))
        child_ids = [r[0] for r in cursor.fetchall()]
        for cid in child_ids:
            count += _delete_with_children(cursor, cid)

    key = get_key(cursor, item_id)
    _delete_one_item(cursor, item_id)
    # Clean syncCache
    if key:
        cursor.execute("DELETE FROM syncCache WHERE libraryID = 1 AND key = ? AND syncObjectTypeID = 3", (key,))
    return count + 1


def cmd_delete(cursor, item_ids):
    for item_id in item_ids:
        key = get_key(cursor, item_id)
        if not key:
            print(f"ItemID {item_id}: 在 items 表中不存在，跳过")
            continue
        type_name = get_type_name(cursor, item_id)
        title = get_title(cursor, item_id)
        confirm = input(f"确定彻底删除 {item_id} ({key}) [{type_name}] {title[:50]}? (y/N): ")
        if confirm.lower() != 'y':
            print("  跳过")
            continue

        n = _delete_with_children(cursor, item_id)
        print(f"  ✅ 已彻底删除 {item_id} ({key})，含 {n} 个子条目")


def cmd_restore(cursor, item_ids):
    for item_id in item_ids:
        in_items, in_del, _ = _item_status(cursor, item_id)
        if not in_items:
            print(f"ItemID {item_id}: 已在 items 表中不存在，无法恢复")
            continue
        if not in_del:
            print(f"ItemID {item_id}: 不在 deletedItems 中，无需恢复")
            continue
        cursor.execute("DELETE FROM deletedItems WHERE itemID = ?", (item_id,))
        key = get_key(cursor, item_id)
        title = get_title(cursor, item_id)
        print(f"  ✅ 已恢复 {item_id} ({key}) {title[:50]}")


def cmd_purge_cache(cursor):
    """清理 syncCache 中所有 type=3（条目）的缓存，防止自动重建。"""
    cursor.execute("""
        SELECT COUNT(*) FROM syncCache
        WHERE libraryID = 1 AND syncObjectTypeID = 3
    """)
    total = cursor.fetchone()[0]

    confirm = input(f"将删除 syncCache 中全部 {total} 条条目缓存，"
                    f"这将阻止 Zotero 自动恢复已删除条目。确认? (y/N): ")
    if confirm.lower() != 'y':
        print("取消")
        return

    cursor.execute("DELETE FROM syncCache WHERE libraryID = 1 AND syncObjectTypeID = 3")
    print(f"  ✅ 已清理 {total} 条 syncCache 条目缓存")


def cmd_cleanup(cursor):
    """全盘整理：删除所有名义删除条目 + 清理 syncCache 残留。"""
    print("\n===== 全盘整理 =====\n")

    # Step 1: scan
    cursor.execute("SELECT itemID FROM items ORDER BY itemID")
    all_items = [r[0] for r in cursor.fetchall()]

    nom_del = []
    for item_id in all_items:
        in_items, in_del, _ = _item_status(cursor, item_id)
        if in_items and in_del:
            nom_del.append(item_id)

    cursor.execute("""
        SELECT sc.key FROM syncCache sc
        WHERE sc.libraryID = 1 AND sc.syncObjectTypeID = 3
        AND NOT EXISTS (SELECT 1 FROM items i WHERE i.key = sc.key)
    """)
    cache_keys = [r[0] for r in cursor.fetchall()]

    if not nom_del and not cache_keys:
        print("没有需要清理的内容。所有条目状态正常。")
        return

    print(f"待处理：")
    print(f"  ⚠️  名义删除条目: {len(nom_del)} 条")
    print(f"  🔄  缓存残留:      {len(cache_keys)} 条\n")

    # 统计磁盘空间
    space_info = calc_dup_space(cursor, detailed=True)
    print()

    # 逐条列出名义删除条目
    if nom_del:
        print("── 以下条目将被删除（仅数据库记录，不涉及子条目和物理文件）──")
        for idx, item_id in enumerate(nom_del, 1):
            key = get_key(cursor, item_id)
            type_name = get_type_name(cursor, item_id)
            title = get_title(cursor, item_id)
            cursor.execute("SELECT dateAdded FROM items WHERE itemID = ?", (item_id,))
            row = cursor.fetchone()
            added = row[0][:10] if row else "—"
            cursor.execute("SELECT COUNT(*) FROM itemAttachments WHERE parentItemID = ?", (item_id,))
            att_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM itemNotes WHERE parentItemID = ?", (item_id,))
            note_cnt = cursor.fetchone()[0]
            print(f"  {idx:>3}. itemID={item_id:<6} key={key:<10} {type_name:<16} added={added} 附件={att_cnt} 笔记={note_cnt}")
            print(f"       {title[:70]}")
        print()

        confirm = input(f"是否彻底删除以上 {len(nom_del)} 条名义删除条目（删除数据库记录，不删除物理文件，不涉及子条目）? (y/N): ")
        if confirm.lower() == 'y':
            for item_id in nom_del:
                n = _delete_one_item_with_synccache(cursor, item_id)
                print(f"  ✅ 已删除 {item_id}")
        else:
            print("  跳过条目删除")
    else:
        print("✅ 无名义删除条目\n")

    # 逐条列出缓存残留
    if cache_keys:
        print(f"\n── 以下缓存残留将被清理（阻止自动重建）──")
        for idx, ck in enumerate(cache_keys, 1):
            # 尝试从 syncCache data 中提取标题
            cursor.execute(
                "SELECT data FROM syncCache WHERE libraryID = 1 AND key = ? AND syncObjectTypeID = 3 LIMIT 1",
                (ck,)
            )
            row = cursor.fetchone()
            title = ck
            if row:
                try:
                    data = json.loads(row[0])
                    title = data.get("data", {}).get("title", ck)
                except json.JSONDecodeError:
                    pass
            print(f"  {idx:>3}. key={ck:<12} {title[:60]}")

        confirm = input(f"\n是否清理以上 {len(cache_keys)} 条 syncCache 缓存？这将阻止它们被自动重建。 (y/N): ")
        if confirm.lower() == 'y':
            cursor.execute("""
                DELETE FROM syncCache WHERE libraryID = 1 AND syncObjectTypeID = 3
                AND NOT EXISTS (SELECT 1 FROM items i WHERE i.key = syncCache.key)
            """)
            print(f"  ✅ 已清理 {len(cache_keys)} 条缓存")
        else:
            print("  跳过缓存清理")

    # 清理孤立的 deletedItems 记录
    cursor.execute("""
        SELECT COUNT(*) FROM deletedItems d
        WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.itemID = d.itemID)
    """)
    isolated_count = cursor.fetchone()[0]
    if isolated_count > 0:
        cursor.execute("""
            DELETE FROM deletedItems WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.itemID = deletedItems.itemID)
        """)
        print(f"  ✅ 已清理 {isolated_count} 条孤立 deletedItems 记录")


def cmd_purge_deleteditems(cursor):
    """清理所有孤立的 deletedItems 记录（条目已不存在的残留）。"""
    cursor.execute("""
        SELECT COUNT(*) FROM deletedItems d
        WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.itemID = d.itemID)
    """)
    count = cursor.fetchone()[0]
    if count == 0:
        print("没有需要清理的孤立 deletedItems 记录。")
        return
    cursor.execute("""
        DELETE FROM deletedItems WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.itemID = deletedItems.itemID)
    """)
    print(f"  ✅ 已清理 {count} 条孤立 deletedItems 记录")


# ─── 主入口 ───────────────────────────────────────────────

COMMANDS = {
    "audit":       lambda c, a: cmd_audit(c),
    "list":        lambda c, a: cmd_list(c, [int(x) for x in a]),
    "list-all":    lambda c, a: cmd_list_all(c, " ".join(a)),
    "delete":      lambda c, a: cmd_delete(c, [int(x) for x in a]),
    "restore":     lambda c, a: cmd_restore(c, [int(x) for x in a]),
    "purge-cache": lambda c, a: cmd_purge_cache(c),
    "cleanup":     lambda c, a: cmd_cleanup(c),
    "purge-ditems": lambda c, a: cmd_purge_deleteditems(c),
    "status":      lambda c, a: cmd_list(c, [int(x) for x in a]),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    needs_args = {"list", "delete", "restore", "status"}
    if command in needs_args and len(args) < 1:
        print(f"用法: python3 {sys.argv[0]} {command} <itemID> [itemID ...]")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        should_commit = command in ("delete", "restore", "purge-cache", "cleanup")
        COMMANDS[command](cursor, args)
        if should_commit:
            conn.commit()
            print("✅ 已提交数据库更改")
    except Exception as e:
        if should_commit:
            conn.rollback()
            print(f"❌ 错误: {e}，已回滚")
        else:
            print(f"❌ 错误: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
