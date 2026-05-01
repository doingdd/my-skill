# My Skill Market

一个轻量级的 Agent Skills 市场，支持多种安装方式。

## 安装方式

### 方式 1: NPX 安装

```bash
npx @yourname/my-skill@latest
```

### 方式 2: 发送描述给 Agent

告诉你的 AI Agent:

```
安装 skill：harness - Harness Engineering 最小实践
描述：这是一个三角色 AI 自治循环系统，包含 Inspector、Worker、Reviewer，通过 TODO.md 共享看板驱动持续改进
安装源：https://github.com/hanzhangzzz/my-skill
```

### 方式 3: Claude Code Market Plugin

在 Claude Code 中使用 `/skill` 命令搜索 "harness"

## Available Skills

| Skill | 描述 | 触发词 |
|-------|------|--------|
| [harness](./harness/) | Harness Engineering 最小实践 — 三角色 AI 自治循环 | `/harness` |

### Harness 脚本直跑示例

```bash
cd <project> && bash ~/.codex/skills/harness/inspector.sh
cd <project> && bash ~/.codex/skills/harness/worker-reviewer.sh --loop
HARNESS_PROJECT_DIR=/abs/path/to/project bash ~/.codex/skills/harness/inspector.sh
```

## 开发自己的 Skill

参考 [Agent Skills 开放标准](https://agentskills.io) 创建你的 skill，发布后可通过上述方式安装。

## 本地开发

```bash
# 克隆市场
git clone https://github.com/hanzhangzzz/my-skill.git

# 查看可用 skills
ls -la skills/

# 安装某个 skill 到本地
cp -r skills/harness ~/.claude/skills/
```
