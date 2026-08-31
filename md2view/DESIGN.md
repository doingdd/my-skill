# md2view 设计依据

- Status: v4 当前生效(2026-08-10 重构)
- Active contract: `SKILL.md`、`references/design-system.md`、`references/diagram-cookbook.md`、`references/anti-patterns.md`

## v4 为什么存在

v3(2026-08-06 前)的路线:模型只写 `view-spec.json`(typed entities/relations/facts/region tree),确定性 family renderer 生成全部 HTML,二十余道合同门 + 独立盲读 verdict + 原子晋升。

它在真实语料上系统性地产出"结构正确但表达愚蠢"的页面:516 行架构设计文档被投影成"flow 结构视图 1/2/3",每张两个框一根箭头。根因不是模型弱,而是架构分工错误:

1. **把溯源当成第一目标** → 每个 block 都必须有 carrier,不值得画图的内容也被画成图。
2. **把图法当成默认输出** → 流程是"分配 block → 套 renderer",而不是"理解 → 判断 → 选择形式"。
3. **renderer 太强,模型太弱** → 设计决策(要不要图、什么形式、怎么合并)被模板接管,模型退化成填 JSON。
4. **合同把"有内容"误认为"有表达"** → coverage 证明来源出现了,证明不了图值得画。
5. **模型从生成到交付看不见任何东西** → 写 JSON 盲盒,直到外部 reviewer 才有人看图。

v4 的反转:**溯源不需要模型只写 JSON,只需要模型在自由创作的 HTML 上标注来源锚点,且确定性层能验证这些锚点**。于是:

- 确定性层(不可谈判):`parse_blocks.py`(来源账本)、`build_reader.py`(左栏权威原文 + 双栏壳 + 锚点联动)、`verify_anchors.py`(覆盖、词法锚点、数字逐字、原子单元)。
- 模型层(自由但有纪律):右栏 `right-pane.html` 完全由模型设计与手写;纪律只有 data-sources 锚点、词法锚点、数字逐字三条,外加强制截图自审 ≥2 轮。
- 设计系统(`assets/shell.css` 的 mv-* 词汇)是质量地板;模型的组合自由是天花板。

## 验证哲学

机器门只验证**可核证性**(来源存在、覆盖完整、词法锚住、数字忠实、结构安全),不验证**表达价值**——后者由"生产者亲眼截图自审"负责。不再使用"审美分数""结构合法性代替好看"之类的代理指标。

词法锚点防得住"完全换词只挂 id",防不住"源文没有的新增断言"。后者是生产者纪律,由自审清单("源文说了吗")和 `references/anti-patterns.md` 第 10 条兜住。

## 已知边界

- 连线运行时路由是通用正交路由 + 避障,不是全图优化;极端密集图仍需模型拆图。
- 同两点间往返连线会重叠,需合并为双向标签(cookbook 已写明)。
- 768 以下不做承诺。
- v3 产物(已生成的自包含 reader.html)仍可离线打开;v3 生成路径(view-spec/schema/renderer/晋升门)已删除,git 历史可回溯。
