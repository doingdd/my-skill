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
4. **数字场景（dashboard）每元素带 `data`**（数值 / 单位 / 占比），从原文**逐字抄录，禁心算改写**，建模后逐个对照原文自检。
5. `concept` 从词汇表选或自创：`layers / pipeline / flow / matrix / timeline / graph / tree / quadrant / funnel / trend / distribution / evidence-chain / kpi-strip`。
6. `relations` 表达元素关系 `{from,to,label,kind}`，`kind ∈ depends/triggers/guards/produces/escalates/contains`。
7. `coverage_note`：哪些内容**不进**任何视图（运行命令、维护细则等查阅型细节），它们留给全文层 / 左栏。

### views.json schema
```json
{
  "title": "页面标题", "subtitle": "一句话副标",
  "views": [
    {
      "id": "v1", "title": "…", "concept": "layers", "insight": "5 秒看懂什么（一句话）",
      "elements": [
        {"id":"e1","label":"≤10字","detail":"≤40字","sourceBlockIds":["b006","b007"],
         "data":{"value":94,"unit":"次","pct":"0.058%"}}
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

## 环 3 · 分视图制图（模型，每视图 1 个 agent，并行）

每个视图派一个制图 agent（**并行**），输入该视图的 views 定义 + `blocks.json`，产出 `fragments/<vid>.html`。

### 铁律
1. **手工 SVG / CSS，禁 Mermaid / 外部库 / 外部资源 / 自带 JS。** 图形要真表达概念：分层就画拦截关系、管道就画数据流、漏斗就真收窄、决策就画判定分支。**禁止退化成"卡片罗列"。**
2. **每个图形元素挂 `data-source-blocks="块id 空格分隔"`**（SVG 元素也支持此属性），可加 `data-label`。全局 JS 靠它做点击下钻 / 双栏同步——**一个都不许漏**。
3. **制图前按 `sourceBlockIds` 回原文核对**数字 / 事实。发现建模层的错（引用了不存在的块、数字取错），**按原文纠正并在图上标注**——这是保真的关键拦截点。
4. **反 AI slop**：禁紫渐变 / glass morphism / 千篇一律居中卡片。只用组装器提供的全局 CSS 变量：`--bg --surface --text --muted --accent --accent-soft --border --ink --good --warn --font --sans --mono`。类名加视图 id 前缀（`v1-…`）避免污染全局。
5. **压缩纪律**：图上只放 `label`/`detail` 级短语，不搬原文段落。
6. **文字不要用 SVG 绝对坐标硬摆到图形上**（会压斜边 / 重叠）——优先 HTML/CSS 布局让文字在块内，或 SVG 里给足留白。

### 片段格式
```html
<section class="view" id="v1">
  <style>/* 类名全部 v1- 前缀 */</style>
  <h2><span class="n">01</span>标题</h2>
  <p class="insight">insight 文案</p>
  <!-- 手工图形，每个元素带 data-source-blocks -->
  <p class="compressed-out">compressedOut 文案</p>
</section>
```

---

## 环 4 · 确定性组装

两种输出形态，按需选：

**双栏同步阅读器（推荐 · 最终交付形态）**
```
python3 $SK/scripts/assemble_split.py blocks.json fragments/ views.json reader.html
```
左栏原文线性渲染（每块 `data-block-id`）＋右栏视图＋顶部三钮（原文 / 双栏 / 信息重组）＋滚动锚定同步＋高亮。
**同步靠 block id 锚定，不是滚动百分比**——两栏长度不等（右栏压缩后短得多），百分比同步必然错位。这是本 skill 独有、依赖 source map 才做得出的能力。

**单栏概念视图（带点击溯源抽屉）**
```
python3 $SK/scripts/assemble_view.py views.json fragments/ blocks.json view.html
```
点任何带 `data-source-blocks` 的元素 → 右侧抽屉显示原文块。适合只要重组视图、不需要原文并置的场景。

两种产物都是自包含单文件 HTML，离线可用、可分享。

---

## 环 5 · 视觉校验（模型，不可省）

SVG 没有布局引擎——制图 agent 在盲写坐标，算得出数值、**看不见渲染**。布局 bug（图文重叠、斜边割字、`path` 缺 `fill:none` 变黑三角、深字压深底、超出 viewBox 被裁）**只有渲染后可见**，无法靠"生成时更小心"消除。

**闭环：渲染 → 截图 → 看图验伤 → 定点修 → 回归截图。**

截图（skill 自带工具，需 playwright）：
```
node $SK/scripts/shot.js reader.html <out-dir> "#v1" "#v2" ...
```
逐 section 截图看细节。无 playwright 时可 `npx playwright` 或用 Chrome headless：
`chrome --headless --screenshot=out.png --window-size=1280,2400 file://<abs-path>`。

**常见 bug 速查**
- SVG `<path>` 做引导线 / 折线但漏了 `fill:none` → 默认黑填充连成实心三角。
- 文字用 SVG 绝对坐标压在图形 / 斜边上 → 改 HTML/CSS 布局，文字进块内。
- 深色背景压深色字 → 对比度不足，改浅色或移出。
- 元素坐标超出 `viewBox` → 被裁。

修复只改出问题的那个 `fragments/<vid>.html`，重跑环 4 组装，重截确认。

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
# 环3：读 views.json，每个 view 派一个制图 agent 并行 → fragments/<vid>.html
python3 $SK/scripts/assemble_split.py blocks.json fragments/ views.json reader.html   # 环4
node $SK/scripts/shot.js reader.html shots "#v1" "#v2"          # 环5 截图
# 看图验伤 → 定点修 fragments → 重跑环4 → 重截，直到干净
python3 $SK/scripts/coverage.py blocks.json reader.html          # 保真机检
```
