---
name: repo-tidy
description: |
  Git repository tidy-up and parallel-task base: switch back to the latest master/main, delete merged or upstream-gone branches, remove stale worktrees; `--new <task>` does tidy + create a task branch in one command and auto-creates a parallel worktree when the main checkout is busy; a SessionStart hook injects repo status when a session starts. Use when starting a new task, when [repo-status] shows the repo is off master or has cleanable items, or when the user says 归位, 整理仓库, 清理分支, 清理 worktree, 开新任务, repo tidy, tidy repo, clean branches.

---

# repo-tidy

把本地仓库恢复到「master = 远端最新、无僵尸分支、无废弃 worktree」的基线状态。归位发生在**下一个任务开始时**（push 完 MR 未合，任务结束时无收尾时机）。

组件（脚本就地运行于 skill 目录，不复制副本）：
- `scripts/repo_tidy.py` —— 核心：tidy / `--all` / `--new`
- `scripts/git-repo-status.sh` —— SessionStart hook，开局注入一行 `[repo-status]`（分支/ahead-behind/脏净）。注册到 `~/.claude/settings.json` 的 `hooks.SessionStart`：`{"matcher": "*", "hooks": [{"type": "command", "command": "<skill绝对路径>/scripts/git-repo-status.sh", "timeout": 10}]}`
- `tests/test_repo_tidy.sh <scratch目录>` —— 对抗测试（7 组场景 27 断言），改脚本后必须跑

## 何时用

- 用户说「归位」「整理仓库」「清理分支/worktree」
- 新任务开工前，SessionStart 注入的 `[repo-status]` 显示：不在 master、master 落后远端、或存在可清理分支
- commit-and-push 完成后用户想收尾

## 执行步骤

### 1. Dry-run 出清单

`SKILL_DIR` 指本 SKILL.md 所在目录（全局安装、项目级安装、plugin 缓存目录均适用，按实际安装位置解析，不要硬编码）。

```bash
# 单仓库（默认当前目录）
python3 "$SKILL_DIR/scripts/repo_tidy.py" <repo-path>

# 全部仓库（扫描 ~/Desktop/Works/code）
python3 "$SKILL_DIR/scripts/repo_tidy.py" --all
```

### 2. 确认后执行

把 dry-run 清单展示给用户；**涉及删除分支/worktree 时必须等用户确认**（用户本轮已明确说「清理」「归位」的，单仓库可直接 `--apply`）。

```bash
python3 "$SKILL_DIR/scripts/repo_tidy.py" <repo-path> --apply
```

### 3. 开新任务（一条命令：归位 + 开分支/worktree）

```bash
python3 "$SKILL_DIR/scripts/repo_tidy.py" <repo-path> --new <task>
```

- 先对该仓库执行一次归位（等价 `--apply`，安全边界相同）
- 主检出空闲（在 master 且无 tracked 改动）→ 原地 `switch -c task/<task> origin/master`
- 主检出被占用（停在进行中分支或有改动）→ 自动创建 sibling worktree `<仓库>--<task>`（基于最新 origin/master）并输出 `cd` 路径 —— 同项目多任务并行就靠这个：一任务一目录一 session，MR 合并后 tidy 自动回收
- `<task>` 含 `/` 时按原样作分支名，否则加 `task/` 前缀

## 脚本行为（安全边界）

| 对象 | 条件 | 动作 |
|------|------|------|
| 本地分支 | 已合并进 origin/master | 删除 |
| 本地分支 | upstream 已删除（squash 合并后的常态） | 删除 |
| 本地分支 | 有未推提交 / 从未推送 / MR 进行中 | **保留并报告** |
| 本地分支 | 与 origin/master 同点且未推送过（刚切出的空任务分支） | **保留**（并行 session 可能正要用） |
| 本地分支 | 空且已落后 origin/master（切出后从未动过） | 删除（无内容可丢，重切才是正确归位） |
| 当前分支 | 可清理且工作区无 tracked 改动 | 切回 master 再删 |
| master | 落后远端 | ff-only 前进 |
| master | 与远端分叉 | **不动，报告** |
| worktree | 分支可清理且工作区干净 | 移除 |
| worktree | 工作区脏 / detached | **保留并报告** |

脚本自身永远可以 dry-run；一切「✋ 保留」项需要人工决策，不要替用户强清。

## 不做的事

- 不删除整目录的克隆分身（如 `xxx-mr199/` 这类完整 clone）——发现时报告给用户，删目录是危险操作需单独确认
- 不 force push、不改写历史、不碰远端分支
