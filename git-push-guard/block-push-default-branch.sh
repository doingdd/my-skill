#!/bin/bash
# PreToolUse(Bash) hook: 拦截直推共享默认分支（master/main）
# 按项目永久放行：把仓库根目录绝对路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt（一行一个，支持 # 注释）
# 放行条目兼容符号链接写法（/var/... 与 /private/var/... 等价，两侧都做 pwd -P 归一）
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# 识别 git push（含 git -C <path> push 形态）
case "$cmd" in
  *"git push"*|*"git -C "*push*) ;;
  *) exit 0 ;;
esac

allowlist="$HOME/.claude/hooks/push-default-branch-allowlist.txt"
cwd=$(printf '%s' "$input" | jq -r '.cwd // "."')
top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
if [ -f "$allowlist" ] && [ -n "$top" ]; then
  while IFS= read -r entry; do
    entry=${entry%%#*}
    entry=$(printf '%s' "$entry" | tr -d '[:space:]')
    [ -z "$entry" ] && continue
    [ "$entry" = "$top" ] && exit 0
    resolved=$(cd "$entry" 2>/dev/null && pwd -P) && [ "$resolved" = "$top" ] && exit 0
  done < <(grep -v '^[[:space:]]*#' "$allowlist")
fi

deny() {
  jq -rn --arg reason "$1（永久放行本仓库：将仓库根路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt）" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

# push 的完整前缀：git [ -C <path> ] push —— 之后的参数区
prefix='(^|[[:space:]])git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+push'
args_after_push() {
  printf '%s' "$cmd" | sed -E "s/.*git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+push//"
}

# 显式指定 master/main 作为目标（含 refspec 形式 xxx:master）
if printf '%s' "$cmd" | grep -qE "${prefix}[^|&;]*[[:space:]](master|main)([[:space:]]|\$)"; then
  deny "即将直推默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi
if printf '%s' "$cmd" | grep -qE "${prefix}[^|&;]*:(master|main)([[:space:]]|\$)"; then
  deny "即将通过 refspec 推送到默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi

# master/main 上：没有显式给出非默认分支目标的 push 一律拦截
# 覆盖：裸 push、只带 flags、只带 remote 名、--all/--mirror
branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
if [ "$branch" = "master" ] || [ "$branch" = "main" ]; then
  remotes="$(git -C "$cwd" remote 2>/dev/null)"
  has_explicit_target=0
  for tok in $(args_after_push | tr '|&;' '  '); do
    case $tok in -*) continue ;; esac          # flags（--force-with-lease=main:x 之类整体当 flag，宁拦勿放）
    is_remote=0
    for r in $remotes; do
      if [ "$tok" = "$r" ]; then is_remote=1; break; fi
    done
    [ "$is_remote" = 1 ] && continue            # remote 名不是目标
    has_explicit_target=1                       # 剩余非 flag 非 remote token：显式分支/refspec
    break
  done
  [ "$has_explicit_target" = 0 ] && deny "当前在默认分支 ${branch}，即将直推（含 --all/--mirror/仅 remote 形态）。共享项目请切功能分支；个人/小型项目确认后放行。"
fi

exit 0
