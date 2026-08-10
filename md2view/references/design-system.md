# md2view 设计系统(组件词汇)

右栏片段由这些类组合而成。全部样式在 `assets/shell.css`,构建时内联。**不要**重定义 `mv-*` 类;单图布局需要自定义网格时,在 `<style>` 里用 `#视图id` 前缀写(如 `#v-arch .bands{display:grid;...}`)。

## 页面与视图骨架

| 类 | 用途 | 要点 |
| --- | --- | --- |
| `.mv-page-head` | 页面开场:kicker + h1 + `.mv-lead` 导语 | 整页只用一次 |
| `.mv-kicker` | mono 小标签,自动带 VIEW 编号(`<span class="vn"></span>`) | 编号由 CSS 计数器生成,不要手写 "VIEW 01"——手写数字过不了数字门 |
| `section.mv-view` | 一个视图回答一个读者问题 | 带 `id="v-xxx"`,供 `#` 定位与 scoped style |
| `.mv-view-head` > `h2` | 视图标题,回答"这张图讲什么" | 衬线,建议回指原文章节词(天然词锚) |
| `.mv-claim` | 中心命题条:这个视图的 5 秒结论 | 每视图一条;必须带来源 |
| `.mv-lead` / `.mv-note` | 导语 / 小字注 | 正文 13.5px / 注 12px |

## 内容组件

| 类 | 用途 | 变体/要点 |
| --- | --- | --- |
| `.mv-grid` | 卡片/指标网格 | `.cols-2/3/4` 或 `.auto`;容器过窄自动降列 |
| `.mv-card` | 标题卡(h4 + p) | `.tone-accent/ok/warn/risk` 顶条着色 |
| `.mv-tablewrap` + `table.mv-table` | 数据表 | `caption` 写表题;首列加 `.k`;数字列加 `.num`;关键行 `tr.is-hl`;`td/th` 内联 `style="width:..."` 控列宽 |
| `.mv-callout` | 标注条(风险/约束/证据/决策) | `.tone-risk/warn/ok/evidence/decision/violet`;内部 `.mv-co-label` + `.mv-co-body` |
| `.mv-tag` | 小标签 chip | `.tone-ok/warn/risk/neutral`;`.mv-tagrow` 成排 |
| `.mv-metric` | 大数字指标 | `.v` 数字 + `.l` 说明;数字必须在来源里逐字存在 |
| `.mv-list` | 紧凑列表 | `ol` 的编号自动 accent |
| `.mv-facts` + `.mv-fact` | 事实行(`.mv-fact-l` 标签 + `.mv-fact-v` 内容) | 适合"幂等/重试/超时"这类规则清单 |
| `.mv-steps` | 纵向步骤条,`li data-n="P0a"` | 阶段路线、操作手册 |

## 图原语(画法详见 diagram-cookbook.md)

| 类 | 用途 |
| --- | --- |
| `figure.mv-diagram[data-diagram]` | 图容器;内有 `.mv-edge` 时由运行时画连线 |
| `.mv-diagram.flat` | 无边框无底的图(与卡片混排时用) |
| `.mv-diagram-cap` | 图注(figcaption) |
| `.mv-node[data-node="id"]` | 图节点;`.is-primary`(主强调)/`.is-external`(虚线边界外)/`.is-muted`(弱化);内文 `.mv-node-t` 标题 + `.mv-node-d` 详情 + `.mv-node-corner` 角标 |
| `.mv-region` | 语义边界(系统/所有权);`>.mv-region-label` 角标;`.is-external` 虚线、`.tone-accent` 主边界 |
| `.mv-lane` + `.mv-lane-title` | 泳道/层带 |
| `i.mv-edge` | 隐藏连线元数据:`data-from`/`data-to`(指向同图 `[data-node]`)、`data-label`、`data-kind`(calls/produces/dependsOn/observes/transitionsTo…)、可选 `data-route="h|v"` |
| `.mv-chain` + `.mv-chain-arrow` | 无 SVG 的短链(状态链、阶段链);节点多时加 `.no-grow` 防折行孤儿卡被拉满 |
| `.mv-chain.vertical` | 纵向链 |

## 联动行为(壳提供,无需实现)

- `[data-sources]` 元素:hover 预览、点击锁定 → 左栏对应 `[data-block]` 滚动高亮;反向亦然;Esc 解除。
- 顶栏三模式:原文 / 双栏 / 信息重组;中线可拖,双击复位。
- 连线在 resize、模式切换、字体就绪后自动重算。

## 设计 token(自定义样式时优先引用)

`--ink --ink-2 --muted --faint --line --line-2 --paper --viewbg --surface --accent --accent-strong --accent-soft --ok --warn --risk --violet`(+各自 `-soft`)、`--sans --serif --mono`、`--shadow-1/2`、`--ease`。

美学约束:一页一个主强调色;状态色只给真实语义(风险=红、证据=绿、警告= amber);先位置/容器/尺寸建立层级,颜色只做冗余增强;不用渐变大卡片、无意义 icon、装饰性阴影。
