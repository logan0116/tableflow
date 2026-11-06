<!--
Sync Impact Report
==================
- Version change: 5.0.0 → 6.0.0
- Bump rationale: MAJOR —— 重定义原则 I（人只读 → 人不能直接写、只能经 Agent 写、写操作必须落审计），
  并从非目标清单删除「公式与汇总引擎」、新增「计算字段边界」一节；属于删除非目标项与重定义原则。
- Modified principles:
  - I. 人只读、Agent 读写（NON-NEGOTIABLE）→ 重定义：人不能直接写业务数据，只能经 Agent 写；
    人发起的状态变更走 Agent 通道并标记 origin；写操作必须落审计，业务字段变更另有业务变更记录。
- Added sections:
  - 计算字段边界（v0.3.0 起允许）
- Removed sections: 无
- Modified non-goals:
  - 移除「公式与汇总引擎」
  - 新增「用户可编辑的公式与表达式引擎」「跨表任意聚合与任意 join」
- Templates/commands: .specify/templates 未变；spec / plan / tasks 命令在运行时读取本文件，无需同步修改。
- Follow-up TODOs: 无
-->

# TableFlow Constitution

## Core Principles

### I. 人只读、Agent 读写（NON-NEGOTIABLE）

- 角色分工固定：人不能直接写业务数据，只能经 Agent 写；Agent 对业务数据有读权限与写权限。该分工不随功能迭代改变。
- 权威数据由 tableflow 自己的 SQLite 持有。原平台 smart_table（192.168.1.155:8093）不再是本项目的运行期数据源；v0 不承担存量数据迁移。
- 数据模型：项目 → 表格 → 字段与数据行；同一项目内的表格之间可建立关联（relation 字段）。
- 本项目承载两类访问：人的读（看板与关联明细的只读查看）与 Agent 的读写。两类访问 MUST 由两套接口承担，不得混用。
- 人侧路由 MUST 只有 GET；人侧 MUST NOT 存在直接写业务数据的端点；前端 MUST NOT 直接持久化业务数据，MUST NOT 提供绕过 Agent 写接口的本地写控件。
- 人的状态变更 MUST 经 Agent 写接口执行：前端只发起变更请求（调用 Agent 写接口），请求 MUST 携带 Agent 标识、MUST 在写审计中标记发起来源（origin），MUST 返回三态。人发起不改变字段级校验与审计要求。
- Agent 写接口 MUST 具备三项：显式契约（字段级校验）、每次写入的审计留痕（谁、何时、改了什么）、三态语义（成功／失败／未知，未知不得当作成功）。缺任一项的写入 MUST NOT 上线。
- 写审计 MUST 记录操作者、发起来源、时间、动作、目标与结果；业务数据变更 MUST 另有字段级业务变更记录（表、行、字段、旧值、新值）。写审计与业务变更记录 MUST 同事务落库。
- 理由：人不能直接写，看板不会变成误操作入口；所有写入集中到 Agent 通道，变更可审计、可回放；「人发起、Agent 执行」保留人的表达意图，同时不放弃留痕。
- 判定：人侧路由清单只有 GET；写接口每一条都有对应审计记录；人发起的变更可在审计中按 origin 识别；字段级旧值/新值可在业务变更记录中查到；无审计的写入视为违规。

### II. 无读缓存（NON-NEGOTIABLE）

- 每次打开页面 MUST 现拉数据。MUST NOT 引入读缓存层：服务端缓存中间件、进程内业务数据缓存、CDN 缓存均不允许。
- 前端 MUST NOT 用 IndexedDB、localStorage、sessionStorage 持久化业务数据；纯 UI 偏好（主题、列宽等）不在此列，且 MUST NOT 与业务数据混存。
- SQLite 是本项目的唯一数据源，不是缓存，不受本条限制；但 MUST NOT 在其之上再叠一层缓存。
- 理由：看板的价值是"看到的就是当前状态"。缓存会把陈旧数据伪装成实时数据，失效策略本身也是新增故障面。
- 判定：前端源码检索不到对业务数据的持久化写入；后端无缓存装饰器或缓存中间件。

### III. Schema 驱动渲染（NON-NEGOTIABLE）

- 字段定义 MUST 存表，表名 fields，列固定为：id / table_id / name / type / options / order / visible。
- 前端 MUST 按 type 通用渲染；MUST NOT 为某个业务列写专用组件，MUST NOT 硬编码业务列名、列序或显示文案。
- 新增或删除一列 MUST 只改数据（增删 fields 记录并调整数据表列），MUST NOT 触发前端代码改动与重新发布。
- type 的取值集合 MUST 在数据层可枚举；新增 type 属功能变更，走 spec 流程。
- 理由：列是业务配置，不是代码。配置留在数据里，改列的成本才是"一条 SQL"。
- 判定：前端源码 grep 不到任何业务列名；删除一条 fields 记录后刷新页面，该列消失且无报错。

- 只读筛选（v0.3.1 起允许）：表格 MUST 支持在**已拉取的行**上按值过滤，筛选条件只存在前端内存与 URL/本地 UI 偏好中，MUST NOT 落库、MUST NOT 改变服务端返回的数据集。
- 筛选 MUST NOT 引入分组、聚合视图、看板/甘特/表单等其它视图形态；这些仍在非目标清单中。

### IV. DOM 表格与滚动性能

- 表格 MUST 由 DOM 节点渲染（table/tr/td 或等价的 div 网格）。
- MUST NOT 用 canvas 或 WebGL 自绘表格内容；MUST NOT 自行实现虚拟滚动；MUST NOT 引入重型表格库（AG Grid、Handsontable、DataTables 等）。
- 表格逻辑 MUST 只用 TanStack Table（headless，不自带渲染）。
- 理由：v0 的数据量是一屏能看完的十几行。canvas 与虚拟滚动换来的是自绘文本、选择、无障碍与调试成本。
- 判定：页面中无 canvas 承载表格；依赖清单不含被禁库；滚动基线见"性能与验收基线"。

### V. 固定技术栈与依赖治理

- 后端 MUST 为 FastAPI + SQLite，Python 3.11+，依赖 MUST 由 uv 管理且 uv.lock 入库。
- SQLite MUST 以 WAL 模式运行（PRAGMA journal_mode=wal）。
- 前端 MUST 为 React + Vite + TypeScript。
- MUST NOT 引入 Electron 或任何桌面壳；MUST NOT 引入额外存储或缓存组件（如 Redis、Memcached）。
- 理由：v0 的复杂度预算只够一条直路；每多一个运行组件，部署与排障成本翻倍。
- 判定：pyproject.toml、uv.lock、package.json 可核对；连接后 PRAGMA journal_mode 返回 wal。

### VI. 中文单语界面

- 界面文案 MUST 全部为中文。
- MUST NOT 引入 i18n 框架或多语言资源目录；MUST NOT 在代码中保留待翻译的占位文案。
- 理由：v0 只有中文用户，多语言是零收益的复杂度。
- 判定：前端依赖无 i18n 库；无 locales 资源目录。

### VII. 边界收敛（NON-NEGOTIABLE）

- 「项目定位与非目标（v0）」中的非目标清单是硬边界。启用其中任一项，MUST 先修订本宪法（版本至少 MINOR），并在 plan 中说明理由与迁移路径；未修订即实现，视为违规，不得合入。
- 超出 spec 已列明范围的新能力，同样 MUST 先经宪法或 spec 变更；MUST NOT 以"顺手加一点"的方式实现。
- 被禁能力 MUST NOT 以占位实现、死代码、隐藏开关、配置项或 TODO 的形式提前存在于代码库中。
- 非目标清单在 v0 内只允许保持不变；清单要变，改宪法。对清单的解释性扩张同样按变更处理。
- 理由：边界靠闸门维持，不靠自律维持。v0 的成败取决于没做什么。
- 判定：代码库中不存在对应被禁能力的依赖、路由、组件或配置项；每次 spec 与 plan 变更可对照非目标清单逐条核对。

## 项目定位与非目标（v0）

定位：替代在 smart_table 上"看一眼状态"的做法，做一块多维表格看板：一个项目下有多张表格，表格之间可建立关联，字段与数据由 Agent 通过写接口定义与写入，人只读。原平台不删，但不再是数据源，v0 不做存量数据迁移。分工等式：人不能直接写、只能经 Agent 写（见原则 I）。v0.3.0 起允许声明式计算字段（边界见下节）。

v0 的非目标（MUST NOT 实现，出现即视为范围蔓延；变更闸门见原则 VII）：

- 多用户协作编辑
- 用户可编辑的公式与表达式引擎
- 跨表任意聚合与任意 join（计算字段只允许经 relation 挂载点、固定类型的声明式聚合，见下节）
- 视图体系：分组、看板、甘特、表单（**筛选已放行**，见原则 III 补充条）
- 字段级与行级权限
- 附件与富文本
- Electron 或任何桌面壳
- 移动端适配
- 历史数据迁移与同步（从原平台导入存量数据、维持两边一致）

### 计算字段边界（v0.3.0 起允许）

- 计算字段（写侧计算、结果落库、读侧只读）不再属于非目标；其允许范围与禁止项以本节为准。
- 允许的计算类型固定为五种：`count`、`percent`、`sum`、`rollup`、`and`。该集合 MUST 在数据层可枚举；新增第六种类型 MUST 先修订本宪法（MINOR）并走 spec 流程。
- 计算 MUST 在写侧完成：Agent 写接口在写入事务内计算并落库结果；读侧 MUST 只读取落库结果，MUST NOT 做任何业务计算或再聚合。
- 计算依赖 MUST 只来自同一项目内、由本表 relation 字段声明的目标行；依赖图 MUST 无环；计算字段 MUST NOT 引用外部数据源、任意 SQL 或脚本。
- `count` / `percent` / `sum` / `rollup` 的筛选与取值 MUST 只引用目标表的非计算字段；只有 `and` 可以引用同表的计算字段，因此依赖最多两层（目标表存储字段 → 本表计算字段 → 本表 `and`）。
- 计算字段 MUST NOT 接受 Agent 直接写入的值。唯一例外是显式覆盖（override）：覆盖 MUST 带原因、操作者与时间，MUST 落审计，且 MUST 可清除；清除后 MUST 立即重算。
- 计算失败 MUST 使该次写入失败并回滚，MUST NOT 落库部分结果，MUST NOT 以 0 或空值掩盖失败。
- 仍属非目标：用户可编辑表达式、跨表任意聚合、视图级计算、读侧计算。
- 判定：计算类型清单可枚举；读接口返回的值与落库值一致；直接写计算字段被拒绝；构造依赖环被拒绝；注入计算失败时该次写入整体回滚。

## 性能与验收基线

- 首屏：14行数据 MUST 在 500ms 内渲染完成。口径：浏览器禁用缓存、局域网访问、从导航开始到第14行可见，取5次中位数。
- 滚动：在关闭硬件加速的浏览器（Chrome --disable-gpu）下连续滚动5秒，平均帧率 MUST ≥50fps，且 MUST NOT 出现超过50ms的长任务。口径：DevTools Performance 录制。
- 上述两项为发布门槛：任一不达标，该版本不得视为可交付。

## Governance

- 本宪法优先于其他实践、文档与个人习惯。spec、plan、tasks 的产物 MUST 与本宪法一致；冲突时以本宪法为准。
- 修订程序：提出修订 → 说明动机与影响面 → 更新本文件并递增版本 → 在 plan 中记录迁移影响。修订未落地前，被禁止的能力 MUST NOT 实现。
- 范围变更闸门见原则 VII：非目标清单与 spec 边界之外的能力，一律先改宪法再实现。
- 版本策略（语义化）：
  - MAJOR：删除或重定义原则、删除非目标项
  - MINOR：新增原则、新增约束或新增非目标项
  - PATCH：措辞澄清、错字、不改变语义的调整
- 合规审查：每次 /speckit-plan 与 /speckit-implement 之前 MUST 逐条核对本宪法；无法满足的条目 MUST 显式记录为偏差并说明理由，未记录的偏差不得合入。
- 运行期指导：项目根目录 AGENTS.md 承载具体操作约定，但不得与本宪法冲突。

**Version**: 7.0.0 | **Ratified**: 2026-11-06 | **Last Amended**: 2026-11-06
