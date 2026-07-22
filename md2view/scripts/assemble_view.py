#!/usr/bin/env python3
"""C 组第三遍：组装概念视图 + 溯源下钻抽屉。
views.json + fragments_c/vX.html + blocks.json -> C.html
页面 = 压缩层（概念视图）在上 + 下钻抽屉（点击任何 data-source-blocks 元素看源文）。
"""
import html as htmllib
import json
import os
import re
import sys

TOKENS_CSS = """
:root{--bg:#faf9f6;--surface:#fff;--text:#1d1a16;--muted:#6f6a61;--accent:#9a4a1f;
--accent-soft:#f3e5da;--border:#e5e0d6;--ink:#211d18;--good:#3d6b4f;--warn:#b45309;
--font:'Source Han Serif SC','Noto Serif CJK SC',Georgia,serif;
--sans:'PingFang SC','Noto Sans CJK SC',-apple-system,sans-serif;
--mono:'SF Mono',ui-monospace,Menlo,monospace}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.7;font-size:15.5px}
.shell{display:grid;grid-template-columns:232px minmax(0,1fr);max-width:1340px;margin:0 auto}
nav.side{position:sticky;top:0;height:100vh;overflow-y:auto;padding:40px 20px;border-right:1px solid var(--border)}
nav.side .brand{font-family:var(--font);font-weight:700;font-size:16px;margin-bottom:4px}
nav.side .sub{font-size:12px;color:var(--muted);margin-bottom:22px;line-height:1.5}
nav.side a{display:block;padding:7px 10px;margin:1px 0;border-radius:8px;color:var(--muted);text-decoration:none;font-size:13.5px}
nav.side a:hover,nav.side a.on{background:var(--accent-soft);color:var(--text)}
nav.side a .n{font-family:var(--mono);font-size:10.5px;color:var(--accent);margin-right:8px}
nav.side .ft{margin-top:22px;padding-top:14px;border-top:1px solid var(--border);font-size:12px;color:var(--muted)}
nav.side .ft a{display:inline;padding:0;color:var(--accent)}
main{max-width:1080px;margin:0 auto;padding:52px 40px 140px;min-width:0}
@media(max-width:900px){.shell{grid-template-columns:1fr}nav.side{position:static;height:auto;border-right:none;border-bottom:1px solid var(--border)}}
header.page{margin-bottom:18px}
header.page .kicker{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
header.page h1{font-family:var(--font);font-size:40px;margin:0 0 10px;letter-spacing:-.01em}
header.page .sub{color:var(--muted);font-size:16px;max-width:640px}
.howto{font-size:13px;color:var(--muted);background:var(--accent-soft);border-radius:10px;padding:10px 16px;display:inline-block;margin:14px 0 34px}
section.view{margin:0 0 72px;scroll-margin-top:24px;opacity:0;transform:translateY(18px);transition:opacity .55s ease,transform .55s ease}
section.view.in{opacity:1;transform:none}
@media(prefers-reduced-motion:reduce){section.view{opacity:1;transform:none;transition:none}}
section.view>h2{font-family:var(--font);font-size:25px;margin:0 0 4px;display:flex;gap:12px;align-items:baseline}
section.view>h2 .n{font-family:var(--mono);font-size:12px;color:var(--accent)}
section.view .insight{color:var(--muted);font-size:14px;margin:0 0 22px;max-width:680px}
section.view .compressed-out{font-size:12.5px;color:var(--muted);margin-top:14px}
[data-source-blocks]{cursor:pointer}
svg [data-source-blocks]:hover{filter:brightness(1.06)}
[data-source-blocks]:not(svg *):hover{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
#drawer{position:fixed;top:0;right:0;width:min(480px,92vw);height:100vh;background:var(--surface);
border-left:1px solid var(--border);box-shadow:-24px 0 60px rgba(20,15,8,.12);transform:translateX(105%);
transition:transform .22s ease;z-index:50;display:flex;flex-direction:column}
#drawer.open{transform:none}
#drawer .head{display:flex;justify-content:space-between;align-items:center;padding:18px 22px;border-bottom:1px solid var(--border)}
#drawer .head b{font-family:var(--font);font-size:16px}
#drawer .head button{border:none;background:var(--accent-soft);color:var(--accent);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px}
#drawer .body{overflow-y:auto;padding:18px 22px;flex:1}
#drawer .src{margin-bottom:18px}
#drawer .src .tag{font-family:var(--mono);font-size:10.5px;color:var(--accent);letter-spacing:.08em;margin-bottom:6px}
#drawer .src pre{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:12px 14px;
font-family:var(--mono);font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;margin:0;color:var(--text)}
#scrim{position:fixed;inset:0;background:rgba(20,15,8,.18);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}
#scrim.open{opacity:1;pointer-events:auto}
footer.fulltext{border-top:1px solid var(--border);padding-top:28px;color:var(--muted);font-size:13.5px}
footer.fulltext a{color:var(--accent)}
@media(max-width:800px){main{padding:28px 18px 100px}}
"""

DRAWER_JS = """
const BLOCKS = JSON.parse(document.getElementById('source-blocks').textContent);
const byId = Object.fromEntries(BLOCKS.map(b => [b.id, b]));
const drawer = document.getElementById('drawer');
const scrim = document.getElementById('scrim');
const body = drawer.querySelector('.body');
const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
function openDrawer(ids, label){
  drawer.querySelector('.head b').textContent = label || '来源 · ' + ids.length + ' 个源块';
  body.innerHTML = ids.map(id => {
    const b = byId[id];
    if(!b) return '';
    return '<div class="src"><div class="tag">' + id + ' · ' + b.type + '</div><pre>' + esc(b.raw) + '</pre></div>';
  }).join('');
  drawer.classList.add('open'); scrim.classList.add('open');
}
function closeDrawer(){ drawer.classList.remove('open'); scrim.classList.remove('open'); }
document.addEventListener('click', e => {
  const el = e.target.closest('[data-source-blocks]');
  if(!el || drawer.contains(e.target)) return;
  const ids = el.getAttribute('data-source-blocks').trim().split(/\\s+/).filter(Boolean);
  if(!ids.length) return;
  e.preventDefault();
  const label = el.getAttribute('data-label') || el.textContent.trim().slice(0, 24);
  openDrawer(ids, label);
});
scrim.addEventListener('click', closeDrawer);
drawer.querySelector('.head button').addEventListener('click', closeDrawer);
document.addEventListener('keydown', e => { if(e.key === 'Escape') closeDrawer(); });
const io = new IntersectionObserver(es => es.forEach(x => { if(x.isIntersecting){ x.target.classList.add('in'); io.unobserve(x.target); } }), { threshold: 0.06 });
document.querySelectorAll('section.view').forEach(s => io.observe(s));
"""


def main(views_path, frag_dir, blocks_path, out_path):
    with open(views_path) as f:
        plan = json.load(f)
    with open(blocks_path) as f:
        blocks = json.load(f)

    parts = []
    problems = []
    for i, v in enumerate(plan['views'], 1):
        path = os.path.join(frag_dir, f"{v['id']}.html")
        if not os.path.exists(path):
            problems.append(f"missing fragment: {v['id']}")
            continue
        with open(path) as f:
            frag = f.read().strip()
        frag = re.sub(r'^```(html)?|```$', '', frag, flags=re.M).strip()
        if '<h2' not in frag:
            frag = (f'<h2><span class="n">{i:02d}</span>{htmllib.escape(v["title"])}</h2>'
                    f'<p class="insight">{htmllib.escape(v["insight"])}</p>{frag}')
        if not re.search(r'<section[^>]*class="view"', frag):
            frag = f'<section class="view" id="{v["id"]}">{frag}</section>'
        parts.append(frag)

    href = plan.get('fulltext_href')
    fulltext_nav = f'<div class="ft">查阅型细节在<a href="{href}">全文层</a></div>' if href else ''
    fulltext_note = f'压缩层刻意省略的内容在<a href="{href}">全文层</a>。' if href else '压缩层刻意省略的内容可通过溯源抽屉回看原文。'

    nav_items = ''.join(
        f'<a href="#{v["id"]}"><span class="n">{i:02d}</span>{htmllib.escape(v["title"])}</a>'
        for i, v in enumerate(plan['views'], 1))

    blocks_json = json.dumps(
        [{'id': b['id'], 'type': b['type'], 'raw': b['raw']} for b in blocks],
        ensure_ascii=False).replace('</', '<\\/')

    doc = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{plan.get('title', '概念视图')}</title>
<style>{TOKENS_CSS}</style>
</head>
<body>
<div class="shell">
<nav class="side">
<div class="brand">{plan.get('title', '概念视图')}</div>
<div class="sub">信息重编码 · {len(parts)} 个概念视图</div>
{nav_items}
{fulltext_nav}
</nav>
<main>
<header class="page">
<div class="kicker">Concept Views · 压缩层</div>
<h1>{plan.get('title', '验收方法 · 概念视图')}</h1>
<p class="sub">{plan.get('subtitle', '同一份文档的信息重组织：不是按章节渲染，而是抽出概念结构重新编码。')}</p>
<div class="howto">点击任何图形元素 → 右侧抽屉查看它提炼自的原文（有损压缩 + 可回溯 = 无损）</div>
</header>
{''.join(parts)}
<footer class="fulltext">
{fulltext_note}{htmllib.escape(plan.get('coverage_note', ''))}
</footer>
</main>
</div>
<div id="scrim"></div>
<div id="drawer"><div class="head"><b>来源</b><button>关闭 esc</button></div><div class="body"></div></div>
<script type="application/json" id="source-blocks">{blocks_json}</script>
<script>{DRAWER_JS}</script>
</body>
</html>"""
    with open(out_path, 'w') as f:
        f.write(doc)
    print(f'assembled -> {out_path} ({len(doc)} bytes, {len(parts)} views)')
    for p in problems:
        print('WARN:', p)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
