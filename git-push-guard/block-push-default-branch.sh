#!/bin/bash
# PreToolUse(Bash) hook: 拦截直推共享默认分支（master/main）
# 放行：把仓库根目录绝对路径加入 ~/.claude/hooks/push-default-branch-allowlist.txt（一行一个，# 注释）
# 判定原则：
#   - 判定对象是 push 位点的目标仓库（git -C <path> 优先，否则会话 cwd）；位点前导空白与引号路径均兼容
#   - 目标仓库在 master/main 上：任何 push 一律 ask（默认分支上没有正常推 push 需求，误拦只是确认一次）
#   - 任何分支：显式 master/main 目标词、refspec（含 + 强推、refs/heads 形态）、删远端默认分支 → ask
#   - --all/--mirror 与当前分支无关：仓库存在本地 master/main 就拦
#   - 一条命令多个 push 位点 → 整体 ask（不逐位点猜）
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# -C 路径：双引号/单引号/裸词（引号内可含空格）
# git 前边界是非名字字符：兼容 &&git、$(git、`git` 等非行首形态，又不误吞 gitx 之类同名二进制
path_alt="(\"[^\"]*\"|'[^']*'|[^[:space:]]+)"
prefix="(^|[^[:alnum:]_-])git([[:space:]]+-C[[:space:]]*${path_alt})?[[:space:]]+push"

sites=$(printf '%s' "$cmd" | grep -oE "${prefix}" 2>/dev/null)
[ -z "$sites" ] && exit 0

allowlist="$HOME/.claude/hooks/push-default-branch-allowlist.txt"
# 指向默认分支的 token 形态（norm 之后匹配）：裸词、refs/heads、斜杠、冒号 refspec 全族
is_default_spec() { # $1=norm 后的 token；逐 glob 判定是否指向默认分支（case 变量展开不解析 | 交替）
  local s
  for s in master main refs/heads/master refs/heads/main "*/master" "*/main" \
           ":master" ":main" ":refs/heads/master" ":refs/heads/main" \
           "*:master" "*:main" "*:refs/heads/master" "*:refs/heads/main"; do
    case $1 in $s) return 0 ;; esac
  done
  return 1
}

norm() { # 白名单保留法：只留合法 refspec 字符（引号/转义/展开符号在真实 ref 中不存在，shell 引用形态无界，
         #  枚举不完就反向只认白名单），再迭代剥 + 强推前缀
  local t prev
  t=$(printf '%s' "$1" | tr -cd '[:alnum:]_/.:+-')
  while :; do
    prev=$t
    t=${t#+}
    [ "$t" = "$prev" ] && break
  done
  printf '%s' "$t"
}

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
    entry="${entry#"${entry%%[![:space:]]*}"}"
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

# 定位位点与其目标仓库：边界字符剥离后重建 git 前缀，仅当位点含 -C 才提取路径
site=$(printf '%s\n' "$sites" | head -1)
case $site in
  git*) : ;;
  *) site="git${site#*git}" ;;   # 边界字符是一个非名字字符，不可能含字母 g/i/t
esac
cpath=""
case $site in
  *-C*)
    cpath=$(printf '%s' "$site" | sed -E "s/^git[[:space:]]+-C[[:space:]]*//; s/[[:space:]]+push\$//")
    cpath=${cpath#\"}; cpath=${cpath%\"}; cpath=${cpath#\'}; cpath=${cpath%\'}
    ;;
esac
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
# 规则 2：refspec 指向默认分支（xxx:main、:main 删除、:refs/heads/main 等）
if printf '%s' "$cmd" | grep -qE "${prefix}[^|&;]*:(refs/heads/)?(master|main)([[:space:]]|\$)"; then
  deny "即将通过 refspec 写入/删除远端默认分支 master/main。共享项目请走分支+MR；个人/小型项目确认后放行。"
fi

# push 之后的参数区：位点之后的子串，并在首个命令分隔符处截断
#   （多位点已整体 ask，位点之后的命令段不可能是 push，规则 3/5 不应看见它们）
args_after_push=${cmd#*"$site"}
args_after_push=${args_after_push%%[|&;]*}

# 规则 3：--all/--mirror 推全部本地分支——仓库存在本地 master/main 就拦（与当前分支无关）
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

# 规则 4：目标仓库当前就在 master/main 上——任何 push 一律 ask
branch=$(git -C "$target" symbolic-ref --short HEAD 2>/dev/null)
if [ "$branch" = "master" ] || [ "$branch" = "main" ]; then
  deny "当前在默认分支 ${branch}，任何 push 都先确认。请切功能分支工作；个人/小型项目确认后放行。"
fi

# 规则 5：非默认分支上，显式指向远端默认分支的 refspec / 删除远端默认分支
prev_delete=0
for tok in $args_after_push; do
  if [ "$prev_delete" = 1 ]; then
    prev_delete=0
    if is_default_spec "$(norm "$tok")"; then
      deny "即将删除远端默认分支（${tok}）。共享项目请走分支+MR；确认属正常操作后放行。"
    fi
    continue
  fi
  case $tok in
    --delete|-d) prev_delete=1; continue ;;
    --delete=*)
      if is_default_spec "$(norm "${tok#--delete=}")"; then
        deny "即将删除远端默认分支。共享项目请走分支+MR；确认属正常操作后放行。"
      fi
      continue
      ;;
  esac
  case $tok in -*) continue ;; esac
  if is_default_spec "$(norm "$tok")"; then
    deny "refspec 显式指向默认分支（${tok}）。共享项目请走分支+MR；个人/小型项目确认后放行。"
  fi
done

exit 0
