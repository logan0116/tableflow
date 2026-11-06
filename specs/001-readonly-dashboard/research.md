# Phase 0：研究与决策

**Feature**: 001-readonly-dashboard | **Date**: 2026-11-06 | **Constitution**: v3.0.0

Technical Context 中不存在未决的 `NEEDS CLARIFICATION`；以下 8 项决策覆盖了计划中所有需要选型的位置。D1 由用户直接决定，D3 按用户 2026-11-06 的降级要求调整，其余由实现者按宪法约束选取。

## D1 数据归属：tableflow 自有 SQLite 为权威数据

- **Decision**: tableflow 自己的 SQLite 是权威数据。v0 不做存量数据迁移，数据以最小样例初始化，运行期不再读取原平台。
- **Rationale**: 用户 2026-11-06 明确选择。它让 v0 不依赖原平台的接口形态与鉴权，也把 v1 的 Agent 写接口收拢到同一份数据上（宪法原则 I）。
- **Alternatives considered**:
  - 只读打开同一份 SQLite 文件：需要与原平台同机部署并共享库文件，部署约束与表结构所有权都不清楚，且原平台未必是 SQLite。
  - 调原平台 HTTP 接口现拉：需要只读账号与接口文档；原平台是 Vue SPA，接口形态未确认，会把 v0 的可用性绑在别人的服务上。
  - 本地快照缓存：与宪法原则 II「无读缓存」直接冲突，否决。

## D2 行值存储：`row_records.data` 存 JSON

- **Decision**: 每个项目的数据行存于 `row_records`，`data` 列是 JSON 对象，键为字段 id、值为该行在该列的值。
- **Rationale**: 增删一列只改 `fields` 表与 JSON 内容，不需要 `ALTER TABLE`；500行×20列的规模下整表读取一次即可，SQLite 的 JSON 解析开销可忽略。满足宪法原则 III「只改数据」。
- **Alternatives considered**:
  - EAV（`row_values(row_id, field_id, value)`）：列变更同样只改数据，但 500行×20列会产生 1万行中间表，查询需要聚合，代码更绕。
  - 每个项目动态建物理表：列变更要 `ALTER TABLE`，迁移与并发风险高，且"表名来自数据"会引入注入面。

## D3 数据来源：v0 不迁移，最小样例初始化

- **Decision**: v0 不承担存量数据迁移。只提供一个最小样例脚本，把 `data/seed.example.json` 写入 SQLite，用于演示与验收；原平台不再是数据来源。
- **Rationale**: 用户 2026-11-06 明确要求降低迁移的优先级——平台建好后可以重新写入，迁移不是 v0 的前置条件。去掉迁移依赖后，v0 不需要原平台的导出格式、字段映射与清洗规则。
- **Alternatives considered**:
  - 保留从原平台一次性导入：要先确定导出格式与字段映射，属额外工作量，且不迁移也不影响 v0 验收。
  - 手工 SQL 造数：不可复现，验收样本不稳定，弃。
- **后续**: 历史数据迁移与同步已列入宪法非目标；需要时按原则 VII 先改宪法，再做映射与清洗。

## D4 只读打开方式：`mode=ro` + `PRAGMA query_only`

- **Decision**: 后端以只读方式打开 SQLite（URI `file:...?mode=ro`），连接后执行 `PRAGMA query_only=ON`；样例脚本单独以读写方式打开。
- **Rationale**: 宪法原则 I 要求 v0 不存在运行期写路径；只读打开把这条约束落到数据库层，而不是靠代码自觉。
- **Alternatives considered**: 读写连接 + 代码里不写——约束靠自觉，不满足「可判定」。
- **风险**: WAL 模式下只读连接需要能访问 `-wal`/`-shm` 文件；样例写入完成后再启动服务即可避免该问题。

## D5 表格渲染：原生 `<table>` + TanStack Table（headless）

- **Decision**: 用 TanStack Table 的 `getCoreRowModel` 生成行模型，渲染层用原生 `<table>/<thead>/<tbody>/<tr>/<td>`，表头 `position: sticky`。
- **Rationale**: 宪法原则 IV 要求 DOM 渲染且只用 TanStack Table；v0 不做排序/筛选/分页，核心行模型足够。
- **Alternatives considered**: 手写行映射（少一个依赖，但列定义与单元格渲染要自己组织，后续加排序会重写）；AG Grid 等重型库（宪法明令禁止）。

## D6 性能验证：手工 DevTools 口径 + 固定脚本步骤

- **Decision**: v0 不引入自动化性能框架。quickstart 给出可复现的测量步骤（禁缓存、LAN、DevTools Performance 录制），由执行者按步骤记录 5 次中位数。
- **Rationale**: 两个指标都是一次性验收门槛，不是回归套件；引入 Playwright 等工具会给 v0 增加一个重型依赖，与「复杂度预算」不符。
- **Alternatives considered**: Playwright + CDP 自动采集帧率——重复性好，但依赖体积与维护成本超出 v0 需要。

## D7 三态展示：加载 / 错误 / 空

- **Decision**: 页面固定三态：加载中（骨架或文字提示）、错误（中文提示 + 重试按钮，不显示旧数据）、空（保留列头的"暂无数据"）。数据态才渲染表格。
- **Rationale**: 对应 spec 的 FR-008、FR-009 与边界情形；错误态必须清空数据，否则会违反「不显示旧数据」。

## D8 字段类型集合：text / number / datetime / enum

- **Decision**: v0 支持四种 `type`：`text`（原样）、`number`（按原值显示）、`datetime`（按浏览器本地时区显示）、`enum`（显示 options 中的 label，v0 不渲染颜色）。其余类型按 `text` 渲染。
- **Rationale**: 覆盖 spec Assumptions 中的四种类型；未识别类型回退纯文本对应 FR-005，保证新增类型不会让页面崩。
- **Alternatives considered**: 只做 text——验收样本里会有日期与状态列，体验不足；做插件式类型注册表——v0 用不上，属于提前抽象。
