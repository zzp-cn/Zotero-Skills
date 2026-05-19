#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
创建 Zotero 详细总结笔记 — 可复用模板

使用方法：
  方式1: python3 create_notes.py --ids 101 102 103   # 指定itemID
  方式2: python3 create_notes.py                      # 自动查增量

默认增量模式，只处理上次之后新增的未处理条目。处理完成后自动标记，下次只查增量。

依赖: zotero_utils.py（同目录）
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from zotero_utils import (get_connection, get_pdf_path, get_item_metadata,
                          create_note, find_items_without_notes, mark_processed)


def generate_summary(item_id, pdf_path, metadata):
    """
    生成详细总结的内容。
    【每次使用时重写此函数，根据文献内容生成对应的总结】

    Args:
        item_id: 文献条目ID
        pdf_path: PDF文件路径 (Path object 或 None)
        metadata: 条目元数据字典

    Returns:
        (title, note_html): 笔记标题和HTML格式的笔记内容
    """
    # ===== 在此处根据实际文献内容编写总结 =====
    title = f"（详细总结）{metadata.get('title', '')[:50]}"
    note = f"""<h1>{title}</h1>

<p><strong>来源：PDF 全文</strong></p>

<h2>摘要</h2>
<p>请在此编写详细总结内容...</p>

<h2>1. 引言</h2>
<p>...</p>

<h2>2. 实验部分</h2>
<p>...</p>

<h2>3. 结果与讨论</h2>
<p>...</p>

<h2>4. 结论</h2>
<p>...</p>
"""
    return title, note


def main():
    parser = argparse.ArgumentParser(description="为Zotero条目创建详细总结笔记")
    parser.add_argument("--ids", nargs="+", type=int, help="要处理的itemID列表")
    parser.add_argument("--all", action="store_true", help="全量扫描未处理条目")
    parser.add_argument("--since", help="从指定时间开始查找 (ISO格式)")
    args = parser.parse_args()

    conn = get_connection()
    cursor = conn.cursor()

    # 确定目标条目
    target_ids = []

    if args.ids:
        target_ids = args.ids
        print(f"指定处理 {len(target_ids)} 个条目")
    elif args.all:
        items = find_items_without_notes(cursor, since='all')
        target_ids = [item['itemID'] for item in items]
    elif args.since:
        items = find_items_without_notes(cursor, since=args.since)
        target_ids = [item['itemID'] for item in items]
    else:
        items = find_items_without_notes(cursor)  # 增量模式
        target_ids = [item['itemID'] for item in items]

    if not target_ids:
        print("没有需要处理的文献。")
        conn.close()
        return

    # 处理每个条目
    processed_ids = []
    for item_id in target_ids:
        metadata = get_item_metadata(cursor, item_id)
        pdf_path = get_pdf_path(cursor, item_id)

        print(f"\n正在处理 itemID={item_id}")
        print(f"  标题: {metadata.get('title', 'N/A')[:60]}...")
        if pdf_path:
            print(f"  PDF: {pdf_path}")
        else:
            print(f"  警告: 未找到PDF附件")

        title, note_html = generate_summary(item_id, pdf_path, metadata)
        note_id = create_note(cursor, item_id, title, note_html)
        print(f"  笔记已创建: itemID={note_id}")
        processed_ids.append(item_id)

    conn.commit()
    conn.close()

    # 标记为已处理
    mark_processed(processed_ids)
    print(f"\n全部完成！已处理 {len(processed_ids)} 个条目，已记录处理状态。")


if __name__ == "__main__":
    main()
