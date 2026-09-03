#!/bin/bash
# SessionStart hook: 若当前目录在 git 仓库内，注入一行仓库状态，
# 让每个 session 开局就知道自己站在哪个分支、离 master 多远、工作区脏不脏。
top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null)
master=""
for m in master main; do
  git show-ref -q "refs/remotes/origin/$m" && { master=$m; break; }
done

# --no-optional-locks：session 开局的状态查询绝不写 index.lock，不与运行中的 git 操作抢锁
dirty=$(git --no-optional-locks status --porcelain 2>/dev/null | wc -l | tr -d ' ')
line="[repo-status] $(basename "$top") | 分支: $branch | 工作区改动: $dirty"

if [ -n "$master" ]; then
  counts=$(git rev-list --left-right --count "origin/$master...HEAD" 2>/dev/null)
  behind=$(echo "$counts" | awk '{print $1}')
  ahead=$(echo "$counts" | awk '{print $2}')
  line="$line | vs origin/$master: ahead ${ahead:-?} / behind ${behind:-?}（基于上次 fetch）"
fi

if [ -n "$master" ] && { [ "$branch" != "$master" ] || [ "${behind:-0}" -gt 0 ] 2>/dev/null; }; then
  line="$line | 若本 session 是开新任务→先归位(repo-tidy)；续任务→就地继续"
fi

echo "$line"
exit 0
