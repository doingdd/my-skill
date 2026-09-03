#!/usr/bin/env python3
"""md2view v4 源侧工具:Markdown 块的确定性 HTML 渲染 + 原子 source unit 提取。

左栏是权威原文,必须 100% 忠实,因此渲染是确定性的,模型不参与。
"""
import html as htmllib
import re

TABLE_ROW = 'table-row'
CHECK_ITEM = 'check-item'


def esc(s):
    return htmllib.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s


def list_item(text):
    task = re.match(r'^\[([ xX])\]\s+(.*)$', text)
    if not task:
        return inline(text)
    checked = ' checked' if task.group(1).lower() == 'x' else ''
    return '<input type="checkbox" disabled%s> %s' % (checked, inline(task.group(2)))


def render_list(raw):
    """Render the indentation hierarchy retained in a parsed Markdown list block."""
    tokens = []
    for line in raw.split('\n'):
        match = re.match(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$', line)
        if match:
            tokens.append({
                'indent': len(match.group(1).expandtabs(4)),
                'ordered': match.group(2)[0].isdigit(),
                'text': match.group(3),
            })
        elif line.strip() and tokens:
            tokens[-1]['text'] += ' ' + line.strip()

    def level(index, indent):
        ordered = tokens[index]['ordered']
        tag = 'ol' if ordered else 'ul'
        items = []
        while index < len(tokens):
            token = tokens[index]
            if token['indent'] != indent or token['ordered'] != ordered:
                break
            index += 1
            children = []
            while index < len(tokens) and tokens[index]['indent'] > indent:
                child, index = level(index, tokens[index]['indent'])
                children.append(child)
            items.append('<li>%s%s</li>' % (list_item(token['text']), ''.join(children)))
        return '<%s>%s</%s>' % (tag, ''.join(items), tag), index

    rendered = []
    index = 0
    while index < len(tokens):
        part, index = level(index, tokens[index]['indent'])
        rendered.append(part)
    return ''.join(rendered)


def render_block(b):
    """一个源块 → 左栏 HTML,带 data-block 锚点。"""
    t = b['type']
    raw = b['raw']
    bid = b['id']
    if t == 'heading':
        depth = min(max(b.get('depth', 2), 1), 6)
        text = re.sub(r'^#+\s*', '', raw)
        inner = '<h%d>%s</h%d>' % (depth, inline(text), depth)
    elif t == 'rule':
        inner = '<hr>'
    elif t == 'quote':
        text = re.sub(r'^\s*>\s?', '', raw, flags=re.M)
        inner = '<blockquote>%s</blockquote>' % inline(text)
    elif t == 'code':
        body = re.sub(r'^```[^\n]*\n?|```$', '', raw).rstrip()
        inner = '<pre><code>%s</code></pre>' % esc(body)
    elif t == 'list':
        inner = render_list(raw)
    elif t == 'table':
        rows = []
        for line in raw.split('\n'):
            if re.match(r'^\s*\|?\s*:?-{3,}', line):
                continue
            if '|' not in line:
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            rows.append(cells)
        if rows:
            head = ''.join('<th>%s</th>' % inline(c) for c in rows[0])
            body = ''.join(
                '<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in r)
                for r in rows[1:]
            )
            inner = ('<div class="tbl-scroll"><table><thead><tr>%s</tr></thead>'
                     '<tbody>%s</tbody></table></div>' % (head, body))
        else:
            inner = ''
    else:
        inner = '<p>%s</p>' % inline(raw)
    return '<div class="src-block" data-block="%s">%s</div>' % (bid, inner)


def _is_table_separator(line):
    return bool(re.match(r'^\s*\|?[\s:|-]+\|?\s*$', line)) and '-' in line


def _table_cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def source_units_for_block(block):
    """表格数据行与 checkbox 项的稳定原子锚点,不改变父 block id。"""
    block_id = block['id']
    raw = block.get('raw', '')
    if block.get('type') == 'table':
        lines = [line for line in raw.splitlines() if '|' in line and not _is_table_separator(line)]
        rows = lines[1:] if lines else []
        units = []
        for index, line in enumerate(rows, 1):
            cells = _table_cells(line)
            if not cells or not any(cells):
                continue
            units.append({
                'id': f'{block_id}:r{index:03d}',
                'kind': TABLE_ROW,
                'key': cells[0] or f'第 {index} 行',
                'raw': line.strip(),
            })
        return units
    if block.get('type') == 'list':
        units = []
        for line in raw.splitlines():
            match = re.match(r'^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]\s+(.+?)\s*$', line)
            if not match:
                continue
            index = len(units) + 1
            units.append({
                'id': f'{block_id}:i{index:03d}',
                'kind': CHECK_ITEM,
                'key': match.group(2),
                'raw': line.strip(),
                'checked': match.group(1).lower() == 'x',
            })
        return units
    return []
