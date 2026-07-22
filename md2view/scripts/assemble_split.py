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


def esc(s):
    return htmllib.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s


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
        ordered = bool(re.match(r'^\s*\d+[.)]', raw))
        items = []
        for line in raw.split('\n'):
            m = re.match(r'^\s*(?:[-*+]|\d+[.)])\s+(.*)$', line)
            if m:
                items.append('<li>%s</li>' % inline(m.group(1)))
            elif line.strip() and items:
                items[-1] = items[-1][:-5] + ' ' + inline(line.strip()) + '</li>'
        tag = 'ol' if ordered else 'ul'
        inner = '<%s>%s</%s>' % (tag, ''.join(items), tag)
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


CSS = """
:root{--bg:#faf9f6;--surface:#fff;--text:#1d1a16;--muted:#6f6a61;--accent:#9a4a1f;
--accent-soft:#f3e5da;--border:#e5e0d6;--ink:#211d18;--good:#3d6b4f;--warn:#b45309;
--font:'Source Han Serif SC','Noto Serif CJK SC',Georgia,serif;
--sans:'PingFang SC','Noto Sans CJK SC',-apple-system,sans-serif;
--mono:'SF Mono',ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.7}
header.bar{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 22px;
border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:0;z-index:10}
header.bar .brand{font-family:var(--font);font-weight:700;font-size:16px}
header.bar .brand small{font-weight:400;color:var(--muted);font-size:12px;margin-left:10px;font-family:var(--sans)}
.modes{display:flex;gap:2px;background:var(--accent-soft);border-radius:10px;padding:3px}
.modes button{border:none;background:none;padding:6px 15px;border-radius:8px;cursor:pointer;font-size:13px;color:var(--muted);font-family:var(--sans)}
.modes button.on{background:var(--surface);color:var(--accent);font-weight:600;box-shadow:0 1px 4px rgba(0,0,0,.08)}
#split{display:grid;grid-template-columns:1fr 1fr;height:calc(100vh - 52px)}
#split.only-l{grid-template-columns:1fr 0}
#split.only-r{grid-template-columns:0 1fr}
.pane{overflow-y:auto;height:100%;position:relative;scroll-behavior:auto}
#paneL{border-right:1px solid var(--border);background:var(--surface)}
.only-l #paneR,.only-r #paneL{display:none}
.pane-tag{position:sticky;top:0;background:linear-gradient(var(--surface),var(--surface) 70%,transparent);
padding:12px 32px 8px;font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);z-index:2}
#paneL .doc{padding:4px 34px 140px;max-width:640px}
#paneL .doc h1{font-family:var(--font);font-size:26px;margin:18px 0 12px}
#paneL .doc h2{font-family:var(--font);font-size:20px;margin:26px 0 10px;padding-top:10px;border-top:1px solid var(--border)}
#paneL .doc h3{font-size:16px;margin:20px 0 8px}
#paneL .doc p{margin:9px 0}
#paneL .doc blockquote{border-left:3px solid var(--accent);margin:12px 0;padding:6px 14px;background:var(--accent-soft);color:var(--text);border-radius:0 8px 8px 0}
#paneL .doc code{font-family:var(--mono);font-size:.85em;background:var(--accent-soft);padding:1px 5px;border-radius:4px}
#paneL .doc pre{background:var(--ink);color:#e8e2d6;padding:12px 14px;border-radius:8px;overflow-x:auto;font-size:12px}
#paneL .doc pre code{background:none;padding:0;color:inherit}
#paneL .doc table{width:100%;border-collapse:collapse;font-size:12.5px;margin:12px 0;border:1px solid var(--border)}
#paneL .doc th{background:var(--accent-soft);color:var(--muted);text-align:left;font-size:11px;text-transform:uppercase}
#paneL .doc th,#paneL .doc td{padding:6px 9px;border-bottom:1px solid var(--border);vertical-align:top}
#paneL .doc ul,#paneL .doc ol{padding-left:22px}#paneL .doc li{margin:4px 0}
.src-block{scroll-margin-top:60px;border-radius:8px;transition:background .25s,box-shadow .25s;padding:2px 8px;margin:0 -8px}
#paneR .doc{padding:8px 34px 140px}
section.view{margin:0 0 60px;opacity:1;scroll-margin-top:60px}
section.view>h2{font-family:var(--font);font-size:22px;margin:0 0 4px;display:flex;gap:10px;align-items:baseline}
section.view>h2 .n{font-family:var(--mono);font-size:11px;color:var(--accent)}
section.view .insight{color:var(--muted);font-size:13.5px;margin:0 0 18px}
section.view .compressed-out{font-size:12px;color:var(--muted);margin-top:12px}
[data-source-blocks]{scroll-margin-top:60px}
.sync-hi{background:color-mix(in srgb,var(--accent) 12%,transparent)!important;box-shadow:0 0 0 2px var(--accent)!important;border-radius:8px}
.hint{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;font-size:12px;
padding:7px 16px;border-radius:999px;opacity:.9;z-index:20;pointer-events:none;transition:opacity .5s}
"""

JS = """
(function(){
  var wrap=document.getElementById('split'),L=document.getElementById('paneL'),R=document.getElementById('paneR');
  var driver=null,lock=false;
  var rIndex={},lIndex={};
  R.querySelectorAll('[data-source-blocks]').forEach(function(el){
    (el.getAttribute('data-source-blocks')||'').trim().split(/\\s+/).forEach(function(bid){ if(bid&&!rIndex[bid])rIndex[bid]=el; });
  });
  L.querySelectorAll('[data-block-id]').forEach(function(el){ lIndex[el.getAttribute('data-block-id')]=el; });
  function anchorOf(pane,attr){
    var mid=pane.getBoundingClientRect().top+pane.clientHeight*0.30,best=null,bd=1e9;
    pane.querySelectorAll('['+attr+']').forEach(function(el){
      var r=el.getBoundingClientRect(),d=Math.abs(r.top-mid);
      if(r.height>0&&d<bd){bd=d;best=el;}
    });
    return best;
  }
  var hiEls=[];
  function clearHi(){ while(hiEls.length)hiEls.pop().classList.remove('sync-hi'); }
  function hi(el){ if(el){el.classList.add('sync-hi');hiEls.push(el);} }
  function align(dst,target,anchor,src){
    var aOff=anchor.getBoundingClientRect().top-src.getBoundingClientRect().top;
    var tOff=target.getBoundingClientRect().top-dst.getBoundingClientRect().top+dst.scrollTop;
    dst.scrollTop=tOff-aOff;
  }
  function sync(from){
    if(lock)return; lock=true; clearHi();
    if(from==='L'){
      var a=anchorOf(L,'data-block-id');
      if(a){var t=rIndex[a.getAttribute('data-block-id')]; if(t){align(R,t,a,L);hi(a);hi(t);}}
    }else{
      var a2=anchorOf(R,'data-source-blocks');
      if(a2){var bid=(a2.getAttribute('data-source-blocks')||'').trim().split(/\\s+/)[0];var t2=lIndex[bid];
        if(t2){align(L,t2,a2,R);hi(t2);hi(a2);}}
    }
    setTimeout(function(){lock=false;},70);
  }
  L.addEventListener('pointerenter',function(){driver='L';});
  R.addEventListener('pointerenter',function(){driver='R';});
  L.addEventListener('scroll',function(){ if(driver==='L'&&!wrap.classList.contains('only-r'))sync('L'); });
  R.addEventListener('scroll',function(){ if(driver==='R'&&!wrap.classList.contains('only-l'))sync('R'); });
  var btns=document.querySelectorAll('.modes button');
  window.setMode=function(m,ev){
    wrap.classList.remove('only-l','only-r');
    if(m==='l')wrap.classList.add('only-l'); else if(m==='r')wrap.classList.add('only-r');
    btns.forEach(function(b){b.classList.remove('on');});
    if(ev)ev.target.classList.add('on');
  };
  var hint=document.querySelector('.hint');
  if(hint)setTimeout(function(){hint.style.opacity='0';},4200);
})();
"""


def main(blocks_path, frag_dir, views_path, out_path):
    with open(blocks_path) as f:
        blocks = json.load(f)
    with open(views_path) as f:
        plan = json.load(f)

    left = ''.join(render_block(b) for b in blocks)

    right_parts = []
    for v in plan['views']:
        p = os.path.join(frag_dir, v['id'] + '.html')
        if os.path.exists(p):
            with open(p) as f:
                frag = f.read().strip()
            frag = re.sub(r'^```(html)?|```$', '', frag, flags=re.M).strip()
            right_parts.append(frag)
    right = '\n'.join(right_parts)

    title = plan.get('title', '双栏同步阅读器')
    doc = ('<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>' + esc(title) + ' · 双栏</title><style>' + CSS + '</style></head><body>'
           '<header class="bar"><div class="brand">' + esc(title) +
           '<small>左：原文 · 右：信息重组 · 滚动同步</small></div>'
           '<div class="modes">'
           '<button onclick="setMode(\'l\',event)">原文</button>'
           '<button class="on" onclick="setMode(\'both\',event)">双栏</button>'
           '<button onclick="setMode(\'r\',event)">信息重组</button>'
           '</div></header>'
           '<div id="split">'
           '<div class="pane" id="paneL"><div class="pane-tag">Markdown 原文 · 权威源</div><div class="doc">' + left + '</div></div>'
           '<div class="pane" id="paneR"><div class="pane-tag">信息重组 · 人类视图</div><div class="doc">' + right + '</div></div>'
           '</div>'
           '<div class="hint">滚动任一栏，另一栏自动锚定到对应内容并高亮</div>'
           '<script>' + JS + '</script></body></html>')

    with open(out_path, 'w') as f:
        f.write(doc)
    print('reader -> %s (%d bytes, %d blocks left / %d views right)' % (out_path, len(doc), len(blocks), len(right_parts)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
