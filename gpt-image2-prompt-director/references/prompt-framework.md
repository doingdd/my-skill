# Prompt Framework

Use this framework to turn a weak idea into a GPT image2 prompt that behaves like a creative director brief.

## Core Shape

```text
Idea
-> user value / publishing context
-> content planning
-> visual container
-> visual system
-> style language
-> anti-failure constraints
-> output spec
-> self-check
```

## Required Blocks

1. **Role**: Assign a useful composite role, such as visual design director, information architect, content editor, commercial photographer, brand designer, or creative technologist.
2. **Anti-definition**: Say what the image is not, then define the higher-standard artifact.
3. **Input contract**: Make clear what the user provides and what the prompt should infer.
4. **Internal planning**: Require the model to understand, select, structure, and design before rendering.
5. **Content planning**: Convert the idea into specific information, pages, stages, labels, story beats, or visual anchors.
6. **Visual system**: Define composition, hierarchy, main visual, image-text relationship, typography, color, whitespace, material, light, and reading path.
7. **Anti-failure constraints**: Ban template feel, cheap PPT/e-commerce feel, crowded text, decorative clutter, generic AI-poster behavior, and style-only output.
8. **Output spec**: State image count, aspect ratio, publishing context, quality bar, and any text/readability requirements.
9. **Self-check**: Force one last internal QA pass before generation.

## Idea Expansion Heuristics

- **Knowledge** -> infographic, atlas, museum plate, annotated diagram, timeline, explainer card.
- **Word/phrase** -> semantic typography, concept poster, Chinese character reconstruction, logo-like visual identity.
- **Photo/reference image** -> retain structure, transform surface language, clean scene, add storytelling overlays, rebuild as product/photo/report.
- **Commercial object** -> product hero, recommendation card, A+ panel, banner, QR visual system.
- **Social content** -> cover + content pages, swipeable cards, diary comic, menu notebook, sticker set.
- **Abstract play** -> define a transformation mechanism, enforce constraints, preserve recognizability or structure while changing language.

## Strong Prompt Skeleton

```text
你是【专业角色组合】。

你的任务不是生成普通图片，而是把用户输入的【点子/主题/参考图】转化为一张/一组具有【传播价值/实用价值/审美价值】的高完成度视觉作品。

用户只需要输入：【最小输入】。

在生成前，请先在内部完成：
1. 理解输入的核心含义、情绪、场景和受众。
2. 判断最适合的视觉类型。
3. 提炼最值得视觉化的内容点。
4. 选择构图、主视觉、图文关系、配色、字体、材质、光影和留白策略。

内容要求：
- 紧扣主题，有信息密度和判断力。
- 不空泛，不鸡汤，不机械罗列。

视觉要求：
- 建立清晰视觉中心。
- 图文互相解释，不是简单贴字。
- 有明确阅读路径和层级。
- 配色、字体、构图因主题而生。
- 高级、克制、有完成度、有记忆点。

重点避免：
- 不要模板感、廉价 PPT 感、满屏小字、元素堆砌、AI 海报感。
- 不要只换词不换视觉系统。

最终输出：
生成【一张/一组】适合【发布场景】的高质量图片。
比例：【比例】。
完成度应像【目标类比】。

生成前自检：
1. 是否一眼有吸引力。
2. 是否能看出主题。
3. 是否有清晰结构。
4. 是否有设计判断。
5. 是否避免模板感和廉价感。
如果不满足，先重构再生成。

用户输入：
【点子】
```

