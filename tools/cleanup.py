#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
清理项目中的临时文件和缓存。

用法：
  python3 tools/cleanup.py            # 清理内部文件（保留目录结构）
  python3 tools/cleanup.py --all      # 额外清理 translations/ 内部文件
  python3 tools/cleanup.py --dry-run  # 预览将清理的内容

安全清理范围（默认）：
  - tmp/                临时脚本、提取的 PDF 文本等中间文件
  - __pycache__/        Python 字节码缓存
  - .DS_Store           macOS 目录元数据
  - tools/__pycache__/

可选清理（--all）：
  - translations/       翻译输出文件（笔记已成功写入 Zotero 后不再需要）

保留范围：
  - processed_state.json    增量处理标记
  - tools/                  工具脚本
  - .claude/                配置和 skill 文件
"""

import shutil
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

# 要清空内部文件的目录（保留目录本身）
EMPTY_DIRS = [
    PROJECT_DIR / "tmp",
    PROJECT_DIR / "translations",
]

# 要完全删除的项
REMOVE_ITEMS = [
    PROJECT_DIR / "__pycache__",
    PROJECT_DIR / ".DS_Store",
    PROJECT_DIR / "tools" / "__pycache__",
]


def empty_directory(path, dry_run):
    """清空目录内所有内容，保留目录本身。"""
    if not path.exists():
        path.mkdir(parents=True)
        return False
    if not path.is_dir():
        return False
    count = 0
    for child in path.iterdir():
        rel = child.relative_to(PROJECT_DIR)
        if dry_run:
            print(f"  📋  {rel}" + ("/" if child.is_dir() else ""))
        else:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            print(f"  🗑  {rel}" + ("/" if child.is_dir() else ""))
        count += 1
    return count > 0


def remove_item(path, dry_run):
    if not path.exists():
        return False
    rel = path.relative_to(PROJECT_DIR)
    if dry_run:
        print(f"  📋  {rel}" + ("/" if path.is_dir() else ""))
        return True
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"  🗑  {rel}" + ("/" if path.is_dir() else ""))
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    clean_all = "--all" in sys.argv

    print(f"{'=== 预览：将清理以下文件 ===' if dry_run else '=== 清理临时文件 ==='}\n")

    # 清空目录内部（保留目录）
    print("── 清空目录内部文件 ──" if not dry_run else "")
    for d in EMPTY_DIRS:
        empty_directory(d, dry_run)

    # 完全删除的项
    print("\n── 删除缓存项 ──" if not dry_run else "")
    for item in REMOVE_ITEMS:
        remove_item(item, dry_run)

    # --all 时清空 translations/
    if clean_all:
        print("\n── 清空 translations/ ──" if not dry_run else "")
        empty_directory(PROJECT_DIR / "translations", dry_run)

    if not dry_run:
        print("\n完成")


if __name__ == "__main__":
    main()
