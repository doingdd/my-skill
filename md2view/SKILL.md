---
name: md2view
description: 把 Markdown 重编码成可溯源的人类阅读视图，而不是只做主题美化。模型先声明义、理据、图法与章法，确定性编译器再生成「左原文、右重组、锚定同步」的单文件 HTML。Use when 用户要把复盘、报告、规格、README 或技术长文变成架构图、流程图、比较矩阵、论证图，或提到 md2view、信息重组、双栏阅读、文档可视化。只要忠实渲染 Markdown 时不要用本 skill。
---

# md2view

把 Markdown 重新编码成可独立阅读、可回原文核证的视觉论证。Markdown 是权威源，HTML 是消费投影；产物有问题时修 `view-spec.json`、合同或 renderer，不手修生成的 HTML。

当前生效合同是 **v3.1**。v2 只用于打开已经生成的自包含快照，不再作为新任务的生成路径。详规见 [PIPELINE.md](PIPELINE.md)，设计依据见 [DESIGN.md](DESIGN.md)。

## 不可违反的边界

- 模型只写 `view-spec.json`，不写 HTML、CSS、SVG、像素坐标或 fragment。
- 先确定读者要形成的判断，再建实体/关系/事实，之后才选择图法和空间骨架；不能从卡片模板倒推语义。
- 关系不等于连线。包含、分层、实例等结构关系优先用容器、嵌套、层带或重复表达。
- 每个 claim、entity、relation、fact 都必须有真实 `sourceBlockIds`；表格行和 checkbox 项按 `sourceUnitId` 逐项投影。
- 每张视图恰有一个 `emphasis=primary` 的 entity；facts 必须就近声明 `entity / relation / region / view` 作用域。
- 标准交付宽度为 1440 / 1280 / 1024 / 768，最低 768；不做手机适配。
- 生产者不能给自己的图放行。浏览器门和独立盲读 verdict 都 PASS 后才能原子替换最终 reader。

## 六段执行流程

来源盘点与“义”合并为第一段，但决策顺序不能颠倒：

1. **来源盘点 + 义**：运行 `parse_blocks.py` 得到不可变 `blocks.json`；再声明 audience、readerTask、页面/视图 centralClaim、question、narrativeRole。此时不选布局。
2. **理与据**：在 `view-spec.json` 中建立 typed entities、typed relations、scoped facts、source map；`stateKind` 表达流程状态语义。
3. **图法**：按主问题选择一个 `diagramKind`，写清 `diagramRationale`；不兼容就拆图或重选。
4. **章法**：用受限 region tree、readingPath、focalIds 分配位置、分组、阅读起点与视觉重点。
5. **确定性编译**：`assemble_v3.py` 严格校验合同并由 family renderer 生成候选；模型不参与 DOM 和样式生成。
6. **独立盲读 + 原子晋升**：真实浏览器生成截图；独立 reviewer 先只看截图复述，再与 spec 对账形成绑定候选摘要的 `visual-verdict.json`；`build_reader.py v3` 重编译并通过全部门禁后原子晋升。

## 四种已实现图法

| family | 何时选择 | 硬条件 | 反例 |
| --- | --- | --- | --- |
| `architecture` | 组成、边界、分层、依赖、共享面 | 有结构/依赖关系或有语义 owner 的 region；不得混入论证 relation，动态关系只能辅助 | 把八层架构画成八步箭头流程 |
| `flow` | 触发、状态推进、条件、回路 | 所有 relation 都属于动态族；entity 用 `stateKind` 标明 `terminal/persistent`，或声明闭合循环 | 无方向的分类/层级被强加起点终点 |
| `matrix` | 多个 option 沿共同维度比较 | 所有 entity 都是 `type=option` 且至少两个；relations 必须为空；每个比较 fact 的 `values[]` 完整覆盖所有 option | 两张方案卡片加一堆全局散文 |
| `argument` | 证据支持、反驳或缓解某结论 | claim + evidence/counterevidence；所有 relation 都属于论证族；claim 是焦点 | 把证据链画成执行 pipeline |

`hierarchy / topology / timeline / dashboard` 只是后续设计候选，不是 v3.1 schema 的合法值；合同阶段必须 `unsupported_diagram_kind` 失败，禁止等到 renderer 才失败，更禁止退化成 flow。

`stateKind` 可取 `start / intermediate / terminal / persistent`。它描述状态本体，不是颜色；普通架构实体无需硬填。flow 若不是闭合循环，至少要显式出现 `terminal` 或 `persistent`。

## 冷启动执行

下文 `$SK` 是本 skill 的实际安装目录。为任务建立独立工作目录：

```bash
mkdir -p work && cd work
python3 $SK/scripts/parse_blocks.py ../input.md blocks.json
# 模型读取 input.md + blocks.json，按 PIPELINE.md 生成 view-spec.json；不要生成 HTML
python3 $SK/scripts/assemble_v3.py blocks.json view-spec.json reader.candidate.html
node $SK/scripts/shot.js reader.candidate.html shots --viewports=1440,1280,1024,768
python3 $SK/scripts/coverage.py blocks.json reader.candidate.html
shasum -a 256 reader.candidate.html
```

然后把 **shots 中的最终截图**交给与生产者不同的视觉 agent 或人工 reviewer。第一轮不得向 reviewer 提供 `centralClaim`、`diagramKind`、relation kinds、`focalIds`；reviewer 先写实际看见的命题、主关系、首个焦点、fact 归属和更低误读方案。第二轮再与 spec 对账，写 `visual-verdict.json`：

- `candidate` 必须是 `<最终文件 stem>.candidate.html`，例如最终文件为 `reader.html` 时写 `reader.candidate.html`。
- `candidateSha256` 必须等于上面候选文件的 64 位 SHA256。
- `reviewer.id` 必须与最终命令的 `--producer-id` 不同，且 `independentFromProducer=true`。
- 每个 view 恰好出现一次；`primaryRelationMatches` 精确覆盖该 view 的全部 `emphasis=primary` relations；`factScopeMatches` 精确覆盖全部 facts。
- `claimMatches`、`focalMatches`、所有逐项 `matches`、每个 view verdict 和总 verdict 都必须为 `true/PASS`。`REJECT` 或 `UNCERTAIN` 都不能晋升。

最终只通过 v3 出口交付：

```bash
python3 $SK/scripts/build_reader.py v3 \
  blocks.json view-spec.json reader.html \
  --visual-verdict visual-verdict.json \
  --producer-id <本次生产者稳定ID> \
  --shots-dir shots
```

该命令会重新确定性编译候选，并验证 1440 / 1280 / 1024 / 768 浏览器行为、verdict 中的候选名与 SHA256、reviewer/producer 独立性、全部视图、全部主关系和全部 facts。任一门失败时不会覆盖已有 `reader.html`。

## 返回前自检

- 右栏脱离原文能否回答：是什么、为什么、约束/取舍、如何行动或判断？
- 这是最匹配主问题的 family，还是因为习惯画流程才选 flow？
- 每条 relation 是否都与 family 兼容？结构关系是否主要由空间表达？
- flow 的主路径、分支终态和回路是否全部显式可见，且每个分支实体都能从起点到达？
- 每个 entity 是否恰好归属一个 region？region tree 是否唯一根、可达、无环？
- facts 是否贴近正确 entity/relation/region，而不是为了排版被抬成 view fact？
- 每个强制表格行/check-item 是否由独立 `sourceUnitId` 保留完整可见内容？数字是否逐字一致？
- 768 及以上是否无横向溢出、遮挡、断裂和失效交互？不要为通过门禁删掉决策事实。
- 独立 reviewer 是否真的先盲读，且原始 readback 没被生产者改写？

对抗回归：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s $SK/scripts -p 'test_*.py'
```

不要把 `assemble_v3.py` 的候选当最终交付，也不要使用 legacy 的 `views.json + fragments/ + assemble_split.py` 路径生成新 reader。
