# md2view v3 Design

## Source of truth

- Status: Implemented，v3.1 当前生效
- Last refreshed: 2026-08-06
- Active executable contract: `SKILL.md`、`PIPELINE.md`、`schemas/view-spec-v3.schema.json`
- Active renderer scope: `architecture / flow / matrix / argument`
- Legacy boundary: v2 仅保留已生成 reader 的自包含静态快照；新任务不再生成 fragment
- Primary product surfaces: 桌面/平板双栏阅读器、信息重组单栏、原文定位与关系探索
- Evidence reviewed: 当前 skill、pipeline、runtime、tests，以及“总体架构：八层栈”、部署容器和 Issue 9 真实语料

本文是 v3.1 schema、skill 指令、family renderer、validator 和交互的设计源。实现字段以严格 schema 与运行时 validator 为机器合同；本文解释为什么这样建模，以及失败应回退到哪一层。

## Why this redesign exists

v2 的主要缺陷不是“线条不漂亮”，而是表达层次被压扁：

- `concept` 是名义标签，`flow` 才是真正的通用运行语法。
- 包含、分层、依赖、调用、观测和论证都被泛化为 edge。
- facts 有 source map，却常被集中到与对象脱节的全局网格。
- 几何门能检查“线有没有坏”，不能检查“这条线该不该存在”。
- 结果是考据可以正确、截图可以通过，但读者形成了错误心智模型。

v3 要修的是表达决策顺序，而不是继续给 flow renderer 增加特殊 case。

## Brand

- Personality: 冷静、可信、技术性强；像一位善于组织复杂信息的架构师。
- Trust signals: 结论明确、关系不误导、证据可回溯、视觉规则一致、失败会被门禁阻止。
- Avoid: AI 风格大卡片、装饰性渐变、无意义 icon、所有关系箭头化、稀疏却占满首屏、靠动效掩盖静态结构。

## Product goals

### Goals

1. 把线性 Markdown 转成可独立阅读的视觉论证，而不是“换主题的 Markdown”。
2. 先保证读者形成正确判断，再保证事实完整、构图清楚和表面美观。
3. 让架构、流程、比较、层级、拓扑、时间、论证和指标使用匹配的视觉语法。
4. 对弱模型形成窄而硬的合同：模型声明语义与构图意图，确定性运行时负责 DOM、几何和交互。
5. 在高信息密度与可读性之间取得结构化平衡，并保留逐项 source map。

### Non-goals

- 不做任意海报、插画、幻灯片或自由画布生成器。
- 不追求把每篇文档压成一张万能图；不同主问题应拆成不同视图。
- 不允许模型输出任意 HTML、CSS、SVG 路径或像素坐标来“自由发挥”。
- 不为旧 fragment 长期维护双轨渲染兼容层。
- 不做手机适配；标准交付面最低到 768px 的桌面/平板窄宽。
- 不用节点数、面积占比、连线无碰撞等单一指标代替人类理解质量。

### Success signals

- 读者在 5 秒内能说出每张视图的中心命题，且复述不改变主关系含义。
- `architecture` 不再退化为纵向步骤流，`contains` 不再默认画成箭头。
- 右栏脱离原文仍能回答“是什么、为什么、约束/取舍、如何行动或判断”。
- 每个会改变判断的事实都有正确作用域和 source map，不再全部堆进全局 facts 网格。
- 标准视口无断线、遮挡、溢出和交互失效；关闭交互后核心含义仍成立。
- 独立审阅者能区分主结论、主关系、辅助证据与边缘信息，无需猜颜色或线型。

## Personas and jobs

- Primary personas:
  - 技术读者：快速建立系统、方案或问题的心智模型，再决定是否下钻原文。
  - 文档作者：把现有 Markdown 转成可信、可分享的阅读投影，而不维护第二份事实源。
  - skill 维护者：用可回归合同修生成器，不逐份修生成产物。
- User jobs:
  - 先看懂主结论与整体骨架。
  - 沿主路径、边界、依赖或证据检查推理。
  - 点击任何判断回到原文核证。
  - 在不同视图间形成完整而不重复的页面级叙事。
- Key contexts of use: 架构说明、技术调研、复盘、方案比较、执行手册、长规格和数据报告。

## Information architecture

- Primary navigation: 顶部保留“原文 / 双栏 / 信息重组”三种阅读模式；它们是同一 source map 的不同投影。
- Core routes/screens: 单文件 `reader.html`；左栏是权威原文，右栏是重组视图，顶部承载模式与阅读状态。
- Content hierarchy:
  1. 页面级读者任务与中心命题。
  2. 有叙事角色的视图序列，而不是原文章节镜像。
  3. 每张视图的一条主问题、一条中心命题和一个主图法。
  4. 结构实体与 typed relations。
  5. 就近的证据、约束、风险、例外和验收条件。
  6. 原文下钻与查阅型细节。

### Page-level narrative

每张视图必须声明一个 `narrativeRole`：

- `orientation`: 建立全局地图。
- `explanation`: 解释结构或机制。
- `comparison`: 展开差异与取舍。
- `decision`: 收束为判断。
- `action`: 给出执行路径。
- `verification`: 给出验收、监控或反证。

典型顺序是“全局 → 机制 → 证据/取舍 → 决策 → 行动 → 验证”，但不是固定模板。相邻视图必须说明它回答的新问题；若只是换皮重复，应合并或删除。

## Design principles

### 1. 视觉先求真，再求美

一张图首先是一段借助空间和感知编码完成的论证。语义关系画错时，线条再顺、颜色再漂亮也属于失败。

### 2. 问题先于图型，图型先于布局

先写读者问题和中心命题，再判断关系本体，之后才能选择图法和空间骨架。不得从“这里能放几张卡片”倒推语义。

### 3. 一张视图只回答一个主问题

同一视图可以有辅助信息，但只能有一个主导阅读方式。若“系统长什么样”和“请求怎样流转”同等重要，拆成 architecture 与 flow 两张视图。

### 4. 关系不等于连线

关系可由包含、位置、对齐、分层、重复、共享轴、邻近、色彩或连线表达。只有真正需要方向和跨区域连接时才画线。

### 5. 静态清晰先于交互增强

hover、点击和动效只能帮助探索、聚焦与溯源，不能承担“没有交互就看不懂”的核心信息。

### 6. 结构化密度，不是稀疏装饰

技术图允许高密度，但信息必须按主次、作用域和关系分区。留白用于分组与节奏，不用于制造“大气感”。

### 7. 语义角色控制视觉

实体类型、关系类型、emphasis、状态和作用域决定视觉编码。模型不能通过任意色值、坐标或私有 CSS 绕开共享合同。

### Tradeoffs

- 结构化 spec 限制了自由 HTML 的造型空间，但显著提高一致性、可验证性和弱模型成功率。
- 多 family renderer 增加实现成本，但消除了“任何内容都被 flow 化”的系统性错误。
- 独立视觉语义审阅增加一次调用或人工成本，但能拦住“几何正确、表达错误”的 Goodhart 失败。

## The six-layer order

六层是不可逆的决策顺序；后层只能表达前层，不能补救前层错误。

| 层 | 核心问题 | 主要产物 | 本层不能做的事 |
| --- | --- | --- | --- |
| **义** | 谁看、为了什么、5 秒后要形成什么判断？ | `readerTask`、`question`、`centralClaim`、`narrativeRole` | 先选模板或先画卡片 |
| **理与据** | 有哪些实体、关系、事实、边界、证据和例外？ | typed entities、relation ontology、scoped facts、source map | 把所有关系泛化成 edge |
| **图法** | 哪种视觉家族最适合回答该问题？ | `diagramKind` 与适配理由 | 因 renderer 只有 flow 就改写问题 |
| **章法** | 什么放哪里、如何分组、从哪里开始读、重点在哪里？ | region tree、阅读路径、焦点和作用域 | 用颜色替代布局层级 |
| **词章** | 怎样让既定结构更易看、更一致、更有节奏？ | 尺度、字重、颜色、线型、icon、文案、动效 | 用装饰掩盖结构错误 |
| **验读** | 读者实际看出了什么，是否忠实、清楚、无误导？ | 语义、证据、构图、几何、交互 verdict | 只因脚本退出码为 0 就晋升 |

### 常见表达属于哪一层

| 表达现象 | 所属层 | 说明 |
| --- | --- | --- |
| 中心 + 周边 | 章法 | 是焦点与空间组织；通常服务 topology、architecture 或 argument 图法。 |
| 上下分层 | 章法 | 是 band 骨架；不自动等于流程。 |
| 上下分层 + 层内左右分区 | 章法 | 是 region tree 的嵌套：纵向 parent 内含横向 child。 |
| 二维画成三维堆叠表示多个实例 | 跨层 | `multiplicity=many` 属于理；重复/错位属于章法；透视、阴影属于词章。 |
| 箭头 | 跨层 | 方向关系属于理；是否显式连线由图法/章法决定；箭头样式属于词章。 |
| 文字 | 跨层 | 命题、标签、证据在义与理阶段确定；截断、字号和排版在词章阶段确定。 |
| 起点与终点 | 义 + 章法 | 流程、因果链需要；架构、矩阵、拓扑不应被强迫拥有。 |

信息密度不是第七层，而是贯穿六层的预算：义决定必须传递多少，理决定不能丢什么，图法决定承载方式，章法分配空间，词章控制可读性，验读检查认知负荷。

## Active semantic contract

v3 的模型产物是结构化 `view-spec.json`，不是 agent 手写 HTML。字段已冻结在 `schemas/view-spec-v3.schema.json`；任何命名调整必须同步更新 schema、runtime validator、本文与失败测试。

```json
{
  "schemaVersion": 3,
  "page": {
    "title": "页面标题",
    "audience": "有经验的技术决策者",
    "readerTask": "理解目标架构并判断实施边界",
    "centralClaim": {
      "text": "一句页面级结论",
      "sourceBlockIds": ["b005", "b006"]
    },
    "narrative": [
      {"viewId": "v1", "role": "orientation", "transition": "先建立全局地图"}
    ]
  },
  "views": [
    {
      "id": "v1",
      "title": "总体架构",
      "question": "系统由哪些职责边界与支撑面构成？",
      "centralClaim": {
        "text": "执行主干由分层职责承载，观测横切全栈",
        "sourceBlockIds": ["b005", "b006"]
      },
      "narrativeRole": "orientation",
      "diagramKind": "architecture",
      "diagramRationale": "主问题是职责边界、分层与横切能力，不是执行顺序",
      "entities": [
        {
          "id": "e0",
          "type": "system",
          "emphasis": "primary",
          "boundary": "internal",
          "label": "执行内核",
          "detail": "承载分层执行职责",
          "multiplicity": "one",
          "sourceBlockIds": ["b005"]
        },
        {
          "id": "e1",
          "type": "layer",
          "emphasis": "secondary",
          "boundary": "internal",
          "label": "编排层",
          "detail": "组织任务与状态",
          "multiplicity": "one",
          "sourceBlockIds": ["b006"]
        }
      ],
      "relations": [
        {
          "id": "rel1",
          "subjectId": "e0",
          "objectId": "e1",
          "kind": "contains",
          "emphasis": "primary",
          "sourceBlockIds": ["b006"]
        }
      ],
      "facts": [
        {
          "id": "f1",
          "kind": "constraint",
          "scope": {"kind": "entity", "targetIds": ["e1"]},
          "label": "边界",
          "value": "只组织任务，不直接执行工具",
          "sourceBlockIds": ["b008"]
        }
      ],
      "composition": {
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
            "childRegionIds": ["orchestration"],
            "targetRegionIds": []
          },
          {
            "id": "orchestration",
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
    }
  ]
}
```

### Claim and entity contract

- `centralClaim` 是带 source map 的对象，不是无来源口号；综合结论可引用多个 block。
- `type` 表达本体，例如 `actor / system / layer / service / datastore / event / decision / metric / claim / evidence / risk`。
- `emphasis` 只表达视觉主次：`primary / secondary / context`；每张视图必须有一个 primary。
- `boundary` 可选地表达 `internal / external`，不能再让读者靠颜色猜系统边界。
- `multiplicity` 至少区分 `one / many / optional`；只有语义为 many 时，章法才可使用重复或堆叠。
- `stateKind` 可选地表达 `start / intermediate / terminal / persistent`。它是流程状态本体，不是样式开关；非循环 flow 必须显式出现 terminal 或 persistent，普通架构实体无需硬填。
- `sourceBlockIds` 与可选 `sourceUnitId` 仍是事实来源，不因换图法而放宽。

### Relation ontology

| 关系族 | 建议 kind | 默认视觉编码 | 禁止的误读 |
| --- | --- | --- | --- |
| 结构 | `contains / partOf / layerOf / instanceOf` | 容器、嵌套、层带、重复 | 默认画成有方向箭头 |
| 动态 | `calls / triggers / produces / transitionsTo / returns` | 有方向的局部连接或主路径 | 用邻近关系假装先后顺序 |
| 依赖 | `dependsOn / enables / constrains / provides` | 邻接、支撑面、端口或弱连接 | 误画成时间流 |
| 连接 | `connectsTo / exchangesWith / peersWith` | 无向/双向端口、cluster | 偷换成单向调用 |
| 观测 | `observes / reports / alerts` | 横切带、汇聚线或监控端口 | 把观测画成最后一步 |
| 论证 | `supportsClaim / contradicts / mitigates` | claim-evidence 邻接或论证连接 | 与调用箭头共用语义 |

关系使用 `subjectId / objectId` 描述语义参与方，`kind` 决定是否有方向；这不等于视觉上必须出现箭头。对称关系的 id 顺序不产生方向含义。比较维度通常不建成 edge，而由共享行/列轴承载。

### Fact scope

`facts` 必须声明作用域，不再默认堆进全局网格：

- `entity`: 贴近某个实体的条件、指标或说明。
- `relation`: 解释某条调用、依赖或证据关系。
- `region`: 约束一个层、泳道、方案或支撑面。
- `view`: 只用于真正全局的结论、风险或不变项。

作用域先决定放置区域，样式随后决定视觉重量。不得为了排版方便把局部事实升级为 view fact。

每条 fact 只有一个作用域目标。若一个约束确实同时作用于多个实体，应挂到它们共同的 region；若是整张视图的判断，再挂到 view。禁止把同一个 fact ID 复制到多个实体旁边，这会把一条证据视觉上伪装成多条。

fact 有两种互斥形态：

- 标量 fact 使用 `value`，说明一个对象、关系、region 或整张视图。
- 比较 fact 使用 `values: [{targetId, value}]`，`label` 是共同维度；每个被比较对象恰有一个值。表格中的一个决策行对应一个比较 fact，并保留该行 `sourceUnitId`，不得拼成无结构长字符串。

## Diagram family contract

`diagramKind` 回答“这是什么类型的问题”，不是“元素怎么排”。每张视图只能有一个主图法，允许一个从属 inset；若两个图法都承担中心命题，必须拆成两张视图。

| diagramKind | 回答的问题 | 语义信号 | 常见骨架 | 硬性禁忌 |
| --- | --- | --- | --- | --- |
| `architecture` | 系统由什么组成，边界与依赖是什么？ | 分层、容器、职责、接口、支撑面 | layered、container、planes、hub-spoke | 把层画成连续步骤 |
| `flow` | 事情按什么条件推进、分支或回路？ | trigger、transition、guard、retry、terminal | left-right、top-down、lanes、cycle | 无方向关系也强加起终点 |
| `matrix` | 多个对象沿共同维度如何比较？ | options × criteria | rows-columns、quadrant | 用多条路径代替共同维度 |
| `hierarchy` | 父子、分类或从属层级是什么？ | parent/child、is-a、part-of | tree、nested outline | 用调用箭头表达从属 |
| `topology` | 多节点如何连接、汇聚或互联？ | 多对多、无单一主链 | network、hub-spoke、clusters | 强迫所有节点进入一条流 |
| `timeline` | 事件如何随时间演进？ | 日期、阶段、里程碑、持续期 | horizontal axis、phases | 把依赖位置伪装成时间 |
| `argument` | 什么证据支持或反驳什么结论？ | claim、evidence、counterevidence、decision | claim-centered、evidence columns | 把论证画成执行 pipeline |
| `dashboard` | 哪些指标处于什么状态，是否越界？ | value、threshold、trend、distribution | metric grid、trend、distribution | 用大号数字卡替代比较上下文 |

上表同时包含长期分类候选与当前实现。v3.1 schema 只接受 `architecture / flow / matrix / argument`；其他 family 必须在合同阶段失败，不能先通过 schema、再把不可渲染问题推迟给 renderer。

### Diagram selection gate

1. 先写 `question` 和 `centralClaim`，再选择 `diagramKind`。
2. 以主导关系为准，不以标题关键词为准。
3. `emphasis=primary` 的关系必须与所选 family 兼容；其他必要关系也必须有合法编码。
4. 只要有一条支撑中心命题的关系无法无误导地表达，就拆图或重选，不能用关系数量比例豁免。
5. `architecture + flow` 不是万能兜底；动态链路只能作为局部 inset，或拆成 flow 视图。
6. renderer 不可用时必须 fail fast，不能静默降级到 flow。

### v3.1 family minimums

- `architecture`: 至少包含一个结构/依赖关系或有语义 owner 的 region；所有结构关系都必须由 nesting/band 证明（`contains` 为 parent → child，其余为 child → parent）。动态关系只能是局部辅助。
- `flow`: 主体由 event/state/decision 与动态关系组成；guard、retry、checkpoint 和 terminal/持续状态必须显式建模。
- `matrix`: 至少两个 option entity、一个共同维度，以及每个强制决策维度对应的比较 fact；每条 `values[]` 必须覆盖所有 option。不得用 A/B 两张大卡加全局散文代替矩阵。
- `argument`: 至少一个 claim entity、一个 evidence/counterevidence entity，以及 `supportsClaim/contradicts/mitigates` 关系；中心 claim 是 primary 焦点，论证关系不得编码为执行顺序。

## Composition grammar

章法不再扩展 `vertical / horizontal / lanes / matrix` 的平面枚举；v3.1 固定使用**受限 region tree**，不采用任意递归绘图 AST。

### Spatial primitives

| primitive | 表达能力 |
| --- | --- |
| `container` | 边界、所有权、上下文或方案分组 |
| `band` | 层级、责任带、支撑面 |
| `axis` | 共同维度、对齐比较、指标扫描 |
| `sequence` | 有起止或明确方向的推进 |
| `radial` | 中心能力与周边消费者/依赖 |
| `stack` | 多实例、批量、同类集合 |
| `crosscut` | 观测、安全、治理等跨区域能力 |
| `inset` | 主图中的局部流程、细节或例外 |

### Region tree fields

- `rootRegionId`: 唯一根 region。
- `readingPath`: `{kind, sequence}`；`sequence` 只引用 entity id，`scan` 可为空。
- `focalIds`: 一个 primary 与有限 secondary 的 entity/fact id。
- `regions[]`:
  - `id`: 视图内唯一。
  - `primitive`: 上表枚举。
  - `role`: `main / support / crosscut / inset / context`。
  - `axis`: `horizontal / vertical / none`。
  - `parentId` 与 `childRegionIds`: 形成有序、无环树。
  - `ownerEntityId`: 可选；把一个 system/layer/option 等实体渲染成 region 边界或标题，而不是 region 内的普通节点。
  - `entityIds`: 本 region 直接承载、但不拥有该 region 的实体。
  - `targetRegionIds`: 只供 crosscut 声明横切目标。

### Deterministic composition checks

1. 恰有一个 root；所有 region 可从 root 到达，parent/children 双向一致且无环。
2. 每个 entity 恰好作为一个 region 的 `ownerEntityId` 或出现在一个 `entityIds` 中，二者不能同时发生；fact scope 只能引用已存在对象。
3. `stack` 只能承载 `multiplicity=many` 的实体；`crosscut` 必须有 target；`inset` 必须有 parent。
4. `sequence` 只允许用于 flow 主图，或其他 family 中有明确动态关系的从属 inset。
5. region tree 只描述空间组织，不复制关系语义；renderer 从 `relations[]` 推导包含、邻接、轴、端口或连线。
6. 未知 primitive、自由 CSS 名、像素位置、任意 z-index 和未声明 fallback 一律拒绝。

### Reading path and emphasis

- `left-right / top-down`: 序列、时间或分层扫描。
- `center-out`: hub、论证中心或核心能力。
- `cyclic`: 反馈回路，必须标出循环闭合点。
- `scan`: 矩阵、dashboard 或无唯一入口的架构。
- 每张视图只有一个 primary 焦点；secondary 只能服务同一中心命题。
- 先用位置、分组和尺寸建立层级，再用颜色增强。
- 空间按信息量与重要性分配，不按节点数量平均分配。

## Visual language

### Perceptual encoding order

1. 位置与对齐：决定阅读顺序和比较轴。
2. 邻近与容器：决定归属和边界。
3. 尺寸、字重与对比：决定主次。
4. 形状与线型：区分实体或关系 family。
5. 颜色：用于类别、状态和重点的冗余编码。
6. icon、阴影、透视和动效：最后使用，不能独自承载含义。

### Color

- 页面采用中性底色；每张视图通常只使用一个主强调色和不超过三个语义状态色。
- 颜色绑定稳定角色，例如 primary、recommended、risk、constraint、external、observability。
- 任一含义都必须同时由文字、形状、位置或线型表达，不能只靠颜色。

### Typography

- 固定四级：页面命题、视图命题、实体标签、证据/注释。
- 节点文字优先“名称 + 一句职责/状态”；关系标签使用动词或关系名。
- 语义文本在理与据阶段确定；词章阶段只能压缩措辞与调整排版，不能改变事实。
- 不用全大写、过多字距或超细字体营造“科技感”。

### Spacing/layout rhythm

- 使用紧凑、可重复的间距阶梯；组内间距显著小于组间间距。
- 留白必须能解释为分组、焦点、阅读节奏或路由空间。
- facts 就近放置；只有 view-scope facts 才占全宽总结区。

### Shape/radius/elevation

- 容器、实体、事实三类对象保持可区分但有限的形状词汇。
- 阴影只表达层级或叠放，不制造漂浮卡片墙。
- 三维透视只有在表达多个实例、层叠或部署平面时使用，并提供文字或数量冗余。

### Motion

- 首次进入只做一次轻量分层显现，不逐卡片排队表演。
- hover/focus 用于邻域、路径或 source map，不改变布局。
- 路径动效只用于状态变化或演示，默认静止。
- `prefers-reduced-motion` 下关闭非必要过渡。

### Imagery/iconography

- icon 只用于高频、稳定的实体类型或状态，并始终配文字。
- 不为每个节点强塞 icon；没有清晰语义价值时不用。
- 不使用大图案作为低密度背景填充。

## Components

### Existing components to reuse

- 原文块与 source map。
- 三模式切换、双栏分隔条和原文定位能力。
- 候选构建、浏览器截图、原子晋升与旧 reader 自包含快照边界。

### New/changed components

- `view-shell`: 问题、中心命题、图法与阅读说明。
- `region`: 层、容器、泳道、支撑面、横切面。
- `entity`: 由 type/emphasis/boundary 驱动，不统一成大卡片。
- `relation-layer`: 按关系本体选择容器、轴、端口或线。
- `fact`: 支持 entity/relation/region/view 四种作用域。
- `legend`: 仅在存在两种以上非显然编码时出现。
- `source-inspector`: hover 预览、click 锁定、键盘定位原文。
- family renderers: v3.1 实现 architecture、flow、matrix、argument；其他 family 仅保留词汇并 fail fast。

### Variants and states

- Entity emphasis: primary、secondary、context；boundary: internal、external。
- Fact kinds: evidence、constraint、risk、exception、metric、checkpoint、decision。
- Relation emphasis: primary、secondary、context；kind 决定编码，颜色不能临时改写含义。
- Selection states: idle、hovered/focused、locked、dimmed、source-active。

### Token/component ownership

- shared runtime 拥有 tokens、DOM、source sync、可访问性和交互。
- family renderer 拥有该图法的布局约束与关系编码。
- view spec 只声明语义、受限章法和 emphasis，不拥有 HTML、CSS 或 SVG。

## Interaction states

### Understanding interactions

- Hover/focus entity: 高亮一跳邻域，并显示关系标签与局部 facts。
- Click/Enter entity or fact: 锁定选择、定位原文并保持上下文；Esc 清除。
- Path focus: 只在 flow 或明确动态 inset 中提供主路径/异常路径聚焦。
- Progressive disclosure: 查阅型细节可展开；主命题、关键约束和决策证据默认可见。
- Mode/split changes: 重排后保持焦点与 source selection，不把用户送回页首。

### Runtime states

- Loading: 自包含文件加载后先隐藏未测量关系层，布局完成后一次显示，避免断线闪烁。
- Empty: compiler 拒绝没有中心命题或有效实体的视图，不向最终产物输出空壳。
- Error: renderer 或 source-map 错误阻止晋升；最终 reader 不展示半成品占位。
- Success: source lock、模式切换和路径聚焦提供清楚、可撤销的反馈。
- Disabled: 不适用的路径/筛选控件不渲染，避免无解释灰态。
- Offline/slow network: 最终 HTML 自包含；核心阅读与交互不依赖网络。

## Accessibility

- Target standard: WCAG 2.2 AA；视觉图同时提供结构化 DOM 阅读顺序与关系摘要。
- Keyboard/focus behavior: 所有实体、fact 和控件可用 Tab、Enter/Space、Esc；焦点态不只靠颜色。
- Contrast/readability: 正文、关系标签和状态满足对比要求；最小字号和行高由 runtime token 控制。
- Screen-reader semantics: 使用真实标题、region、list/table 与关系摘要；视觉位置不能改写 DOM 逻辑顺序。
- Reduced motion and sensory considerations: 支持 reduced motion；颜色、动画、阴影和位置都不是唯一语义通道。

## Responsive behavior

- Supported breakpoints/devices: 1440、1280、1024、768；不包含手机。
- Layout adaptations:
  - 1440/1280: 双栏和信息重组模式都保持主图法骨架。
  - 1024: 允许收紧间距、局部 region 换行或 inset 下移，不改变关系语义。
  - 768: 仍属于受支持的桌面/平板窄宽，双栏 shell 和三种模式必须可用；family 内部可换行或局部堆叠，但矩阵轴、层级与主路径必须保留。
- 小于 768px 不属于交付合同；运行时可以有保护性降级，但不得据此宣称手机适配。
- Touch/hover differences: hover 是增强项；focus/click 覆盖同等能力。768 仍按桌面/平板交互，不另建手机手势。

## Content voice

- Tone: 精确、短促、以判断和动词为中心，不喊口号。
- Terminology: 同一实体和关系在页面内只用一个名称；`calls`、`dependsOn`、`contains` 不可泛化成“关联”。
- Microcopy rules:
  - 标题回答“这张图讲什么”；中心命题回答“应该得出什么结论”。
  - entity detail 写职责、状态或边界，不复述 label。
  - relation label 使用动词；fact label 使用维度/类别名。
  - 禁止不能被 source evidence 具体化的“赋能、闭环、全链路”等空词。

## Active pipeline

执行面收敛为六段。为避免把确定性来源工作误当成视觉层，“来源盘点”和“义”合并为第一段；其内部仍严格先建立 source ledger，再做表达决策。

1. **来源盘点 + 义**
   - `parse_blocks.py` 解析 blocks/sourceUnits，建立不可变 source ledger。
   - 模型输出 audience、readerTask、page/view centralClaim、question、narrativeRole；先审“是否值得成为一张视图”，不接触 layout。
2. **理与据：语义建模（模型 + 确定性校验）**
   - 输出 typed entities、typed relations、scoped facts、emphasis、multiplicity、`stateKind` 与 source map。
   - 表格/checklist 逐项对账；可见文字必须与模型一致。
3. **图法：family 选择（模型提议 + 硬规则）**
   - 选择一个 `diagramKind` 并写 `diagramRationale`。
   - compatibility gate 不通过时拆图或退回理据，renderer 不可用时 fail fast。
4. **章法：受限 composition spec（模型）**
   - 输出 region tree、readingPath、focalIds 和 fact scope。
   - 不输出 HTML、CSS、SVG 或像素坐标。
5. **确定性编译**
   - `assemble_v3.py` 执行严格字段、semantic-fit、source-fidelity 与 composition 合同，再由 family renderer 编译语义 DOM。
   - shared runtime 应用 tokens、source sync、可访问性、交互和必要关系几何，只产出 `*.candidate.html`。
6. **独立盲读 + 原子晋升**
   - 真实浏览器在 1440 / 1280 / 1024 / 768 生成截图和机器报告；独立 reviewer 先 blind readback，再与 spec comparison。
   - `build_reader.py v3` 重新确定性编译，核验候选 SHA256、reviewer/producer 独立性、所有视图、所有 primary relations、所有 facts 与 PASS；全部通过才原子替换 reader。

### Failure routing

| 失败现象 | 回退层 |
| --- | --- |
| 读者复述错中心命题 | 义 |
| 漏事实、关系类型错、局部 fact 变全局 | 理与据 |
| 架构被看成流程、证据被看成步骤 | 图法 |
| 主次不清、线过长、区域冲突、路径混乱 | 章法 |
| 色彩失控、文字堆砌、icon/动效抢重点 | 词章 |
| 断线、遮挡、键盘失效、source map 错 | renderer/runtime；修复后重走验读 |

禁止在词章层用“换颜色/加阴影”掩盖义、理、图法或章法问题。

## Validation contract

### 1. Semantic-fit gate

- 每张视图有且只有一个主问题和中心命题。
- diagramKind 与每条 relation 都兼容；`primary` 只表示视觉主导关系，不是逃过 family 合同的豁免口。
- `contains / partOf / layerOf / instanceOf` 必须由空间结构表达；不得只画方向箭头。
- flow 至少有一个动态关系且所有 relations 都属于动态族，并有入口/闭合回路及终止或持续状态；全部分支实体从主路径起点可达并显式呈现，每条回边也有可见有向 connector。
- matrix 的所有 entities 都是 option 且至少两个，并有共享维度和逐维比较 facts；每个 `values[]` 完整覆盖 options，且 relations 为空。
- argument 至少有一个 claim、一个 evidence/counterevidence 和一条论证关系；所有 relations 都属于论证族，中心 claim 是主焦点，论证关系不得编码为执行顺序。
- visible label/detail/value/values 必须来自模型，compiler 不可自创或漂移。

### 2. Evidence-fidelity gate

- 所有强制原子项逐项投影，数字逐字一致。
- 每个 claim、entity、relation 和 fact 的 source map 精确存在。
- renderer 声明的 entity / relation / fact id 集合与实际 DOM 精确相等；不得以可见文字替代缺失的语义对象。
- `compressedOut` 不得包含会改变结论、约束、风险或验收的信息。
- fact scope 不得因布局便利而改变。

### 3. Composition gate

- 5 秒内先看到中心命题与主骨架，而不是装饰和空白。
- 一次视线移动能跟完主关系；辅助关系不穿越主焦点。
- region 密度与重要性匹配，不平均分配大卡片。
- 关闭颜色后，分组、主次和关系仍可理解。
- 关闭交互后，核心结论仍成立。

### 4. Browser gate

- 在 1440 / 1280 / 1024 / 768 检查 DOM、几何、溢出、遮挡、端点、文字、键盘、模式、调宽和 reduced motion。
- 每个 family 有自己的断言；不能只复用通用 edge 检查。
- 字体加载、模式切换、栏宽调整和重排后关系层稳定重算，不出现断线闪烁。

### 5. Independent visual-semantic gate

生产者不能独自给自己的图放行。每次 v3 晋升必须产生 `visual-verdict.json`；reviewer 可以是独立视觉 agent 或人工，但必须独立于生成者。

审阅分两步，避免 reviewer 直接复述预期答案：

1. **Blind readback**: reviewer 只看最终截图，不接收 `centralClaim`、`diagramKind`、relation kinds 或 `focalIds`，先独立写下它实际看见的命题、关系、焦点和 fact 归属。
2. **Comparison**: 另一个确定性/独立 evaluator 再把 blind readback 与 view spec 对账，生成 PASS/REJECT。生产者不能改写 blind readback。

```json
{
  "schemaVersion": 1,
  "candidate": "reader.candidate.html",
  "candidateSha256": "把候选文件的 64 位 SHA256 粘贴到这里",
  "reviewer": {
    "id": "independent-reviewer-id",
    "mode": "vision-agent",
    "independentFromProducer": true
  },
  "views": [
    {
      "viewId": "v1",
      "blindReadback": {
        "centralClaimParaphrase": "这是分层架构，不是八步流程",
        "dominantRelation": "containment",
        "firstFocalLabels": ["执行内核"],
        "factAttachments": [
          {"factLabel": "边界", "attachedToLabel": "编排层"}
        ],
        "lowerMisreadAlternative": "none"
      },
      "comparison": {
        "claimMatches": true,
        "primaryRelationMatches": [
          {"relationId": "rel1", "matches": true}
        ],
        "focalMatches": true,
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

- reviewer 必须盲读中心命题、主要关系、首个焦点和 fact 作用域，并判断是否存在更低误读的图法。
- `candidateSha256` 必须绑定确定性候选的实际字节；重新编译后摘要漂移会阻止晋升。
- `comparison.primaryRelationMatches` 必须精确覆盖该 view 的全部 `emphasis=primary` relations；`factScopeMatches` 必须精确覆盖全部 facts，不得缺项或加入 spec 外 id。
- reviewer/producer 身份由编排器记录和比较：`reviewer.id` 必须与 `build_reader.py v3 --producer-id` 不同，不能只信 JSON 中自报的布尔值。
- 任一 match 为 false、任一 view 为 `REJECT` 或 `UNCERTAIN`、verdict 缺失、摘要不符或 reviewer 与 producer 不独立，都阻止晋升。
- 几何门通过不能覆盖视觉语义 verdict。

### Adversarial regressions

下列输入必须被拒绝或纠正：

- architecture 使用等宽纵向节点和连续箭头表达层/面。
- `kind=contains` 只以方向箭头表达。
- 模型是分层架构，visible text 却换成无关流程文案，即使 id 与节点数正确。
- 两个方案的大卡片大量空白，真正比较维度全塞到全局 facts。
- 风险、约束、推荐项仅靠红/黄/绿区分。
- 核心关系必须 hover 后才出现。
- 通用 router 无碰撞，但长线绕过半张图，让结构被误读为流程。

## Reference corpus and architecture benchmark

“总体架构：八层栈”是 v3 的第一条纵向切片，不是手修特例：

- Reader task: 理解主执行栈、侧向能力、共享支撑面与横切观测面。
- Central claim: 主链职责分层，定义/知识贴近使用它们的层，支撑服务被多层复用，观测横切全栈。
- Diagram kind: architecture，不是 flow。
- Composition: 主职责使用 bands；定义/知识就近；支撑使用 shared region；观测使用 crosscut。
- Relations: 包含与分层由位置/容器表达；只有原文明确且理解需要时才画局部调用箭头。
- Density: 每层展示名称、职责与关键边界，不使用八张同尺寸、低密度长卡。
- Pass: 独立读者复述为“分层架构与横切支撑”，而不是“八步流程”。

architecture renderer 的当前基准同时包含“八层栈”和部署容器两份不同骨架的真实 fixture，覆盖 layered/crosscut 与 container/shared-plane。后续修改必须同时回归；只让单一样例通过时，不得声明 architecture family 仍然通用。

## Implementation constraints

- Framework/styling system: 继续输出自包含 HTML；Python 负责合同与编译，浏览器 runtime 负责测量和交互。
- Model/runtime boundary:
  - 模型输出 `view-spec.json`，不直接写 HTML。
  - compiler 生成语义 DOM；family renderer 决定布局与关系编码。
  - shared runtime 拥有 tokens、source sync、可访问性、状态和必要几何路由。
- v3.1 renderer scope:
  - 必须实现：architecture、flow、matrix、argument。
  - 暂未实现且不进入 schema：hierarchy、topology、timeline、dashboard。
  - 未实现 kind 在合同阶段返回 `unsupported_diagram_kind` 并停止，禁止 fallback 到 flow。
- Design-token constraints: spec 不得引入任意色值、字号、阴影或 z-index。
- Performance constraints: 单文件离线；首次布局无明显闪烁；调整分栏只重算受影响视图。
- Compatibility constraints:
  - 已生成的 v2 reader 继续作为静态快照打开。
  - v2 fragments 不在 v3 runtime 中透明兼容；重新生成获得 v3 能力。
  - 新任务只使用 `view-spec.json + assemble_v3.py + build_reader.py v3`；v2 CLI 是 legacy，不再扩展。
- Test/screenshot expectations:
  - JSON Schema、失败合同和 family renderer 回归同步维护。
  - 四个 v3.1 family 都有正例、类别错误、关系误编码、密度和 source-fidelity 反例。
  - 浏览器截图按视图保存；visual verdict 必须绑定候选 SHA256，并与机器报告一起作为晋升证据。

## Implemented baseline and evolution

v3.1 已完成可交付基线：

1. 严格 JSON Schema、关系本体、`stateKind`、region tree、family gate、source-fidelity 和 visual-verdict 合同。
2. 两份不同空间骨架的 architecture 真实 fixture，贯通 spec → compiler → renderer → 浏览器/验读门。
3. architecture、flow、matrix、argument 四个确定性 renderer；模型不再输出通用 `data-flow` fragment；renderer 会逐 view 对账声明与实际 DOM 的 entity/relation/fact ID 集合，任何静默丢失都 fail fast。
4. entity/relation/region/view 四级 fact scope，以及 page narrative、source map 和原子 source-unit 对账。
5. 候选 SHA256、reviewer/producer 身份独立、逐 view/主关系/fact 对账与原子晋升。

后续演进仍遵循“先失败测试、再实现、最后真实 reader 浏览器验收”：邻域/路径的理解型交互可以继续增强；`hierarchy / topology / timeline / dashboard` 只有在真实语料达到覆盖门槛后才实现。未知 diagramKind 绝不降级成 flow。

## Open questions

- [ ] page narrative 的重复度与缺口如何形成可验证、但不易被 Goodhart 的信号。
- [ ] 新 family 所需的“真实语料覆盖门槛”如何定义，避免单样例过拟合。
- [ ] source package 中现有 README 与开放 Agent Skills 打包规范如何收敛；不影响表达合同，但影响发布形态。
