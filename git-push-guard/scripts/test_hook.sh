#!/bin/bash
# git-push-guard 行为测试：scratch 仓库 + 受控 HOME，逐场景断言 hook 输出。
# 用法：bash git-push-guard/scripts/test_hook.sh
# 断言语义：allow = 退出码 0 且无输出；ask = 输出含 permissionDecision:"ask"。

set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/block-push-default-branch.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 假 HOME：allowlist 完全受控
export HOME="$WORK/home"
mkdir -p "$HOME/.claude/hooks"
ALLOWLIST="$HOME/.claude/hooks/push-default-branch-allowlist.txt"

# scratch 仓库：master + feature 各一提交，配 bare 远端
mkdir -p "$WORK/repo"
git -C "$WORK/repo" init -q -b master "$WORK/repo"
git -C "$WORK/repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
git -C "$WORK/repo" checkout -q -b feature
git -C "$WORK/repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m f
git -C "$WORK/repo" checkout -q master
git -C "$WORK/repo" remote add origin "$WORK/remote.git"
git init -q --bare "$WORK/remote.git"

pass=0; fail=0
run() { # run <名称> <期望 allow|ask> <当前分支> <命令> [allowlist 内容]
  local label="$1" expect="$2" branch="$3" cmd="$4" list="${5:-}"
  git -C "$WORK/repo" checkout -q "$branch"
  if [ -n "$list" ]; then printf '%s\n' "$list" > "$ALLOWLIST"; else : > "$ALLOWLIST"; fi
  local input out rc got
  input=$(jq -n --arg cmd "$cmd" --arg cwd "$WORK/repo" '{tool_input:{command:$cmd}, cwd:$cwd}')
  out=$(printf '%s' "$input" | bash "$HOOK"); rc=$?
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
run "allowlist 命中放行（未解析路径，钉符号链接容忍）"   allow master "git push origin master" "$WORK/repo"
run "allowlist 含注释/空行仍命中"          allow master "git push origin main" "# 注释

$WORK/repo"
run "allowlist 未命中仍拦"                ask   feature "git push origin main" "/some/other/repo"
# —— 以下为读代码疑似的绕过洞，先用测试钉住事实 ——
run "git -C 指定路径推 main 拦截"         ask   master "git -C $WORK/repo push origin main"
run "--all 连 master 一起推拦截"          ask   master "git push --all origin"
run "--mirror 拦截"                       ask   master "git push --mirror origin"

echo "── 通过 $pass / 失败 $fail"
[ "$fail" -eq 0 ]
