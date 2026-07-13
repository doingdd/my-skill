#!/usr/bin/env python3
"""UserPromptSubmit hook: 用户输入中出现注册表内的仓库名时，注入解析结果。

只读缓存（~/.claude/repo-map-cache.json），不扫描不联网，毫秒级返回；
未命中时静默退出（零注入税）。任何异常都不阻断用户输入，
但必须记录到 ~/.claude/logs/repo-map-hook.jsonl（不静默吞异常）。
"""
import json
import re
import sys
import time
from pathlib import Path

CACHE_PATH = Path.home() / '.claude' / 'repo-map-cache.json'
LOG_PATH = Path.home() / '.claude' / 'logs' / 'repo-map-hook.jsonl'
MIN_ALIAS_LEN = 3
MAX_HITS = 5
# 自定义边界: 中文与英文名相邻（"跟skills-flow对接"）也算命中，
# 但 "kube" 不得命中 "kubernetes"，"skills-flow" 不得命中 "skills-flow-v2"
BOUNDARY_L, BOUNDARY_R = r'(?<![a-z0-9_-])', r'(?![a-z0-9_-])'


def log(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%d %H:%M:%S'), **record},
                           ensure_ascii=False) + '\n')


def match_repos(prompt, cwd, repos):
    low = prompt.lower()
    hits = []
    for r in repos.values():
        if cwd == r['path'] or cwd.startswith(r['path'] + '/'):
            continue  # 当前所在仓库自身不注入
        aliases = (a for a in r['aliases'] if len(a) >= MIN_ALIAS_LEN)
        if any(re.search(BOUNDARY_L + re.escape(a) + BOUNDARY_R, low)
               for a in aliases):
            hits.append(r)
    return hits[:MAX_HITS]


def main():
    data = json.loads(sys.stdin.read() or '{}')
    prompt = data.get('prompt') or ''
    cwd = data.get('cwd') or ''
    if not prompt or not CACHE_PATH.exists():
        return
    repos = json.loads(CACHE_PATH.read_text()).get('repos', {})
    hits = match_repos(prompt, cwd, repos)
    if not hits:
        return
    lines = '\n'.join(
        f'- {r["name"]} → {r["path"]}（{r["role"]}）'
        + (f' —— {r["summary"]}' if r['summary'] else '') for r in hits)
    context = (
        '本地仓库地图命中（repo-map 自动注入）:\n' + lines +
        '\n约定: 引用时优先读该仓库 README/知识入口而非全库遍历；'
        '"第三方·只读"仓库禁止写入；为当前项目任务修改其他仓库时，'
        '改动在对方仓库独立成 commit、独立授权，不与当前仓库改动混杂；'
        '关联沉淀遵循"宁可漏掉，不能沉淀错"：仅当本次真实读取/修改了该仓库、且关系会复发（依赖/对接/上下游）时，才向用户一句话确认后追加到当前项目 CLAUDE.md 的"## 关联仓库"节；仅提及、误提及、一次性查询、cwd 为全局配置目录（如 ~/.claude）一律不沉淀。')
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': context}}, ensure_ascii=False))
    log({'cwd': cwd, 'hits': [r['name'] for r in hits]})


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # hook 绝不阻断用户输入；异常入日志后放行
        try:
            log({'error': repr(exc)})
        except OSError:
            pass
