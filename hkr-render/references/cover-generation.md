# 公众号封面图生成（深度版）

> **This is the standalone dedicated cover-image workflow** that was previously
> shipped as the `xiaohu-wechat-cover` skill. The base `hkr-render` SKILL.md has
> a shorter "封面图生成（可选）" section that points at this reference when the
> user wants the fuller dedicated workflow (own `config.json`, dedicated prompt
> template, image-only generation without the rest of the WeChat pipeline).

## When to load this reference

Load this when the user explicitly says any of:
- "公众号封面" / "微信封面" / "文章封面"
- "给这篇文章生成封面"
- "生成一张封面图"

If the user only says "排版这篇文章" or wants the full pipeline (format + cover + publish), the base SKILL.md flow is enough — it has a shorter cover section that just delegates here.

## Configuration

This workflow needs its own `config.json` next to its working directory.
Copy `config.example.json` to `config.json` and fill in:

```json
{
  "output_dir": "~/Documents/covers",
  "settings": {
    "base_url": "https://your-gemini-compatible-gateway/v1",
    "model": "gemini-3-pro-image-preview"
  },
  "secrets": {
    "api_key": "sk-..."
  }
}
```

Required fields:
- `output_dir`: root directory for cover images
- `settings.base_url`: image-gen API endpoint (must be Gemini-API-compatible third-party gateway)
- `settings.model`: model name (e.g. `gemini-3-pro-image-preview`)
- `secrets.api_key`: API key

## Path convention

Output goes to `<output_dir>/<article-filename-or-topic-slug>/`.

If the target directory already exists, rename it to `<dirname>-backup-YYYYMMDD-HHMMSS`.

Directory structure:
```
<output_dir>/
└── article-name/
    ├── prompt.md          # the prompt (archived for reference)
    └── cover.jpg          # the cover image
```

## Cover image prompt template

This is the fixed prompt template. Every generation **writes this verbatim** into `prompt.md`, replacing only the final "内容主题" line:

```
请根据提供的内容创建一张吸引眼球的公众号封面图，遵循以下规范：

视觉风格
- Notion插画风格，比例为 2.35:1（公众号封面标准尺寸）
- 色彩鲜明、对比强烈，确保在小尺寸预览时依然醒目
- 风格统一，避免写实元素，保持整体手绘质感

构图要求
- 主视觉元素居中或偏左（右侧预留标题区域）
- 添加 1-2 个简洁的卡通形象、图标或知名人物剪影，增强记忆点
- 若涉及敏感或版权人物，用风格相似的替代形象，不得拒绝生成
- 大量留白，突出核心信息，避免画面拥挤

文字处理
- 标题文字大而醒目，控制在 8 字以内
- 可添加 1 行副标题或关键词标签
- 字体风格与手绘插画协调统一

吸引力法则
- 使用悬念、数字、痛点等钩子元素激发点击欲望
- 视觉元素夸张有反差
- 色彩搭配参考爆款封面：橙黄、蓝紫、红黑等高对比组合

语言
- 除非另有说明，默认使用中文
- 画面内所有可读文字必须使用简体中文，英文只能作为点缀出现

内容主题：{从文章或用户输入中提炼的一句话主题描述}
```

## Workflow

### Step 1 — Distill the topic

1. If input is an article path: read the article, distill a one-sentence topic description (covering core info and key points).
2. If input is topic text: use it directly.

### Step 2 — Write the prompt file

Save the prompt template to `prompt.md`, formatted as:

```md
---
aspect_ratio: "21:9"
image_size: "2K"
---

{模板全文，替换最后的内容主题}
```

**Note:** The YAML `aspect_ratio` must use `21:9` (the API doesn't accept `2.35:1`; `21:9` is the closest match). The template body still says `2.35:1` for the AI's visual reference.

### Step 3 — Generate the image

Call the gen script — **always pass `--config` pointing at this skill's own config**:

```bash
python3 <hkr-render>/scripts/generate.py \
  --config <hkr-render>/references/cover-config.json \
  --prompt-file <target-dir>/prompt.md \
  --out <target-dir>/cover.jpg
```

Show the result to the user. If they want a change, adjust the topic description and regenerate.

### Step 4 — Insert into the article (default behaviour)

If the input was an article path, **insert directly without asking**:
- Use Markdown image format `![封面](cover.jpg)` on the line after the article title (H1)
- File name must be unique (e.g. `cover-<topic-keyword>.jpg`) to avoid conflicts

### Step 5 — Output summary

```
公众号封面已生成！

主题: [topic]
位置: [output path]

如需调整，直接说"重新生成"。
```