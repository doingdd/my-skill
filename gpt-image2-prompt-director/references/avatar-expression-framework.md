# Avatar and Expression Framework

Use this when the user asks for avatars, profile pictures, personal IP portraits, stickers, emoji packs, meme packs, or expression sheets.

## Core Lesson

Do not treat an avatar as a normal portrait.

An avatar is a small reusable identity asset. It must survive circular cropping, chat-list size, timeline thumbnails, and long-term repetition. A beautiful editorial portrait can still fail as an avatar if the face is too realistic, the crop is too wide, the symbol is too complex, or the image reads as a one-off poster.

## Xiaoxiaodong Patterns

The strongest avatar and expression examples in the archived Xiaoxiaodong corpus use two mechanisms:

1. **Reference transformation**
   - Start from a user-provided photo or existing avatar when available.
   - Preserve only the core structure, silhouette, attitude, and minimum recognisable traits.
   - Rewrite the visual language aggressively: MS Paint, one-line drawing, torn paper, crayon, notebook doodle, rounded abstract blocks, childlike drawing, etc.
   - The point is not realism. The point is a memorable transformation rule.

2. **System output**
   - For exploration, generate a `3 x 3` avatar contact sheet.
   - For stickers, generate a `4 x 4` pack.
   - Each cell must be independently usable, but the set must share the same behavior, simplification logic, error pattern, or identity DNA.

## Avatar Routing

When the user asks for an avatar and provides no reference image:

1. Prefer a `3 x 3 avatar exploration sheet` unless the user explicitly requests one final image only.
2. Build the same persona across all nine cells, but vary one design axis at a time:
   - medium: ink, risograph, torn paper, flat vector, digital gouache, badge, clay, collage, pixel
   - expression: calm, skeptical, amused, focused, defiant
   - crop: close face, half face, mask-like silhouette, symbol overlay, profile badge
   - symbol: pen, paper, spark, note mark, crystal, black box, cursor, redline
3. After exploration, the best cell can be selected and expanded into one final avatar.

When the user asks for one final avatar:

1. Make it an avatar asset, not a portrait poster.
2. Use a large face/head silhouette, simple background, one memorable symbol, and one accent color.
3. Keep the symbol small enough to support the face, not replace the face.
4. Avoid heavy occlusion. If part of the face is hidden, keep both the outline and one eye readable.
5. Explicitly check the image at `80px` and in a circular crop.

When the user provides a reference image:

1. Use the reference as identity anchor.
2. Decide the transformation rule before style words.
3. Preserve minimum identity anchors: silhouette, hairstyle, face shape, signature color, glasses, clothing shape, or posture.
4. Do not preserve exact facial realism unless the user asks for a photographic avatar.

## Sticker / Expression Routing

For stickers and expression packs, use a `4 x 4` grid by default.

The key is **consistent imperfection**, not realistic consistency:

- The same character does not need to be anatomically identical in each frame.
- It should look like the same unskilled hand drew all frames.
- Keep the same simplification logic, line behavior, error pattern, and messiness level.
- Preserve only the minimum recognisable features.

For text-based stickers:

- Text must feel drawn with the image, not typeset after the image.
- Use crooked, uneven, hand-drawn text while keeping it readable.
- Each sticker should feel like a spontaneous emotional event.
- Avoid polite, formal, or template-like captions.

## Avatar Anti-Failures

Ban these for avatar prompts unless explicitly requested:

- realistic celebrity-like face
- generic handsome man or pretty influencer face
- cinematic poster portrait
- complex full-body character art
- oversized symbolic object covering most of the face
- background louder than the avatar
- unreadable tiny text
- typography as the main identity
- complex scene narrative
- cyberpunk neon clutter
- luxury fashion editorial styling when platform avatar usability matters

## Avatar Prompt Shape

```text
你是个人品牌视觉总监、头像系统设计师和社交平台缩略图设计师。

你的任务不是生成一张好看的肖像，而是生成可长期使用的个人头像资产。
它必须在圆形裁切、80px 小尺寸、聊天列表、公众号资料页中都清晰可识别。

先在内部判断：
1. 这是头像资产，不是证件照、海报、真人写真或游戏立绘。
2. 选择一个最强的记忆机制：轮廓、表情、符号、材质、颜色或变形规则。
3. 控制复杂度：一个主体、一个符号、一个强调色。
4. 如果没有参考图，优先做 3 x 3 头像探索 sheet；如果必须单张，则输出最终头像。

输出要求：
- 1:1 square avatar asset.
- The head/face silhouette fills most of the frame.
- Circular crop safe.
- Readable at 80px.
- Semi-realistic / semi-graphic, not photographic realism.
- One simple signature symbol, secondary to the face.
- No readable text, no logo letters, no watermark.
```

## Repair Rule

If an avatar result looks like a magazine portrait, movie poster, game character, or luxury editorial photo, repair the prompt by:

1. Reducing realism.
2. Enlarging the head/face silhouette.
3. Removing scene depth and background narrative.
4. Shrinking or simplifying the symbol.
5. Adding circular crop and 80px constraints.
6. Switching to `3 x 3 avatar exploration sheet` if the single direction is still generic.
