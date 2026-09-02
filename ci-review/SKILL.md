---
name: ci-review
description: |
  Install a CI-triggered LLM code reviewer into the current repo: on every push to a PR/MR, Claude Code runs headless, reproduces every claim the change makes ("tests pass", "verified", "supports X"), hunts correctness bugs with concrete failure scenarios, and posts inline comments plus one sticky summary. It judges execution, not direction — the other half of the do-something flywheel. GitHub (anthropics/claude-code-action) and GitLab CI templates. Use when the user says /ci-review, 装一个 CI 代码审查, CI 里自动 code review, 给 PR/MR 加 AI review, 让机器人验证 PR.
trigger: /ci-review
compatibility: Claude Code
license: MIT
---

# ci-review

给仓库装一个只回答一个问题的审查机器人：**这次改动宣称做到的事，真的做到了吗？**

它和人类 reviewer 分工：方向、取舍、值不值得做，是人的事；
声明能不能复现、diff 里有没有能写出失败场景的缺陷，是它的事。
配合 do-something 的 MR 模式即成飞轮：do-something 提出方向并实践，ci-review 验证实践质量，
do-something 下一轮先回应它的评论。人类只在想收割时出现。

## 触发条件

- `/ci-review`：装进当前仓库（幂等，已存在的文件不覆盖；`/ci-review --force` 覆盖）。
- `/ci-review status`：检查已安装的文件与 secrets 是否齐全。

## 安装

依赖检查放最前：当前目录是 git 仓库且有 origin，否则停下说明。

```bash
bash <本 SKILL.md 所在目录>/scripts/install.sh [仓库路径] [--force]
```

脚本按 origin 判平台，复制两个文件并打印下一步：

| 平台 | CI 配置 | 审查规范 |
|---|---|---|
| GitHub | `.github/workflows/ci-review.yml`（官方 `anthropics/claude-code-action@v1`） | `.github/ci-review.md` |
| GitLab | `.gitlab/ci-review.yml`（`claude -p` 头less，需 `include:`） | `.gitlab/ci-review.md` |

审查规范就是 `prompts/review.md` 的副本，落在仓库里供按口味修改；CI 里的 Claude 读它执行。

**Secrets 由人设置，脚本只打印清单，不代替。** 模型接入默认走"Anthropic 兼容网关 + API key"，
不占 Claude 订阅额度：GitHub 用 secret `CI_REVIEW_API_KEY` + 变量 `CI_REVIEW_BASE_URL`、`CI_REVIEW_MODEL`；
GitLab 用 CI 变量 `ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`。
base URL 留空即官方 Anthropic；想烧 Pro/Max 额度改用 `claude setup-token` 生成的 `CLAUDE_CODE_OAUTH_TOKEN`。
GitLab 额外需要 `GITLAB_TOKEN`（项目访问令牌，api scope），因为 `CI_JOB_TOKEN` 不能发 MR 评论。
审查是工具调用密集型任务，网关上选支持 tool use、上下文够大的模型。

安装完成后必须告诉用户：还差哪些 secret、怎么设、开一个 PR/MR 才能看到第一次运行。

## `status` 检查

```bash
ls .github/workflows/ci-review.yml .github/ci-review.md 2>/dev/null || ls .gitlab/ci-review.yml .gitlab/ci-review.md
gh secret list 2>/dev/null | grep -E 'CI_REVIEW_API_KEY|CLAUDE_CODE_OAUTH_TOKEN' || echo "缺认证 secret"
gh variable list 2>/dev/null | grep -E 'CI_REVIEW_BASE_URL|CI_REVIEW_MODEL' || echo "未设网关变量，将走官方 Anthropic"
gh run list --workflow ci-review --limit 3 2>/dev/null   # 最近三次运行
```

## 审查行为（写在 prompts/review.md，此处只列不变量）

- 范围增量：sticky 总结里记 `<!-- ci-review last=<sha> -->`，下次只审这个 sha 之后的 diff，不重复评论。
- 先验证声明再找缺陷：正文、commit message、DO.md 日志里的"验证过了"逐条亲自复现。
- 每条发现必须有失败场景，否则不发；风格、命名、"可以考虑"一律不报。
- 只发评论，不改代码、不 approve、不 request changes。
- 评论正文以 `<!-- ci-review -->` 开头，do-something 据此识别机器人线程并对回合数设上限。

## 调口味

- 改审查规范：直接编辑仓库里的 `.github/ci-review.md` 或 `.gitlab/ci-review.md`，下次 push 生效。
- 换模型或换网关：改仓库变量 `CI_REVIEW_MODEL` / `CI_REVIEW_BASE_URL`（GitLab 改 CI 变量），不用动 workflow。
- 降成本：`concurrency.cancel-in-progress` 已开，连续 push 只审最后一次。

## 错误处理

- Action 报认证失败 → secret 名与 workflow 里 `with:` 字段不匹配，二选一改齐。
- 网关返回 401 → 该网关只认 Bearer 头或只认 x-api-key；模板两种都发，检查 key 是否属于该网关。
- 网关返回 model not found → `CI_REVIEW_MODEL` 写的是官方 ID 而非网关上的名字。
- 报 "Claude Code is not installed on this repository" → workflow 里的 `github_token` 行被删了却没装 Claude GitHub App，二者留一个。
- 评论没出现但 job 成功 → 看 job 日志里 Claude 的输出；常见是 `--allowedTools` 缺 `mcp__github_inline_comment__create_inline_comment`。
- GitLab 发评论 401/403 → `GITLAB_TOKEN` 权限不够，需要 api scope 且 Reporter 以上。
