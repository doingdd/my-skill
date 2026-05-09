# My Skill Market

一个轻量级的 Agent Skills 市场，收录可直接复制到本地 Agent/Claude/Codex skills 目录使用的工作流。

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

或：

```
安装 skill：gpt-image2-prompt-director
描述：把普通点子升级成高质量 GPT image2 生图提示词，并提供头像、表情包、信息图、卡片、海报等任务的评测门禁
安装源：https://github.com/hanzhangzzz/my-skill
```

### 方式 3: Claude Code Market Plugin

在 Claude Code 中使用 `/skill` 命令搜索 "harness" 或 "gpt-image2-prompt-director"

## Available Skills

| Skill | 描述 | 触发词 |
|-------|------|--------|
| [harness](./harness/) | Harness Engineering 最小实践 — 三角色 AI 自治循环 | `/harness` |
| [gpt-image2-prompt-director](./gpt-image2-prompt-director/) | GPT image2 提示词导演：从弱点子生成高完成度生图 brief，并用 benchmark/hard gates 评测提示词质量 | `$gpt-image2-prompt-director` |

## GPT Image2 Prompt Director

这个 skill 面向 GPT image2 / 文生图工作流，目标不是写普通风格词，而是把一个很弱的点子升级成可执行的创意总监 brief。

适合场景：

- 头像 / 个人 IP / 表情包 / 贴纸包
- 小红书、公众号、X 等平台卡片和封面
- 信息图、知识图鉴、海报、产品图
- 从“没有点子”自动生成可传播的图片玩法
- 对已有 prompt 做结构评测和失败修复

内置能力：

- artifact-first prompt framework
- 头像和表情包专项框架
- `3 x 3` 头像探索、`4 x 4` 表情包系统输出
- 40 个 benchmark cases
- hard gates：防止“看起来完整但导向错误”的 prompt 通过评测

评测示例：

```bash
cd gpt-image2-prompt-director
node scripts/eval_prompt_director.mjs --gold --report /tmp/gpt-image2-prompt-director-gold-report.md
node scripts/eval_prompt_director.mjs --case-id 40 --prompt-file /absolute/path/to/prompt.md --fail-under 80 --strict
```

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
find . -maxdepth 2 -name SKILL.md

# 安装某个 skill 到本地
cp -r harness ~/.claude/skills/
cp -r gpt-image2-prompt-director ~/.claude/skills/

# Codex 用户也可以复制到
cp -r gpt-image2-prompt-director ~/.codex/skills/
```
