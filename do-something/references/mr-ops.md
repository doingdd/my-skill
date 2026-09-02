# MR 模式命令参考

do-something 在 MR 模式下要做的远端操作，GitHub 用 `gh`，GitLab 用 `glab` + REST。
先判断平台：`git remote get-url origin` 含 `github.com` → GitHub；否则按 GitLab 处理。
两边都要求 CLI 已登录（`gh auth status` / `glab auth status`），未登录就在日志里记下并退回"绝不 push"行为。

## 第 0 步：读状态

| 要什么 | GitHub | GitLab |
|---|---|---|
| do/main 是否已并入默认分支 | `git merge-base --is-ancestor do/main origin/<default>` | 同左 |
| 找现有 MR | `gh pr list --head do/main --state all --json number,state,url,isDraft` | `glab mr list --source-branch do/main --all -F json` |
| CI 状态 | `gh pr checks <n>`（非零退出 = 有失败） | `glab ci status --branch do/main` |
| 失败的 CI 日志 | `gh run list --branch do/main --limit 1 --json databaseId` → `gh run view <id> --log-failed` | `glab ci view --branch do/main` 找失败 job → `glab ci trace <job-id>` |

## 评审线程

GitHub 的"已解决"状态只在 GraphQL 里：

```bash
# 列出未解决线程（含每条评论的 path/line/body/author）
gh api graphql -f query='
query($owner:String!,$repo:String!,$n:Int!){
  repository(owner:$owner,name:$repo){ pullRequest(number:$n){
    reviewThreads(first:100){ nodes{ id isResolved path line
      comments(first:20){ nodes{ author{login} body createdAt } } } } } } }' \
  -f owner=<owner> -f repo=<repo> -F n=<n> \
  --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved==false)'

# 在线程里回复
gh api repos/<owner>/<repo>/pulls/<n>/comments/<comment-id>/replies -f body='已修：<sha>'

# resolve
gh api graphql -f query='mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{ isResolved } } }' -f id=<thread-id>
```

GitLab：

```bash
# 未解决的 discussion
glab api "projects/:id/merge_requests/<iid>/discussions?per_page=100" \
  | jq '.[] | select(.notes[0].resolvable==true and .notes[0].resolved==false)'
# 回复
glab api -X POST "projects/:id/merge_requests/<iid>/discussions/<discussion-id>/notes" -f body='已修：<sha>'
# resolve
glab api -X PUT "projects/:id/merge_requests/<iid>/discussions/<discussion-id>" -f resolved=true
```

机器人线程的识别：ci-review 发的评论正文以 `<!-- ci-review -->` 开头；作者是人就不设回合上限。
"同一线程来回 3 轮"按你自己在该线程里的回复条数计。

## 结束：push 与 MR 正文

```bash
git push -u origin do/main

# GitHub：无 MR 则建 draft，有则更新正文
gh pr create --draft --head do/main --base <default> --title 'do: <目的一句话>' --body-file /tmp/do-body.md
gh pr edit <n> --body-file /tmp/do-body.md

# GitLab
glab mr create --draft --source-branch do/main --target-branch <default> --title 'do: <目的一句话>' --description "$(cat /tmp/do-body.md)" --yes
glab mr update <iid> --description "$(cat /tmp/do-body.md)"
```

`/tmp/do-body.md` = DO.md 的"目的"一节 + "日志"一节原文。不写别的：MR 正文就是 DO.md 的远端镜像。
