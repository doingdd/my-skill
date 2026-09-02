#!/usr/bin/env bash
# 把 ci-review 装进一个仓库：复制 CI 模板 + 审查规范，打印 secrets 清单。
# 用法：install.sh [仓库路径] [--force]
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
TARGET="."; FORCE=0
for a in "$@"; do case "$a" in --force) FORCE=1;; *) TARGET="$a";; esac; done
cd "$TARGET"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "✗ $TARGET 不是 git 仓库"; exit 1; }
cd "$ROOT"
REMOTE="$(git remote get-url origin 2>/dev/null || true)"
[ -n "$REMOTE" ] || { echo "✗ 没有 origin 远端，ci-review 需要托管平台"; exit 1; }

copy() { # src dst
  if [ -e "$2" ] && [ "$FORCE" = 0 ]; then echo "· 已存在，跳过：$2（--force 覆盖）"; else mkdir -p "$(dirname "$2")"; cp "$1" "$2"; echo "✓ 写入 $2"; fi
}

if [[ "$REMOTE" == *github.com* ]]; then
  copy "$SKILL_DIR/templates/github-ci-review.yml" ".github/workflows/ci-review.yml"
  copy "$SKILL_DIR/prompts/review.md" ".github/ci-review.md"
  cat <<'MSG'

下一步（GitHub）：
  1. 模型接入（不占 Claude 订阅额度）：
     gh secret set CI_REVIEW_API_KEY                                    # 网关或 Anthropic 的 key
     gh variable set CI_REVIEW_BASE_URL --body https://open.bigmodel.cn/api/anthropic   # 留空/不设 = 官方 Anthropic
     gh variable set CI_REVIEW_MODEL --body glm-5.3                    # 网关上的模型名
     —— 想用 Pro/Max 订阅额度：`claude setup-token` 后 gh secret set CLAUDE_CODE_OAUTH_TOKEN，并按 workflow 顶部注释改认证字段
  2. 提交 .github/workflows/ci-review.yml 与 .github/ci-review.md，开一个 PR 看它跑
MSG
else
  copy "$SKILL_DIR/templates/gitlab-ci-review.yml" ".gitlab/ci-review.yml"
  copy "$SKILL_DIR/prompts/review.md" ".gitlab/ci-review.md"
  cat <<'MSG'

下一步（GitLab，未在真实实例验证过）：
  1. .gitlab-ci.yml 里加：
       include:
         - local: .gitlab/ci-review.yml
     并确认 stages 里有 test
  2. Settings → CI/CD → Variables（masked）：
       ANTHROPIC_AUTH_TOKEN（网关或 Anthropic 的 key）、ANTHROPIC_BASE_URL、ANTHROPIC_MODEL
       GITLAB_TOKEN  （项目访问令牌，api scope，Reporter 以上）
  3. 提交后开一个 MR 看它跑
MSG
fi
