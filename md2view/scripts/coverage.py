#!/usr/bin/env python3
"""量一个 HTML 文件对 source blocks 的内容覆盖率。
方法：每个 block 的 raw 拆成内容片段（行/表格单元格），
归一化后看是否出现在 HTML 的纯文本里。
block 覆盖 = 片段命中率 >= 0.5。对所有被测 HTML 用同一标准。
"""
import html as htmllib
import json
import re
import sys
from html.parser import HTMLParser

MD_SYNTAX = re.compile(r'\[[ xX]\]|[#>*`|_\-\[\]()!]|\d+[.)]\s')
WS_PUNCT = re.compile(r'[\s，。：；、,.:;·—\-()（）「」“”"\'<>=/\\+*#`|_\[\]{}!?？！]')


class SourceMapParser(HTMLParser):
    """Collect source-map references and semantic element counts."""

    def __init__(self):
        super().__init__()
        self.source_ids = set()
        self.nodes = 0
        self.facts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get('class') or '').split())
        source_blocks = attrs.get('data-source-blocks')
        if source_blocks:
            self.source_ids.update(source_blocks.split())
        if 'mv-node' in classes:
            self.nodes += 1
        if 'mv-fact' in classes:
            self.facts += 1


def html_source_map(path):
    parser = SourceMapParser()
    with open(path) as f:
        parser.feed(f.read())
    parser.close()
    return parser


def norm(s):
    return WS_PUNCT.sub('', s).lower()


def html_text(path):
    with open(path) as f:
        raw = f.read()
    raw = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', raw, flags=re.S | re.I)
    raw = re.sub(r'<[^>]+>', ' ', raw)
    return norm(htmllib.unescape(raw))


def block_chunks(block):
    raw = block['raw']
    parts = []
    if block['type'] == 'table':
        for line in raw.split('\n'):
            if re.match(r'^\s*\|?\s*:?-{3,}', line):
                continue
            parts.extend(c.strip() for c in line.strip().strip('|').split('|'))
    elif block['type'] == 'code':
        for line in raw.split('\n'):
            line = line.strip()
            if line and not line.startswith('```'):
                parts.append(line)
    elif block['type'] == 'heading':
        # 标题常被改写：去编号前缀，把括号引用拆成独立片段
        line = re.sub(r'^#+\s*', '', raw)
        line = re.sub(r'^[一二三四五六七八九十\d.、\s]+', '', line)
        for seg in re.split(r'[（）()，,、:：]', line):
            parts.append(seg.strip())
    else:
        for line in raw.split('\n'):
            line = MD_SYNTAX.sub(' ', line).strip()
            # 长行再按句子切
            for seg in re.split(r'[。；;]', line):
                parts.append(seg.strip())
    chunks = [norm(p) for p in parts]
    return [c for c in chunks if len(c) >= 4]


def measure(blocks, html_path):
    text = html_text(html_path)
    source_map = html_source_map(html_path)
    covered, partial, missing = [], [], []
    chunk_total = chunk_hit = 0
    for b in blocks:
        chunks = block_chunks(b)
        if not chunks:
            continue
        hits = sum(1 for c in chunks if c in text)
        chunk_total += len(chunks)
        chunk_hit += hits
        ratio = hits / len(chunks)
        if ratio >= 0.5:
            covered.append(b['id'])
        elif ratio > 0:
            partial.append(b['id'])
        else:
            missing.append(b['id'])
    n = len(covered) + len(partial) + len(missing)
    projection_ids = [
        b['id'] for b in blocks
        if b['type'] != 'heading' and block_chunks(b)
    ]
    mapped = [block_id for block_id in projection_ids if block_id in source_map.source_ids]
    unmapped = [block_id for block_id in projection_ids if block_id not in source_map.source_ids]
    projection_total = len(projection_ids)
    return {
        'html': html_path,
        'blocks_measured': n,
        'covered': len(covered),
        'partial': len(partial),
        'missing': len(missing),
        'block_coverage': round(len(covered) / n * 100, 1),
        'chunk_coverage': round(chunk_hit / chunk_total * 100, 1),
        'missing_ids': missing,
        'partial_ids': partial,
        'source_map_measured': projection_total,
        'source_map_mapped': len(mapped),
        'source_map_coverage': round(len(mapped) / projection_total * 100, 1) if projection_total else 0.0,
        'nodes': source_map.nodes,
        'facts': source_map.facts,
        'unmapped_ids': unmapped,
    }


if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        blocks = json.load(f)
    for path in sys.argv[2:]:
        r = measure(blocks, path)
        print(f"\n== {path}")
        print(f"  block 覆盖: {r['covered']}/{r['blocks_measured']} = {r['block_coverage']}%  "
              f"(partial {r['partial']}, missing {r['missing']})")
        print(f"  chunk 覆盖: {r['chunk_coverage']}%")
        if r['missing_ids']:
            print(f"  missing: {' '.join(r['missing_ids'])}")
        print(f"  source-map 投影: {r['source_map_mapped']}/{r['source_map_measured']} = "
              f"{r['source_map_coverage']}%")
        print(f"  nodes/facts: {r['nodes']}/{r['facts']}")
        if r['unmapped_ids']:
            print(f"  unmapped: {' '.join(r['unmapped_ids'])}")
