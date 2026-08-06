# md2view v3.1 流水线 · 生效合同

本文件描述新任务必须执行的 v3.1 路径。脚本都位于本 skill 的 `scripts/`；下文 `$SK` 代表 skill 实际安装目录，不要写死某台机器的绝对路径。

最终交付物是自包含 `reader.html`：左栏保留权威原文，右栏是信息重组视图，两者通过 source map 锚定联动。v2 的 `views.json + fragments/` 只保留 legacy 入口，用于维护旧快照；新任务不得继续生成 fragment。

## 职责边界

| 参与者 | 负责 | 不负责 |
| --- | --- | --- |
| 生产模型 | 义、理据、图法、章法，输出 `view-spec.json` | HTML、CSS、SVG、像素坐标、最终放行 |
| 确定性 compiler/runtime | 合同校验、family DOM、共享视觉、source sync、交互、浏览器检查 | 发明事实、改变 relation kind、替模型选择结论 |
| 独立 reviewer | 只看截图盲读，再与 spec 对账 | 参与生产、接受预期答案后假装盲读、替生产者润色 readback |
| 编排器 | 记录 producer/reviewer 身份，组织门禁和原子晋升 | 用自报布尔值代替身份比较 |

## 六段总览

为保持执行清晰，来源盘点和“义”合为第一段；其内部仍严格先盘点、后表达决策。

1. 来源盘点 + 义
2. 理与据
3. 图法
4. 章法
5. 确定性编译
6. 独立盲读 + 原子晋升

后段只能表达前段，不能修补前段错误。若 reviewer 把架构读成流程，应回到图法/章法，不应只换颜色或加阴影。

---

## 第 1 段 · 来源盘点 + 义

### 1.1 建立 source ledger（确定性）

```bash
python3 $SK/scripts/parse_blocks.py <input.md> blocks.json
```

`blocks.json` 中每个 block 有稳定 id（`b000`…）。表格数据行和 checkbox 项仍属于父 block，但另有稳定 `sourceUnits`：

- 表格数据行：`b030:r001`
- checkbox 项：`b038:i001`

后续所有 claim/entity/relation/fact 只允许引用这里真实存在的来源。不要改写 `blocks.json` 来迁就模型输出。

### 1.2 先写读者任务和命题（模型）

模型读取原文和 `blocks.json`，先只回答：

- 谁读：`page.audience`
- 为了做什么：`page.readerTask`
- 全文希望读者形成什么判断：`page.centralClaim`
- 每张视图回答什么唯一问题：`view.question`
- 该视图的 5 秒结论：`view.centralClaim`
- 视图在全文叙事中的角色：`narrativeRole` 与 `page.narrative`

建议叙事角色使用 `orientation / explanation / comparison / decision / action / verification`。视图序列应切过原文章节重组心智模型；若一章对应一张图，通常只是目录搬家。

本段禁止选择卡片模板、颜色、坐标或具体 region。若一个视图同时要回答“系统由什么组成”和“请求怎样推进”，拆成 `architecture` 与 `flow`，不要做万能混合图。

---

## 第 2 段 · 理与据

模型继续完成同一个 `view-spec.json`。根结构为：

```json
{
  "schemaVersion": 3,
  "page": {
    "title": "页面标题",
    "audience": "有经验的技术决策者",
    "readerTask": "理解系统边界并判断方案",
    "centralClaim": {
      "text": "一句页面级结论",
      "sourceBlockIds": ["b005"]
    },
    "narrative": [
      {"viewId": "v1", "role": "orientation", "transition": "先建立全局地图"}
    ]
  },
  "views": []
}
```

完整机器结构见 [schemas/view-spec-v3.schema.json](schemas/view-spec-v3.schema.json)。字段是封闭合同，未知字段会被拒绝。

### Entity

每个 entity 必须声明：

- `id / type / label / detail`
- `emphasis: primary | secondary | context`
- `multiplicity: one | many | optional`
- `sourceBlockIds`，必要时加 `sourceUnitId`
- 可选 `boundary: internal | external`
- 可选 `stateKind: start | intermediate | terminal | persistent`

每张视图必须恰好一个 `emphasis=primary` 的 entity。`stateKind` 表达流程状态本体：普通架构节点不用为了视觉样式硬填；flow 若不是闭合循环，至少有一个 entity 为 `terminal` 或 `persistent`。

### Relation ontology

relation 统一使用 `id / subjectId / objectId / kind / emphasis / sourceBlockIds`，可加短 `label` 和 `sourceUnitId`。

| 关系族 | kind | 默认表达 |
| --- | --- | --- |
| 结构 | `contains / partOf / layerOf / instanceOf` | 嵌套、层带、重复，不默认画箭头 |
| 动态 | `calls / triggers / produces / transitionsTo / returns` | 有方向的局部连接或主路径 |
| 依赖 | `dependsOn / enables / constrains / provides` | 邻接、支撑面、端口或弱连接 |
| 连接 | `connectsTo / exchangesWith / peersWith` | 端口、cluster、无向/双向连接 |
| 观测 | `observes / reports / alerts` | 横切带、汇聚或监控端口 |
| 论证 | `supportsClaim / contradicts / mitigates` | claim 与 evidence 的邻接/论证关系 |

`subjectId/objectId` 描述语义参与方，不表示视觉上一定出现一条箭头。比较维度通常由 matrix 行列轴表达，不应建成流程 relation。

### Fact 与作用域

fact 表达会改变判断的证据、约束、风险、例外、指标、检查点或决策。每条 fact 必须声明：

- `kind: evidence | constraint | risk | exception | metric | checkpoint | decision`
- `scope.kind: entity | relation | region | view`
- `scope.targetIds`：引用对应对象；view scope 目标是当前 view id
- `label`、`sourceBlockIds`，必要时 `sourceUnitId`
- `value` 或 `values` 二选一

标量事实用 `value`。共同维度比较用：

```json
{
  "id": "f-latency",
  "kind": "metric",
  "scope": {"kind": "view", "targetIds": ["v1"]},
  "label": "延迟",
  "values": [
    {"targetId": "opt-a", "value": "低"},
    {"targetId": "opt-b", "value": "高"}
  ],
  "sourceBlockIds": ["b030"],
  "sourceUnitId": "b030:r001"
}
```

局部事实不得为了排版方便升级成 view fact。表格每个强制决策行、checkbox 每个条目都要由独立 entity 或 fact 的 `sourceUnitId` 承载；可见 `label + detail/value(s)` 必须保留完整原子内容。数字逐字抄录，不心算换算。

---

## 第 3 段 · 图法

每张 view 先写 `diagramRationale`，再选择一个主 `diagramKind`。以主导关系和读者问题为准，不以标题里有没有“流程”“架构”等词为准。

### v3.1 已实现 family

| family | 选择信号 | 合同门 | 不得这样画 |
| --- | --- | --- | --- |
| `architecture` | 组成、边界、分层、依赖、共享/横切面 | 至少一个结构/依赖 relation，或有语义 owner 的 region；primary relation 只能是结构、依赖、连接、观测 | 把层或容器画成连续步骤；`contains` 只画箭头 |
| `flow` | 触发、调用、状态推进、分支、回路 | 至少一条动态 relation；全部 primary relations 必须动态；显式 terminal/persistent 或闭合循环 | 对无方向关系强加起点终点 |
| `matrix` | options × 共同 criteria | 至少两个 `type=option`；至少一个比较 fact；每个 `values[]` 精确覆盖全部 options；不得有动态 relation | A/B 大卡片 + 全局散文，或多条路径冒充共同维度 |
| `argument` | claim、evidence、counterevidence、decision | 至少 claim + evidence/counterevidence + 论证 relation；claim 在 `focalIds`；primary relation 必须是论证族 | 把支持/反驳画成执行 pipeline |

`hierarchy / topology / timeline / dashboard` 已进入 schema 词汇表但没有 v3.1 renderer。选择它们会以 `unsupported_diagram_kind` 失败；不得静默 fallback 到 flow。如果真实问题必须使用这些 family，当前任务应明确阻塞，而不是歪曲语义。

### 拆图门

只要一条支撑中心命题的关系无法在所选 family 中无误导地表达，就拆图或重选。architecture 可有局部动态辅助关系，但不能让动态链路成为主导；需要完整调用路径时另建 flow view。

---

## 第 4 段 · 章法

`composition` 是受限 region tree，不是任意绘图 AST：

```json
{
  "rootRegionId": "main",
  "readingPath": {"kind": "top-down", "sequence": ["e0", "e1"]},
  "focalIds": ["e0"],
  "regions": [
    {
      "id": "main",
      "primitive": "container",
      "role": "main",
      "axis": "vertical",
      "parentId": null,
      "ownerEntityId": "e0",
      "entityIds": [],
      "childRegionIds": ["layer-1"],
      "targetRegionIds": []
    },
    {
      "id": "layer-1",
      "primitive": "band",
      "role": "main",
      "axis": "horizontal",
      "parentId": "main",
      "ownerEntityId": "e1",
      "entityIds": [],
      "childRegionIds": [],
      "targetRegionIds": []
    }
  ]
}
```

### Spatial primitives

| primitive | 表达 |
| --- | --- |
| `container` | 边界、所有权、上下文、方案组 |
| `band` | 层级、责任带、支撑面 |
| `axis` | 共同维度和对齐扫描 |
| `sequence` | 明确方向的推进；主图只属于 flow |
| `radial` | 中心能力与周边对象 |
| `stack` | 多实例/同类集合，只承载 `multiplicity=many` |
| `crosscut` | 观测、安全、治理等横切能力，必须有 targets |
| `inset` | 主图中的局部细节，必须有 parent |

`role` 可取 `main / support / crosscut / inset / context`，`axis` 可取 `horizontal / vertical / none`。`readingPath.kind` 可取 `left-right / top-down / center-out / cyclic / scan`。

确定性合同要求：

1. 唯一根、全部 region 可达、parent/children 双向一致、无环。
2. 每个 entity 恰好一次：作为某 region 的 `ownerEntityId`，或出现在一个 `entityIds` 中，不能两者兼有。
3. `contains` 的 subject region 必须是 object region 的空间祖先。
4. `crosscut` 必须声明真实 `targetRegionIds`；`stack` 只能放 many；`inset` 必须有 parent。
5. 非 flow 的 `sequence` 只允许作为有真实动态 relation 的 inset。
6. `focalIds` 只引用已有 entity/fact；先靠位置、容器和尺寸建立主次，再由共享视觉增强。

flow 的 `readingPath.sequence` 按视觉主路径排序，相邻实体之间必须有对应动态 relation；argument 的 claim 应是中心焦点；matrix 可使用 `scan`，不要伪造起点终点。

---

## 第 5 段 · 确定性编译

### 5.1 生成候选

```bash
python3 $SK/scripts/assemble_v3.py \
  blocks.json view-spec.json reader.candidate.html
```

输出路径必须以 `.candidate.html` 结尾。compiler 会先执行 v3 严格字段、family、region tree、source map 和原子语义合同，再由 `architecture / flow / matrix / argument` renderer 生成语义 DOM，并注入共享双栏、视觉和交互。任何未知字段、错误引用、未实现 family 或错误 source unit 都应 fail fast。

候选只是审阅对象，不是交付物。不要手改候选；回到 view-spec、合同或 renderer 修根因后重编译。

### 5.2 真实浏览器和覆盖率

```bash
node $SK/scripts/shot.js \
  reader.candidate.html shots \
  --viewports=1440,1280,1024,768

python3 $SK/scripts/coverage.py blocks.json reader.candidate.html
```

标准面只覆盖 768 及以上桌面/平板宽度，不做手机适配。768 仍是正式门禁，不允许靠隐藏关系、删 facts 或退化成纯列表通过。

浏览器门检查：

- 页面横向溢出、遮挡、裁剪、console/page error
- 三模式切换、双栏拖动/键盘/复位、source map 点击与键盘定位
- family 语义 DOM、阅读路径、主关系、fact 作用域
- architecture containment、flow 方向与状态、matrix 行列轴、argument claim/evidence
- 视觉密度、长文本、焦点态、reduced motion

`coverage.py` 同时报告全文文本、右栏 block 投影、原子 source-unit 投影和实体/fact 计数。左栏保留全文会让全文覆盖天然很高，因此不能用它替代右栏原子完整性。

---

## 第 6 段 · 独立盲读 + 原子晋升

### 6.1 冻结候选身份

```bash
shasum -a 256 reader.candidate.html
```

记录 64 位摘要。若最终文件叫 `report.html`，verdict 的候选逻辑名必须是 `report.candidate.html`；若叫 `reader.html`，必须是 `reader.candidate.html`。

### 6.2 两步审阅

1. **Blind readback**：把最终截图交给与生产者不同的视觉 agent 或人工 reviewer。不要给它 `centralClaim`、`diagramKind`、relation kinds、`focalIds`。让 reviewer 原样写下：中心命题复述、主导关系、最先看到的焦点、fact 实际归属、可能的更低误读方案。
2. **Comparison**：再将原始 readback 与 `view-spec.json` 对账。生产者不能改写 readback，只能在对账项中给 true/false 和 PASS/REJECT/UNCERTAIN。

`visual-verdict.json` 最小形态：

```json
{
  "schemaVersion": 1,
  "candidate": "reader.candidate.html",
  "candidateSha256": "把 shasum 输出的 64 位摘要粘贴到这里",
  "reviewer": {
    "id": "independent-reviewer-id",
    "mode": "vision-agent",
    "independentFromProducer": true
  },
  "views": [
    {
      "viewId": "v1",
      "blindReadback": {
        "centralClaimParaphrase": "这是职责分层与横切支撑，不是八步流程",
        "dominantRelation": "层级包含",
        "firstFocalLabels": ["执行内核"],
        "factAttachments": [
          {"factLabel": "边界", "attachedToLabel": "编排层"}
        ],
        "lowerMisreadAlternative": "未发现更低误读的图法"
      },
      "comparison": {
        "claimMatches": true,
        "focalMatches": true,
        "primaryRelationMatches": [
          {"relationId": "rel1", "matches": true}
        ],
        "factScopeMatches": [
          {"factId": "f1", "matches": true}
        ]
      },
      "verdict": "PASS"
    }
  ],
  "verdict": "PASS"
}
```

将摘要占位文字替换成候选的真实 64 位 SHA256。所有 view 必须精确覆盖；每个 view 的 `primaryRelationMatches` 必须精确覆盖 spec 中全部 `emphasis=primary` relations，`factScopeMatches` 必须精确覆盖全部 facts，不能缺项或加入 spec 外 id。所有 matches、view verdict 与总 verdict 都必须 PASS。

`reviewer.id` 与下一步的 `--producer-id` 必须不同。`independentFromProducer=true` 是必要声明，但最终门还会比较身份；不能只靠自报布尔值。

### 6.3 唯一最终出口

```bash
python3 $SK/scripts/build_reader.py v3 \
  blocks.json view-spec.json reader.html \
  --visual-verdict visual-verdict.json \
  --producer-id <本次生产者稳定ID> \
  --shots-dir shots
```

`build_reader.py v3` 不直接信任先前候选：它会从同一 blocks/spec 重新确定性编译一个同目录临时候选，然后依次执行：

1. 1440 / 1280 / 1024 / 768 真实浏览器门；
2. verdict 候选逻辑名与实际输出 stem 对账；
3. `candidateSha256` 与重编译候选字节对账；
4. reviewer id 与 CLI producer id 独立性；
5. 全部 views、全部 primary relations、全部 facts 与 PASS 状态。

全部通过后以 `os.replace` 原子替换最终文件。任何一步失败，临时候选被清理，已有 `reader.html` 保持不变。单独运行 `visual_verdict.py` 只能做基础结构检查，不能替代最终 v3 入口的 digest/spec/identity 强门禁。

---

## 失败应回到哪一段

| 失败 | 回退 |
| --- | --- |
| reviewer 复述错中心命题 | 第 1 段：义 |
| 漏事实、relation kind 错、fact 作用域错 | 第 2 段：理与据 |
| 架构被读成流程、证据被读成步骤 | 第 3 段：图法 |
| 主次不清、区域冲突、路径绕远 | 第 4 段：章法 |
| DOM、布局、交互、断裂、长词溢出 | 第 5 段：compiler/runtime |
| reviewer 不独立、摘要漂移、coverage 不完整 | 第 6 段：验读/晋升编排 |

禁止在视觉样式层用换色、阴影或动效掩盖义、理、图法或章法错误。

## 对抗回归

```bash
PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s $SK/scripts -p 'test_*.py'
```

至少拒绝：architecture 连续箭头化、`contains` 不嵌套、flow 无动态 relation 或无终态、matrix 漏 option/混入动态 relation、argument 无 claim/evidence 或使用主 sequence、source id 伪造、表格/checklist 被总结吞并、错误 verdict、摘要不匹配、reviewer 与 producer 同一身份，以及浏览器失败仍覆盖旧 reader。

## Legacy v2 边界

- 已生成的 v2 `reader.html` 是自包含快照，可继续离线打开。
- v2 的 `views.json`、fragments 和 `assemble_split.py` 不会透明升级为 v3。
- 新任务必须重新生成 `view-spec.json`，走 `assemble_v3.py` 与 `build_reader.py v3`。
- 不维护“v2 自由 fragment + v3 family renderer”的长期双轨生成合同。
