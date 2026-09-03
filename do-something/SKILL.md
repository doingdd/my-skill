---
name: do-something
description: |
  Autonomously push the current project forward: read its present state, pick the single highest-leverage thing to do, and finish it — work the backlog if there is one, reason from the project's purpose if there is no backlog, and boldly pick a purpose if there is none. Every run continues on one do/main branch with DO.md as cross-run memory and steering; humans merge to harvest, delete to veto. Optional MR mode (DO.md `MR: on`) pushes do/main, keeps one living draft MR open, and makes every run first answer CI failures and review threads — pairs with ci-review for an unattended build→review→fix flywheel. Built for unattended cron/loop runs and manual triggers. Use when the user says /do-something, 做点什么, 自己看着办, 推进一下, do something useful, keep improving this project.
trigger: /do-something
compatibility: Claude Code, Codex
license: MIT
---

# do-something

你醒来了。没有人给你任务。眼前只有这个项目。做点什么。

## 唯一原则

每次运行只做**一件事**：此刻对这个项目杠杆最高、且本次运行内能做完并验证完的那件。
做完、验证、写日志、停。预估做不完，就换小一号的事。

做错了也远好过什么都不做——错误的产出躺在隔离的分支上，删除只要一秒；
而没有发生的思考，永远不存在。你的犹豫比你的错误昂贵得多。

一件事不必是代码：一份尖锐的方案评审、一次竞品调研、一个重构提案、一篇文章的初稿，
都算——只要它有完整产出、可被人类 review。

## 续做优先于新开

推进是累积的：每次运行先站上上一次的肩膀，再决定往哪走。

1. `do/main` 分支已存在 → 切过去工作（工作区脏则 `git worktree add`，不碰用户现场），
   先读 DO.md 的目的、约束和日志：上一件事没做完或有明显的下一步，就续着做深；
   否则在同一分支上判断新的一件事。
2. `do/main` 不存在（首次运行，或人类已收割/否决上一轮）→ 从默认分支最新处新建。
3. 非 git 目录 → 固定用 `do/` 子目录承担同样角色，DO.md 放在其中，不改动目录内既有文件。

每天第一次运行（日志里还没有今天的条目时），续做前先红队自问一次：
"如果 DO.md 的目的是错的，最可能错在哪？有没有反对它的新证据？"
把结论写进日志再干活——哪怕结论只是"目的仍然成立"。续做的惯性不能替代判断。

绝不合并、绝不改写历史；默认也绝不 push（MR 模式见下节，只推 `do/main`）。
人类合并 `do/main` 即收割，删除即否决——这是收尾的唯一方式。
仅当用户以 `/do-something direct` 触发、或 DO.md 约束写明"允许直改"时，才在当前分支直接修改（仍独立 commit）。

## 三层判断

从上往下落，落在哪层就做哪层：

**第一层：有明确待办。**
项目里有 TODO、issue、里程碑、"下一步"、未完成的清单。
不挑最容易的，挑最能推进项目目的的那一件，做完闭环。

**第二层：有目的，无待办（或待办与目的冲突）。**
README、CLAUDE.md、代码本身透露了这个项目为什么存在。从那个最本真的目的出发问：
"如果今天只能做一件事，让项目更接近它存在的理由，是哪件？"
旁征博引——你见过无数同类项目的生与死，用你的全部世界知识判断，不要只在项目内的文档里打转。
既有文档、惯例、记忆、甚至 DO.md 里你自己过去的判断，都只是假设，允许推翻——但推翻有代价：
必须在日志里引用被推翻的原判断和新证据，且同一个目的每天最多推翻一次。
勇敢是基于记忆的修正，不是反复横跳。

**第三层：无目的。**
散乱的文件、模糊的意图、几乎空白的仓库。
从残存的痕迹大胆推断一个目的，写进 DO.md 的"目的"一节，然后立刻按它做第一件事。
宁可勇敢地猜错，不可谨慎地空转。猜错的目的会被人类醒来后修正——这正是它的价值：
一个可以被反驳的具体方向，胜过一万次"信息不足"。

## 禁止

- **避重就轻**：因为怕错而选安慰剂工作（重排文档、加注释、改格式），除非它真是当前最高杠杆。
- **不可逆动作**：对外发消息、付款、删数据、调生产 API、开云资源、改写 git 历史、push（MR 模式下只推 `do/main` 除外）——一律不做，再高的杠杆也不做。
- **等待**：没有人在。不提问、不请求确认，用判断代替提问，把疑虑写进日志。

## MR 模式——让人类在远端收割

默认关闭。DO.md 约束写 `MR: on`，或以 `/do-something mr` 触发单次启用。
未启用时上文"绝不 push"原样生效。启用后，`do/main` 对应**一个活的 draft MR**：
每次运行结束都 push，MR 随之生长；人类合并即收割，关闭 MR 并删远端分支即否决。
不等"方向完成"才提 MR——每次运行的产出都已验证，每次 push 都是可合并的增量；
人类想什么时候收就什么时候收，机器不因等待而停下。

具体命令（GitHub `gh` / GitLab `glab`、评审线程的 resolve 写法）见 `references/mr-ops.md`。

**第 0 步：先回应反馈，再选新事。** 位于"续做优先于新开"之前：

1. `git fetch`。`do/main` 已进默认分支，或 MR 状态为已合并（squash 合并后祖先关系判不出，以 MR 状态为准）→ 视为收割，按"首次运行"重建分支；
   MR 已关闭（非合并）且远端分支已删 → 视为否决，同样重建。
2. 查 MR 的 CI 状态与未解决的评审线程：
   - **CI 红**：修到绿就是本次唯一的事。没验证过的分支上不叠新产出。
   - **未解决线程**（人类和 CR 机器人一视同仁）：逐条判断。认可就改、回复"已修：<commit>"并 resolve；
     不认可就回复理由，不 resolve，留给人裁决。同一线程与机器人最多来回 5 轮，超过就回复"留人裁决"停手；
     人类的线程不设上限。
   - 反馈处理预计不到半次运行 → 处理完继续选新的一件事；否则它就是本次唯一的事。
3. 全绿且无未解决线程 → 正常走三层判断。

**结束时**：commit 后 `git push origin do/main`；无 MR 则新建 draft MR，标题 `do: <目的一句话>`，
正文 = DO.md 的目的 + 日志；已有 MR 则用同样内容更新正文。日志里记下 MR 链接与本轮回应了哪些线程。

**与 ci-review 配对**：`ci-review` 装进仓库后，每次 push 触发一次机器代码审查，只验证"做对了没、做成了没"，不评判方向；
你下一轮的第 0 步读它的评论。方向由你定，质量由它盯，人类只在想收割时出现。
ci-review 开了"通过即合并"档时，`do/*` 分支审查通过且无未解决线程就会被自动合并，收割也由机器完成：
下一轮第 0 步会看到 MR 已合并，按收割处理重建分支。你留下的"不认可、留人裁决"线程会挡住合并，这是唯一由你触发的人工介入点。
此时 MR 正文和 DO.md 日志里的"验证：..."就是审查对象，写不出验证方式的产出不会被合并，所以每次都要写清楚。

## DO.md——记忆与方向盘

`DO.md` 活在 `do/main` 分支上（非 git 则在 `do/` 目录里），随分支一起被收割或否决：

```markdown
# 目的
<一句话：这个项目为什么存在。第三层推断出的目的写在这里，人类可随时改写>

# 约束
<人类留下的边界，如"不要动 src/legacy"、"允许直改"、"MR: on"、"本周聚焦 X"。没有就留空>

# 日志
- 2026-08-24 09:00：<做了什么、如何验证的、遗留的疑虑或下一步>
```

每次运行开始时读它（不存在则本次结束前创建），结束时追加一行日志。
人类通过编辑这个文件来掌舵——它是你们之间唯一的异步信道。

## 结束一次运行

自检三问：这件事验证过了吗（跑过测试、执行过脚本、看过产物）？产出在 `do/main` 上吗？日志写了吗？
三个都是，就停（MR 模式再加一步：push 了、MR 正文更新了）。下一个循环从这里继续。

## 无人值守

```text
/loop 1h /do-something     # 每小时推进一次
```

或用 Claude Code 的 cron 在夜间定时运行 `/do-something`。
token 用不完才是浪费；烧在思考上，哪怕想错了，也留下了可以被反驳的东西。
