#!/usr/bin/env python3
"""把 markdown 切成 source blocks，输出 blocks.json。
块类型: heading / paragraph / list / table / code / quote
"""
import json
import re
import sys


def parse_blocks(text):
    lines = text.split('\n')
    blocks = []
    buf = []
    buf_type = None
    in_code = False

    def flush():
        nonlocal buf, buf_type
        if buf and buf_type:
            raw = '\n'.join(buf).strip()
            if raw:
                blocks.append({'type': buf_type, 'raw': raw})
        buf = []
        buf_type = None

    for line in lines:
        stripped = line.strip()
        if in_code:
            buf.append(line)
            if stripped.startswith('```'):
                in_code = False
                flush()
            continue
        if stripped.startswith('```'):
            flush()
            buf_type = 'code'
            buf = [line]
            in_code = True
            continue
        if not stripped:
            flush()
            continue
        if re.match(r'^#{1,6}\s', stripped):
            flush()
            depth = len(stripped) - len(stripped.lstrip('#'))
            blocks.append({'type': 'heading', 'depth': depth, 'raw': stripped})
            continue
        if stripped.startswith('|'):
            if buf_type != 'table':
                flush()
                buf_type = 'table'
            buf.append(line)
            continue
        if re.match(r'^(\s*[-*+]\s|\s*\d+[.)]\s)', line):
            if buf_type != 'list':
                flush()
                buf_type = 'list'
            buf.append(line)
            continue
        if stripped.startswith('>'):
            if buf_type != 'quote':
                flush()
                buf_type = 'quote'
            buf.append(line)
            continue
        if buf_type in ('list', 'quote'):  # 续行归属前块
            buf.append(line)
            continue
        if buf_type != 'paragraph':
            flush()
            buf_type = 'paragraph'
        buf.append(line)
    flush()

    return [{'id': f'b{i:03d}', **b} for i, b in enumerate(blocks)]


if __name__ == '__main__':
    src = sys.argv[1]
    with open(src) as f:
        blocks = parse_blocks(f.read())
    out = sys.argv[2] if len(sys.argv) > 2 else 'blocks.json'
    with open(out, 'w') as f:
        json.dump(blocks, f, ensure_ascii=False, indent=1)
    from collections import Counter
    print(f'{len(blocks)} blocks:', dict(Counter(b['type'] for b in blocks)))
