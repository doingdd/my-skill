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

from semantic_contract import CHECK_ITEM, TABLE_ROW, derive_source_units, is_decision_table

MD_SYNTAX = re.compile(r'\[[ xX]\]|[#>*`|_\-\[\]()!]|\d+[.)]\s')
WS_PUNCT = re.compile(r'[\s，。：；、,.:;·—\-()（）「」“”"\'<>=/\\+*#`|_\[\]{}!?？！]')


class SourceMapParser(HTMLParser):
    """Collect source-map references and semantic element counts."""

    def __init__(self):
        super().__init__()
        self.source_ids = set()
        self.source_unit_ids = set()
        self.matrix_source_ids = set()
        self.stack = []
        self.flow_stack = []
        self.nodes = 0
        self.facts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get('class') or '').split())
        starts_flow = 'data-flow' in attrs
        if starts_flow:
            self.flow_stack.append(attrs.get('data-layout') == 'matrix')
        if tag not in {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
            'meta', 'param', 'source', 'track', 'wbr',
        }:
            self.stack.append((tag, starts_flow))
        source_blocks = attrs.get('data-source-blocks')
        if source_blocks:
            block_ids = source_blocks.split()
            self.source_ids.update(block_ids)
            if self.flow_stack and self.flow_stack[-1]:
                self.matrix_source_ids.update(block_ids)
        source_unit = attrs.get('data-source-unit')
        if source_unit:
            self.source_unit_ids.add(source_unit)
        if 'mv-node' in classes:
            self.nodes += 1
        if 'mv-fact' in classes:
            self.facts += 1

    def handle_endtag(self, tag):
        while self.stack:
            open_tag, starts_flow = self.stack.pop()
            if starts_flow and self.flow_stack:
                self.flow_stack.pop()
            if open_tag == tag:
                break


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
    source_units = derive_source_units(blocks)
    mapped_unit_ids = [unit_id for unit_id in source_units if unit_id in source_map.source_unit_ids]
    unmapped_unit_ids = [unit_id for unit_id in source_units if unit_id not in source_map.source_unit_ids]
    source_unit_total = len(source_units)
    decision_block_ids = {block['id'] for block in blocks if is_decision_table(block)}
    required_unit_ids = [
        unit_id
        for unit_id, unit in source_units.items()
        if unit['kind'] == CHECK_ITEM or (
            unit['kind'] == TABLE_ROW and (
                unit['blockId'] in decision_block_ids or
                unit['blockId'] in source_map.matrix_source_ids
            )
        )
    ]
    mapped_required_unit_ids = [
        unit_id for unit_id in required_unit_ids if unit_id in source_map.source_unit_ids
    ]
    unmapped_required_unit_ids = [
        unit_id for unit_id in required_unit_ids if unit_id not in source_map.source_unit_ids
    ]
    required_unit_total = len(required_unit_ids)
    return {
        'html': html_path,
        'blocks_measured': n,
        'covered': len(covered),
        'partial': len(partial),
        'missing': len(missing),
        'block_coverage': round(len(covered) / n * 100, 1) if n else 0.0,
        'chunk_coverage': round(chunk_hit / chunk_total * 100, 1) if chunk_total else 0.0,
        'missing_ids': missing,
        'partial_ids': partial,
        'source_map_measured': projection_total,
        'source_map_mapped': len(mapped),
        'source_map_coverage': round(len(mapped) / projection_total * 100, 1) if projection_total else 0.0,
        'source_unit_measured': source_unit_total,
        'source_unit_mapped': len(mapped_unit_ids),
        'source_unit_coverage': round(len(mapped_unit_ids) / source_unit_total * 100, 1) if source_unit_total else 0.0,
        'required_source_unit_measured': required_unit_total,
        'required_source_unit_mapped': len(mapped_required_unit_ids),
        'required_source_unit_coverage': round(
            len(mapped_required_unit_ids) / required_unit_total * 100,
            1,
        ) if required_unit_total else 0.0,
        'nodes': source_map.nodes,
        'facts': source_map.facts,
        'unmapped_ids': unmapped,
        'unmapped_unit_ids': unmapped_unit_ids,
        'unmapped_required_source_unit_ids': unmapped_required_unit_ids,
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
        if r['required_source_unit_measured']:
            print(f"  强制原子语义投影: {r['required_source_unit_mapped']}/"
                  f"{r['required_source_unit_measured']} = {r['required_source_unit_coverage']}%")
        if r['source_unit_measured'] > r['required_source_unit_measured']:
            print(f"  全部原子锚点投影（观察）: {r['source_unit_mapped']}/"
                  f"{r['source_unit_measured']} = {r['source_unit_coverage']}%")
        print(f"  nodes/facts: {r['nodes']}/{r['facts']}")
        if r['unmapped_ids']:
            print(f"  unmapped: {' '.join(r['unmapped_ids'])}")
        if r['unmapped_unit_ids']:
            print(f"  unmapped units: {' '.join(r['unmapped_unit_ids'])}")
        if r['unmapped_required_source_unit_ids']:
            print(f"  unmapped required units: {' '.join(r['unmapped_required_source_unit_ids'])}")
