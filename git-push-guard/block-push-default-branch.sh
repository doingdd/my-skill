#!/bin/bash
# PreToolUse(Bash) hook: 拦截直推共享默认分支（master/main）
# 按项目永久放行：把仓库根目录绝对路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt（一行一个，支持 # 注释）
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

case "$cmd" in
  *"git push"*) ;;
  *) exit 0 ;;
esac

allowlist="$HOME/.claude/hooks/push-default-branch-allowlist.txt"
cwd=$(printf '%s' "$input" | jq -r '.cwd // "."')
if [ -f "$allowlist" ]; then
  top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
  if [ -n "$top" ] && grep -Fxq "$top" <(grep -v '^[[:space:]]*#' "$allowlist"); then
    exit 0
  fi
fi

deny() {
  jq -n --arg reason "$1（永久放行本仓库：将仓库根路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt）" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

# 显式指定 master/main 作为目标（含 refspec 形式 xxx:master）
if printf '%s' "$cmd" | grep -qE 'git push[^|&;]*[[:space:]](master|main)([[:space:]]|$)'; then
  deny "即将直推默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi
if printf '%s' "$cmd" | grep -qE 'git push[^|&;]*:(master|main)([[:space:]]|$)'; then
  deny "即将通过 refspec 推送到默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi

# 无显式目标的裸 git push：当前分支即 master/main 时拦截
if printf '%s' "$cmd" | grep -qE 'git push([[:space:]]+(--[a-z-]+|-[a-z]+))*[[:space:]]*($|[|&;])' \
   || printf '%s' "$cmd" | grep -qE 'git push[[:space:]]*$'; then
  branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
  if [ "$branch" = "master" ] || [ "$branch" = "main" ]; then
    deny "当前在默认分支 ${branch}，即将直推。共享项目请切功能分支；个人/小型项目确认后放行。"
  fi
fi

exit 0
