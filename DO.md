# 目的
面向中文开发者的 Agent Skills 集合：每个 skill 解决一类真实重复劳动，装上就能用，产出可被展示验证。

# 约束
MR: on

# 日志
- 2026-09-03 10:15：给 ci-review 做展示卡（狗粮第一件事）。cards.json 加第 9 条，内容取自 PR #8 机器人的真实评论；build_cards.py 生成 HTML，Playwright 1200x675 视口截叠放 index.html 后按 675px 切出 cards/ci-review.png（已目检：标题/双栏/红绿标注渲染正常）；README 画廊加一格并配飞轮实景说明。验证：sips 确认 1200x675，README 引用路径与文件一致。下一步：合并后观察 ci-review 对本 MR 的审查。
- 2026-09-03 23:18：先回应上轮"下一步"——查 PR #9/#11 的 ci-review 结论：均 pass、零未解决线程，反馈面干净。本次：x-article-download/SKILL.md 650 行超仓库红线（500 行），把路径 D（整账号批量）与路径 E（Article 图片）整体平移到 references/x-batch-account.md（288 行）、references/x-article-images.md（50 行），SKILL.md 瘦身到 324 行并保留路由与 Article 前置沟通警示。验证：与 git show HEAD:x-article-download/SKILL.md 逐行比对，头部/尾部/frontmatter 字节级一致，路径 D 286 行、路径 E 48 行无丢失（仅节间 --- 分隔线未平移）；wc -l 确认 324 ≤ 500；SKILL.md 引用的两个 references 文件均存在。疑虑：切分时发现 Read 工具显示行号与原始文件在 400-600 行区间有 2 行偏移，已改用内容锚点切分规避。下一步：等 ci-review 审查本 MR；pass 且无线程将自动合并（档位已 on）。
- 2026-09-03 23:50：第 0 步——PR #12 被机器人自动合并（审查 pass→pr ready→merge，全自动收割首次跑通）。本次：把手工体检固化为市场质量门禁，.github/scripts/validate_marketplace.py（纯标准库：frontmatter/行数/硬编码路径/引用存在/可执行位/索引一致性）+ .github/workflows/validate.yml（PR 与 main push 触发）；顺带修复门禁扫出的 10 处真违规（hkr-render、md2view 的 scripts 补 chmod +x）。验证：主仓跑门禁 ✓ 12 skill/13 entry 退出码 0；/tmp 拷贝注入 7 类违规（name 不匹配/超 500 行/硬编码路径/引用缺失/README 缺行/无可执行位/JSON 损坏）逐类退出码 1，恢复后复绿 0。裁决记录：~/.claude 硬编码规则收窄到 ~/.claude/skills/（repo-map/repo-tidy 引用的是用户级配置文件，属合法引用）；README 正则修正为 ./name/ 链接格式。疑虑：门禁查 SKILL.md 不查 README 的路径写法（README 是人读文档）；引用检查只认反引号包裹的 scripts|references 路径。下一步：观察本 MR 上 validate 与 ci-review 双检查并跑。
- 2026-09-03 23:59：第 0 步——PR #13 被 ci-review 判 fail：field_value() 对 `description: |` 块标量返回字面 "|"，description 缺失/≤1024 两项检查对全仓 12 个 skill 的实际格式零效力（真 bug，认可）。修复：field_value 识别 |、|-、> 等块标量指示符，读后续缩进行拼值。验证：/tmp 注入机器人原失败场景（| 格式 1200 字符 description）→ 拦截；缺 description → 拦截；单行 1100 字符 → 拦截；主仓复检 ✓ 退出码 0。已回复机器人线程「已修」并 resolve。下一步：等 ci-review 复审本修复。
