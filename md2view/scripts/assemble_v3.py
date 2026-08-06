#!/usr/bin/env python3
"""Compile blocks.json + view-spec.json into a gated md2view v3 candidate."""
import json
import os
import sys

from assemble_split import CSS as SHELL_CSS
from assemble_split import JS as SHELL_JS
from assemble_split import _require_candidate_output, esc, render_block
from v3_contract import validate_v3_spec
from v3_renderer import render_v3_view


V3_CSS = r"""
.mv-view{--family-accent:var(--accent);margin-bottom:38px}
.mv-view-header{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,44%);gap:5px 22px;align-items:end;margin:0 0 12px}
.mv-view-question{grid-column:1/-1;margin:0;color:var(--accent);font:650 10px/1.35 var(--mono);letter-spacing:.08em;text-transform:uppercase}
.mv-view-header h2{margin:0;font-family:var(--font);font-size:clamp(21px,2vw,28px);line-height:1.18;letter-spacing:-.025em}
.mv-view-claim{margin:0;padding:7px 10px;border-left:3px solid var(--family-accent);background:color-mix(in srgb,var(--accent-soft) 62%,transparent);color:var(--accent-strong);font-size:12px;line-height:1.45;border-radius:0 7px 7px 0}
.mv-diagram{position:relative;min-width:0;padding:16px;border:1px solid var(--border);border-radius:14px;background:color-mix(in srgb,var(--surface) 96%,transparent);box-shadow:0 10px 28px rgba(46,37,26,.055);overflow:hidden}
.mv-diagram::before{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(118deg,rgba(162,68,30,.035),transparent 34%),linear-gradient(rgba(35,31,25,.026) 1px,transparent 1px),linear-gradient(90deg,rgba(35,31,25,.026) 1px,transparent 1px);background-size:auto,28px 28px,28px 28px;mask-image:linear-gradient(#000,transparent 96%)}
.mv-region,.mv-entity,.mv-matrix,.mv-argument{position:relative;z-index:1}
.mv-region{min-width:0}
.mv-region--container{display:grid;gap:9px;padding:10px;border:1px solid color-mix(in srgb,var(--border) 92%,var(--accent));border-radius:12px;background:rgba(255,254,250,.76)}
.mv-region--container[data-axis=horizontal]{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));align-items:start}.mv-diagram>.mv-region--container[data-axis=horizontal]{grid-template-columns:repeat(var(--mv-region-columns,1),minmax(0,1fr))}.mv-region--container[data-axis=horizontal]>.mv-region-owner,.mv-region--container[data-axis=horizontal]>.mv-fact,.mv-region--container[data-axis=horizontal]>.mv-region--crosscut{grid-column:1/-1}
.mv-region--container[data-axis=horizontal]>.mv-region[data-role=inset]{grid-column:1/-1}
.mv-region--container>.mv-region-owner{margin:-10px -10px 1px;border:0;border-bottom:1px solid var(--border);border-radius:11px 11px 0 0;background:color-mix(in srgb,var(--accent-soft) 54%,var(--surface));padding:10px 12px}
.mv-region--band{display:grid;grid-template-columns:minmax(132px,22%) minmax(0,1fr);align-items:stretch;gap:10px;padding:8px;border:1px solid color-mix(in srgb,var(--border) 86%,transparent);border-radius:9px;background:color-mix(in srgb,var(--surface) 90%,transparent)}
.mv-region--band>.mv-region-owner{grid-column:1;margin:0;border:0;border-right:1px solid var(--border);border-radius:6px 0 0 6px;background:transparent;padding:5px 10px 5px 5px}
.mv-region--band>.mv-region:not(.mv-region-owner),.mv-region--band>.mv-entity:not(.mv-region-owner){grid-column:2}
.mv-region--band[data-has-content=false]{grid-template-columns:minmax(0,1fr)}.mv-region--band[data-has-content=false]>.mv-region-owner{grid-column:1;border-right:0;border-radius:6px}
.mv-region--crosscut{padding:9px 11px;border:1px dashed color-mix(in srgb,var(--accent) 58%,var(--border));border-radius:9px;background:color-mix(in srgb,var(--accent-soft) 52%,var(--surface));box-shadow:inset 3px 0 0 var(--accent)}
.mv-crosscut-targets{margin:5px 0 0;color:var(--muted);font:10px/1.4 var(--mono)}.mv-crosscut-targets strong{color:var(--accent-strong)}
.mv-region[data-role=support]{background:color-mix(in srgb,var(--good-soft) 42%,var(--surface));border-color:color-mix(in srgb,var(--good) 28%,var(--border))}.mv-region[data-role=context]{opacity:.88}
.mv-region--radial{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;align-items:center;min-height:300px}
.mv-region--radial>.mv-entity[data-emphasis=primary]{grid-column:2;grid-row:2;transform:scale(1.04);box-shadow:0 10px 28px rgba(119,48,21,.13)}
.mv-region--stack{display:grid;padding:0 10px 10px 0}.mv-region--stack>.mv-entity{grid-area:1/1;transform:translate(calc(var(--stack-index,0)*5px),calc(var(--stack-index,0)*5px))}
.mv-region--axis{display:grid;gap:8px}.mv-region--inset{padding:9px;border:1px dashed var(--border);border-radius:8px;background:var(--surface-2)}
.mv-entity{min-width:0;padding:8px 10px;border:1px solid color-mix(in srgb,var(--border) 90%,transparent);border-radius:8px;background:var(--surface);cursor:pointer;transition:transform 140ms var(--ease),border-color 140ms,box-shadow 160ms,background 140ms}
.mv-entity:hover{transform:translateY(-1px);border-color:color-mix(in srgb,var(--accent) 46%,var(--border));box-shadow:0 7px 18px rgba(44,34,24,.09)}
.mv-entity[data-emphasis=primary]{border-color:color-mix(in srgb,var(--accent) 58%,var(--border));box-shadow:inset 3px 0 0 var(--accent)}
.mv-entity h3{margin:0;font-size:12.5px;line-height:1.25;letter-spacing:-.01em}.mv-entity p{margin:3px 0 0;color:var(--muted);font-size:10.5px;line-height:1.38}
.mv-entity h3,.mv-entity p,.mv-fact strong,.mv-fact span,.mv-matrix th,.mv-matrix td{overflow-wrap:break-word;word-break:normal;line-break:auto}
.mv-flow-sequence{position:relative;z-index:1;display:flex;align-items:stretch;gap:7px;width:100%;min-width:0;padding:4px;overflow-x:auto}.mv-flow-step{display:grid;align-content:start;gap:5px;min-width:150px;max-width:220px;flex:1 0 150px}.mv-flow-step>.mv-entity{height:100%}
.mv-connector{display:grid;align-content:center;justify-items:center;flex:0 0 72px;color:var(--accent-strong)}.mv-connector>span{font:26px/1 var(--sans)}.mv-connector>small{max-width:72px;text-align:center;color:var(--muted);font:600 8.5px/1.2 var(--mono);overflow-wrap:anywhere}.mv-connector>.mv-fact{max-width:92px;padding:5px 6px;text-align:center}.mv-connector>.mv-fact strong,.mv-connector>.mv-fact span{font-size:8.5px}
.mv-matrix{width:100%;border-collapse:separate;border-spacing:0;font-size:11px;background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.mv-matrix th,.mv-matrix td{padding:8px 10px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);vertical-align:top;text-align:left}.mv-matrix tr:last-child>*{border-bottom:0}.mv-matrix tr>*:last-child{border-right:0}
.mv-matrix thead th{background:color-mix(in srgb,var(--accent-soft) 58%,var(--surface));color:var(--accent-strong)}.mv-matrix thead th:first-child{width:19%;color:var(--muted);font:650 9px/1.2 var(--mono);letter-spacing:.08em}.mv-matrix th[data-emphasis=primary]{background:color-mix(in srgb,var(--good-soft) 72%,var(--surface))}
.mv-matrix th strong,.mv-matrix th small{display:block}.mv-matrix th small{margin-top:3px;color:var(--muted);font-weight:400;line-height:1.35}
.mv-argument{display:grid;grid-template-columns:minmax(220px,34%) minmax(0,1fr);gap:14px;align-items:center}.mv-argument-claim{grid-column:1}.mv-argument-evidence-list{grid-column:2;display:grid;gap:8px}.mv-argument-evidence{display:grid;grid-template-columns:minmax(0,1fr) minmax(92px,auto);align-items:center;gap:7px}.mv-argument-evidence-main,.mv-argument-link{display:grid;gap:5px;min-width:0}.mv-argument-link{justify-items:start}.mv-argument-relation{padding:4px 7px;border:1px solid color-mix(in srgb,var(--good) 34%,var(--border));border-radius:999px;background:var(--good-soft);color:var(--good);font:650 8.5px/1.2 var(--mono)}.mv-argument-link>.mv-fact{max-width:150px}
.mv-architecture-relations{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0;padding:0;list-style:none}.mv-architecture-relation{display:flex;align-items:center;gap:6px;min-width:0;padding:5px 8px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);font-size:9.5px}.mv-architecture-relation strong{color:var(--text);font-weight:650}.mv-architecture-relation em{color:var(--accent-strong);font-style:normal;font:650 8.5px/1.2 var(--mono)}.mv-architecture-relation[data-visual=crosscut]{border-style:dashed;background:var(--accent-soft)}
.mv-fact{position:relative;z-index:1}.mv-view-facts{position:relative;z-index:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:6px;margin-top:8px}.mv-region>.mv-fact{align-self:start}.mv-relation[hidden]{display:none!important}
@media(min-width:768px) and (max-width:899px){
  header.bar{height:var(--header-h);padding:0 12px 0 15px}.brand small{display:inline}.sync-status{display:block}.modes button[data-md2view-mode=both]{display:inline-block}
  #split,#split.only-l,#split.only-r{display:grid;grid-template-columns:minmax(300px,var(--source-ratio)) 12px minmax(390px,1fr);height:calc(100vh - var(--header-h))}
  #split.only-l{grid-template-columns:minmax(0,1fr) 0 0}#split.only-r{grid-template-columns:0 0 minmax(0,1fr)}
  #split:not(.only-l):not(.only-r) #paneL{display:block}.only-l #paneL,.only-r #paneR{display:block}
  #paneL{grid-column:1;grid-row:auto}#paneR{grid-column:3;grid-row:auto}.splitter{display:block;grid-column:2}.only-l .splitter,.only-r .splitter{display:none}
}
@container(max-width:650px){.mv-view-header{grid-template-columns:1fr}.mv-view-header>*{grid-column:1}.mv-region--container[data-axis=horizontal]{grid-template-columns:minmax(0,1fr)}.mv-region--band{grid-template-columns:minmax(108px,28%) minmax(0,1fr)}.mv-argument{grid-template-columns:1fr}.mv-argument-claim,.mv-argument-evidence-list{grid-column:1}}
"""
V3_JS = (
    SHELL_JS
    .replace('(max-width:899px)', '(max-width:767px)')
    .replace('320/width*100', '300/width*100')
    .replace('(width-420)/width*100', '(width-390)/width*100')
)


def _reader_document(blocks, spec):
    title = spec['page']['title']
    left = ''.join(render_block(block) for block in blocks)
    right = '\n'.join(render_v3_view(view) for view in spec['views'])
    return (
        '<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + esc(title) + ' · 双栏</title><style>' + SHELL_CSS + V3_CSS + '</style></head><body>'
        '<header class="bar"><div class="brand">' + esc(title)
        + '<small>source ↔ view-spec v3</small></div><div class="toolbar">'
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
        '<div class="pane-tag">信息重组 · 人类视图</div><div class="doc">' + right + '</div></div>'
        '</div><div class="hint" aria-hidden="true">拖动中线调宽 · 点击内容锁定映射</div>'
        '<script>' + V3_JS + '</script></body></html>'
    )


def main(blocks_path, spec_path, out_path):
    """Validate and compile one v3 candidate. Never writes a final reader directly."""
    _require_candidate_output(out_path)
    with open(blocks_path, encoding='utf-8') as handle:
        blocks = json.load(handle)
    with open(spec_path, encoding='utf-8') as handle:
        spec = json.load(handle)
    validate_v3_spec(blocks, spec)
    document = _reader_document(blocks, spec)
    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write(document)
    print(
        'reader v3 candidate -> %s (%d bytes, %d blocks / %d views)'
        % (out_path, len(document), len(blocks), len(spec['views']))
    )


def cli(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        raise SystemExit(
            '用法: assemble_v3.py <blocks.json> <view-spec.json> <output.candidate.html>'
        )
    try:
        _require_candidate_output(args[2])
    except ValueError as error:
        raise SystemExit(str(error)) from error
    main(*map(os.fspath, args))


if __name__ == '__main__':
    cli()


__all__ = ['V3_CSS', 'V3_JS', 'cli', 'main']
