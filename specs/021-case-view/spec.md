# Feature Specification: 测试用例视图与执行清单弹窗（v0.7.0）

**Feature Branch**: `021-case-view`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 021-AR。board@4 把测试域落成两张表：`case`（测试用例，`kind=board`）与 `run`（用例执行情况，`kind=detail`），版本行用 `ver.runs` 持有一条执行清单。当前前端对所有表一视同仁：`frontend/src/App.tsx` 直接把 `/api/projects/{id}/tables` 的返回灌进 `TableTabs`，`frontend/src/types.ts` 的 `TableSummary` 只有 `id/name/order`，没有表级 kind。结果会是执行记录表混进表导航，而"本版跑了哪些用例、跑没跑"仍要靠猜。本规格给测试用例表一个可切换的只读视图，并把执行清单挂到版本行的「测试用例」字段上。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 导航没有表级 kind | `frontend/src/types.ts` 的 `TableSummary` 只有 `id/name/order`；`frontend/src/App.tsx` 直接把表格接口返回灌进 `TableTabs` | `run` 表会以第六个页签出现，执行记录与用例资产混在一起 |
| 表级可见性已在契约定义但读侧未消费 | `specs/019-test-contract/board@4.yaml` 的 `conventions.table_kind`：`run=detail` 不进导航，其余五表 `board` | 前端不读该标记，契约落不了地 |
| 执行清单靠临时拼 | 019 `conventions.display_of_run`：第一列 run 行 id、第二列 `display_field=run.case_no`、第三列 `status_field=run.state`；复用关系弹层 | 没有配置或没消费配置时，弹层只剩编号列，看不出用例号与是否执行 |
| 进度与结论混在一起 | 019 `rules.case_progress_only`：版本表只消费 `run.state`，通过与否留在 `run.result` | 弹层必须能点进执行明细看结果，不能把 `result` 塞进第三列 |

## Clarifications

### Session 2026-11-22

- Q: 测试用例表进导航吗？ → A: 进。`case` 是 `kind=board`，用通用只读表格视图展示，不写专用页面。
- Q: 用例执行情况表怎么挡在导航外？ → A: 读服务端返回的表级 `kind`，只渲染 `kind != detail` 的表；**不按表名或表 id 猜**。
- Q: 旧接口没有 `kind` 怎么办？ → A: 按 `board` 兼容，导航行为与 board@3 时期一致；宁可比契约多显示，不可静默吞表。
- Q: 执行清单为什么复用 `RelationListModal`？ → A: 版本行的「测试用例」本身就是 relation。三列口径（编号 + `display_field` + `status_field`）006 已实现，021 不新造弹窗组件、不改列头推导规则。
- Q: 通过率进版本表吗？ → A: 不进。版本表只回答"跑没跑"（`run.state`）；"通过与否"点进执行明细看 `run.result`，不进入版本闸门（019 `case_progress_only`）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 表导航按 kind 展示测试用例表、隐藏执行记录表 (Priority: P1)

打开一个 board@4 项目，表导航出现「测试用例」，不出现「用例执行情况」；点「测试用例」能按字段查看用例行。

**Why this priority**: 导航是用户找到用例表的唯一入口；执行记录表混进导航会让"用例资产"和"某版本跑的结果"看起来是同一层东西。

**Independent Test**: 用一个六表项目打开看板，数页签；点「测试用例」，核对列与行。

**Acceptance Scenarios**:

1. **Given** 项目返回六张表且带 `kind`（ver/indep/dep/case/bug 为 `board`，run 为 `detail`），**When** 打开看板，**Then** 表导航有五个页签：版本管理、独立规格需求、依赖需求、测试用例、缺陷；**没有**「用例执行情况」。
2. **Given** 上述项目，**When** 点「测试用例」页签，**Then** 当前表切到 `case`，列头来自它自己的字段（用例号、用例名、来源规格、前置条件、操作步骤、预期结果、优先级、负责人），行数与接口返回一致。
3. **Given** board@3 项目的接口不返回 `kind`，**When** 打开看板，**Then** 所有返回的表仍显示在导航里（按 board 兼容），行为与升级前一致。
4. **Given** 一个项目只有 `detail` 表，**When** 打开看板，**Then** 显示「暂无表格」，不显示空白页签或报错。
5. **Given** 当前选中的表被切换到另一项目后不再存在，**When** 项目加载完成，**Then** 默认选中该项目的第一张 `board` 表；不得默认落到 `detail` 表。

### User Story 2 - 版本行「测试用例」打出三列执行清单并点进明细 (Priority: P1)

在版本管理表点某行的「测试用例」，弹层按执行清单显示三列：执行编号、用例号、执行状态（`run.state`）；点一行进入执行明细，能看到通过与否（`run.result`）。

**Why this priority**: 这是"本版纳入哪些用例、跑了没有"的唯一可操作入口，也是测试节点能否推进的肉眼依据。

**Independent Test**: 版本行 `runs` 含两条执行记录（一条 `todo`、一条 `done` 且 `result=pass`），点开弹层核对三列与明细。

**Acceptance Scenarios**:

1. **Given** 版本行的「测试用例」值为 `["v0.7.0--008-US1-AS1","v0.7.0--008-US1-AS2"]`，**When** 点击该格，**Then** 弹出关联条目弹层，标题为「关联条目 · 2 项」，恰好三列：编号、用例号、执行状态。
2. **Given** 上述弹层，**When** 读取每行，**Then** 第一列是 run 行 id（如 `v0.7.0--008-US1-AS1`），第二列是 `run.case_no` 的文本（如 `008-US1-AS1`），第三列是 `run.state` 的枚举标签（`todo=待执行` / `done=已执行`，取数据里的枚举标签）。
3. **Given** 弹层中某条记录 `state=todo`，**When** 查看第三列，**Then** 显示未执行标签；列表里不出现 `run.result`（通过与否不占第三列）。
4. **Given** 弹层中某条记录 `state=done` 且 `result=pass`，**When** 点击该行，**Then** 打开执行明细弹层，显示该 run 行的全部可见字段，其中「执行结果」可读为通过；`fail/blocked/skip` 同样在明细里读。
5. **Given** 版本行的 `runs` 为空数组，**When** 点击「测试用例」，**Then** 显示「关联条目 · 0 项」与空态「暂无关联条目」，不报错、不出现持续加载。
6. **Given** `ver.runs` 的配置指向的某个 run 行已被删除，**When** 打开弹层，**Then** 该行标为「关联已失效」且不可点击，其余行正常。
7. **Given** `ver.runs` 未配置 `display_field` / `status_field`，**When** 打开弹层，**Then** 回退为只显示编号列，不按列名猜测补列。

### User Story 3 - 不破坏既有关系弹层与表格结构 (Priority: P2)

版本行的独立需求、依赖需求、缺陷弹层仍按各自配置显示；表格结构色与列宽等既有行为不变。

**Why this priority**: 021 只复用弹层，任何"顺手改弹层"都可能把 006 的配置驱动规则改回硬编码。

**Independent Test**: 逐个打开版本行四个 relation 字段，核对列头与标签；对比改动前后表格结构色。

**Acceptance Scenarios**:

1. **Given** 版本行的「独立需求管理」「依赖需求管理」「Bug管理」，**When** 分别打开，**Then** 列头与状态列与 006/017 一致，不因 021 改变。
2. **Given** 前端源码，**When** 搜索表导航的隐藏逻辑，**Then** 只读 `kind`，不存在按「用例执行情况」「run」等表名/表 id 的硬编码判断。
3. **Given** 改动前后的表格样式文件，**When** 对比，**Then** 未修改表格结构色（表头、边框、行底色、标签色）。

## Requirements *(mandatory)*

- **FR-001**: 读接口 `GET /api/projects/{id}/tables` 的每张表摘要 MUST 提供表级 `kind`（`board` | `detail`），取值遵循 board@4 `conventions.table_kind`；前端 `TableSummary` MUST 消费该字段（依赖 019/020 的读侧实现）。
- **FR-002**: 表导航 MUST 只渲染 `kind != detail` 的表；`kind` 缺失或未知 MUST 按 `board` 保留，MUST NOT 用表名、表 id 或字段特征猜测可见性。
- **FR-003**: 测试用例表 MUST 作为一个普通 `board` 表出现在导航中，并 MUST 由现有 `DataTable` 按字段元数据渲染；MUST NOT 为它写死列名或专用样式。
- **FR-004**: 项目切换或刷新后，当前选中表 MUST 落在 `board` 表上；默认取接口顺序中的第一张 `board` 表；没有 `board` 表时 MUST 显示「暂无表格」。
- **FR-005**: 版本行「测试用例」relation MUST 复用现有 `RelationListModal`，MUST NOT 新增弹窗组件；列 MUST 由关系字段自身配置推导：第一列 run 行 id，第二列 `options.display_field`，第三列 `options.status_field`。
- **FR-006**: 弹层的第二、三列列头 MUST 使用被配置目标字段的 `name`（如「用例号」「执行状态」），MUST NOT 在组件内出现业务列名字面量。
- **FR-007**: 点击执行记录行 MUST 复用现有明细弹层读取该 run 行，展示全部可见字段，使用户能读到 `run.result`；列表第三列 MUST NOT 展示 `run.result`。
- **FR-008**: 空清单 MUST 显示「0 项」与空态，MUST NOT 因空清单持续 loading 或读取目标表；悬空行 MUST 标为「关联已失效」且不可点击；配置字段缺失 MUST 回退到只显示编号列。三条回退行为沿用 006。
- **FR-009**: 本规格 MUST NOT 引入新依赖、MUST NOT 改变人侧只读边界（前端只 GET）、MUST NOT 修改表格结构色、行高、列宽记忆与密度行为。
- **FR-010**: `cd frontend && npm run build` MUST 通过（含 `tsc --noEmit`）；验收 MUST 以截图证明导航不含执行记录表、弹层为三列。

## Non-Goals

- 顶部通栏角色切换与角色配色（022）。
- 版本表六节点四态与串行/闸门校验（025）。
- 执行记录的建行、状态/结果写入与两步写协议（020）；重复纳入同一用例的 400 与"重跑就地更新"由 020 处理，021 不放任何写入按钮。
- 从 spec 场景派生用例、幂等同步（019 的数据层与 tf-test-plan）。
- MeterSphere 历史执行数据迁移。
- 通过率、失败数等质量指标进入版本表或发布条件。
- 专用测试用例页面（步骤编辑器、批量执行、筛选器）；021 只提供只读表格视图。

## Success Criteria

- 六表项目的表导航只有五个 `board` 页签，不含「用例执行情况」；board@3 旧接口的项目导航不减少表。
- 「测试用例」页签能显示用例行与字段列，切换后表格数据来自 `/api/tables/{case表id}/table`。
- 版本行「测试用例」弹层稳定为三列（编号 / 用例号 / 执行状态），`todo` 与 `done` 标签可区分；点行能读到 `run.result`。
- `cd frontend && npm run build` 退出码 0。
- 截图证据：导航页签、三列弹层、执行明细各一张，路径见下方「验收证据」。

## 验收证据

**日期**: 2026-11-22
**环境**: 本地 uvicorn（127.0.0.1:8099）+ `frontend/dist`（本次 `npm run build` 产物）+ 六表夹具库（`TABLEFLOW_DB=.tmp-shots/021-case-view/fixture/tf021.db`）；backend 为当前仓库原样代码（T1 的 `tables.kind` 读侧已落地，非 mock）；浏览器视口 1280×800。

### 命令

| 命令 | 结果 |
|---|---|
| `cd frontend && npm run build` | 退出码 0；`tsc --noEmit` 零错误，vite 产物 `dist/assets/index-DioiLV3I.js` / `index-D4GFT2VE.css` |
| `curl -s http://127.0.0.1:8099/api/projects/tf/tables` | 六张表：`tf-ver`/`tf-indep`/`tf-dep`/`tf-case`/`tf-bug` 为 `"kind":"board"`，`tf-run` 为 `"kind":"detail"` |
| `curl -s http://127.0.0.1:8099/api/tables/tf-run/rows/v0.7.0--021-US1-AS1` | 200；`run` 表不进导航但仍可读单行（弹窗明细走这条路径） |

### 截图

| 截图 | 证明 |
|---|---|
| `.tmp-shots/021-case-view/nav.png` | 表导航只有 5 个 board 页签（版本管理、独立规格需求、依赖需求、测试用例、缺陷），**无「用例执行情况」**；版本行有「测试用例」入口 |
| `.tmp-shots/021-case-view/run-modal.png` | 版本行「测试用例」弹层为三列：编号（执行编号）/ 用例号 / 执行状态；`已执行`/`待执行` 标签可区分，列表不显示通过与否 |
| `.tmp-shots/021-case-view/run-detail.png` | 点执行记录行进入明细：执行结果=通过，含证据、执行时间、执行人、备注 |
| `.tmp-shots/021-case-view/case-view.png` | 点「测试用例」页签切到 case 表，按字段显示 4 条用例行；导航仍无执行记录表 |

### D-02 修复证据（空关联可点）

D-02 复验使用当前 build 产物 `dist/assets/index-BiOAlHox.js`；夹具中 `v0.6.5` 的 `runs` 为空、`v0.7.0` 有 3 条执行记录。

| 截图 | 证明 |
|---|---|
| `.tmp-shots/021-case-view/d02-empty-cell.png` | `v0.6.5` 的「测试用例」空值单元格显示可点击的「0 项」（不再是空白） |
| `.tmp-shots/021-case-view/d02-empty-modal.png` | 点击后弹层标题「关联条目 · 0 项」并显示空态「暂无关联条目」，不报错、不持续 loading |
| `.tmp-shots/021-case-view/d02-nonempty-modal.png` | 非空单元格回归：`v0.7.0` 仍是三列（编号 / 用例号 / 执行状态）原样弹层 |

### 复现方式

```bash
cd frontend && npm run build
cd .. && backend/.venv/bin/python .tmp-shots/021-case-view/fixture/seed.py
TABLEFLOW_DB=$PWD/.tmp-shots/021-case-view/fixture/tf021.db \
TABLEFLOW_STATIC_DIR=$PWD/frontend/dist \
backend/.venv/bin/python .tmp-shots/021-case-view/fixture/serve_real.py
# 打开 http://127.0.0.1:8099/
```

> 夹具脚本与夹具库是一次性验收产物，放在未入库的 `.tmp-shots/021-case-view/fixture/`；正式验收应在 T1 迁移出六表的真实项目上复跑同一组检查。夹具只用于把六表合同、`ver.runs` 配置与执行记录数据摆到界面上；`kind` 字段与读接口来自 backend 实现，前端没有为夹具写任何分支。

## Assumptions

- 读接口按 FR-001 返回 `kind`；这是 019 六表落地的读侧一部分，前端不自行推导。
- `ver.runs` 的 `display_field=run.case_no`、`status_field=run.state` 由数据迁移/模板配置，前端只消费。
- `run.state` 的枚举标签由字段 `options.items` 提供（`todo=待执行`、`done=已执行`）；标签缺失时回退显示原始值。
- `run` 表虽不进导航，`/api/tables/{id}/table` 与 `/api/tables/{id}/rows/{row_id}` 仍可读，供关系弹层使用（019 US1-AS3）。
