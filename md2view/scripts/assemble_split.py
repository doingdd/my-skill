#!/usr/bin/env python3
"""双栏同步阅读器：左栏原文线性渲染 + 右栏信息重组，滚动锚定同步 + 高亮 + 单栏切换。
blocks.json（左栏源）+ fragments 目录（右栏视图，带 data-source-blocks）-> reader.html
两栏通过 block id 建立映射：左栏每块 data-block-id，右栏每元素 data-source-blocks。
"""
import html as htmllib
import json
import os
import re
import sys
from html.parser import HTMLParser


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
    t = b['type']
    raw = b['raw']
    bid = b['id']
    if t == 'heading':
        depth = min(max(b.get('depth', 2), 1), 6)
        text = re.sub(r'^#+\s*', '', raw)
        inner = '<h%d>%s</h%d>' % (depth, inline(text), depth)
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
            body = ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in r) for r in rows[1:])
            inner = '<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (head, body)
        else:
            inner = ''
    else:
        inner = '<p>%s</p>' % inline(raw)
    return '<div class="src-block" data-block-id="%s">%s</div>' % (bid, inner)


class FragmentContract(HTMLParser):
    """Collect fragment-v2 semantics and reject geometry owned by the runtime."""

    def __init__(self, source_ids):
        super().__init__()
        self.source_ids = source_ids
        self.stack = []
        self.flow_stack = []
        self.flows = []
        self.has_flow = False
        self.problems = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get('class', '').split())
        starts_flow = 'data-flow' in attrs
        if starts_flow:
            self.has_flow = True
            flow = {'nodes': {}, 'facts': {}, 'edges': [], 'layout': attrs.get('data-layout')}
            self.flows.append(flow)
            self.flow_stack.append(flow)
            if not flow['layout']:
                self.problems.append('data-flow 缺少 data-layout')
        in_flow = bool(self.flow_stack)
        flow = self.flow_stack[-1] if self.flow_stack else None
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, starts_flow))
        if tag == 'script':
            self.problems.append('fragment 不得自带 script')
        if in_flow and tag in {'path', 'line', 'polyline'}:
            self.problems.append('data-flow 内不得手写 <%s> 连线' % tag)
        mapped_source = attrs.get('data-source-blocks')
        source = mapped_source.split() if mapped_source is not None else []
        if mapped_source is not None:
            unknown = [bid for bid in source if bid not in self.source_ids]
            if unknown:
                self.problems.append('data-source-blocks 引用了不存在的源块: %s' % ', '.join(unknown))
        if 'mv-node' in classes:
            node_id = attrs.get('data-node-id')
            if not flow:
                self.problems.append('mv-node 必须位于 data-flow 内')
            if not node_id:
                self.problems.append('mv-node 缺少 data-node-id')
            elif flow and node_id in flow['nodes']:
                self.problems.append('重复 data-node-id: %s' % node_id)
            elif flow:
                flow['nodes'][node_id] = source
            if not source:
                self.problems.append('%s 缺少 data-source-blocks' % (node_id or 'mv-node'))
        if 'mv-fact' in classes:
            fact_id = attrs.get('data-fact-id')
            if not flow:
                self.problems.append('mv-fact 必须位于 data-flow 内')
            if not fact_id:
                self.problems.append('mv-fact 缺少 data-fact-id')
            elif flow and fact_id in flow['facts']:
                self.problems.append('重复 data-fact-id: %s' % fact_id)
            elif flow:
                flow['facts'][fact_id] = source
            if not source:
                self.problems.append('%s 缺少 data-source-blocks' % (fact_id or 'mv-fact'))
        if 'mv-edge' in classes:
            from_id, to_id = attrs.get('data-from'), attrs.get('data-to')
            if not flow:
                self.problems.append('mv-edge 必须位于 data-flow 内')
            if not from_id or not to_id:
                self.problems.append('mv-edge 缺少 data-from/data-to')
            elif flow:
                flow['edges'].append((from_id, to_id))
            if 'hidden' not in attrs:
                self.problems.append('mv-edge 必须 hidden，仅声明关系')

    def handle_endtag(self, tag):
        while self.stack:
            open_tag, starts_flow = self.stack.pop()
            if starts_flow:
                if self.flow_stack:
                    self.flow_stack.pop()
            if open_tag == tag:
                break


def validate_fragment(fragment, view, source_ids):
    parser = FragmentContract(source_ids)
    parser.feed(fragment)
    if not parser.has_flow:
        parser.problems.append('fragment v2 缺少 data-flow 语义作用域')
        raise ValueError('%s fragment 合同失败:\n- %s' % (view['id'], '\n- '.join(parser.problems)))
    expected_nodes = {}
    for element in view.get('elements', []):
        node_id = element.get('id')
        if not node_id:
            parser.problems.append('views.json element 缺少 id')
            continue
        if node_id in expected_nodes:
            parser.problems.append('views.json 重复 element id: %s' % node_id)
        sources = element.get('sourceBlockIds', [])
        if not sources:
            parser.problems.append('%s 缺少 sourceBlockIds' % node_id)
        unknown = [bid for bid in sources if bid not in source_ids]
        if unknown:
            parser.problems.append('%s 引用了不存在的源块: %s' % (node_id, ', '.join(unknown)))
        expected_nodes[node_id] = set(sources)
    actual_node_items = [(node, set(sources)) for flow in parser.flows for node, sources in flow['nodes'].items()]
    actual_nodes = {node: sources for node, sources in actual_node_items}
    duplicate_nodes = sorted(node for node in actual_nodes if sum(1 for key, _ in actual_node_items if key == node) > 1)
    if duplicate_nodes:
        parser.problems.append('跨 data-flow 重复 data-node-id: %s' % ', '.join(duplicate_nodes))
    missing_nodes = sorted(set(expected_nodes) - set(actual_nodes))
    extra_nodes = sorted(set(actual_nodes) - set(expected_nodes))
    if missing_nodes:
        parser.problems.append('缺少 views.json 节点: %s' % ', '.join(missing_nodes))
    if extra_nodes:
        parser.problems.append('出现 views.json 外节点: %s' % ', '.join(extra_nodes))
    for node_id in sorted(set(expected_nodes) & set(actual_nodes)):
        if expected_nodes[node_id] != actual_nodes[node_id]:
            parser.problems.append('%s 的 data-source-blocks 与 views.json 不一致: 期望 %s，实际 %s' % (
                node_id, ' '.join(sorted(expected_nodes[node_id])), ' '.join(sorted(actual_nodes[node_id]))))

    expected_facts = {}
    scoped_facts = list(view.get('facts', []))
    for element in view.get('elements', []):
        scoped_facts.extend(element.get('facts', []))
    for fact in scoped_facts:
        fact_id = fact.get('id')
        if not fact_id:
            parser.problems.append('views.json fact 缺少 id')
            continue
        if fact_id in expected_facts:
            parser.problems.append('views.json 重复 fact id: %s' % fact_id)
        sources = fact.get('sourceBlockIds', [])
        if not sources:
            parser.problems.append('%s 缺少 sourceBlockIds' % fact_id)
        unknown = [bid for bid in sources if bid not in source_ids]
        if unknown:
            parser.problems.append('%s 引用了不存在的源块: %s' % (fact_id, ', '.join(unknown)))
        expected_facts[fact_id] = set(sources)
    actual_fact_items = [(fact, set(sources)) for flow in parser.flows for fact, sources in flow['facts'].items()]
    actual_facts = {fact: sources for fact, sources in actual_fact_items}
    duplicate_facts = sorted(fact for fact in actual_facts if sum(1 for key, _ in actual_fact_items if key == fact) > 1)
    if duplicate_facts:
        parser.problems.append('跨 data-flow 重复 data-fact-id: %s' % ', '.join(duplicate_facts))
    missing_facts = sorted(set(expected_facts) - set(actual_facts))
    extra_facts = sorted(set(actual_facts) - set(expected_facts))
    if missing_facts:
        parser.problems.append('缺少 views.json facts: %s' % ', '.join(missing_facts))
    if extra_facts:
        parser.problems.append('出现 views.json 外 facts: %s' % ', '.join(extra_facts))
    for fact_id in sorted(set(expected_facts) & set(actual_facts)):
        if expected_facts[fact_id] != actual_facts[fact_id]:
            parser.problems.append('%s 的 data-source-blocks 与 views.json 不一致: 期望 %s，实际 %s' % (
                fact_id, ' '.join(sorted(expected_facts[fact_id])), ' '.join(sorted(actual_facts[fact_id]))))
    expected_edges = {(edge['from'], edge['to']) for edge in view.get('relations', [])}
    actual_edges = {edge for flow in parser.flows for edge in flow['edges']}
    missing_edges = sorted(expected_edges - actual_edges)
    extra_edges = sorted(actual_edges - expected_edges)
    if missing_edges:
        parser.problems.append('缺少 views.json 关系: %s' % ', '.join('%s→%s' % edge for edge in missing_edges))
    if extra_edges:
        parser.problems.append('出现 views.json 外关系: %s' % ', '.join('%s→%s' % edge for edge in extra_edges))
    for index, flow in enumerate(parser.flows, 1):
        dangling = sorted({node for edge in flow['edges'] for node in edge if node not in flow['nodes']})
        if dangling:
            parser.problems.append('第 %d 个 data-flow 的关系引用不存在节点: %s' % (index, ', '.join(dangling)))
    if parser.problems:
        raise ValueError('%s fragment v2 合同失败:\n- %s' % (view['id'], '\n- '.join(parser.problems)))


CSS = """
:root{--bg:#f3f0e8;--surface:#fffefa;--surface-2:#f8f5ed;--text:#191816;--muted:#716b61;
--accent:#a2441e;--accent-strong:#773015;--accent-soft:#f2dfd3;--border:#dcd5c8;--ink:#1f2323;
--good:#37634a;--good-soft:#e2eee6;--warn:#a96716;--warn-soft:#f5ead5;
--font:'Songti SC','Source Han Serif SC','Noto Serif CJK SC',Georgia,serif;
--sans:'Avenir Next','PingFang SC','Hiragino Sans GB','Noto Sans CJK SC',sans-serif;
--mono:'SFMono-Regular','Cascadia Code','Roboto Mono',Menlo,monospace;
--source-ratio:42%;--header-h:58px;--ease:cubic-bezier(.22,.8,.3,1)}
*{box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.58}
button{font:inherit}
header.bar{height:var(--header-h);display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 18px 0 22px;
border-bottom:1px solid var(--border);background:color-mix(in srgb,var(--surface) 94%,transparent);backdrop-filter:blur(16px);position:relative;z-index:20}
header.bar .brand{font-family:var(--font);font-weight:700;font-size:16px;letter-spacing:-.015em;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
header.bar .brand small{font-weight:500;color:var(--muted);font-size:10px;margin-left:10px;font-family:var(--mono);letter-spacing:.02em}
.toolbar{display:flex;align-items:center;gap:8px;flex:none}
.sync-status{min-width:118px;text-align:right;color:var(--muted);font:10.5px/1.3 var(--mono);letter-spacing:.02em;white-space:nowrap}
.sync-status::before{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:7px;background:var(--good);box-shadow:0 0 0 3px var(--good-soft);vertical-align:1px}
.modes{display:flex;gap:2px;background:#e9e4d9;border:1px solid #dfd8cb;border-radius:11px;padding:3px;box-shadow:inset 0 1px 2px rgba(31,25,19,.05)}
.modes button{min-height:28px;border:0;background:transparent;padding:4px 11px;border-radius:8px;cursor:pointer;font-size:11.5px;color:var(--muted);transition:color 120ms,background 160ms,box-shadow 160ms,transform 80ms}
.modes button:hover{color:var(--text)}.modes button:active{transform:translateY(1px)}
.modes button.on,.modes button[aria-pressed=true]{background:var(--surface);color:var(--accent-strong);font-weight:650;box-shadow:0 1px 5px rgba(37,28,19,.12)}
.modes button:focus-visible,.splitter:focus-visible,[data-source-blocks]:focus-visible,[data-block-id]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
#split{display:grid;grid-template-columns:minmax(320px,var(--source-ratio)) 12px minmax(420px,1fr);height:calc(100vh - var(--header-h));min-width:0;background:var(--surface-2)}
#split.only-l{grid-template-columns:minmax(0,1fr) 0 0}#split.only-r{grid-template-columns:0 0 minmax(0,1fr)}
.pane{overflow-y:auto;overflow-x:hidden;height:100%;position:relative;scroll-behavior:auto;min-width:0;overscroll-behavior:contain;scrollbar-gutter:stable}
#paneL{grid-column:1;background:var(--surface)}#paneR{grid-column:3;background-color:var(--surface-2);background-image:radial-gradient(circle at 1px 1px,rgba(61,51,40,.075) 1px,transparent 0);background-size:22px 22px}
.only-l #paneR,.only-r #paneL{display:none}
.splitter{grid-column:2;position:relative;z-index:12;cursor:col-resize;touch-action:none;background:linear-gradient(90deg,transparent 5px,var(--border) 5px,var(--border) 6px,transparent 6px)}
.splitter::before{content:'';position:absolute;top:50%;left:3px;width:6px;height:48px;transform:translateY(-50%);border-radius:9px;background:var(--surface);border:1px solid var(--border);box-shadow:0 2px 9px rgba(31,25,19,.13);transition:height 160ms var(--ease),border-color 120ms,background 120ms}
.splitter::after{content:'⋮';position:absolute;top:50%;left:0;width:12px;transform:translateY(-53%);text-align:center;color:var(--muted);font:16px/1 var(--mono)}
.splitter:hover::before,.splitter:focus-visible::before,.splitter.is-dragging::before{height:66px;border-color:var(--accent);background:var(--accent-soft)}
.only-l .splitter,.only-r .splitter{display:none}
.pane-tag{position:sticky;top:0;display:flex;align-items:center;gap:8px;background:linear-gradient(var(--surface),var(--surface) 72%,transparent);padding:10px 28px 8px;font:9.5px/1.3 var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--accent);z-index:8}
#paneR .pane-tag{background:linear-gradient(var(--surface-2),var(--surface-2) 72%,transparent)}
.pane-tag::before{content:'';width:18px;height:1px;background:currentColor}
#paneL .doc{padding:0 clamp(20px,3.2vw,38px) 110px;max-width:800px;margin:0 auto}
#paneL .doc h1{font-family:var(--font);font-size:clamp(23px,2.2vw,30px);line-height:1.22;margin:15px 0 10px;letter-spacing:-.025em}
#paneL .doc h2{font-family:var(--font);font-size:19px;line-height:1.3;margin:24px 0 8px;padding-top:10px;border-top:1px solid var(--border)}
#paneL .doc h3{font-size:15px;margin:17px 0 6px}#paneL .doc p{margin:6px 0}
#paneL .doc blockquote{border-left:3px solid var(--accent);margin:10px 0;padding:6px 12px;background:var(--accent-soft);color:var(--text);border-radius:0 8px 8px 0}
#paneL .doc code{font-family:var(--mono);font-size:.84em;background:var(--accent-soft);padding:1px 5px;border-radius:4px}
#paneL .doc pre{background:var(--ink);color:#eee9df;padding:11px 13px;border-radius:9px;overflow-x:auto;font-size:11.5px}
#paneL .doc pre code{background:none;padding:0;color:inherit}
#paneL .doc table{width:100%;border-collapse:collapse;font-size:12px;margin:10px 0;border:1px solid var(--border)}
#paneL .doc th{background:var(--accent-soft);color:var(--muted);text-align:left;font-size:10.5px;text-transform:uppercase}
#paneL .doc th,#paneL .doc td{padding:6px 8px;border-bottom:1px solid var(--border);vertical-align:top}
#paneL .doc ul,#paneL .doc ol{padding-left:20px}#paneL .doc li{margin:2px 0}
.src-block{scroll-margin-top:62px;border-radius:7px;transition:background 180ms,box-shadow 180ms,opacity 180ms;padding:1px 6px;margin:0 -6px;cursor:pointer}
#paneR .doc{padding:6px clamp(18px,2.5vw,38px) 112px;max-width:1280px;margin:0 auto}
section.view{margin:0 0 46px;scroll-margin-top:60px;opacity:0;transform:translateY(10px);transition:opacity 360ms var(--ease),transform 360ms var(--ease)}
section.view.in{opacity:1;transform:none}
section.view>h2{font-family:var(--font);font-size:clamp(20px,1.8vw,25px);line-height:1.2;margin:0 0 4px;display:flex;gap:9px;align-items:baseline;letter-spacing:-.02em}
section.view>h2 .n{font-family:var(--mono);font-size:9.5px;color:var(--accent);letter-spacing:.11em}
section.view .insight{color:var(--muted);font-size:12.5px;margin:0 0 10px;max-width:760px}
section.view .compressed-out{font-size:11px;color:var(--muted);margin-top:9px;padding-left:10px;border-left:2px solid var(--border)}
[data-source-blocks]{scroll-margin-top:62px}
.mv-flow{position:relative;isolation:isolate;min-width:0;padding:clamp(14px,1.9vw,22px);border:1px solid var(--border);border-radius:14px;background:color-mix(in srgb,var(--surface) 96%,transparent);box-shadow:0 10px 28px rgba(46,37,26,.06);overflow:hidden;container-type:inline-size}
.mv-flow::before{content:'';position:absolute;inset:0;z-index:-2;background:linear-gradient(115deg,rgba(162,68,30,.035),transparent 38%),linear-gradient(rgba(35,31,25,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(35,31,25,.035) 1px,transparent 1px);background-size:auto,28px 28px,28px 28px;mask-image:linear-gradient(to bottom,#000,transparent 92%)}
.mv-flow[data-layout=vertical]{display:grid;gap:22px}.mv-flow[data-layout=horizontal]{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(160px,1fr);gap:24px}.mv-flow[data-layout=lanes]{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:17px}
.mv-lane{position:relative;z-index:auto;min-width:0;padding:10px;border:1px solid color-mix(in srgb,var(--border) 82%,transparent);border-radius:11px;background:color-mix(in srgb,var(--surface) 84%,transparent)}
.mv-lane-title{display:flex;align-items:center;gap:7px;margin:0 0 7px;color:var(--muted);font:650 9.5px/1.2 var(--mono);letter-spacing:.11em;text-transform:uppercase}
.mv-lane-title::before{content:'';width:14px;height:2px;background:var(--accent)}
.mv-node{appearance:none;position:relative;z-index:3;display:grid;grid-template-columns:minmax(4.5em,max-content) minmax(0,1fr);align-items:baseline;column-gap:10px;row-gap:2px;width:100%;min-width:0;padding:10px 28px 10px 14px;border:1px solid #d9d1c3;border-radius:9px;background:var(--surface);color:var(--text);text-align:left;box-shadow:0 3px 10px rgba(44,34,24,.055);cursor:pointer;transition:box-shadow 160ms,border-color 120ms,background 120ms,opacity 220ms var(--ease)}
.mv-node::before{content:'';position:absolute;left:-1px;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--accent)}
.mv-node::after{content:attr(data-node-index);position:absolute;right:9px;top:7px;color:#aca397;font:8.5px/1 var(--mono);letter-spacing:.04em}
.mv-node:hover{border-color:color-mix(in srgb,var(--accent) 45%,var(--border));box-shadow:0 10px 24px rgba(44,34,24,.11)}
.mv-node:active{box-shadow:0 3px 10px rgba(44,34,24,.09)}
.mv-node[data-tone=good]::before{background:var(--good)}.mv-node[data-tone=warn]::before{background:var(--warn)}
.mv-node-title{margin:0;min-width:0;font:700 13px/1.28 var(--sans);letter-spacing:-.01em;white-space:nowrap}.mv-node-detail{margin:0;min-width:0;color:var(--muted);font-size:11px;line-height:1.35;overflow-wrap:anywhere}
.mv-node-meta{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.mv-node-meta span{display:inline-flex;align-items:center;min-height:17px;padding:1px 6px;border-radius:999px;background:var(--accent-soft);color:var(--accent-strong);font:600 9.5px/1.2 var(--mono)}
.mv-fact-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:7px;margin:9px 0 0}
.mv-fact{min-width:0;padding:7px 9px;border:1px solid color-mix(in srgb,var(--border) 84%,transparent);border-radius:8px;background:color-mix(in srgb,var(--surface) 90%,transparent);cursor:pointer;transition:background 140ms,border-color 140ms,box-shadow 140ms}
.mv-fact:hover{border-color:color-mix(in srgb,var(--accent) 42%,var(--border));box-shadow:0 5px 14px rgba(44,34,24,.07)}
.mv-fact-label,.mv-fact>strong{display:block;margin:0 0 2px;color:var(--text);font:700 11.5px/1.25 var(--sans)}
.mv-fact-value,.mv-fact>span{display:block;color:var(--muted);font-size:10.5px;line-height:1.35;overflow-wrap:anywhere}
.mv-edge{display:none!important}
.mv-edge-layer{position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none;overflow:visible}
.mv-edge-path{fill:none;stroke:#837a6e;stroke-width:1.65;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;opacity:.82;transition:stroke 160ms,stroke-width 160ms,opacity 160ms,stroke-dashoffset 460ms var(--ease)}
.mv-edge-path[data-kind=guards]{stroke:var(--good)}.mv-edge-path[data-kind=escalates]{stroke:var(--warn)}.mv-edge-path[data-kind=produces]{stroke:var(--accent)}
.mv-edge-path.is-active{stroke:var(--accent-strong);stroke-width:2.6;opacity:1}.mv-edge-path.is-muted{opacity:.2}
.mv-edge-label{font:600 9.5px var(--mono);fill:var(--muted);stroke:var(--surface);stroke-width:5px;paint-order:stroke fill;stroke-linejoin:round;text-anchor:middle;dominant-baseline:central;letter-spacing:.02em}
.mv-edge-label.is-active{fill:var(--accent-strong)}
.mv-flow:not(.is-ready) .mv-node{opacity:0}
.mv-flow.is-ready .mv-node{transition-delay:calc(var(--mv-index,0) * 24ms)}
.sync-hi,.is-preview{background:color-mix(in srgb,var(--accent) 10%,var(--surface))!important;box-shadow:0 0 0 1.5px color-mix(in srgb,var(--accent) 75%,transparent)!important;border-radius:8px}
.is-pinned{background:color-mix(in srgb,var(--accent) 14%,var(--surface))!important;box-shadow:0 0 0 2px var(--accent)!important;border-radius:8px}
.mv-node.is-pinned{border-color:var(--accent);box-shadow:0 11px 28px rgba(119,48,21,.16)!important}
.hint{position:fixed;bottom:16px;left:50%;transform:translate(-50%,8px);background:var(--ink);color:#fffefa;font:11px/1.35 var(--mono);padding:8px 14px;border-radius:999px;opacity:0;z-index:30;pointer-events:none;transition:opacity 220ms,transform 220ms var(--ease);box-shadow:0 8px 24px rgba(0,0,0,.18)}
.hint.show{opacity:.92;transform:translate(-50%,0)}
@media(max-width:899px){
  :root{--header-h:54px}header.bar{padding:0 12px 0 15px}.brand small,.sync-status{display:none}.modes button{padding-inline:11px}.modes button[data-md2view-mode=both]{display:none}
  #split,#split.only-l,#split.only-r{display:grid;grid-template-columns:minmax(0,1fr);height:calc(100vh - var(--header-h))}.splitter{display:none}
  #split:not(.only-l):not(.only-r) #paneL{display:none}.only-l #paneL,.only-r #paneR{display:block}
  #paneL,#paneR{grid-column:1;grid-row:1}.pane-tag{padding-inline:16px}#paneL .doc,#paneR .doc{padding-inline:16px}
}
@media(max-width:560px){header.bar .brand{max-width:44vw;font-size:14px}.modes button{font-size:11px;padding-inline:9px}.mv-flow{padding:12px;border-radius:12px}}
@container(max-width:620px){.mv-flow[data-layout=horizontal],.mv-flow[data-layout=lanes]{grid-auto-flow:row;grid-template-columns:minmax(0,1fr);grid-auto-columns:auto}}
@container(max-width:520px){.mv-node{grid-template-columns:minmax(0,1fr);padding-right:24px}.mv-node-title{white-space:normal}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation:none!important;transition-duration:.001ms!important;transition-delay:0ms!important}section.view{opacity:1;transform:none}.mv-flow:not(.is-ready) .mv-node{opacity:1}}
"""

JS = """
(function(){
  'use strict';
  var wrap=document.getElementById('split'),L=document.getElementById('paneL'),R=document.getElementById('paneR');
  var separator=document.querySelector('[data-md2view-separator]');
  var status=document.querySelector('[data-md2view-status]');
  var hint=document.querySelector('.hint');
  var compact=window.matchMedia('(max-width:899px)');
  var reduced=window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  var driver=null,lock=false,pinned=null,pendingReveal=null,previewed=[],syncEls=[],drawQueued=false;
  var rIndex={},lIndex={};
  function idsOf(el){return (el.getAttribute('data-source-blocks')||'').trim().split(/\\s+/).filter(Boolean);}
  R.querySelectorAll('[data-source-blocks]:not(.mv-edge)').forEach(function(el){
    idsOf(el).forEach(function(bid){(rIndex[bid]||(rIndex[bid]=[])).push(el);});
    if(!el.matches('button,a,input,select,textarea,[tabindex]'))el.tabIndex=0;
    if(!el.hasAttribute('role')&&!el.matches('button,a,input,select,textarea'))el.setAttribute('role','button');
    if(!el.hasAttribute('aria-label'))el.setAttribute('aria-label','定位原文：'+(el.getAttribute('data-label')||el.textContent.trim().slice(0,24)));
  });
  Object.keys(rIndex).forEach(function(bid){
    rIndex[bid].sort(function(a,b){var af=a.classList.contains('mv-fact')?0:1,bf=b.classList.contains('mv-fact')?0:1;return af-bf||idsOf(a).length-idsOf(b).length;});
  });
  L.querySelectorAll('[data-block-id]').forEach(function(el){
    var bid=el.getAttribute('data-block-id');lIndex[bid]=el;el.tabIndex=0;el.setAttribute('role','button');el.setAttribute('aria-label','定位信息重组：'+bid);
  });
  function setStatus(text){if(status)status.textContent=text;}
  function flashHint(text){if(!hint)return;hint.textContent=text;hint.classList.add('show');clearTimeout(flashHint.timer);flashHint.timer=setTimeout(function(){hint.classList.remove('show');},2200);}
  function storageGet(key){try{return localStorage.getItem(key);}catch(e){return null;}}
  function storageSet(key,value){try{localStorage.setItem(key,value);}catch(e){}}
  function anchorOf(pane,attr){
    var mid=pane.getBoundingClientRect().top+pane.clientHeight*.30,best=null,bd=1e9;
    pane.querySelectorAll('['+attr+']').forEach(function(el){var rect=el.getBoundingClientRect(),d=Math.abs(rect.top-mid);if(rect.height>0&&d<bd){bd=d;best=el;}});
    return best;
  }
  function clearClass(list,name){while(list.length)list.pop().classList.remove(name);}
  function mark(list,el,name){if(el&&!el.classList.contains(name)){el.classList.add(name);list.push(el);}}
  function align(dst,target,anchor,src,behavior){
    var aOff=anchor.getBoundingClientRect().top-src.getBoundingClientRect().top;
    var tOff=target.getBoundingClientRect().top-dst.getBoundingClientRect().top+dst.scrollTop;
    dst.scrollTo({top:Math.max(0,tOff-aOff),behavior:behavior||'auto'});
  }
  function revealTarget(pane,target){
    if(!pane||!target||getComputedStyle(pane).display==='none')return false;
    var paneRect=pane.getBoundingClientRect(),targetRect=target.getBoundingClientRect();
    if(!paneRect.height||!targetRect.height)return false;
    var top=targetRect.top-paneRect.top+pane.scrollTop-pane.clientHeight*.36;
    pane.scrollTo({top:Math.max(0,top),behavior:reduced?'auto':'smooth'});return true;
  }
  function revealPending(){if(pendingReveal&&revealTarget(pendingReveal.pane,pendingReveal.target))pendingReveal=null;}
  function queueReveal(pane,target){pendingReveal={pane:pane,target:target};requestAnimationFrame(function(){requestAnimationFrame(revealPending);});}
  function sync(from){
    if(lock||pinned||compact.matches)return;lock=true;clearClass(syncEls,'sync-hi');
    if(from==='L'){
      var a=anchorOf(L,'data-block-id'),targets=a&&rIndex[a.getAttribute('data-block-id')];
      if(a&&targets&&targets[0]){align(R,targets[0],a,L);mark(syncEls,a,'sync-hi');mark(syncEls,targets[0],'sync-hi');}
    }else{
      var a2=anchorOf(R,'data-source-blocks'),bid=a2&&idsOf(a2)[0],target=bid&&lIndex[bid];
      if(a2&&target){align(L,target,a2,R);mark(syncEls,target,'sync-hi');mark(syncEls,a2,'sync-hi');}
    }
    setTimeout(function(){lock=false;},80);
  }
  function setEdgeFocus(node){
    var nodeId=node&&node.getAttribute('data-node-id'),flow=node&&node.closest('[data-flow]');
    document.querySelectorAll('.mv-edge-path').forEach(function(path){
      var sameFlow=flow&&path.closest('[data-flow]')===flow;
      var active=nodeId&&sameFlow&&(path.dataset.from===nodeId||path.dataset.to===nodeId);
      path.classList.toggle('is-active',!!active);path.classList.toggle('is-muted',!!nodeId&&!!sameFlow&&!active);
      if(path._label)path._label.classList.toggle('is-active',!!active);
    });
  }
  function clearPreview(){clearClass(previewed,'is-preview');if(!pinned)setEdgeFocus(null);}
  function preview(el){
    clearPreview();if(pinned)return;mark(previewed,el,'is-preview');idsOf(el).forEach(function(id){mark(previewed,lIndex[id],'is-preview');});setEdgeFocus(el.closest('.mv-node'));
  }
  function clearPinned(announce){
    document.querySelectorAll('.is-pinned').forEach(function(el){el.classList.remove('is-pinned');});pinned=null;pendingReveal=null;setEdgeFocus(null);
    if(announce){setStatus('双栏联动 · 未锁定');flashHint('已取消定位');}
  }
  function pinRight(el,move){
    clearPinned(false);clearPreview();pinned=el;el.classList.add('is-pinned');
    var ids=idsOf(el),sources=ids.map(function(id){return lIndex[id];}).filter(Boolean);sources.forEach(function(src){src.classList.add('is-pinned');});
    if(move&&sources[0])queueReveal(L,sources[0]);
    setEdgeFocus(el.closest('.mv-node'));var label=el.getAttribute('data-label')||el.textContent.trim().slice(0,20);
    setStatus('已定位 · '+label+' · '+sources.length+' 处原文');flashHint(wrap.classList.contains('only-r')?'已锁定 · 切换到原文查看':'已锁定原文映射 · Esc 取消');
  }
  function pinLeft(el,move){
    var bid=el.getAttribute('data-block-id'),targets=rIndex[bid]||[];clearPinned(false);clearPreview();pinned=el;el.classList.add('is-pinned');targets.forEach(function(target){target.classList.add('is-pinned');});
    if(move&&targets[0])queueReveal(R,targets[0]);
    setEdgeFocus(targets[0]&&targets[0].closest('.mv-node'));setStatus('已定位 · '+bid+' · '+targets.length+' 个视图元素');flashHint(wrap.classList.contains('only-l')?'已锁定 · 切换到信息重组查看':'已锁定重组映射 · Esc 取消');
  }
  R.addEventListener('pointerover',function(event){var el=event.target.closest('[data-source-blocks]:not(.mv-edge)');if(el&&R.contains(el))preview(el);});
  R.addEventListener('pointerout',function(event){var el=event.target.closest('[data-source-blocks]:not(.mv-edge)');if(el&&!el.contains(event.relatedTarget))clearPreview();});
  R.addEventListener('click',function(event){var el=event.target.closest('[data-source-blocks]:not(.mv-edge)');if(!el)return;event.preventDefault();if(pinned===el)clearPinned(true);else pinRight(el,true);});
  L.addEventListener('click',function(event){var el=event.target.closest('[data-block-id]');if(!el)return;if(pinned===el)clearPinned(true);else pinLeft(el,true);});
  document.addEventListener('keydown',function(event){
    var el=event.target.closest&&event.target.closest('[data-source-blocks]:not(.mv-edge),[data-block-id]');
    if(el&&(event.key==='Enter'||event.key===' ')){event.preventDefault();el.click();}
    if(event.key==='Escape'&&pinned)clearPinned(true);
  });
  L.addEventListener('pointerenter',function(){driver='L';});R.addEventListener('pointerenter',function(){driver='R';});
  L.addEventListener('scroll',function(){if(driver==='L'&&!wrap.classList.contains('only-r'))sync('L');},{passive:true});
  R.addEventListener('scroll',function(){if(driver==='R'&&!wrap.classList.contains('only-l'))sync('R');},{passive:true});

  var modeButtons=[].slice.call(document.querySelectorAll('[data-md2view-mode]'));
  var preferredMode='both';
  function setMode(mode,announce,persist){
    if(['l','both','r'].indexOf(mode)<0)mode='both';if(persist!==false)preferredMode=mode;var actual=compact.matches&&mode==='both'?'r':mode;wrap.classList.remove('only-l','only-r');
    if(actual==='l')wrap.classList.add('only-l');else if(actual==='r')wrap.classList.add('only-r');
    wrap.dataset.layout=actual;modeButtons.forEach(function(button){var on=button.dataset.md2viewMode===actual;button.classList.toggle('on',on);button.setAttribute('aria-pressed',on?'true':'false');});
    if(persist!==false)storageSet('md2view:mode',mode);scheduleDraw();queueMicrotask(function(){requestAnimationFrame(revealPending);});if(announce){var names={l:'原文',both:'双栏',r:'信息重组'};setStatus(names[actual]+'模式');flashHint('已切换到'+names[actual]);}
  }
  window.setMode=function(mode){setMode(mode,true);};modeButtons.forEach(function(button){button.addEventListener('click',function(){setMode(button.dataset.md2viewMode,true);});});

  function splitBounds(){var width=wrap.getBoundingClientRect().width;if(compact.matches||width<740)return{min:28,max:68};return{min:Math.max(28,320/width*100),max:Math.min(68,(width-420)/width*100)};}
  function setRatio(value,persist){var bounds=splitBounds(),ratio=Math.max(bounds.min,Math.min(bounds.max,value));wrap.style.setProperty('--source-ratio',ratio.toFixed(2)+'%');separator.setAttribute('aria-valuemin',Math.ceil(bounds.min));separator.setAttribute('aria-valuemax',Math.floor(bounds.max));separator.setAttribute('aria-valuenow',Math.round(ratio));if(persist)storageSet('md2view:splitRatio',ratio.toFixed(2));scheduleDraw();return ratio;}
  function resetRatio(announce){setRatio(42,true);if(announce){setStatus('原文宽度 · 42%');flashHint('已恢复默认栏宽');}}
  var dragging=false;
  separator.addEventListener('pointerdown',function(event){if(compact.matches)return;dragging=true;separator.classList.add('is-dragging');separator.setPointerCapture(event.pointerId);event.preventDefault();});
  separator.addEventListener('pointermove',function(event){if(!dragging)return;var rect=wrap.getBoundingClientRect(),ratio=setRatio((event.clientX-rect.left)/rect.width*100,false);setStatus('原文宽度 · '+Math.round(ratio)+'%');});
  separator.addEventListener('pointerup',function(event){if(!dragging)return;dragging=false;separator.classList.remove('is-dragging');var ratio=parseFloat(separator.getAttribute('aria-valuenow'));setRatio(ratio,true);flashHint('栏宽已记住 · 双击可重置');separator.releasePointerCapture(event.pointerId);});
  separator.addEventListener('pointercancel',function(){dragging=false;separator.classList.remove('is-dragging');});
  separator.addEventListener('dblclick',function(){resetRatio(true);});
  separator.addEventListener('keydown',function(event){var now=parseFloat(separator.getAttribute('aria-valuenow'))||42,next=now;if(event.key==='ArrowLeft')next-=2;else if(event.key==='ArrowRight')next+=2;else if(event.key==='Home')next=splitBounds().min;else if(event.key==='End')next=splitBounds().max;else if(event.key==='Enter')next=42;else return;event.preventDefault();next=setRatio(next,true);setStatus('原文宽度 · '+Math.round(next)+'%');});

  var NS='http://www.w3.org/2000/svg';
  function svgEl(name,attrs){var el=document.createElementNS(NS,name);Object.keys(attrs||{}).forEach(function(key){el.setAttribute(key,attrs[key]);});return el;}
  function point(rect,side,root){var x=rect.left-root.left,y=rect.top-root.top,w=rect.width,h=rect.height;if(side==='top')return{x:x+w/2,y:y};if(side==='bottom')return{x:x+w/2,y:y+h};if(side==='left')return{x:x,y:y+h/2};return{x:x+w,y:y+h/2};}
  function roundedPath(points){
    var cleaned=points.filter(function(p,i){return !i||Math.abs(p.x-points[i-1].x)>.2||Math.abs(p.y-points[i-1].y)>.2;});if(cleaned.length===2)return'M '+cleaned[0].x+' '+cleaned[0].y+' L '+cleaned[1].x+' '+cleaned[1].y;
    var d='M '+cleaned[0].x+' '+cleaned[0].y;for(var i=1;i<cleaned.length-1;i++){var prev=cleaned[i-1],cur=cleaned[i],next=cleaned[i+1],a=Math.min(10,Math.hypot(cur.x-prev.x,cur.y-prev.y)/2,Math.hypot(next.x-cur.x,next.y-cur.y)/2);var before={x:cur.x+(prev.x-cur.x)*(a/Math.max(1,Math.hypot(prev.x-cur.x,prev.y-cur.y))),y:cur.y+(prev.y-cur.y)*(a/Math.max(1,Math.hypot(prev.x-cur.x,prev.y-cur.y)))};var after={x:cur.x+(next.x-cur.x)*(a/Math.max(1,Math.hypot(next.x-cur.x,next.y-cur.y))),y:cur.y+(next.y-cur.y)*(a/Math.max(1,Math.hypot(next.x-cur.x,next.y-cur.y)))};d+=' L '+before.x+' '+before.y+' Q '+cur.x+' '+cur.y+' '+after.x+' '+after.y;}return d+' L '+cleaned[cleaned.length-1].x+' '+cleaned[cleaned.length-1].y;
  }
  function segmentHitsRect(a,b,rect){var pad=5,left=rect.left-pad,right=rect.right+pad,top=rect.top-pad,bottom=rect.bottom+pad;if(Math.abs(a.x-b.x)<.5)return a.x>left&&a.x<right&&Math.max(a.y,b.y)>top&&Math.min(a.y,b.y)<bottom;if(Math.abs(a.y-b.y)<.5)return a.y>top&&a.y<bottom&&Math.max(a.x,b.x)>left&&Math.min(a.x,b.x)<right;return false;}
  function routePoints(start,end,axis,obstacles,bounds){
    var candidates=[],distance=Math.abs(axis==='v'?end.y-start.y:end.x-start.x),step=Math.min(24,Math.max(10,distance/4)),escape=6;
    if(axis==='v'){
      var sign=end.y>=start.y?1:-1,ys=[(start.y+end.y)/2,start.y+sign*step,end.y-sign*step];obstacles.forEach(function(rect){ys.push(rect.top-10,rect.bottom+10);});
      ys.filter(function(y){return y>Math.min(start.y,end.y)+4&&y<Math.max(start.y,end.y)-4;}).forEach(function(y){candidates.push([start,{x:start.x,y:y},{x:end.x,y:y},end]);});
      var detourXs=[bounds.left,bounds.right];obstacles.forEach(function(rect){detourXs.push(rect.left-10,rect.right+10);});
      detourXs.filter(function(x){return x>=bounds.left&&x<=bounds.right;}).forEach(function(x){var exit=start.y+sign*escape,entry=end.y-sign*escape;candidates.push([start,{x:start.x,y:exit},{x:x,y:exit},{x:x,y:entry},{x:end.x,y:entry},end]);});
    }else{
      var signX=end.x>=start.x?1:-1,xs=[(start.x+end.x)/2,start.x+signX*step,end.x-signX*step];obstacles.forEach(function(rect){xs.push(rect.left-10,rect.right+10);});
      xs.filter(function(x){return x>Math.min(start.x,end.x)+4&&x<Math.max(start.x,end.x)-4;}).forEach(function(x){candidates.push([start,{x:x,y:start.y},{x:x,y:end.y},end]);});
      var detourYs=[bounds.top,bounds.bottom];obstacles.forEach(function(rect){detourYs.push(rect.top-10,rect.bottom+10);});
      detourYs.filter(function(y){return y>=bounds.top&&y<=bounds.bottom;}).forEach(function(y){var exitX=start.x+signX*escape,entryX=end.x-signX*escape;candidates.push([start,{x:exitX,y:start.y},{x:exitX,y:y},{x:entryX,y:y},{x:entryX,y:end.y},end]);});
    }
    if(!candidates.length)candidates.push([start,end]);
    function score(points){var hits=0,length=0;for(var i=1;i<points.length;i++){var a=points[i-1],b=points[i];length+=Math.hypot(b.x-a.x,b.y-a.y);obstacles.forEach(function(rect){if(segmentHitsRect(a,b,rect))hits++;});}var hugsOuterEdge=points.some(function(p){return p.x-bounds.left<16||bounds.right-p.x<16||p.y-bounds.top<16||bounds.bottom-p.y<16;});return hits*100000+length+points.length*2+(hugsOuterEdge?64:0);}
    candidates.sort(function(a,b){return score(a)-score(b);});return candidates[0];
  }
  function routePath(start,end,axis,obstacles,bounds){return roundedPath(routePoints(start,end,axis,obstacles,bounds));}
  function setupFlow(flow,index){
    flow.querySelectorAll('.mv-node').forEach(function(node,nodeIndex){
      node.style.setProperty('--mv-index',nodeIndex);
      node.setAttribute('data-node-index',String(nodeIndex+1).padStart(2,'0'));
    });
    var svg=svgEl('svg',{'class':'mv-edge-layer','aria-hidden':'true'}),defs=svgEl('defs'),markerId='mv-arrow-'+index,marker=svgEl('marker',{id:markerId,viewBox:'0 0 10 10',refX:'8.5',refY:'5',markerWidth:'6',markerHeight:'6',orient:'auto-start-reverse'}),arrow=svgEl('path',{d:'M 1 1 L 9 5 L 1 9 z',fill:'context-stroke'});marker.appendChild(arrow);defs.appendChild(marker);svg.appendChild(defs);flow.insertBefore(svg,flow.firstChild);
    flow._edges=[];flow.querySelectorAll('.mv-edge[data-from][data-to]').forEach(function(meta){var path=svgEl('path',{'class':'mv-edge-path','data-kind':meta.dataset.kind||'depends','marker-end':'url(#'+markerId+')','pathLength':'1'}),label=svgEl('text',{'class':'mv-edge-label'});label.textContent=meta.dataset.label||'';path.dataset.from=meta.dataset.from;path.dataset.to=meta.dataset.to;path._label=label;svg.appendChild(path);svg.appendChild(label);flow._edges.push({meta:meta,path:path,label:label});});flow._svg=svg;
    if('ResizeObserver'in window){var observer=new ResizeObserver(scheduleDraw);observer.observe(flow);flow.querySelectorAll('.mv-node').forEach(function(node){observer.observe(node);});flow._observer=observer;}
  }
  function drawFlow(flow){
    if(!flow.offsetParent||!flow._svg)return;var root=flow.getBoundingClientRect(),width=flow.clientWidth,height=flow.clientHeight;flow._svg.setAttribute('viewBox','0 0 '+width+' '+height);flow._svg.setAttribute('width',width);flow._svg.setAttribute('height',height);
    flow._edges.forEach(function(edge){var from=flow.querySelector('.mv-node[data-node-id="'+CSS.escape(edge.meta.dataset.from)+'"]'),to=flow.querySelector('.mv-node[data-node-id="'+CSS.escape(edge.meta.dataset.to)+'"]');if(!from||!to){edge.path.setAttribute('d','');edge.label.textContent='';return;}var a=from.getBoundingClientRect(),b=to.getBoundingClientRect(),dx=b.left+b.width/2-(a.left+a.width/2),dy=b.top+b.height/2-(a.top+a.height/2),axis=edge.meta.dataset.route||((Math.abs(dy)>=Math.abs(dx)*.72)?'v':'h');var fromSide=edge.meta.dataset.fromSide||(axis==='v'?(dy>=0?'bottom':'top'):(dx>=0?'right':'left')),toSide=edge.meta.dataset.toSide||(axis==='v'?(dy>=0?'top':'bottom'):(dx>=0?'left':'right')),start=point(a,fromSide,root),end=point(b,toSide,root),obstacles=[].slice.call(flow.querySelectorAll('.mv-node')).filter(function(node){return node!==from&&node!==to;}).map(function(node){var rect=node.getBoundingClientRect();return{left:rect.left-root.left,right:rect.right-root.left,top:rect.top-root.top,bottom:rect.bottom-root.top};}),bounds={left:10,right:width-10,top:10,bottom:height-10},d=routePath(start,end,axis,obstacles,bounds);edge.path.setAttribute('d',d);edge.label.textContent=edge.meta.dataset.label||'';if(edge.label.textContent){try{var pos=edge.path.getPointAtLength(edge.path.getTotalLength()*.5);edge.label.setAttribute('x',pos.x);edge.label.setAttribute('y',pos.y);}catch(e){edge.label.textContent='';}}});
  }
  function drawAll(){drawQueued=false;document.querySelectorAll('[data-flow]').forEach(drawFlow);}
  function scheduleDraw(){if(drawQueued)return;drawQueued=true;requestAnimationFrame(function(){requestAnimationFrame(drawAll);});}
  document.querySelectorAll('[data-flow]').forEach(setupFlow);
  window.addEventListener('resize',scheduleDraw,{passive:true});
  var reveal=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting){entry.target.classList.add('in');var flow=entry.target.querySelector('[data-flow]');if(flow)setTimeout(function(){flow.classList.add('is-ready');},80);reveal.unobserve(entry.target);}});},{root:R,threshold:.05});
  document.querySelectorAll('section.view').forEach(function(view){reveal.observe(view);});
  function compactChanged(){setMode(preferredMode,false,false);scheduleDraw();}
  if(compact.addEventListener)compact.addEventListener('change',compactChanged);else compact.addListener(compactChanged);
  var savedRatio=parseFloat(storageGet('md2view:splitRatio'));setRatio(Number.isFinite(savedRatio)?savedRatio:42,false);
  preferredMode=storageGet('md2view:mode')||'both';setMode(preferredMode,false,false);compactChanged();scheduleDraw();
  setTimeout(function(){document.querySelectorAll('.mv-flow').forEach(function(flow){flow.classList.add('is-ready');});scheduleDraw();},240);
  setStatus(compact.matches?'信息重组模式':'双栏联动 · 拖动中线调宽');setTimeout(function(){flashHint(compact.matches?'点击节点可定位原文':'拖动中线调宽 · 点击内容锁定映射');},420);
})();
"""


def main(blocks_path, frag_dir, views_path, out_path):
    with open(blocks_path, encoding='utf-8') as f:
        blocks = json.load(f)
    with open(views_path, encoding='utf-8') as f:
        plan = json.load(f)

    left = ''.join(render_block(b) for b in blocks)
    source_ids = {block['id'] for block in blocks}

    right_parts = []
    for v in plan['views']:
        p = os.path.join(frag_dir, v['id'] + '.html')
        if not os.path.exists(p):
            raise FileNotFoundError('missing fragment: %s' % p)
        with open(p, encoding='utf-8') as f:
            frag = f.read().strip()
        frag = re.sub(r'^```(html)?|```$', '', frag, flags=re.M).strip()
        validate_fragment(frag, v, source_ids)
        right_parts.append(frag)
    right = '\n'.join(right_parts)

    title = plan.get('title', '双栏同步阅读器')
    doc = ('<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>' + esc(title) + ' · 双栏</title><style>' + CSS + '</style></head><body>'
           '<header class="bar"><div class="brand">' + esc(title) +
           '<small>source ↔ view</small></div><div class="toolbar">'
           '<div class="sync-status" data-md2view-status role="status" aria-live="polite">双栏联动</div>'
           '<div class="modes" role="group" aria-label="阅读模式">'
           '<button data-md2view-mode="l" aria-pressed="false">原文</button>'
           '<button class="on" data-md2view-mode="both" aria-pressed="true">双栏</button>'
           '<button data-md2view-mode="r" aria-pressed="false">信息重组</button>'
           '</div></div></header>'
           '<div id="split" data-md2view-split data-layout="both">'
           '<div class="pane" id="paneL" aria-label="Markdown 原文"><div class="pane-tag">Markdown 原文 · 权威源</div><div class="doc">' + left + '</div></div>'
           '<div class="splitter" data-md2view-separator role="separator" tabindex="0" aria-label="调整原文栏宽度" aria-orientation="vertical" aria-valuemin="28" aria-valuemax="68" aria-valuenow="42" title="拖动调宽 · 双击重置"></div>'
           '<div class="pane" id="paneR" aria-label="信息重组"><div class="pane-tag">信息重组 · 人类视图</div><div class="doc">' + right + '</div></div>'
           '</div>'
           '<div class="hint" aria-hidden="true">拖动中线调宽 · 点击内容锁定映射</div>'
           '<script>' + JS + '</script></body></html>')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    print('reader -> %s (%d bytes, %d blocks left / %d views right)' % (out_path, len(doc), len(blocks), len(right_parts)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
