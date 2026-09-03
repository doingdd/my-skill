#!/bin/bash
# git-push-guard 行为测试：scratch 仓库 + 受控 HOME，逐场景断言 hook 输出。
# 用法：bash git-push-guard/scripts/test_hook.sh
# 断言语义：allow = 退出码 0 且无输出；ask = 输出含 permissionDecision:"ask"。

set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/block-push-default-branch.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

export HOME="$WORK/home"
mkdir -p "$HOME/.claude/hooks"
ALLOWLIST="$HOME/.claude/hooks/push-default-branch-allowlist.txt"
setlist() { if [ -n "${1:-}" ]; then printf '%s\n' "$1" > "$ALLOWLIST"; else : > "$ALLOWLIST"; fi; }

mkgit() { local d="$1"; shift; git -C "$d" -c user.email=t@t -c user.name=t "$@"; }
mkrepo() { # mkrepo <路径> <初始分支> ；返回后当前在初始分支，含 1 提交，配 bare 远端 <路径>.git
  git init -q -b "$2" "$1"
  mkgit "$1" commit -q --allow-empty -m init
  git init -q --bare "$1.git"
  git -C "$1" remote add origin "$1.git"
}

# 主仓库：master + feature
mkrepo "$WORK/repo" master
git -C "$WORK/repo" checkout -q -b feature
mkgit "$WORK/repo" commit -q --allow-empty -m f
git -C "$WORK/repo" checkout -q master
# 仓库 B：master（跨仓库 -C 目标）
mkrepo "$WORK/repoB" master
# 带空格路径的仓库：master
mkrepo "$WORK/repo with space" master
# trunk 仓库：无 master/main
mkrepo "$WORK/repoTrunk" trunk

pass=0; fail=0
run() { # run <名称> <allow|ask> <主仓库当前分支> <命令> [allowlist 内容]
  local label="$1" expect="$2" branch="$3" cmd="$4" list="${5:-}"
  git -C "$WORK/repo" checkout -q "$branch"
  setlist "$list"
  local input out rc got
  input=$(jq -n --arg cmd "$cmd" --arg cwd "$WORK/repo" '{tool_input:{command:$cmd}, cwd:$cwd}')
  out=$(printf '%s' "$input" | bash "$HOOK"); rc=$?
  judge
}
raw() { # raw <名称> <allow|ask> <cwd> <命令> [allowlist 内容]（不切主仓库分支）
  local label="$1" expect="$2" cwd="$3" cmd="$4" list="${5:-}"
  setlist "$list"
  local input out rc got
  input=$(jq -n --arg cmd "$cmd" --arg cwd "$cwd" '{tool_input:{command:$cmd}, cwd:$cwd}')
  out=$(printf '%s' "$input" | bash "$HOOK"); rc=$?
  judge
}
judge() {
  if [ "$expect" = allow ]; then
    if [ $rc -eq 0 ] && [ -z "$out" ]; then got=allow; else got="other(rc=$rc,out=${out:0:60})"; fi
  else
    if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q 'permissionDecision' && printf '%s' "$out" | grep -q '"ask"'; then got=ask; else got="other(rc=$rc,out=${out:0:60})"; fi
  fi
  if [ "$got" = "$expect" ]; then
    echo "✓ ${label}"; pass=$((pass+1))
  else
    echo "✗ ${label} 期望 ${expect} 实得 ${got}"; fail=$((fail+1))
  fi
}

run "非 git 命令放行"                    allow master "ls -la"
run "非 push 的 git 命令放行"             allow master "git status"
run "推功能分支放行"                      allow feature "git push origin feature"
run "显式推 master 拦截"                  ask   master "git push origin master"
run "显式推 main 拦截"                    ask   master "git push origin main"
run "refspec main:main 拦截"              ask   master "git push origin main:main"
run "refspec HEAD:main 拦截"              ask   master "git push origin HEAD:main"
run "refspec 删远端 main 拦截"            ask   master "git push origin :main"
run "--force 推 main 拦截"                ask   master "git push --force origin main"
run "master 上裸 push 拦截"               ask   master "git push"
run "master 上裸 push origin 拦截"        ask   master "git push origin"
run "feature 上裸 push 放行"              allow feature "git push"
run "allowlist 命中放行（未解析路径）"     allow master "git push origin master" "$WORK/repo"
run "allowlist 含注释/空行仍命中"          allow master "git push origin main" "# 注释

$WORK/repo"
run "allowlist 未命中仍拦"                ask   feature "git push origin main" "/some/other/repo"
run "git -C 指定路径推 main 拦截"         ask   master "git -C $WORK/repo push origin main"
run "--all 连 master 一起推拦截"          ask   master "git push --all origin"
run "--mirror 拦截"                       ask   master "git push --mirror origin"

# ── 跨仓库：判定对象必须是 -C 目标仓库 ──
raw "跨仓库 -C --all（cwd 在 feature 仓库）拦截"   ask "$WORK/repo"  "git -C $WORK/repoB push --all"          "$WORK/repo"
raw "跨仓库 -C 显式推 main 拦截"                   ask "$WORK/repo"  "git -C $WORK/repoB push origin main"    "$WORK/repo"
raw "跨仓库 -C 裸 push（B 在 master）拦截"          ask "$WORK/repo"  "git -C $WORK/repoB push"                "$WORK/repo"
raw "allowlist 的是 cwd 仓库 A 不放行 -C 推 B"      ask "$WORK/repo"  "git -C $WORK/repoB push origin main"    "$WORK/repo"
raw "allowlist 的是目标仓库 B 才放行"               allow "$WORK/repo" "git -C $WORK/repoB push origin main"   "$WORK/repoB"
# ── 引号空格路径（thread 2）──
raw "git -C \"带空格路径\" 推 master 拦截"          ask "$WORK/repo"  "git -C \"$WORK/repo with space\" push origin master"
raw "allowlist 带空格路径命中放行"                  allow "$WORK/repo" "git -C \"$WORK/repo with space\" push origin master" "$WORK/repo with space"
# ── 默认分支等价写法（thread 3 及同族）──
run "refs/heads/main 拦截"                ask   master "git push origin refs/heads/main"
run "origin/main 为目标拦截"              ask   master "git push origin origin/main"
run "@{u} 上游拦截"                       ask   master "git push origin @{u}"
# ── --all 与仓库内容判定（当前分支非默认但仓库有本地 master）──
run "feature 上 --all 连本地 master 推拦截"  ask   feature "git push --all origin"
raw "trunk 仓库（无 master/main）--all 放行"  allow "$WORK/repoTrunk" "git push --all origin"
# ── 多 push 位点从宽拦截 ──
raw "一条命令两个 push 位点拦截"                  ask "$WORK/repo"  "git push origin feature && git -C $WORK/repoB push --all"

echo "── 通过 $pass / 失败 $fail"
[ "$fail" -eq 0 ]
