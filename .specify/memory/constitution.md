# TableFlow Constitution

## Core Principles

### I. 人只读、Agent 读写（NON-NEGOTIABLE）

- 角色分工固定：人对业务数据只有读权限；Agent 对业务数据有读权限与写权限。该分工不随功能迭代改变。
- 本项目 MUST 只服务人的读路径。MUST NOT 提供任何写入、修改、删除业务数据的端点或前端控件。
- Agent 的写路径 MUST 落在原平台 smart_table（192.168.1.155:8093）。本项目与其读同一份结构化数据，MUST NOT 另建可写副本。
- 本项目 v0 MUST NOT 引入写接口。若后续要让 Agent 经本项目写入，MUST 先修订本宪法（版本至少 MINOR），并在 spec 中定义写侧契约、审计留痕与失败语义。
- 理由：人只读，看板不会变成误操作入口；Agent 读写，变更集中一处、可审计、可回放。两侧边界清晰，故障与责任才好切分。
- 判定：路由清单中不存在 POST/PUT/PATCH/DELETE；前端不存在提交类路径；业务数据变更只出现在原平台。

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

定位：替代在 smart_table 上"看一眼状态"的做法，做一块只读看板。原平台不删，继续作为数据源与写入口；本项目读同一份结构化数据。分工等式：人只读、Agent 读写（见原则 I）。看板支持多项目管理。

v0 的非目标（MUST NOT 实现，出现即视为范围蔓延；变更闸门见原则 VII）：

- 多用户协作编辑
- 公式与汇总引擎
- 视图体系：筛选、分组、看板、甘特、表单
- 字段级与行级权限
- 附件与富文本
- Electron 或任何桌面壳
- 移动端适配

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

**Version**: 2.0.0 | **Ratified**: 2026-11-06 | **Last Amended**: 2026-11-06
