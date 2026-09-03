# 目的
面向中文开发者的 Agent Skills 集合：每个 skill 解决一类真实重复劳动，装上就能用，产出可被展示验证。

# 约束
MR: on

# 日志
- 2026-09-03 10:15：给 ci-review 做展示卡（狗粮第一件事）。cards.json 加第 9 条，内容取自 PR #8 机器人的真实评论；build_cards.py 生成 HTML，Playwright 1200x675 视口截叠放 index.html 后按 675px 切出 cards/ci-review.png（已目检：标题/双栏/红绿标注渲染正常）；README 画廊加一格并配飞轮实景说明。验证：sips 确认 1200x675，README 引用路径与文件一致。下一步：合并后观察 ci-review 对本 MR 的审查。
