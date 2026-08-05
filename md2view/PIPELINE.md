# md2view 五环流水线 · 详规

脚本都在本 skill 的 `scripts/` 下。下文 `$SK` 指代**本 skill 的安装目录**（加载本 skill 时即已知道它的实际路径）；执行脚本时把 `$SK` 替换成该路径，不要写死。
建议为一次任务建一个工作目录（放 blocks.json / views.json / fragments/ / 产物），不要污染源仓库。

一份 md → 单文件双栏 HTML。保真靠环间对账，不靠某层不犯错。

---

## 环 1 · 块切分（确定性）

```
python3 $SK/scripts/parse_blocks.py <input.md> blocks.json
```

产出 `blocks.json`：每块 `{id, type, raw, depth?}`，`type ∈ heading/paragraph/list/table/code/quote`。
这是溯源和覆盖率的基础——每块一个稳定 id（`b000`…），后续所有溯源都指向它。

---

## 环 2 · 语义建模（模型，1 个 agent）

派 1 个建模 agent，输入 `md` 全文 + `blocks.json`，产出 `views.json`。**只建模，不写 HTML。**

### 铁律
1. **视图必须切过章节结构**。先问自己："这份文档描述的系统 / 该在读者脑中建立的心智模型，是什么图？"把散在多个章节的同类概念聚成一个视图。**若每个视图对应原文一章 = 失败，重来。**
2. **每个视图是压缩**：元素 ≤ 12，`label` ≤ 10 字，`detail` ≤ 40 字。
3. **每个元素带 `sourceBlockIds`**（提炼自哪些块），供下钻。压缩掉的不是丢弃，是没被投影。
4. **决策 / 对比场景保留维度。** 方案矩阵、证据矩阵、取舍判断不能只剩 A/B 标签；必须抽出可比较维度（路径、依赖、风险、边界、测试、成本等）并在 `data` 或元素结构中保留。
5. **数字场景（dashboard）每元素带 `data`**（数值 / 单位 / 占比），从原文**逐字抄录，禁心算改写**，建模后逐个对照原文自检。
6. `concept` 从词汇表选或自创：`layers / pipeline / flow / matrix / timeline / graph / tree / quadrant / funnel / trend / distribution / evidence-chain / kpi-strip`。
7. `relations` 表达元素关系 `{from,to,label,kind}`，`kind ∈ depends/triggers/guards/produces/escalates/contains`。
8. `coverage_note`：哪些内容**不进**任何视图（运行命令、维护细则等查阅型细节），它们留给全文层 / 左栏。

### views.json schema
```json
{
  "title": "页面标题", "subtitle": "一句话副标",
  "views": [
    {
      "id": "v1", "title": "…", "concept": "layers", "insight": "5 秒看懂什么（一句话）",
      "elements": [
        {"id":"e1","label":"≤10字","detail":"≤40字","sourceBlockIds":["b006","b007"],
         "data":{"value":94,"unit":"次","pct":"0.058%"},
         "facts":[{"id":"f1","label":"维度","detail":"≤40字","sourceBlockIds":["b006"]}]}
      ],
      "relations": [{"from":"e1","to":"e2","label":"…","kind":"guards"}],
      "compressedOut": "这个视图省略了什么、去哪看"
    }
  ],
  "coverage_note": "留给全文层的内容"
}
```

### 自检（返回前）
- 视图是否真切过章节（不是目录搬家）？
- 所有 `sourceBlockIds` 在 `blocks.json` 里真实存在？
- dashboard 的每个 `data` 与原文逐字一致？

---

## 环 3 · 分视图编码（模型，每视图 1 个 agent，并行）

每个视图派一个 fragment agent（**并行**），输入该视图的 views 定义 + `blocks.json`，产出 `fragments/<vid>.html`。

fragment v2 把职责切开：**agent 决定信息如何重编码，运行时决定它如何稳定地画出来。** agent 输出节点、边、顺序 / 泳道 / 分组等布局意图；组装器统一负责视觉语言、连线几何、响应式和交互反馈。这样既保留模型的构图能力，也避免每张图重复盲写坐标造成断线和风格漂移。

### fragment v2 最小合同

| 标记 | 责任 |
| --- | --- |
| `data-flow` | 声明一个独立的流程图作用域；节点 id 和边引用只在此容器内解析。 |
| `data-layout` | 声明布局意图，例如 `horizontal`、`vertical` 或 `lanes`；运行时可按可用宽度降级重排。 |
| `data-node-id` | 节点在当前 `data-flow` 内的稳定唯一 id，通常与 `views.json.elements[].id` 一致。 |
| `data-fact-id` | 可选事实条在当前 `data-flow` 内的稳定唯一 id；用于 `.mv-fact` 承载比较维度或证据点。 |
| `data-source-blocks` | 空格分隔的源块 id。每个承载事实、判断或数字的内容节点都必须有，用于点击 / 键盘溯源和双栏同步。 |
| `data-from` / `data-to` | 只声明一条边的起止节点 id；两端必须存在于同一个 `data-flow`。 |
| `data-kind` / `data-label` | 可选的关系类型和短标签，对应 `relations[].kind` / `label`。 |

推荐片段：

```html
<section class="view" id="v1">
  <h2><span class="n">01</span>登录路径</h2>
  <p class="insight">两条路径在身份建立处汇合</p>

  <div class="mv-flow" data-flow data-layout="horizontal" aria-label="登录路径流程">
    <article class="mv-node" data-node-id="e1"
             data-source-blocks="b006 b007" tabindex="0">
      <span class="mv-node-title">身份输入</span>
      <span class="mv-node-detail">用户提交已有凭据</span>
    </article>
    <article class="mv-node" data-node-id="e2"
             data-source-blocks="b012" tabindex="0">
      <span class="mv-node-title">建立会话</span>
      <span class="mv-node-detail">校验通过后签发会话</span>
    </article>

    <span class="mv-edge" data-from="e1" data-to="e2"
          data-kind="guards" data-label="校验" hidden></span>
  </div>

  <p class="compressed-out">异常细则见左栏原文</p>
</section>
```

`.mv-edge` 是机器可读的关系声明，不是可见线条；组装器会在同一流程容器上生成一层共享 SVG overlay，并依据节点的真实 DOM 边界绘制 `.mv-edge-path`。窗口缩放、分隔条拖动、字体加载或节点尺寸变化后，运行时重新测量并路由，因此 fragment 不保存像素坐标。

### 铁律

1. **图形必须表达概念，不退化成卡片罗列。** 分层要体现拦截关系，流程要体现方向和分支，泳道要体现责任边界；用 DOM 顺序、`data-layout`、分组和关系声明表达构图意图。
2. **每个内容节点都要可溯源。** `data-source-blocks` 中的 id 必须真实存在于 `blocks.json`；同一事实来自多块时完整列出，不能只挂第一个。
3. **流程边只写关系，不写坐标。** 禁止 fragment 在 `data-flow` 内使用 SVG `path` / `line` / `polyline`、伪元素或固定像素线段绘制流程连线；否则节点响应式变化后必然断裂。静态图标或不承担节点连接的迷你图形应放在 `data-flow` 外，避免和运行时几何层混用。
4. **禁外部库、外部资源和自带 JS。** 片段保持离线可组装；交互和连线由运行时统一实现。允许少量视图专属 CSS 表达网格区域、顺序或强调层级，但不能重定义共享节点、连线、焦点和动效规则；类名加视图 id 前缀（`v1-…`）避免污染全局。
5. **制图前回源核对。** 按 `sourceBlockIds` 核对数字 / 事实；发现不存在的块或错误数字，按原文纠正并标注，这是保真的关键拦截点。
6. **继续压缩。** 图上只放 `label` / `detail` 级短语，不搬原文段落；被省略内容通过左栏和 `compressed-out` 保留访问路径。
7. **提高语义密度。** 压缩不是删成空壳。每个关键节点优先保留 1-3 个决策相关微事实，可用 `.mv-node-meta` 做短标签；矩阵 / 取舍视图应追加 `.mv-fact-grid` / `.mv-fact[data-fact-id][data-source-blocks]`，把路径、依赖、风险、边界、测试等比较维度做成可溯源事实条。
8. **控制视觉密度。** 默认把一个视图压进 600px 左右的阅读高度；留白只服务于分组、层级和连线避让。不要用装饰性大间距、过窄节点、松散错层或“每个概念一张孤立卡片”来制造高级感。若为了避让连线必须留空间，应优先扩大节点宽度、压缩 lane padding，再保留必要的路由通道。

---

## 环 4 · 确定性组装

两种输出形态，按需选：

**双栏同步阅读器（推荐 · 最终交付形态）**
```
python3 $SK/scripts/assemble_split.py blocks.json fragments/ views.json reader.html
```
左栏原文线性渲染（每块 `data-block-id`）＋右栏视图＋顶部三钮（原文 / 双栏 / 信息重组）＋可调宽分隔条＋滚动锚定同步＋动态连线＋点击 / 键盘溯源。
**同步靠 block id 锚定，不是滚动百分比**——两栏长度不等（右栏压缩后短得多），百分比同步必然错位。这是本 skill 独有、依赖 source map 才做得出的能力。

双栏宽度由运行时按视口给出可用默认值，支持拖动、方向键微调、双击复位并记忆比例；窄视口不强行挤压两栏，而是切换成单栏模式。流程连线同样属于运行时：它解析 fragment 的边声明、测量真实节点位置，在一个共享 SVG 层中绘制，并在 `ResizeObserver`、视图切换和分隔条变化后重算。

**单栏概念视图（兼容路径，不需要动态流程线时使用）**
```
python3 $SK/scripts/assemble_view.py views.json fragments/ blocks.json view.html
```
点任何带 `data-source-blocks` 的元素 → 右侧抽屉显示原文块。适合只要重组视图、不需要原文并置的场景。

两种产物都是自包含单文件 HTML，离线可用、可分享；fragment v2 的动态连线与自适应双栏以 `assemble_split.py` 为准。

---

## 环 5 · 真实浏览器校验（不可省）

fragment v2 消除了流程连线的盲写坐标，但不能消除真实浏览器中的布局、字体、事件和响应式问题。最终交付物是 `reader.html`，验收也必须针对它，而不是只检查 fragment 文本或脚本退出码。

**闭环：组装 → 多视口渲染 → 交互与几何检查 → 截图验伤 → 修生成器 / fragment → 完整回归。**

skill 自带的 `shot.js` 默认在 1440 / 1280 / 1024 / 768 四个宽度截图并运行 smoke assertions（需 playwright）：
```
node $SK/scripts/shot.js reader.html <out-dir> --viewports=1440,1280,1024,768 "#v1" "#v2" ...
```

必须覆盖以下验收面：

- **响应式**：四个视口都无页面横向溢出；宽屏双栏可用，窄屏单栏切换正确。
- **双栏调宽**：拖动分隔条即时反馈；方向键可调；双击复位；刷新后恢复上次比例。
- **模式与溯源**：原文 / 双栏 / 信息重组三种模式可切换；鼠标点击和键盘 Enter / Space 都能锁定映射、定位原文并显示明确选中态，Esc 可清除。
- **连线连续性**：每个边声明都生成有效 `.mv-edge-path`；端点贴合对应节点，路径非空、无 `NaN`、不越界、不被节点遮成视觉断线；改变栏宽后仍成立。
- **视觉与动效**：节点层级、对比度、焦点态清楚；动效不抢阅读焦点，并在 `prefers-reduced-motion` 下关闭非必要过渡。
- **信息密度**：截图中每个视图的核心流程不应像海报一样松散；桌面信息单栏下优先检查视图高度、节点面积占比和装饰性留白，必要时修 fragment 的局部网格或组装器的全局 spacing。
- **运行健康**：无浏览器 console error / page error；每个 fragment 的 source map 仍可用。

`shot.js` 的 assertions 负责确定性 smoke 检查，截图仍需人工看层级、留白、标签碰撞和线路观感。若问题来自共享布局、连线或交互，应修组装器而不是逐个修生成产物；只有某个视图的语义顺序、分组或局部网格错误时才修对应 fragment。

---

## 保真校验（贯穿，确定性）

```
python3 $SK/scripts/coverage.py blocks.json <out.html>
```
机检：内容块覆盖率（有多少源块的内容进了产物）、关键数字是否在场。
组装后跑一遍做机械对账——它抓不出"图画错"，但能抓出"内容丢了 / 数字没进去"。配合环 3 的回源核对、环 5 的看图验伤，三道对账共同保真。

---

## 一次完整跑（骨架）

```
mkdir work && cd work
python3 $SK/scripts/parse_blocks.py ../doc.md blocks.json      # 环1
# 环2：派建模 agent 读 doc.md + blocks.json → 写 views.json
mkdir fragments
# 环3：读 views.json，每个 view 派一个 fragment agent 并行输出语义 fragment
python3 $SK/scripts/assemble_split.py blocks.json fragments/ views.json reader.html   # 环4
node $SK/scripts/shot.js reader.html shots --viewports=1440,1280,1024,768 "#v1" "#v2"  # 环5
# 看图验伤 + 交互/连线断言 → 修生成器或 fragment → 重跑环4/环5
python3 $SK/scripts/coverage.py blocks.json reader.html          # 保真机检
```

## fragment v2 兼容边界

已经生成的旧 `reader.html` 是自包含快照，不依赖本 skill 的后续版本，仍可离线打开。旧 fragments 没有语义边声明，无法自动获得动态连线、自适应布局和新交互；要获得这些能力，按环 3 重新生成 fragment，再重跑环 4。不要在运行时长期维护“旧手写坐标 + v2 动态连线”双轨兼容层。
