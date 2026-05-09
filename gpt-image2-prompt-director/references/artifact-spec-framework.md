# Artifact Spec Framework

Use this when a prompt needs more surprise, product feel, or "wow" than a normal visual brief. The lesson from the original `awesome-gpt-image-2-prompts` corpus is that many strong GPT image2 outputs are not just images; they are believable artifacts.

## Core Shift

Do not start with:

```text
What style should this image use?
```

Start with:

```text
What artifact should this image pretend to be?
```

Examples of artifact containers:

- avatar identity system
- multi-variant avatar sheet
- social media screenshot
- X / Xiaohongshu / WeChat profile card
- livestream screenshot
- UI design system
- mobile app screen
- game HUD / status screen
- character sheet
- magazine cover
- encyclopedia card
- museum plate
- product flyer
- handwritten note photo
- multi-frame grid

## Grid Decomposition / Contact Sheet

Another high-yield artifact pattern is to split one generated image into an `n x n` grid of smaller sub-images. This often works unusually well when each cell can be simple, self-contained, and visually comparable.

Use grid decomposition for:

- avatar exploration
- expression packs
- sticker / meme packs
- character design variants
- icon systems
- material/style comparisons
- storyboard panels
- step-by-step decomposition
- information cards with repeated structure
- before/after or A/B comparison boards
- small social assets that benefit from variety

Avoid grid decomposition for:

- cinematic hero posters
- single key visuals
- luxury product hero images
- high-impact landscape/city posters
- images that need one dominant focal point
- emotional scenes where scale, depth, and atmosphere matter

Common grid formats:

- `2 x 2`: four concept directions, readable and polished.
- `3 x 3`: nine variants; best default for avatars, style exploration, and expression packs.
- `4 x 4`: sixteen small stickers, emoji sheets, UI icon sets, or meme packs.
- `1 x 4` / `4 x 1`: storyboard beats, process steps, or before/after sequences.

For avatar work, a `3 x 3 avatar contact sheet` can be better than a single portrait:

```text
Generate a 3 x 3 grid of nine square avatar variants for the same AI independent author persona.
Each cell is a different high-concept direction, but all share the same identity DNA:
semi-realistic original male character, cold editorial AI-author energy, dark gray/blue palette, strong thumbnail readability.
No cell should look like a real celebrity or generic handsome man.
Each avatar must work independently as a circular platform avatar.
```

Grid prompts need extra consistency rules:

- Each cell must be clearly separated.
- Each cell should be independently usable.
- Preserve the same identity DNA across variants when needed.
- Vary one axis at a time: expression, angle, medium, symbol, color accent, or artifact container.
- Do not let the grid become a crowded collage.
- Avoid tiny unreadable text unless the task is explicitly UI/contact-sheet based.

## High-Concept Collision

Many strong prompts are short because the concept collision is already powerful:

```text
historical figure + modern social feed
ancient event + livestream screenshot
AI author + personal operating system profile
ordinary product + premium launch keynote
technical diagram + museum-quality editorial infographic
```

Generate 3-5 high-concept candidates before writing the final prompt when the user's idea feels ordinary.

Formula:

```text
Subject A + artifact/media B + transformation mechanism C
```

## Structured Spec Mode

For UI, social screenshots, profile systems, cards, posters, and avatar identity systems, prefer a structured YAML/JSON-like prompt or a clearly sectioned spec.

Minimum fields:

```yaml
type: artifact type
subject:
  identity:
  visual_traits:
artifact:
  components:
  layout:
  platform_context:
style_system:
  medium:
  color:
  typography:
  material:
content:
  labels:
  microcopy:
constraints:
  must:
  avoid:
definition_of_done:
  - success condition
```

## Reference Anchor Mode

For avatar, character, brand, and IP tasks, a reference image is strongly preferred. If no reference image is available, create symbolic anchors:

- silhouette
- hairstyle
- eye shape or expression
- signature color
- clothing shape
- recurring symbol
- crop rule
- platform preview
- background motif

Without anchors, the model tends to output generic attractive characters.

## Avatar Upgrade Pattern

Do not generate only:

```text
a cool semi-realistic male avatar
```

Generate:

```text
an avatar identity system board
```

Components:

- main semi-realistic avatar
- circular crop preview
- Xiaohongshu avatar preview
- WeChat official account avatar preview
- personal symbol or profile badge
- background/crop safety rules
- optional profile-card mockup
- optional `3 x 3` avatar variant sheet before selecting the final avatar

Avatar-specific constraint:

- A platform avatar is not a cinematic portrait. The face/head silhouette must dominate, the background must stay quiet, and the personal symbol must be simple enough to remain readable after circular crop and `80px` downscaling.
- Avoid over-covering the face. If a mask, paper page, crystal, UI pane, or abstract structure is used, it should create identity, not hide the avatar.
- For WeChat / Xiaohongshu / public-account avatars, no readable text should be required for recognition.

High-concept directions:

- AI independent author + personal operating system + profile badge
- underground AI magazine editor + cover portrait + author mark
- black-box researcher + UI card + thought-node graph
- chaos notes + face emerging from annotations
- future knowledge nomad + cold editorial identity system

## Definition of Done

Every artifact-first prompt should include concrete success criteria, for example:

```text
Definition of Done:
- The image reads as a complete artifact, not a loose illustration.
- The main subject is clear at thumbnail size.
- The artifact container is recognizable.
- It contains one memorable concept hook.
- It avoids generic AI-poster/template behavior.
```
