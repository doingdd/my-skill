#!/bin/bash
# PreToolUse(Bash) hook: 拦截直推共享默认分支（master/main）
# 放行：把仓库根目录绝对路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt（一行一个，# 注释）
#   - 判定对象是 push 的目标仓库：git -C <path> push 检查 <path> 的仓库，不是会话 cwd
#   - allowlist 条目兼容符号链接写法（/var/... 与 /private/var/... 等价，双侧 pwd -P 归一）
#   - 一条命令多个 push 位点、或无法判定目标时从宽拦截（ask）——宁可多问不漏放
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# -C 路径：双引号/单引号/裸词（引号内可含空格）
path_alt="(\"[^\"]*\"|'[^']*'|[^[:space:]]+)"
prefix="(^|[[:space:]])git([[:space:]]+-C[[:space:]]+${path_alt})?[[:space:]]+push"

# 快速门：没有任何 git push 位点直接放行
sites=$(printf '%s' "$cmd" | grep -oE "${prefix}" 2>/dev/null)
[ -z "$sites" ] && exit 0

allowlist="$HOME/.claude/hooks/push-default-branch-allowlist.txt"

deny() {
  jq -rn --arg reason "$1（永久放行本仓库：将仓库根路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt）" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$reason}}'
  exit 0
}

allowlisted() { # $1=仓库 toplevel；条目原文或 pwd -P 解析后命中皆可
  [ -f "$allowlist" ] || return 1
  local entry resolved
  while IFS= read -r entry; do
    entry=${entry%$'\r'}
    entry="${entry#"${entry%%[![:space:]]*}"}"   # 去首尾空白，保留路径内部空格
    entry="${entry%"${entry##*[![:space:]]}"}"
    [ -z "$entry" ] && continue
    [ "$entry" = "$1" ] && return 0
    resolved=$(cd "$entry" 2>/dev/null && pwd -P) && [ "$resolved" = "$1" ] && return 0
  done < <(grep -v '^[[:space:]]*#' "$allowlist")
  return 1
}

# 多个 push 位点：不逐位点猜目标，整个人工确认
nsites=$(printf '%s\n' "$sites" | wc -l | tr -d ' ')
[ "$nsites" -gt 1 ] && deny "一条命令包含 ${nsites} 个 git push 位点，无法逐位点判定目标，请人工确认。"

# 定位本位点目标仓库：-C 路径优先，否则会话 cwd
site=$(printf '%s\n' "$sites" | head -1)
cpath=$(printf '%s' "$site" | sed -E "s/^git([[:space:]]+-C[[:space:]]+)?//; s/[[:space:]]+push\$//")
cpath=${cpath#\"}; cpath=${cpath%\"}; cpath=${cpath#\'}; cpath=${cpath%\'}
cwd=$(printf '%s' "$input" | jq -r '.cwd // "."')
target=$cwd
[ -n "$cpath" ] && [ -e "$cpath" ] && target=$cpath

top=$(git -C "$target" rev-parse --show-toplevel 2>/dev/null)
[ -z "$top" ] && exit 0            # 目标不是 git 仓库，push 不会发生
allowlisted "$top" && exit 0

# 规则 1：显式 master/main 目标词
if printf '%s' "$cmd" | grep -qE "${prefix}[^|&;]*[[:space:]](master|main)([[:space:]]|\$)"; then
  deny "即将直推默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi
# 规则 2：refspec 形式（xxx:main、:main 删除等）
if printf '%s' "$cmd" | grep -qE "${prefix}[^|&;]*:(master|main)([[:space:]]|\$)"; then
  deny "即将通过 refspec 推送到默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi

args_after_push=$(printf '%s' "$cmd" | sed -E "s/${prefix}//" | tr '|&;' '  ')

# 规则 3：--all/--mirror 推全部本地分支——只要仓库存在本地 master/main 就拦（与当前分支无关）
for tok in $args_after_push; do
  case $tok in
    --all|--mirror)
      if git -C "$top" show-ref --verify -q refs/heads/master 2>/dev/null \
         || git -C "$top" show-ref --verify -q refs/heads/main 2>/dev/null; then
        deny "即将 --all/--mirror 推送，会把本地 master/main 一起推上远端。共享项目请走分支+MR；个人/小型项目确认后放行。"
      fi
      ;;
  esac
done

# 规则 4：目标仓库当前在 master/main 上——没有显式非默认分支目标的 push 一律拦
#   （裸 push、只带 flags、只带 remote 名都算无显式目标）
branch=$(git -C "$target" symbolic-ref --short HEAD 2>/dev/null)
if [ "$branch" = "master" ] || [ "$branch" = "main" ]; then
  remotes="$(git -C "$target" remote 2>/dev/null)"
  has_explicit_target=0
  for tok in $args_after_push; do
    case $tok in -*) continue ;; esac                       # flags（--force-with-lease=x:y 整体当 flag，宁拦勿放）
    is_remote=0
    for r in $remotes; do
      if [ "$tok" = "$r" ]; then is_remote=1; break; fi
    done
    [ "$is_remote" = 1 ] && continue
    case $tok in                                            # 默认分支的等价写法都算直推
      master|main|refs/heads/master|refs/heads/main|*/master|*/main|@{u}*|@{upstream})
        deny "即将直推默认分支（${tok}）。共享项目请走分支+MR；个人/小型项目确认后放行。"
        ;;
    esac
    has_explicit_target=1                                   # 剩余 token 是显式非默认分支/refspec
    break
  done
  [ "$has_explicit_target" = 0 ] && deny "当前在默认分支 ${branch}，即将直推（无显式非默认分支目标）。共享项目请切功能分支；个人/小型项目确认后放行。"
fi

exit 0
