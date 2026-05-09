# Personal Brand Avatar Repair Example

Use this example when a prompt creates a realistic editorial portrait instead of a usable platform avatar.

## Failure Diagnosis

The failed prompt sounds sophisticated but routes the model toward the wrong artifact:

- "半张脸 + 纸页 + 发光晶体 + 电影侧光" pushes the output toward a cinematic portrait poster.
- The face becomes a specific realistic-looking person, which is bad for a user who does not want a fake-real identity.
- The paper/crystal symbol becomes too large and competes with the avatar.
- The crop is too wide and detailed; it works as a square illustration but not as a WeChat circular avatar.
- The prompt asks for "长期个人品牌头像" but does not force avatar-asset mechanics strongly enough.

## Better Route

First generate a `3 x 3 avatar exploration sheet`. Pick a direction, then generate the final avatar.

```text
你是个人品牌视觉总监、头像系统设计师和社交平台缩略图设计师。

你的任务不是生成普通肖像，也不是生成电影海报或真人写真。
你要为一个长期写 AI、内容方法、独立思考的微信公众号作者，设计一张可长期使用的头像探索板。

用户只提供目标：
有个性、略男性化、AI 先锋、独立作者、酷，但不能像真人照片，也不能像网红精修头像。

请生成一张 1:1 正方形图片，内部是 3 x 3 九宫格头像探索 sheet。
九个格子都是同一个原创个人 IP 的不同头像方向。
每个格子都必须能单独裁成微信/小红书圆形头像。

统一身份 DNA：
- 半写实 + 半图形化，不要摄影写实。
- 轻微男性化，中性也可以，五官简化但有清醒、审视、克制的眼神。
- 像独立作者、AI 先锋、冷静内容编辑，而不是帅哥、偶像、游戏角色或赛博朋克人物。
- 头部和脸部轮廓必须占画面主体，小尺寸下先看到头像，不是先看到背景。
- 每个格子只允许一个核心符号，不要堆砌。

九个方向：
1. 黑色钢笔线稿头像，眼神锋利，极简纸张纹理背景。
2. 低饱和 risograph 头像，酸性绿色小光点作为思想火花。
3. 图形小说封面式头像，粗轮廓线，朱砂红编辑批注线。
4. 数字水粉头像，侧脸加一个小型发光知识晶体徽章。
5. 撕纸拼贴头像，脸部轮廓清楚，纸片只做边缘装饰。
6. 个人操作系统 badge 头像，圆形头像内有极简 UI 光标符号。
7. 黑白油墨头像，只有一只眼睛和发型剪影强识别。
8. 轻微像素化复古头像，保留清晰头部剪影和冷青色高光。
9. 极简抽象圆角块头像，用最少形状表达人物、笔、纸、火花。

视觉限制：
- 每格必须是头像近景，不要半身照，不要复杂场景。
- 不要真实摄影质感，不要像具体真人名人。
- 不要文字、logo 字母、水印。
- 不要让纸页、晶体、几何线条遮挡大半张脸。
- 背景必须安静，不能比头像更抢眼。
- 每格都要圆形裁切安全。

输出规格：
- 1:1 square.
- 3 x 3 grid, equal square cells, clear gutters.
- Each cell independently usable as a circular avatar.
- Readable at 80px: head silhouette, eye/expression, one symbol, one accent color.

生成前自检：
1. 每格裁成圆形后还像头像吗？
2. 缩小到 80px 后还能认出轮廓和气质吗？
3. 是否避免了写实帅哥/电影海报/游戏立绘？
4. 是否至少有 3 个方向让人有“这可以长期当 IP 头像”的感觉？
如果不满足，请先重构九宫格再生成。
```

## Final Single Avatar Repair

After selecting the best cell, repair the prompt into one final avatar:

```text
请基于九宫格中最适合长期个人品牌使用的方向，生成一张最终 1:1 头像。

要求：
- 圆形裁切安全，头部轮廓占画面 70% 左右。
- 半写实 + 半图形化，不是摄影真人。
- 一个清晰眼神，一个极简个人符号，一个强调色。
- 背景安静，符号不能盖过脸。
- 不要文字，不要 logo，不要复杂场景，不要电影海报感。
- 80px 小尺寸下仍能看清头像轮廓、眼神和符号。
```
