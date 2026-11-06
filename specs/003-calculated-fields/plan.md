# Implementation Plan: 计算字段与发布判定（v0.3.0）

**Branch**: `003-calculated-fields` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-calculated-fields/spec.md`

## Summary

新增 `type=computed` 字段与五种计算类型（count / percent / sum / rollup / and）。计算发生在写事务内：数据变更后按依赖拓扑重算受影响字段，结果写入 `computed_values`；读接口只合并落库值，覆盖值优先，读侧零计算。版本表用这套机制表达开发进度、回归通过、Bug已清空与发布条件；人经 Agent 写接口发起状态变更，审计标记 `origin=human-request`。

## Technical Context

**Language/Version**: Python 3.11+（后端）；TypeScript 5.x + Node 24（前端）

**Primary Dependencies**: 不新增依赖；沿用 FastAPI、uvicorn、pytest、httpx、React 18、Vite、TypeScript、@tanstack/react-table

**Storage**: SQLite（WAL）；新增 `computed_values` 表；`fields.type` 增加 `computed`；复用 002 的 `business_changes` 与 `write_audit.origin`

**Testing**: pytest + httpx；新增 `backend/tests/test_calculation.py`，扩展 `test_field_system.py` / `test_agent_api.py` / `test_api.py` / `test_seed.py`；前端不引入测试框架

**Target Platform**: Linux（本机或局域网服务器），Chrome / Edge 桌面浏览器

**Project Type**: web application（backend + frontend）

**Performance Goals**: 单次写入 + 重算在单表 500 行规模下 ≤200ms（本机）；14 行首屏 ≤500ms、滚动 ≥50fps 基线不回退

**Constraints**: 读侧零计算；五种 kind 封闭集合；依赖无环；失败整体回滚；人侧仍只有 GET；不新增依赖

**Scale/Scope**: ≤20 项目、每项目 ≤10 表、单表 ≤500 行；新增 1 张表、1 个重算接口、1 个覆盖参数、1 个前端变更入口；模板新增 6 个计算/数字字段、改造 2 个

## Constitution Check

*GATE: 对照宪法 v6.0.0 逐条核验，重点检查「计算字段边界」。*

| 原则 / 边界 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 人侧仍只有 GET；状态变更经 Agent 写接口，`X-Origin: human-request` 落审计与业务变更记录 | PASS |
| II 无读缓存 | 计算值落 SQLite（数据源，不是缓存）；读接口每次现查；前端不持久化业务数据 | PASS |
| III Schema 驱动 | 新增 `type=computed`；五种 kind 在 `options.kind` 可枚举；前端按 kind 通用渲染 | PASS |
| IV DOM 表格 | 计算值仍是普通单元格；不引入 canvas/虚拟滚动 | PASS |
| V 固定技术栈 | 不新增依赖；SQLite WAL 不变 | PASS |
| VI 中文单语 | 布尔显示「是/否」、空值显示「—」，全部中文 | PASS |
| VII 边界收敛 | 只实现五种固定 kind；不做用户表达式、跨表任意聚合、视图级计算、读侧计算 | PASS |
| 计算字段边界 | 写侧计算并落库；依赖只来自 relation 目标行；依赖无环；失败回滚；覆盖带原因且可清除 | PASS |

无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/003-calculated-fields/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── src/tableflow/
│   ├── calculation.py       # 新增：配置校验、依赖图、五种 kind 计算、重算入口
│   ├── db.py                # 新增 computed_values 表与索引
│   ├── repository.py        # 读侧合并 computed_values 与 computed_meta
│   ├── write_service.py     # 写事务内调用重算；拒绝直接写计算字段；override 处理
│   ├── schemas.py           # ComputedMetaOut、重算响应
│   └── app.py               # 重算接口；行 PATCH 接受 overrides；X-Origin 解析
├── scripts/seed_data.py     # 样例校验：computed 配置与落库值
└── tests/
    ├── test_calculation.py      # 新增：五种 kind、空值、失败回滚、环检测
    ├── test_field_system.py     # 扩展：computed options 校验
    ├── test_agent_api.py        # 扩展：重算、override、origin、直接写拒绝
    ├── test_api.py              # 扩展：computed_meta、读侧零计算
    └── test_seed.py             # 扩展：模板计算字段配置可加载

frontend/
└── src/
    ├── types.ts                 # ComputedOptions、ComputedMeta、BusinessChange
    ├── api.ts                   # submitHumanChange、fetchTable 透传 computed_meta
    ├── components/
    │   ├── Cell.tsx             # computed 值渲染（number/boolean）、覆盖标记
    │   ├── ChangeDialog.tsx     # 新增：人经 Agent 改状态（选值 + 原因）
    │   ├── DataTable.tsx        # 计算列只读、点击 enum 触发变更入口
    │   └── RelationModal.tsx    # 行明细展示计算值与条件当前值
    └── styles.css               # 覆盖标记、条件列表、布尔标签

data/
├── template_fd_system.py  # v-dev/v-cond 改 computed；新增 v-bug-open/v-bug-clear/v-regress/v-dep-count/v-scenes/v-tasks
├── load_fd_system.py      # 移除 v-bug/v-dev/v-cond 的手写值；按新字段重灌
├── load_tableflow.py      # 同上
└── load_specs.py          # v0.3.0 行按新字段写入
```

**Structure Decision**: 计算逻辑独立成 `calculation.py`，避免 `write_service.py` 继续膨胀；`write_service` 只负责在事务内调用 `calculation.recompute_for_write` 与处理 override，读侧 `repository` 只做合并。

## Data Model Changes

### 1. `computed_values`（新增）

```sql
CREATE TABLE computed_values (
  table_id        TEXT NOT NULL,
  row_id          TEXT NOT NULL,
  field_id        TEXT NOT NULL,
  value           TEXT,
  computed_at     TEXT NOT NULL,
  override_value  TEXT,
  override_reason TEXT,
  override_by     TEXT,
  override_at     TEXT,
  PRIMARY KEY (table_id, row_id, field_id)
);
CREATE INDEX idx_computed_values_field ON computed_values (field_id);
```

- `value` / `override_value`：JSON 编码；`NULL` 表示无法计算（如 percent 分母为 0）。
- 有效值 = `override_value` 非空时取覆盖值，否则取 `value`。
- 清理：删除行、字段、表时同步删除对应 `computed_values`。
- 不建外键：由写服务保证一致性，避免 SQLite 级联与复合主键的额外复杂度。

### 2. `fields.type = computed` 与 `options.kind`

```json
// count：依赖需求数
{"kind": "count", "source": "v-dep"}

// percent：开发进度
{"kind": "percent", "source": "v-indep",
 "where": {"field_id": "i-implement", "equals": "done"}, "decimals": 1}

// sum：任务总数
{"kind": "sum", "source": "v-indep", "field_id": "i-tasks", "decimals": 0}

// rollup：回归通过
{"kind": "rollup", "source": "v-dep", "field_id": "d-regress",
 "aggregate": "all", "equals": "passed"}

// and：Bug已清空 / 发布条件
{"kind": "and", "conditions": [{"field_id": "v-bug-open", "equals": 0}],
 "true_label": "是", "false_label": "否", "allow_override": true}
```

规则：

- `source` MUST 是本表 `type=relation` 的字段 id。
- `where.field_id` / `field_id` MUST 是目标表的非计算字段；`sum` 要求 number；`rollup min/max` 要求 number/datetime。
- `and.conditions[].field_id` MUST 是同表字段，可以是计算字段；`equals` 不允许 `null`。
- `true_label` / `false_label` 可选，缺省「是 / 否」。
- `allow_override` 可选，缺省 `false`；只有为 `true` 的计算字段接受覆盖。
- 配置校验在字段创建/更新时执行，同时完成引用检查与环检测。

### 3. 依赖图与重算顺序

- 节点：同一张表内的计算字段。
- 边：`and` 字段的条件引用同表计算字段时，被引用字段 → 引用字段。
- 跨表依赖只到「目标表的非计算字段」，不构成计算节点之间的边。
- 创建/更新计算字段时用 DFS 检测环；成环即 `failed`。
- 同表重算按拓扑序执行；跨表依赖只到目标表的存储字段，因此不存在跨表计算链。

### 4. 模板字段（版本管理）

| 字段 id | 名称 | type | 配置 |
|---|---|---|---|
| `v-bug-open` | 未清Bug数 | number | `{"decimals":0,"constraints":{"min":0}}` |
| `v-bug-clear` | Bug已清空 | computed | `and([{v-bug-open,0}])`，`allow_override=true` |
| `v-regress` | 回归通过 | computed | `rollup(v-dep,d-regress,all,passed)` |
| `v-dev` | 开发进度 | computed | `percent(v-indep,i-implement=done,decimals=1)` |
| `v-cond` | 发布条件 | computed | `and([v-dev=100,v-regress=true,v-bug-clear=true,v-doc=done])` |
| `v-dep-count` | 依赖需求数 | computed | `count(v-dep)` |
| `v-scenes` | 场景总数 | computed | `sum(v-indep,i-scenes)` |
| `v-tasks` | 任务总数 | computed | `sum(v-indep,i-tasks)` |

旧 `v-bug`（text）删除；`v-dev` / `v-cond` 从 text 改 computed。`v-test` 保持 text（测试进度由 Agent 手填），避免超出本 spec 语义。

### 5. 重算触发矩阵

| 触发 | 重算范围 |
|---|---|
| 行创建/更新/删除（表 T） | T 上依赖本表字段的计算字段；所有以 relation 指向 T 的表，其 `source` 指向该 relation 的计算字段 |
| relation 字段值变化 | 同上（行更新的一种） |
| 目标行删除 | 引用方重算；悬空引用被忽略 |
| 计算字段创建/更新/删除 | 该表全量；引用该表的表全量 |
| 被引用的普通字段类型/options 变化 | 依赖该字段的计算字段所在表全量 |
| `POST /api/agent/tables/{table_id}/recompute` | 该表全量 + 引用该表的表全量 |
| 清除 override | 该字段该行立即重算 |

实现采用「按表全量计算受影响字段」而非逐行增量：单表 ≤500 行、每项目 ≤10 表，规模内足够，少一层增量正确性风险。落库时只 upsert 与旧值不同的行/字段，并为变化写 `business_changes`（`change_kind=recompute`）。

### 6. 失败语义与三态

- 计算函数抛异常、配置非法、依赖缺失 → `WriteError` → `run_write` 回滚 → 400 `failed`，审计 `failed`。
- 提交阶段数据库错误 → 503 `unknown`；`computed_values` 可能已写或未写，MUST NOT 当作成功；调用重算接口修复。
- 分母为 0 / 无关联行 / 悬空引用 → 按 kind 语义落 `null`、`0` 或布尔，不失败。
- 重算接口幂等：重复调用结果一致。

## API Contract Changes

### 读侧

| 接口 | 变化 |
|---|---|
| `GET /api/tables/{table_id}/table` | 行值中合并计算字段有效值；新增 `computed_meta: {field_id: {computed_at, overridden, override_reason}}`；计算字段的 `options` 返回 kind 配置 |
| `GET /api/tables/{table_id}/rows/{row_id}` | 同上，单行 |
| `GET /api/tables/{table_id}/rows/{row_id}/changes` | 不变（002 提供） |

读侧实现：`repository` 查询 `computed_values`，按 `override_value ?? value` 合并进 `values`，**不做任何计算**。

### 写侧

| 接口 | 变化 |
|---|---|
| `POST /api/agent/tables/{table_id}/rows` | `values` 中出现 `type=computed` 的键 → `failed`；成功后触发重算 |
| `PATCH /api/agent/tables/{table_id}/rows/{row_id}` | 新增可选 `overrides: {field_id: {value, reason}}`；`value=null` 清除覆盖；`values` 中不允许计算字段；成功后重算 |
| `DELETE /api/agent/tables/{table_id}/rows/{row_id}` | 成功后重算引用方 |
| `POST /api/agent/tables/{table_id}/recompute` | **新增**：全量重算，要求 `X-Agent-Id`；返回 `{"result":"success","rows":N,"fields":M}`；落审计 |
| 字段写接口 | `type=computed` 配置校验 + 环检测；删除被引用字段/表拒绝 |

### 请求头与审计

- `X-Agent-Id`：必填（沿用 001）。
- `X-Origin`：可选，取值 `agent`（缺省）/ `human-request` / `seed`；其他值 400 `failed`。
- `write_audit.origin` 记录来源；`business_changes.change_kind` 记录动作。
- `target` 规则沿用 002：行操作 `"{table_id}/{row_id}"`；重算 `"{table_id}"`。

## Testing

- **计算单元**：`test_calculation.py` 覆盖五种 kind、空集合、分母 0、悬空引用、类型错误、环检测、override 优先级。
- **事务**：注入异常，断言源数据、`computed_values`、`business_changes` 全部回滚，审计 `failed`。
- **读侧零计算**：直接改源数据不重算，断言读接口返回旧值；断言 `repository` 不调用 `calculation`。
- **模板**：`test_seed.py` 断言 8 个计算/数字字段配置正确，`v-dev`/`v-cond` 不再是 text。
- **接口**：`test_agent_api.py` 覆盖重算、override、直接写计算字段拒绝、`X-Origin` 校验、人发起审计。
- **前端**：`npx tsc --noEmit`；quickstart 手工核对「66.7%」「是/否」「—」「覆盖标记」。
- **性能**：单表 500 行写入 + 重算 ≤200ms；首屏与滚动基线复测。

## Complexity Tracking

无违规项，本节留空。

## Risks

- **重算放大**：按表全量重算在 10 表 × 500 行时可能到 5000 行级别；规模内可接受，若超限先加索引与按表缓存行（不引入读缓存，仅事务内临时结构）。
- **覆盖与重算竞争**：覆盖值优先，重算跳过 override；清除后立即重算，避免出现"清除后仍是旧值"的窗口。
- **模板耦合**：`v-cond` 依赖 4 个字段，任一字段改名/删除都会使配置失效；字段写接口必须拒绝删除被引用字段。
- **人发起入口**：前端调用 Agent 接口，需确保 `X-Origin` 不被普通 Agent 写入误用；审计以请求头为准，v0 不做鉴权。
- **003 与 002 同批发布**：002 的 `business_changes`、`origin`、业务编号 id 是前置；003 不重复实现。
