#!/usr/bin/env python3
"""md2view v4 构建器:blocks.json + 模型自由创作的 right-pane.html → 单文件 reader.html。

职责边界:
  确定性层(本脚本)——左栏权威原文渲染、双栏壳、锚点联动、溯源验证、原子写出。
  模型——右栏内容的设计与表达(自由 HTML + mv-* 组件 + data-sources 锚点)。

溯源验证不通过时不写任何文件。

用法: build_reader.py <blocks.json> <right-pane.html> <reader.html> [--title 标题]
"""
import argparse
import json
import os
import sys

from md_source import esc, render_block
from verify_anchors import verify_fragment

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'assets')


def load_asset(name):
    with open(os.path.join(ASSETS, name), encoding='utf-8') as f:
        return f.read()


def default_title(blocks):
    for block in blocks:
        if block['type'] == 'heading':
            return block['raw'].lstrip('#').strip()
    return 'md2view 阅读器'


def build(blocks, fragment, title):
    css = load_asset('shell.css')
    js = load_asset('shell.js')
    left = ''.join(render_block(b) for b in blocks)
    return (
        '<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + esc(title) + ' · 双栏</title><style>' + css + '</style></head><body>'
        '<header class="bar"><div class="brand">' + esc(title) +
        '<small>source ↔ view</small></div><div class="toolbar">'
        '<div class="sync-status" data-md2view-status role="status" aria-live="polite">双栏联动</div>'
        '<div class="modes" role="group" aria-label="阅读模式">'
        '<button data-md2view-mode="l" aria-pressed="false">原文</button>'
        '<button class="on" data-md2view-mode="both" aria-pressed="true">双栏</button>'
        '<button data-md2view-mode="r" aria-pressed="false">信息重组</button>'
        '</div></div></header>'
        '<div id="split" data-md2view-split data-layout="both">'
        '<div class="pane" id="paneL" aria-label="Markdown 原文">'
        '<div class="pane-tag">Markdown 原文 · 权威源</div><div class="doc">' + left + '</div></div>'
        '<div class="splitter" data-md2view-separator role="separator" tabindex="0" '
        'aria-label="调整原文栏宽度" aria-orientation="vertical" aria-valuemin="28" '
        'aria-valuemax="68" aria-valuenow="42" title="拖动调宽 · 双击重置"></div>'
        '<div class="pane" id="paneR" aria-label="信息重组">'
        '<div class="pane-tag">信息重组 · 人类视图</div><div class="doc">' + fragment + '</div></div>'
        '</div>'
        '<div class="hint" aria-hidden="true">拖动中线调宽 · 点击内容锁定映射</div>'
        '<script>' + js + '</script></body></html>'
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description='md2view v4 构建器')
    parser.add_argument('blocks', help='parse_blocks.py 输出的 blocks.json')
    parser.add_argument('fragment', help='模型创作的 right-pane.html')
    parser.add_argument('output', help='最终 reader.html')
    parser.add_argument('--title', help='页面标题(默认取首个标题块)')
    args = parser.parse_args(argv)

    with open(args.blocks, encoding='utf-8') as f:
        blocks = json.load(f)
    with open(args.fragment, encoding='utf-8') as f:
        fragment = f.read()

    errors, warnings, stats = verify_fragment(blocks, fragment)
    for warning in warnings:
        print(f'WARN  {warning}')
    if errors:
        print(f'FAIL  溯源验证未通过,{len(errors)} 个问题;未写出 {args.output}:')
        for error in errors:
            print(f'  - {error}')
        return 1

    title = args.title or default_title(blocks)
    doc = build(blocks, fragment, title)
    tmp = args.output + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(doc)
    os.replace(tmp, args.output)
    print(f'PASS  覆盖 {stats["covered"]}/{stats["blocks"]} blocks · '
          f'{stats["sourced_elements"]} 个溯源元素 · {stats["views"]} 个视图')
    print(f'reader -> {args.output} ({len(doc)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
