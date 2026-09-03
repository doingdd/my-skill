# 目的
面向中文开发者的 Agent Skills 集合：每个 skill 解决一类真实重复劳动，装上就能用，产出可被展示验证。

# 约束
MR: on

# 日志
- 2026-09-03 10:15：给 ci-review 做展示卡（狗粮第一件事）。cards.json 加第 9 条，内容取自 PR #8 机器人的真实评论；build_cards.py 生成 HTML，Playwright 1200x675 视口截叠放 index.html 后按 675px 切出 cards/ci-review.png（已目检：标题/双栏/红绿标注渲染正常）；README 画廊加一格并配飞轮实景说明。验证：sips 确认 1200x675，README 引用路径与文件一致。下一步：合并后观察 ci-review 对本 MR 的审查。
- 2026-09-03 23:18：先回应上轮"下一步"——查 PR #9/#11 的 ci-review 结论：均 pass、零未解决线程，反馈面干净。本次：x-article-download/SKILL.md 650 行超仓库红线（500 行），把路径 D（整账号批量）与路径 E（Article 图片）整体平移到 references/x-batch-account.md（288 行）、references/x-article-images.md（50 行），SKILL.md 瘦身到 324 行并保留路由与 Article 前置沟通警示。验证：与 git show HEAD:x-article-download/SKILL.md 逐行比对，头部/尾部/frontmatter 字节级一致，路径 D 286 行、路径 E 48 行无丢失（仅节间 --- 分隔线未平移）；wc -l 确认 324 ≤ 500；SKILL.md 引用的两个 references 文件均存在。疑虑：切分时发现 Read 工具显示行号与原始文件在 400-600 行区间有 2 行偏移，已改用内容锚点切分规避。下一步：等 ci-review 审查本 MR；pass 且无线程将自动合并（档位已 on）。
