#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Chokpun
"""
从 tmp/all_texts.json 中提取各文献的 PDF 文本，
保存为 tmp/paper_{itemID}.txt。
"""
import json
from pathlib import Path

JSON_PATH = Path(__file__).parent / "tmp" / "all_texts.json"
OUTPUT_DIR = Path(__file__).parent / "tmp"


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    OUTPUT_DIR.mkdir(exist_ok=True)

    for item_id, entry in data.items():
        text = entry.get("pdf_text")
        if text:
            out = OUTPUT_DIR / f"paper_{item_id}.txt"
            out.write_text(text, encoding="utf-8")
            print(f"paper_{item_id}.txt: {len(text)} chars")
        else:
            print(f"paper_{item_id}.txt: 无文本 (跳过)")


if __name__ == "__main__":
    main()
