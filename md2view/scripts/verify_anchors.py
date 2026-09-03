#!/usr/bin/env python3
"""md2view v4 溯源验证器:对模型自由创作的 right-pane.html 做确定性核查。

只验证"可核证性",不干预表达形式:
  1. 结构安全:无 script/外部资源/事件处理器/隐藏文字把戏
  2. 来源合法:每个 data-sources 非空且 id 真实存在
  3. 覆盖完整:每个非标题 block 至少被一个右栏元素引用
  4. 词法锚点:元素可见正文与每个被引 block 共享至少一个实义词锚(可概括,不可完全换词)
  5. 数字忠实:元素可见正文里的阿拉伯数字必须逐字出现在被引 block 中(防捏造)
  6. 原子单元:表格行 / checkbox 项的数字与关键词在右栏有可见承接

用法: verify_anchors.py blocks.json right-pane.html
退出码 0 = PASS;1 = 有问题(逐条打印)。
"""
import json
import re
import sys
from html.parser import HTMLParser

VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
             'link', 'meta', 'param', 'source', 'track', 'wbr'}
FORBIDDEN_TAGS = {'script', 'iframe', 'embed', 'object', 'video', 'audio', 'img', 'link', 'base'}

CJK_RE = re.compile(r'[一-鿿　-〿＀-￯]')
CJK_RUN = re.compile(r'[一-鿿]+')
LATIN_TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_.+-]+')
NUMBER_TOKEN = re.compile(r'(?<![\w./:~-])\d+(?:[.,:/-]\d+)*%?')

HIDING_CSS = re.compile(
    r'display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:[.\d]*)?\b|'
    r'font-size\s*:\s*0|color\s*:\s*transparent|text-indent\s*:\s*-|'
    r'position\s*:\s*fixed|content-visibility\s*:\s*hidden',
    flags=re.I,
)
EXTERNAL_RES = re.compile(
    r'<\s*(script|link|iframe|embed|object)\b|'
    r'\b(?:src|href)\s*=\s*["\']\s*(?:https?:)?//|'
    r'url\(\s*["\']?\s*(?:https?:)?//|@import|\bon[a-z]+\s*=',
    flags=re.I,
)


def norm(text):
    """归一化用于锚点比对:去空白与 markdown 记号,保留实义字符。"""
    return re.sub(r'[\s`*#>|_~\-—–·•,，。、;；:：!！?？()（）\[\]{}<>《》「」"\'“”‘’/\\]+', '', text or '')


def cjk_windows(text, n):
    windows = set()
    for run in CJK_RUN.findall(text or ''):
        for i in range(len(run) - n + 1):
            windows.add(run[i:i + n])
    return windows


def latin_tokens(text):
    return {t.lower() for t in LATIN_TOKEN.findall(text or '')}


def number_tokens(text):
    return NUMBER_TOKEN.findall(text or '')


class FragmentProbe(HTMLParser):
    """收集右栏片段的来源标注、可见文本与图结构。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sourced = []          # [{sources, unit, text, tag, classes, drawer}]
        self.stack = []            # open elements: {tag, attrs, entry}
        self.hidden_depth = 0
        self.details_depth = 0
        self.diagrams = []         # [{nodes: [id], edges: [(from,to)]}]
        self.diagram_stack = []
        self.forbidden = []        # 禁用的标签出现位置
        self.all_text = []         # 右栏全部可见文本
        self.views = 0

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        classes = set((attrs.get('class') or '').split())
        if tag in FORBIDDEN_TAGS:
            self.forbidden.append(tag)
        hidden_here = (
            tag in ('script', 'style', 'template')
            or 'hidden' in attrs
            or attrs.get('aria-hidden') == 'true'
            or 'mv-edge' in classes
        )
        if hidden_here:
            self.hidden_depth += 1
        if tag == 'details':
            self.details_depth += 1
        diagram = None
        if 'data-diagram' in attrs:
            diagram = {'nodes': [], 'edges': []}
            self.diagrams.append(diagram)
            self.diagram_stack.append(diagram)
        elif self.diagram_stack:
            diagram = self.diagram_stack[-1]
        if diagram is not None:
            if 'data-node' in attrs:
                diagram['nodes'].append(attrs['data-node'])
            if 'mv-edge' in classes and attrs.get('data-from') and attrs.get('data-to'):
                diagram['edges'].append((attrs['data-from'], attrs['data-to']))
        entry = None
        if attrs.get('data-sources'):
            entry = {
                'sources': attrs['data-sources'].split(),
                'unit': attrs.get('data-unit'),
                'text': [],
                'tag': tag,
                'classes': classes,
                'drawer': self.details_depth > 0,
            }
            self.sourced.append(entry)
        if 'mv-view' in classes:
            self.views += 1
        if tag not in VOID_TAGS:
            self.stack.append({'tag': tag, 'entry': entry, 'hidden': hidden_here,
                               'details': tag == 'details',
                               'diagram': self.diagram_stack and 'data-diagram' in attrs})

    def handle_startendtag(self, tag, attrs_list):
        self.handle_starttag(tag, attrs_list)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        while self.stack:
            open_el = self.stack.pop()
            if open_el['hidden']:
                self.hidden_depth -= 1
            if open_el.get('details'):
                self.details_depth -= 1
            if open_el['diagram']:
                self.diagram_stack.pop()
            if open_el['tag'] == tag:
                break

    def handle_data(self, data):
        if self.hidden_depth:
            return
        if data.strip():
            self.all_text.append(data)
        for open_el in self.stack:
            if open_el['entry'] is not None:
                open_el['entry']['text'].append(data)
def has_lexical_anchor(element_text, block_raw):
    """可见正文与被引 block 至少共享一个实义词锚:3 字中文窗口、
    两个不同的 2 字中文窗口,或一个拉丁词(token≥3)。数字不算词法锚。"""
    if cjk_windows(element_text, 3) & cjk_windows(block_raw, 3):
        return True
    bigram_overlap = cjk_windows(element_text, 2) & cjk_windows(block_raw, 2)
    if len(bigram_overlap) >= 2:
        return True
    return bool(latin_tokens(element_text) & latin_tokens(block_raw))


def verify_fragment(blocks, fragment):
    """返回 (errors, warnings, stats)。"""
    errors = []
    warnings = []
    probe = FragmentProbe()
    probe.feed(fragment)
    probe.close()

    # ---- 结构安全 ----
    for tag in probe.forbidden:
        errors.append(f'右栏禁止使用 <{tag}>;图用 div/SVG,装饰用 CSS,交互由 shell 提供')
    for match in EXTERNAL_RES.finditer(fragment):
        errors.append(f'右栏禁止外部资源或事件处理器: ...{match.group(0)[:60]}...')
    style_bodies = re.findall(r'<style\b[^>]*>(.*?)</style\s*>', fragment, flags=re.I | re.S)
    inline_styles = re.findall(r'\bstyle\s*=\s*"([^"]*)"|\bstyle\s*=\s*\'([^\']*)\'', fragment)
    css_haystack = '\n'.join(style_bodies + [a or b for a, b in inline_styles])
    for match in HIDING_CSS.finditer(css_haystack):
        errors.append(f'右栏禁止隐藏/遮盖类 CSS(防垫字凑锚点): {match.group(0)}')
    if probe.views == 0:
        errors.append('右栏没有任何 <section class="mv-view">;一个视图回答一个读者问题')

    known_ids = {b['id'] for b in blocks}
    block_by_id = {b['id']: b for b in blocks}

    # ---- 来源合法 + 词法锚点 + 数字忠实 ----
    cited = {}
    for entry in probe.sourced:
        text = ' '.join(entry['text'])
        unknown = [s for s in entry['sources'] if s not in known_ids]
        if unknown:
            errors.append(f'data-sources 引用不存在的 block: {" ".join(unknown)}')
            continue
        if not text.strip():
            errors.append(f'空元素标注了 data-sources={" ".join(entry["sources"])};无可见内容的引用不算溯源')
            continue
        for bid in entry['sources']:
            cited.setdefault(bid, []).append(entry)
        for bid in entry['sources']:
            raw = block_by_id[bid]['raw']
            if not has_lexical_anchor(text, raw):
                errors.append(
                    f'元素(“{text.strip()[:24]}…”)宣称引用 {bid},但可见正文与该块无任何共享词锚;'
                    f'可以概括,不能完全换词')
        cited_raw = '\n'.join(block_by_id[bid]['raw'] for bid in entry['sources'])
        cited_norm = norm(cited_raw)
        for token in number_tokens(text):
            if norm(token) not in cited_norm:
                errors.append(
                    f'元素(“{text.strip()[:24]}…”)中的数字 “{token}” 未逐字出现在其来源 '
                    f'{" ".join(entry["sources"])} 中;数字必须抄录,不得估算或心算')
        if len(entry['sources']) > 8 and 'mv-view' not in entry['classes']:
            warnings.append(f'一个元素引用 {len(entry["sources"])} 个 block(“{text.strip()[:16]}…”);过粗的引用等于没有溯源')

    # ---- 覆盖完整 ----
    uncovered = [b['id'] for b in blocks
                 if b['type'] not in ('heading', 'rule') and b['id'] not in cited]
    if uncovered:
        preview = ', '.join(uncovered[:12]) + (' …' if len(uncovered) > 12 else '')
        errors.append(f'{len(uncovered)} 个非标题 block 未被任何右栏元素引用: {preview}')
    drawer_only = [bid for bid, entries in cited.items()
                   if bid in block_by_id
                   and block_by_id[bid]['type'] not in ('heading', 'rule')
                   and all(e['drawer'] for e in entries)]
    if drawer_only:
        preview = ', '.join(sorted(drawer_only)[:12]) + (' …' if len(drawer_only) > 12 else '')
        warnings.append(f'{len(drawer_only)} 个 block 只在抽屉/折叠区被引用(主视觉零承载): {preview};'
                        f'若有核心命题混在其中,把它提到主视觉')

    # ---- 原子单元:表格行 / checkbox 项 ----
    pane_text = norm(' '.join(probe.all_text))
    unit_claims = {}
    for entry in probe.sourced:
        if entry['unit']:
            unit_claims.setdefault(entry['unit'], entry)
    for block in blocks:
        for unit in block.get('sourceUnits', []):
            claim = unit_claims.get(unit['id'])
            haystack = norm(' '.join(claim['text'])) if claim else pane_text
            where = f'data-unit={unit["id"]} 的元素' if claim else '右栏任意位置'
            missing_numbers = [t for t in number_tokens(unit['raw']) if norm(t) not in haystack]
            if missing_numbers:
                errors.append(
                    f'原子单元 {unit["id"]}({unit["key"][:18]})的数字 {" ".join(missing_numbers)} '
                    f'未在{where}出现;表格行/checkbox 项的数字必须逐字保留')
            key_windows = cjk_windows(unit['key'], 4)
            if key_windows and not any(w in haystack for w in key_windows):
                if not claim:
                    errors.append(
                        f'原子单元 {unit["id"]} 的关键词 “{unit["key"][:18]}” 在右栏无可见承接;'
                        f'决策行不能被总结吞并')

    # ---- 图结构 ----
    for index, diagram in enumerate(probe.diagrams, 1):
        nodes = diagram['nodes']
        duplicates = sorted({n for n in nodes if nodes.count(n) > 1})
        if duplicates:
            errors.append(f'第 {index} 个 diagram 重复 data-node: {", ".join(duplicates)}')
        dangling = sorted({ep for edge in diagram['edges'] for ep in edge if ep not in nodes})
        if dangling:
            errors.append(f'第 {index} 个 diagram 的连线引用不存在的节点: {", ".join(dangling)}')

    stats = {
        'blocks': len(blocks),
        'covered': len(cited),
        'sourced_elements': len(probe.sourced),
        'views': probe.views,
        'diagrams': len(probe.diagrams),
    }
    return errors, warnings, stats


def main(argv):
    if len(argv) != 3:
        raise SystemExit('用法: verify_anchors.py <blocks.json> <right-pane.html>')
    with open(argv[1], encoding='utf-8') as f:
        blocks = json.load(f)
    with open(argv[2], encoding='utf-8') as f:
        fragment = f.read()
    errors, warnings, stats = verify_fragment(blocks, fragment)
    for warning in warnings:
        print(f'WARN  {warning}')
    if errors:
        print(f'FAIL  {len(errors)} 个溯源问题:')
        for error in errors:
            print(f'  - {error}')
        return 1
    print(f'PASS  覆盖 {stats["covered"]}/{stats["blocks"]} blocks · '
          f'{stats["sourced_elements"]} 个溯源元素 · '
          f'{stats["views"]} 个视图 · {stats["diagrams"]} 张图')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
