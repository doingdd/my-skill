---
name: My Skill Market
description: Agent Skills Market - 轻量级 AI Agent Skills 市场
version: 1.0.0
registry: https://github.com/hanzhangzzz/my-skill
---

# My Skill Market Registry

本文件是 Skill Market 的注册表索引，Agent 可以解析此文件来发现和安装可用的 skills。

## Skills 索引

### harness

```json
{
  "name": "harness",
  "version": "1.0.0",
  "description": "Harness Engineering 最小实践 — 三角色 AI 自治循环（Inspector → Worker → Reviewer），通过 TODO.md 共享看板驱动持续改进",
  "trigger": "/harness",
  "keywords": ["harness", "automation", "inspection", "workflow", "CI/CD"],
  "compatibility": "Claude Code",
  "install_path": "harness/",
  "repo": "https://github.com/hanzhangzzz/my-skill",
  "license": "MIT"
}
```

### gpt-image2-prompt-director

```json
{
  "name": "gpt-image2-prompt-director",
  "version": "1.0.0",
  "description": "GPT image2 提示词导演：把弱点子升级成高质量生图 brief，并用 benchmark 与 hard gates 评测头像、表情包、信息图、卡片、海报等 prompt",
  "trigger": "$gpt-image2-prompt-director",
  "keywords": ["gpt-image2", "image generation", "prompt", "avatar", "sticker", "infographic", "visual design", "evaluation"],
  "compatibility": "Claude Code, Codex",
  "install_path": "gpt-image2-prompt-director/",
  "repo": "https://github.com/hanzhangzzz/my-skill",
  "license": "MIT"
}
```

## 安装指令模板

Agent 可以通过以下方式安装本市场中的 skill：

### 自然语言描述（推荐）

```
请从 https://github.com/hanzhangzzz/my-skill 安装 harness skill
描述：这是一个三角色 AI 自治循环系统，包含 Inspector、Worker、Reviewer，通过 TODO.md 共享看板驱动持续改进
```

```
请从 https://github.com/hanzhangzzz/my-skill 安装 gpt-image2-prompt-director skill
描述：这是一个 GPT image2 提示词导演，可从弱点子生成高质量生图 brief，并用 benchmark/hard gates 做评测
```

### 直接引用

```
安装 skill：harness
来源：https://github.com/hanzhangzzz/my-skill
路径：harness/
```

```
安装 skill：gpt-image2-prompt-director
来源：https://github.com/hanzhangzzz/my-skill
路径：gpt-image2-prompt-director/
```

## 市场运营指南

### 作为 Skill Market 的角色

本仓库作为一个轻量级 Skill Market：
1. **展示**: 在 README.md 中展示所有可用的 skills
2. **索引**: 在 MARKETPLACE.md 中提供机器可读的索引
3. **安装**: 支持 NPX、Agent 描述安装等多种方式

### 添加新 Skill

1. 在仓库根目录创建 `<skill-name>/` 目录
2. 按规范组织 `SKILL.md` 和相关文件
3. 更新 `MARKETPLACE.md` 添加新 skill 的索引
4. 更新 `README.md` 添加新 skill 的说明

### NPX 安装格式

```bash
npx github:hanzhangzzz/my-skill/harness
```

或克隆后本地安装：

```bash
git clone https://github.com/hanzhangzzz/my-skill
cp -r my-skill/harness ~/.claude/skills/
```
