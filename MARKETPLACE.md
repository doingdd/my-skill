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

### repo-map

```json
{
  "name": "repo-map",
  "version": "1.0.0",
  "description": "本地仓库地图（全局项目自动索引）：扫描本地全部 git 仓库生成增量自愈缓存，UserPromptSubmit hook 在用户提到仓库名时自动注入路径与读写角色，跨仓库引用不再手贴路径；关联关系按'宁可漏掉，不能沉淀错'选择性沉淀",
  "trigger": "仓库地图 / repo-map",
  "keywords": ["repo-map", "仓库地图", "跨仓库", "multi-repo", "索引", "hook", "registry"],
  "compatibility": "Claude Code（完整体验）；Codex 仅 resolve 命令，无 hook 自动注入",
  "install_path": "repo-map/",
  "repo": "https://github.com/hanzhangzzz/my-skill",
  "license": "MIT"
}
```

### wechat-article-md-local

```json
{
  "name": "wechat-article-md-local",
  "version": "1.0.0",
  "description": "微信公众号单篇文章下载为本地 Markdown：自动提取正文、下载图片到本地、生成带格式的 Markdown，支持 Playwright 截断回退",
  "trigger": "wechat-article-md-local",
  "keywords": ["wechat", "weixin", "公众号", "微信公众号", "markdown", "下载", "article"],
  "compatibility": "Claude Code, Codex, Hermes Agent",
  "install_path": "wechat-article-md-local/",
  "repo": "https://github.com/hanzhangzzz/my-skill",
  "license": "MIT"
}
```

### x-article-download

```json
{
  "name": "x-article-download",
  "version": "4.0.0",
  "description": "X/Twitter 内容下载为 Markdown：支持单条推文（文字/图片/视频/GitHub 仓库）和整账号批量下载，自动转录视频口播",
  "trigger": "x-article-download",
  "keywords": ["x", "twitter", "下载", "markdown", "推文", "视频转录", "whisper", "xreach"],
  "compatibility": "Claude Code, Codex, Hermes Agent",
  "install_path": "x-article-download/",
  "repo": "https://github.com/hanzhangzzz/my-skill",
  "license": "MIT"
}
```

### xiaohongshu-downloader

```json
{
  "name": "xiaohongshu-downloader",
  "version": "2.0.0",
  "description": "小红书视频下载 + Whisper 口播转录为 Markdown：中文视频直接保存逐字稿，英文视频翻译后保存，自动生成 transcript.md",
  "trigger": "xiaohongshu-downloader",
  "keywords": ["xiaohongshu", "小红书", "下载", "视频", "转录", "whisper", "逐字稿", "markdown"],
  "compatibility": "Claude Code, Codex, Hermes Agent",
  "install_path": "xiaohongshu-downloader/",
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

```json
安装 skill：gpt-image2-prompt-director
来源：https://github.com/hanzhangzzz/my-skill
路径：gpt-image2-prompt-director/
```

```json
安装 skill：harness
来源：https://github.com/hanzhangzzz/my-skill
路径：harness/
```

```json
安装 skill：wechat-article-md-local
来源：https://github.com/hanzhangzzz/my-skill
路径：wechat-article-md-local/
```

```json
安装 skill：x-article-download
来源：https://github.com/hanzhangzzz/my-skill
路径：x-article-download/
```

```json
安装 skill：xiaohongshu-downloader
来源：https://github.com/hanzhangzzz/my-skill
路径：xiaohongshu-downloader/
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
