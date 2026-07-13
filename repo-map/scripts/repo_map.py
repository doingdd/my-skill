#!/usr/bin/env python3
"""本地 git 仓库地图（repo-map）：扫描、增量缓存、名称解析。

用法:
  repo_map.py scan            强制全量重扫（重新分析所有仓库）
  repo_map.py resolve <词>    解析名称/关键词 → 路径与读写角色（自动增量同步）
  repo_map.py list            列出全部仓库（自动增量同步）

配置: ~/.claude/repo-map.config.json
  {"scan_roots": ["~/code"], "self_emails": ["you@example.com"],
   "trusted_hosts": ["gitlab.your-org.com"]}
缓存: ~/.claude/repo-map-cache.json —— 纯产物，勿手工编辑，删除后自动重建。

角色判定（读写边界的证据链）:
  有本人 commit → 自研·可写；无 remote → 本地·可写（不存在上游，谈不上第三方）；
  remote host 在 trusted_hosts → 协作·可写；其余 → 第三方·只读。

新增/删除/移动仓库无需任何维护动作：每次 resolve/list 先做低成本一致性
检查（find .git 清单 vs 缓存路径集合），只对差集做增量分析与剪枝。
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CONFIG_PATH = Path.home() / '.claude' / 'repo-map.config.json'
CACHE_PATH = Path.home() / '.claude' / 'repo-map-cache.json'
MAXDEPTH = 6
SKIP_DIRS = {'node_modules', 'venv', '.venv', 'vendor', '__pycache__',
             'dist', 'build', 'target', 'Library'}


def fail(msg):
    print(f'repo-map 错误: {msg}', file=sys.stderr)
    sys.exit(1)


def load_config():
    if not CONFIG_PATH.exists():
        fail(f'缺少配置 {CONFIG_PATH}，示例: '
             '{"scan_roots": ["~/code"], "self_emails": ["you@example.com"], '
             '"trusted_hosts": ["gitlab.your-org.com"]}')
    cfg = json.loads(CONFIG_PATH.read_text())
    roots = [Path(r).expanduser() for r in cfg.get('scan_roots', [])]
    if not roots:
        fail('配置中 scan_roots 为空')
    return {'scan_roots': roots,
            'self_emails': [e for e in cfg.get('self_emails', []) if e],
            'trusted_hosts': set(cfg.get('trusted_hosts', []))}


def find_repo_paths(roots):
    """逐层下探找仓库根：目录含 .git 即收录并停止下探。

    仓库内部（含 .git/objects）完全不遍历，嵌套仓库（子模块/vendor）天然剔除。
    """
    found = set()

    def walk(d, depth):
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        if any(e.name == '.git' for e in entries):
            found.add(d)
            return
        if depth >= MAXDEPTH:
            return
        for e in entries:
            if not e.is_dir(follow_symlinks=False):
                continue
            if e.name.startswith('.') or e.name in SKIP_DIRS:
                continue
            walk(e.path, depth + 1)

    for root in roots:
        if not root.exists():
            print(f'警告: 扫描根不存在，跳过: {root}', file=sys.stderr)
            continue
        walk(str(root), 1)
    return found


def git(path, *args):
    try:
        r = subprocess.run(['git', '-C', path, *args],
                           capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return ''
    return r.stdout.strip() if r.returncode == 0 else ''


def readme_summary(path):
    for name in ('README.md', 'readme.md', 'README.rst', 'README'):
        f = Path(path) / name
        if not f.is_file():
            continue
        for line in f.read_text(errors='replace').splitlines():
            text = line.strip().lstrip('#').strip()
            if text:
                return text[:80]
        return ''
    return ''


def remote_host(remote):
    m = re.search(r'^(?:\w+://)?(?:[^@/]+@)?([^:/]+)', remote)
    return m.group(1) if m else ''


def decide_role(path, remote, cfg):
    if any(git(path, 'log', '--all', '-1', f'--author={e}', '--format=%H')
           for e in cfg['self_emails']):
        return '自研·可写'
    if not remote:
        return '本地·可写'
    if remote_host(remote) in cfg['trusted_hosts']:
        return '协作·可写'
    return '第三方·只读'


def analyze_repo(path, cfg):
    remote = git(path, 'remote', 'get-url', 'origin')
    aliases = {Path(path).name.lower()}
    m = re.search(r'[/:]([^/:]+?)(?:\.git)?$', remote) if remote else None
    if m:
        aliases.add(m.group(1).lower())
    return {
        'name': Path(path).name,
        'path': path,
        'role': decide_role(path, remote, cfg),
        'remote': remote,
        'last_active': git(path, 'log', '-1', '--format=%cs'),
        'summary': readme_summary(path),
        'aliases': sorted(aliases),
    }


def sync(cfg, force=False):
    old = (json.loads(CACHE_PATH.read_text()).get('repos', {})
           if CACHE_PATH.exists() else {})
    current = find_repo_paths(cfg['scan_roots'])
    kept = {} if force else {p: r for p, r in old.items() if p in current}
    fresh = {p: analyze_repo(p, cfg)
             for p in sorted(current - set(kept))}
    repos = {**kept, **fresh}
    removed = sorted(set(old) - current)
    if fresh or removed or force or not CACHE_PATH.exists():
        CACHE_PATH.write_text(json.dumps(
            {'updated': time.strftime('%Y-%m-%d %H:%M:%S'), 'repos': repos},
            ensure_ascii=False, indent=1))
    return repos, len(fresh), len(removed)


def fmt(r):
    summary = f' —— {r["summary"]}' if r['summary'] else ''
    return (f'{r["name"]} → {r["path"]}'
            f'（{r["role"]}，最近活跃 {r["last_active"] or "?"}）{summary}')


def cmd_resolve(cfg, keyword):
    repos, _, _ = sync(cfg)
    kw = keyword.lower()
    exact = [r for r in repos.values() if kw in r['aliases']]
    partial = [r for r in repos.values()
               if r not in exact and any(kw in a for a in r['aliases'])]
    fuzzy = [r for r in repos.values()
             if r not in exact + partial and kw in r['summary'].lower()]
    hits = exact + partial + fuzzy
    if not hits:
        print(f'未命中 "{keyword}"。可能原因: 仓库在扫描根之外'
              f'（编辑 {CONFIG_PATH} 的 scan_roots 后重试），或换个关键词/用 list 全量查看。')
        sys.exit(2)
    for r in hits[:10]:
        print(fmt(r))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('scan', 'resolve', 'list'):
        print(__doc__)
        sys.exit(1)
    cfg = load_config()
    cmd = sys.argv[1]
    if cmd == 'scan':
        t0 = time.time()
        repos, added, removed = sync(cfg, force=True)
        print(f'全量重扫完成: {len(repos)} 个仓库'
              f'（重析 {added}，剪枝 {removed}），耗时 {time.time() - t0:.1f}s')
    elif cmd == 'resolve':
        if len(sys.argv) < 3:
            fail('用法: resolve <名称或关键词>')
        cmd_resolve(cfg, sys.argv[2])
    else:
        repos, _, _ = sync(cfg)
        for r in sorted(repos.values(),
                        key=lambda x: x['last_active'] or '', reverse=True):
            print(fmt(r))


if __name__ == '__main__':
    main()
