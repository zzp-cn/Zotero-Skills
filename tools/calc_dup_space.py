#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
统计名义删除和 syncCache 残留条目占用的磁盘空间。

可作为独立脚本运行，也可被其他模块导入使用：

    from calc_dup_space import calc_dup_space, fmt_size

    cursor = conn.cursor()
    result = calc_dup_space(cursor)
    print(result["summary"])  # 纯文本报告
    print(fmt_size(result["total_bytes"]))
"""

import os
import sqlite3
from pathlib import Path
from collections import defaultdict

ZOTERO_DATA_DIR = Path(os.environ.get("ZOTERO_DATA_DIR", str(Path.home() / "Zotero")))
DB_PATH = str(ZOTERO_DATA_DIR / "zotero.sqlite")
STORAGE_PATH = ZOTERO_DATA_DIR / "storage"


def get_dir_size(path):
    """计算目录的总字节数"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except (PermissionError, FileNotFoundError):
        pass
    return total


def fmt_size(bytes_val):
    """格式化文件大小为可读字符串"""
    if bytes_val >= 1e9:
        return f"{bytes_val/1e9:.2f} GB"
    elif bytes_val >= 1e6:
        return f"{bytes_val/1e6:.2f} MB"
    elif bytes_val >= 1e3:
        return f"{bytes_val/1e3:.2f} KB"
    return f"{bytes_val} B"


def calc_dup_space(cursor, detailed=True):
    """
    统计名义删除和 syncCache 残留条目占用的磁盘空间。

    Args:
        cursor: 数据库游标
        detailed: 是否打印详细报告

    Returns:
        dict: {
            "total_bytes": int,          # 占用总字节数
            "nominal_count": int,        # 名义删除条目数
            "cache_count": int,          # syncCache 缓存残留数
            "type_counts": dict,         # 按类型分类计数
            "with_sync_count": int,      # 含 syncCache 的名义删除条目数
            "attachment_count": int,     # 关联的附件文件数
            "summary": str,              # 纯文本汇总
        }
    """
    # 1) 名义删除条目
    cursor.execute("""
        SELECT i.itemID, i.key, t.typeName AS itemType
        FROM items i
        JOIN itemTypes t ON i.itemTypeID = t.itemTypeID
        JOIN deletedItems d ON i.itemID = d.itemID
        ORDER BY i.itemID
    """)
    nominal_rows = cursor.fetchall()

    # 2) syncCache 缓存残留
    cursor.execute("""
        SELECT sc.key FROM syncCache sc
        WHERE sc.libraryID = 1 AND sc.syncObjectTypeID = 3
        AND NOT EXISTS (SELECT 1 FROM items i WHERE i.key = sc.key)
    """)
    cache_keys = set(r[0] for r in cursor.fetchall())

    # 统计名义删除条目按类型分类
    type_counts = defaultdict(int)
    for r in nominal_rows:
        type_counts[r["itemType"]] += 1

    # 统计关联附件文件大小
    total_bytes = 0
    attachment_count = 0
    attachment_details = []

    for r in nominal_rows:
        item_id = r["itemID"]
        item_key = r["key"]
        item_type = r["itemType"]

        if item_type == "attachment":
            dir_path = STORAGE_PATH / item_key
            if dir_path.exists():
                size = get_dir_size(dir_path)
                total_bytes += size
                if size > 0:
                    attachment_count += 1
                    attachment_details.append((item_id, item_key, item_type, dir_path, size))
            continue

        cursor.execute("""
            SELECT i.key FROM itemAttachments ia
            JOIN items i ON ia.itemID = i.itemID
            WHERE ia.parentItemID = ?
        """, (item_id,))
        for (att_key,) in cursor.fetchall():
            dir_path = STORAGE_PATH / att_key
            if dir_path.exists():
                size = get_dir_size(dir_path)
                total_bytes += size
                if size > 0:
                    attachment_count += 1
                    attachment_details.append((item_id, item_key, item_type, dir_path, size))

    # 含 syncCache 的名义删除条目
    cursor.execute("""
        SELECT COUNT(*) FROM items i
        JOIN deletedItems d ON i.itemID = d.itemID
        JOIN syncCache sc ON sc.libraryID = 1 AND i.key = sc.key AND sc.syncObjectTypeID = 3
    """)
    with_sync = cursor.fetchone()[0]

    # 排序
    attachment_details.sort(key=lambda x: x[4], reverse=True)

    # ── 生成报告 ──
    lines = []
    lines.append("=" * 60)
    lines.append("  磁盘空间统计")
    lines.append("=" * 60)
    lines.append(f"")
    lines.append(f"▶ 名义删除条目（UI 不可见，待彻底删除）: {len(nominal_rows)} 条")
    lines.append(f"   ├─ 文献条目 (journalArticle):  {type_counts.get('journalArticle', 0)}")
    lines.append(f"   ├─ 附件 (attachment):          {type_counts.get('attachment', 0)}")
    lines.append(f"   ├─ 笔记 (note):                {type_counts.get('note', 0)}")
    lines.append(f"   ├─ 网页 (webpage):              {type_counts.get('webpage', 0)}")
    lines.append(f"   └─ 其他:                        {type_counts.get('document', 0)}")
    lines.append(f"")
    lines.append(f"▶ syncCache 缓存残留（将被自动重建）: {len(cache_keys)} 条")
    if cache_keys and detailed:
        for k in sorted(cache_keys):
            lines.append(f"   🔄  {k}")
    lines.append(f"")
    lines.append(f"▶ 关联的 PDF 附件占用磁盘空间: {fmt_size(total_bytes)} （仅供参考，cleanup 不删除物理文件）")
    lines.append(f"   └─ 附件文件数: {attachment_count} 个")

    if attachment_details and detailed:
        lines.append(f"")
        lines.append(f"  最大的附件文件（前10）:")
        lines.append(f"  {'ItemID':>7}  {'Key':<10}  {'大小':>10}  路径")
        lines.append(f"  {'-'*7}  {'-'*10}  {'-'*10}  {'-'*50}")
        for item_id, item_key, item_type, path, size in attachment_details[:10]:
            lines.append(f"  {item_id:>7}  {item_key:<10}  {fmt_size(size):>10}  {path}")
        if len(attachment_details) > 10:
            lines.append(f"  ... 还有 {len(attachment_details) - 10} 个附件文件")

    lines.append(f"")
    lines.append(f"▶ 其中含 syncCache 残留（需要清理以防自动重建）: {with_sync} 条")
    lines.append(f"")
    lines.append(f"总计将释放磁盘空间: {fmt_size(total_bytes)}")
    lines.append(f"")

    summary = "\n".join(lines)

    if detailed:
        print(summary)

    return {
        "total_bytes": total_bytes,
        "nominal_count": len(nominal_rows),
        "cache_count": len(cache_keys),
        "type_counts": dict(type_counts),
        "with_sync_count": with_sync,
        "attachment_count": attachment_count,
        "summary": summary,
    }


def main():
    """命令行入口"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    try:
        calc_dup_space(cursor, detailed=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
