# Evaluation Rubric

The benchmark is derived from the 39 archived GPT image2 prompt examples. Do not require copying their wording. Score whether a generated prompt reconstructs the same kind of capability from a weak input.

## Deterministic Prompt Score

Total: 100.

- Role positioning: 8
- Anti-plain-task definition: 10
- Input variable: 8
- Understand and plan first: 12
- Content planning: 12
- Visual system: 18
- Failure constraints: 12
- Output spec: 8
- Self-check: 6
- Novice usability: 6

Pass bands:

- 80+: pass, can proceed to image generation
- 70-79: repair prompt before image generation
- <70: fail

## Expert Capability Coverage

Each benchmark case has expected capabilities. Score coverage rather than lexical similarity.

Example:

```json
{
  "weakInput": "我想做一张介绍“马踏飞燕”的高级图片。",
  "expectedCapabilities": [
    "识别为文物知识海报/图鉴",
    "要求事实核验",
    "提炼基础信息和文化价值",
    "设计主体文物主视觉",
    "设计图文关系和局部注释",
    "避免资料堆砌和模板展签"
  ]
}
```

## Hard Gates

Some categories have non-negotiable gates in `evals/benchmark-cases.json`.

These gates exist because a prompt can look structurally complete while still routing the model toward the wrong artifact. When a hard gate fails, the evaluator caps the score below the pass band even if the generic structure score is high.

Examples:

- avatar tasks must include platform-avatar mechanics such as circular crop, `80px` readability, non-photographic treatment, and face-first symbol hierarchy
- vague no-reference avatar tasks should prefer `3 x 3` exploration before a final single avatar
- sticker tasks must preserve `4 x 4` / 16-frame pack structure, consistent imperfection, and hand-drawn text behavior

Run strict mode to make any hard-gate failure exit non-zero:

```bash
node scripts/eval_prompt_director.mjs --outputs <dir> --fail-under 80 --strict
```

## Image Score

When GPT image2 output is available, score manually or with a vision judge:

- First-glance impact: 10
- Theme clarity: 10
- Visual finish: 10
- Design quality: 10
- Image-text relationship: 10
- Information organization: 10
- Non-template feel: 10
- Publishability: 10
- Text readability: 10
- Prompt adherence: 10

Image pass bands:

- 80+: excellent
- 70-79: usable
- 60-69: repair prompt
- <60: fail

## Avatar Asset Fit

When reviewing an avatar prompt or generated image, score it as an avatar asset rather than as a portrait.

Pass criteria:

- Works as a square source image and a circular crop.
- Still reads at `80px`.
- Face/head silhouette is dominant enough for platform use.
- The style is semi-realistic, semi-graphic, illustrated, badge-like, or deliberately transformed rather than accidentally photographic.
- There is one memorable identity hook.
- The hook supports the face instead of replacing it.
- The background is quiet and does not compete with the avatar.

Fail criteria:

- Looks like a cinematic poster, magazine editorial, game character splash art, or realistic celebrity portrait.
- Symbolic object covers most of the face.
- Too much scene depth, background narrative, lighting drama, or decorative geometry.
- Depends on tiny text or logo letters.
- Could be mistaken for a random attractive person.

## Grid / Contact Sheet Fit

When reviewing a prompt, check whether grid decomposition is appropriate.

Use a grid when:

- the task is avatar exploration, stickers, expressions, character variants, icons, style/material tests, storyboard beats, or repeated card structures
- the user benefits from comparing multiple options in one output
- each sub-image can remain readable at small size

Avoid a grid when:

- the goal is a cinematic poster, hero key visual, luxury product shot, landscape/city poster, or single emotional scene
- the image needs one dominant focal point
- grid cells would make text or details unreadable

Grid quality criteria:

- Cells are clearly separated and consistently sized.
- Each cell is independently usable.
- Variation is meaningful, not random.
- Identity DNA stays consistent when needed.
- The grid does not become a crowded collage.

## Stability Test

Run the same weak input 5 times.

Pass criteria:

- At least 4 of 5 prompt structure scores are >= 80.
- At least 3 of 5 image scores are >= 75 when images are generated.
- Creative directions are not near duplicates.
- No output is only style-word stacking.
