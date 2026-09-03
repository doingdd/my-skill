#!/bin/bash
# git-repo-status.sh 行为测试：scratch 仓库矩阵，逐场景断言 [repo-status] 输出。
# 用法：bash repo-tidy/scripts/test_git_repo_status.sh
# 断言协议：以 ! 开头 = 必须不命中；EMPTY = 输出必须为空串；其余 = egrep 必须命中。

set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/scripts/git-repo-status.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0; fail=0
g() { local d="$1"; shift; git -C "$d" -c user.email=t@t -c user.name=t "$@"; }

run() { # run <名称> <cwd> <断言...>
  local label="$1" dir="$2"; shift 2
  local out rc a ok=1
  out=$(cd "$dir" && bash "$HOOK" 2>/dev/null); rc=$?
  for a in "$@"; do
    if [ "$a" = EMPTY ]; then
      if [ -n "$out" ]; then echo "✗ ${label} 期望空输出 实得: ${out:0:80}"; ok=0; fi
      continue
    fi
    if [ "${a#!}" != "$a" ]; then
      if printf '%s' "$out" | grep -qE "${a#!}"; then echo "✗ ${label} 不应命中 [${a#!}]"; ok=0; fi
      continue
    fi
    if ! printf '%s' "$out" | grep -qE "$a"; then
      echo "✗ ${label} 断言未命中 [$a] 实得: $(printf '%s' "$out" | head -1)"
      ok=0
    fi
  done
  if [ "$ok" = 1 ]; then echo "✓ ${label}"; pass=$((pass+1)); else fail=$((fail+1)); fi
}

# T1 非 git 目录
mkdir -p "$WORK/plain"
run "非 git 目录无输出" "$WORK/plain" EMPTY

# T2 标准仓库：master 同步干净
mkrepo() { git init -q -b "$2" "$1" && g "$1" commit -q --allow-empty -m init; }
mkrepo "$WORK/std" master
g "$WORK/std" commit -q --allow-empty -m second
git init -q --bare "$WORK/std-origin.git"
git -C "$WORK/std" remote add origin "$WORK/std-origin.git"
g "$WORK/std" push -q origin master
run "master 同步干净：无归位建议" "$WORK/std" '\[repo-status\]' '分支: master' '工作区改动: 0' 'ahead 0 / behind 0' '!归位'

# T3 ahead 1
g "$WORK/std" commit -q --allow-empty -m wip
run "ahead 1：无归位建议" "$WORK/std" 'ahead 1 / behind 0' '!归位'
g "$WORK/std" push -q origin master

# T4 behind 1（wip 已上远端，本地回退一格 → 远端领先 1）
g "$WORK/std" reset -q --hard HEAD~1
g "$WORK/std" fetch -q origin
run "behind 1：有归位建议" "$WORK/std" 'behind 1' '归位'

# T5 工作区脏
g "$WORK/std" reset -q --hard origin/master
echo x > "$WORK/std/a.txt"; mkdir -p "$WORK/std/d"; echo y > "$WORK/std/d/b.txt"
run "工作区 2 处改动（含未跟踪）" "$WORK/std" '工作区改动: 2'

# T6 feature 分支
g "$WORK/std" checkout -q -b feature
run "feature 分支：有归位建议" "$WORK/std" '分支: feature' '归位'

# T7 trunk 流派仓库（无 origin/master|main）
mkrepo "$WORK/trunk" trunk
run "trunk 仓库：不弹归位建议" "$WORK/trunk" '\[repo-status\]' '分支: trunk' '!归位' '!vs origin'

# T8 无远端仓库
mkrepo "$WORK/solo" master
run "无远端：无 vs 段" "$WORK/solo" '\[repo-status\]' '分支: master' '!vs origin' '!归位'

# T9 空仓库（无提交）
mkdir -p "$WORK/empty" && git init -q -b master "$WORK/empty"
run "空仓库：分支名可读、不崩" "$WORK/empty" '\[repo-status\]' '分支: master' '!ahead \?'

# T10 detached HEAD
g "$WORK/std" checkout -q --detach
run "detached HEAD：分支显示 HEAD 且有归位建议" "$WORK/std" '分支: HEAD' '归位'

# T11 linked worktree
g "$WORK/std" checkout -q feature
g "$WORK/std" worktree add -q -b wt2 "$WORK/wt"
run "linked worktree 正常显示" "$WORK/wt" '\[repo-status\]' '分支: wt2'

echo "── 通过 $pass / 失败 $fail"
[ "$fail" -eq 0 ]
