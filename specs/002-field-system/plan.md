# Implementation Plan: 字段体系与单向关联（v0.3.0）

**Branch**: `002-field-system` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-field-system/spec.md`

## Summary

把字段从「自由 JSON」收敛为「结构化 options + 写侧校验」：enum 统一对象结构并带 `tone`，number/datetime 显式声明格式，所有类型共享 `constraints`；行 id 改为业务编号并把 `row_records` 主键改为 `(table_id, id)`；relation 禁止双向，fd_system 模板中版本管理表是唯一挂载点；新增 `business_changes` 字段级业务留痕；独立规格需求补齐 speckit-clarify/analyze/checklist 三态与治理字段。计算字段留给 003，界面视觉打磨留给 004。

## Technical Context

**Language/Version**: Python 3.11+（后端）；TypeScript 5.x + Node 24（前端）

**Primary Dependencies**: FastAPI、uvicorn、pytest、httpx（后端，均已在 001 引入）；React 18、Vite、TypeScript、@tanstack/react-table（前端，不新增依赖）

**Storage**: SQLite（WAL），标准库 sqlite3；001 的五张表 + 新增 `business_changes`，`row_records` 主键调整

**Testing**: pytest + httpx；新增 `backend/tests/test_field_system.py`，扩展现有 `test_api.py` / `test_agent_api.py` / `test_seed.py`；前端不引入测试框架，验收按 quickstart 手工执行

**Target Platform**: Linux（本机或局域网服务器），Chrome / Edge 桌面浏览器

**Project Type**: web application（backend + frontend）

**Performance Goals**: 保持 001 基线：14 行首屏 ≤500ms、关闭硬件加速滚动 ≥50fps、无 >50ms 长任务；字段校验与变更记录不得引入额外往返

**Constraints**: 人侧只有 GET；写接口带契约/审计/三态；无读缓存；DOM 表格；界面全中文；不新增依赖；不做旧库自动迁移

**Scale/Scope**: ≤20 项目、每项目 ≤10 表、单表 ≤500 行；本 spec 改 1 张表结构、新增 1 张表、新增 1 个只读接口、调整 2 个写接口路径、新增 7 个治理字段

## Constitution Check

*GATE: 对照宪法 v6.0.0 逐条核验；本 spec 不启用计算字段。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 人侧仍只有 GET；写接口每条落 `write_audit`（新增 `origin`）与 `business_changes`；三态不变 | PASS |
| II 无读缓存 | 读接口 `no-store`；变更记录每次现查；前端不持久化业务数据 | PASS |
| III Schema 驱动 | 状态色/格式/约束全部进 `fields.options`；前端按 type/options 通用渲染，无业务列名 | PASS |
| IV DOM 表格 | 仍是原生 table + TanStack Table；新增只读变更列表，不引入 canvas/虚拟滚动 | PASS |
| V 固定技术栈 | 不新增后端/前端依赖；SQLite WAL 不变 | PASS |
| VI 中文单语 | 新增文案全部中文；无 i18n 库 | PASS |
| VII 边界收敛 | 不实现计算字段（003）、不做用户表达式/跨表任意聚合；relation 仅单向声明 | PASS |

无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/002-field-system/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── src/tableflow/
│   ├── db.py             # 建表：row_records 复合主键、business_changes、write_audit.origin
│   ├── schemas.py        # 响应模型：变更记录、字段 options 透传
│   ├── repository.py     # 读查询：变更记录、options 解析、复合主键取行
│   ├── write_service.py  # 字段 options/约束校验、行 id 校验、双向 relation 拒绝、变更记录
│   └── app.py            # 行写接口路径带 table_id、变更记录只读接口
├── scripts/seed_data.py  # 样例数据校验：业务编号 id、options 对象、单向 relation
└── tests/
    ├── test_field_system.py  # 新增：options/约束/id/双向/变更记录
    ├── test_api.py           # 扩展：变更记录读接口、options 透传
    ├── test_agent_api.py     # 扩展：行写路径、id 校验、约束失败
    └── test_seed.py          # 扩展：新模板样例可加载

frontend/
└── src/
    ├── types.ts                 # FieldOptions 判别联合、BusinessChange
    ├── api.ts                   # fetchRowChanges
    ├── components/
    │   ├── Cell.tsx             # enum tone、number 格式、datetime with_time
    │   ├── DataTable.tsx        # 透传 field.options（不改渲染结构）
    │   └── RelationModal.tsx    # 只读变更记录列表
    └── styles.css               # 状态标签、变更记录样式

data/
├── template_fd_system.py   # 表/字段定义：单向 relation、enum tone、治理字段、业务编号
├── load_fd_system.py       # fd_system 加载：业务编号行 id、新 options
├── load_tableflow.py       # tableflow 加载：同上
├── load_specs.py           # 002/003/004 + v0.3.0：业务编号、enum 三态
├── load_backlog.py         # 历史 backlog：按新 enum/约束适配或标记废弃
└── seed.example.json       # 样例：业务编号 id、options 对象
```

**Structure Decision**: 沿用 001 的前后端双目录。字段校验集中在 `write_service.py`，读侧只做 JSON 解析与透传；变更记录读写分别落在 `repository.py` 与 `write_service.py`，不新建服务层。

## Data Model Changes

### 1. `row_records`：主键改为 `(table_id, id)`

```sql
CREATE TABLE row_records (
  id        TEXT NOT NULL,
  table_id  TEXT NOT NULL REFERENCES tables(id),
  data      TEXT NOT NULL,
  PRIMARY KEY (table_id, id)
);
CREATE INDEX idx_row_records_table ON row_records (table_id, id);
```

- `id` 是业务编号，必须匹配 `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`。
- 表内唯一、跨表可同名；relation 值只在字段声明的目标表内解析。
- id 不可变：更新接口只接受 `values`，出现 `id` 键即拒绝。
- 迁移方式：不自动迁移；重建数据库后用加载脚本重灌。

### 2. `business_changes`（新增）

```sql
CREATE TABLE business_changes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL,
  actor       TEXT NOT NULL,
  origin      TEXT NOT NULL,
  table_id    TEXT NOT NULL,
  row_id      TEXT NOT NULL,
  field_id    TEXT NOT NULL,
  field_name  TEXT NOT NULL,
  old_value   TEXT,
  new_value   TEXT,
  change_kind TEXT NOT NULL,
  reason      TEXT
);
CREATE INDEX idx_business_changes_row
  ON business_changes (table_id, row_id, id DESC);
```

- `origin`：`agent` / `human-request` / `seed`（发起来源）。
- `change_kind`：`create` / `update` / `delete` / `recompute` / `override`（动作类型）。
- `old_value` / `new_value`：JSON 编码；`NULL` 表示无值（创建时旧值、删除时新值）。
- `field_name`：写入时的字段名快照，字段改名后历史记录仍可读。
- 只增不改；与数据变更同事务。

### 3. `write_audit`：新增 `origin`

```sql
ALTER TABLE write_audit ADD COLUMN origin TEXT NOT NULL DEFAULT 'agent';
```

重建库时直接建列，不保留旧表。`origin` 与 `business_changes.origin` 取值一致，用于区分人发起与 Agent 自主写入；`recompute` / `override` 属于 `change_kind`，不放进 `origin`。

### 4. `fields.options`：统一为对象

001 的 enum 数组形态废止，所有类型统一为对象；前端与加载脚本同步修改。

```json
// enum
{
  "items": [
    {"value": "released", "label": "已发布", "tone": "success"},
    {"value": "planned", "label": "计划中", "tone": "info"},
    {"value": "dropped", "label": "已废弃", "tone": "neutral"}
  ],
  "constraints": {"required": true, "enum_strict": true}
}
```

```json
// number
{"decimals": 2, "percent": false, "unit": "台",
 "constraints": {"required": false, "min": 0, "max": 100}}
```

```json
// datetime
{"with_time": false, "constraints": {"required": true}}
```

```json
// relation
{"table_id": "fd-indep", "constraints": {"relation_must_exist": true}}
```

```json
// text
{"constraints": {"required": false}}
```

规则：

- `enum.items` 非空数组；`value`/`label`/`tone` 必填；`tone ∈ {neutral, info, success, warning, danger}`；`color` 可选 `{bg, fg}`。
- `number.decimals` 为 0–6 的整数，缺省 `0`；`percent` 缺省 `false`；`unit` 长度 ≤8。
- `datetime.with_time` 缺省 `true`。
- `constraints` 可出现在任意类型；未知键忽略，类型错误拒绝。
- 顶层未知键忽略（为 003 的 `human_request`、`allow_override` 预留）；已知键类型错误拒绝。
- 写字段时 MUST 做完整结构校验；读字段时 MUST 做容错解析（坏 options 回退空对象，不阻断整表）。

### 5. 单向关联规则

- 创建/更新 relation 字段前，查同项目内是否存在「目标表 → 当前表」的 relation 字段（更新时排除当前字段自身）；存在即 `failed`。
- 允许自关联（表指向自身），但同一对表仍只允许一个方向。
- fd_system 模板：版本管理表保留 `v-indep` / `v-dep`；依赖变更需求表删除 `d-version`，且不再新增任何 relation。
- 反向一致性由写接口校验保证；不做数据库触发器。

### 6. 枚举字段清单（模板）

| 表 | 字段 | 取值（value / label / tone） |
|---|---|---|
| 版本管理 | 发布状态 | `released/已发布/success`、`planned/计划中/info`、`dropped/已废弃/neutral` |
| 版本管理 | 文档状态 | `todo/未开始/neutral`、`doing/进行中/info`、`done/已完成/success`、`na/不适用/neutral` |
| 独立规格需求 | 状态 | `todo/待启动/neutral`、`doing/实现中/info`、`done/已完成/success`、`blocked/已阻塞/danger` |
| 独立规格需求 | speckit-constitution / specify / plan / task / implement | `todo/未开始/neutral`、`doing/进行中/info`、`done/完成/success` |
| 独立规格需求 | speckit-clarify / analyze / checklist | 同上三态 |
| 独立规格需求 | 验收状态 | `pending/未验收/neutral`、`accepted/已验收/success`、`rejected/不通过/danger` |
| 独立规格需求 | 优先级 | `P0/P0/danger`、`P1/P1/warning`、`P2/P2/info`、`P3/P3/neutral` |
| 依赖变更需求 | 状态 | `todo/待办/neutral`、`doing/进行中/info`、`done/已完成/success`、`blocked/已阻塞/danger`、`cancelled/已取消/neutral` |
| 依赖变更需求 | 回归状态 | `todo/未开始/neutral`、`doing/进行中/info`、`passed/通过/success`、`failed/失败/danger`、`na/不适用/neutral` |

### 7. 独立规格需求新增字段

| 字段 id | 名称 | type | options |
|---|---|---|---|
| `i-clarify` | speckit-clarify状态 | enum | 三态 |
| `i-analyze` | speckit-analyze状态 | enum | 三态 |
| `i-checklist` | speckit-checklist状态 | enum | 三态 |
| `i-constitution-version` | 宪法版本 | text | `{"constraints":{"required":false}}` |
| `i-acceptance` | 验收状态 | enum | 未验收 / 已验收 / 不通过 |
| `i-owner` | 负责人 | text | — |
| `i-priority` | 优先级 | enum | P0 / P1 / P2 / P3 |

## API Contract Changes

### 读侧（全部 GET）

| 接口 | 变化 |
|---|---|
| `GET /api/projects` | 不变 |
| `GET /api/projects/{project_id}/tables` | 不变 |
| `GET /api/tables/{table_id}/table` | `fields[].options` 变为对象；行 id 为业务编号；其余不变 |
| `GET /api/tables/{table_id}/rows/{row_id}` | 不变 |
| `GET /api/tables/{table_id}/rows/{row_id}/changes?limit=50` | **新增**：按 `id` 倒序返回 `{changes:[{id,occurred_at,actor,origin,field_id,field_name,old_value,new_value,change_kind,reason}]}`；`limit` 默认 50、上限 200；行不存在 404 |

### 写侧（全部 `/api/agent/*`，要求 `X-Agent-Id`）

| 接口 | 变化 |
|---|---|
| `POST /api/agent/projects` | 不变 |
| `DELETE /api/agent/projects/{project_id}` | 不变 |
| `POST /api/agent/projects/{project_id}/tables` | 不变 |
| `PATCH/DELETE /api/agent/tables/{table_id}` | 不变 |
| `POST /api/agent/tables/{table_id}/fields` | options 结构校验加强；双向 relation 拒绝 |
| `PATCH/DELETE /api/agent/fields/{field_id}` | 同上 |
| `POST /api/agent/tables/{table_id}/rows` | `id` 必填且校验格式；约束校验；写变更记录 |
| `PATCH/DELETE /api/agent/tables/{table_id}/rows/{row_id}` | **路径变更**（原 `/api/agent/rows/{row_id}`）：复合主键需要表上下文；`id` 不可变；约束按合并值校验；写变更记录 |

### 三态与审计

- 成功：`{"result":"success","id":...}`；失败：400 + `{"result":"failed","error":...}`；未知：503 + `{"result":"unknown"}`。
- 每次调用写一条 `write_audit`，含 `agent_id`、`origin`、`action`、`target`、`payload`、`result`、`error`、`created_at`。
- `target` 对行操作为 `"{table_id}/{row_id}"`，避免跨表同名歧义。

## Validation Rules

| 对象 | 规则 | 失败语义 |
|---|---|---|
| 行 id | 必填、正则 `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`、表内唯一、创建后不可变 | 400 failed，不落库 |
| relation | 目标表存在且同项目；不得与目标表形成双向 | 400 failed，不落库 |
| enum options | `items` 非空；`value/label/tone` 必填；tone 枚举；color 合法 | 400 failed，不落库 |
| number options | `decimals` 0–6 整数；`percent` 布尔；`unit` ≤8 字符 | 400 failed，不落库 |
| datetime options | `with_time` 布尔 | 400 failed，不落库 |
| constraints | 键类型正确；`min ≤ max`；只允许声明支持的五类键 | 400 failed，不落库 |
| required | 创建时必填；更新时按合并值必填；空字符串、`null`、缺失均视为空 | 400 failed，不落库 |
| min / max | 仅 number；非数字值不参与比较 | 400 failed，不落库 |
| enum_strict | 值必须在 `items` 内 | 400 failed，不落库 |
| relation_must_exist | 每个目标 id 必须在目标表存在 | 400 failed，不落库 |

读侧容错：坏 options、未知 type、越界历史值一律降级显示，不返回 5xx。

## Migration & Rollout

1. 删除 `data/tableflow.db*`，用新 `db.py` 重建五张表 + `business_changes`。
2. 更新 `data/template_fd_system.py`：单向 relation、enum 对象、格式、约束、治理字段。
3. 更新加载脚本：行 id 改业务编号（版本 `7.0.1`、需求 `UD-01` 等），relation 值同步；`load_specs.py` 的 002/003/004 行改用业务编号。
4. 用 `backend/.venv/bin/python backend/scripts/seed_data.py` 或三个加载脚本重灌；可新增 `data/migrate_v030.py` 封装「删库 → 重建 → 按新模板重灌」，不做旧数据转换；跑全量 pytest。
5. 前端随之后发；`v-dev` / `v-cond` 在 002 阶段仍是 text，003 落库后改为计算字段；`v-bug` 在 003 由 `v-bug-open` + `v-bug-clear` 取代。

回滚：v0.3.0 不承诺旧库兼容；回滚需重新 checkout 001 代码并重灌 001 样例。

## Testing

- **单元/契约**：`backend/tests/test_field_system.py` 覆盖 options 校验、行 id、双向 relation、约束、变更记录、读侧容错。
- **接口**：`test_api.py` 覆盖 changes 只读接口、options 透传、坏 options 降级；`test_agent_api.py` 覆盖新行路径、id 不可变、约束失败回滚。
- **样例**：`test_seed.py` 覆盖新模板可加载、无反向 relation、所有状态字段为 enum。
- **前端**：不引入测试框架；`npx tsc --noEmit` 作为类型门禁，quickstart 手工核对渲染。
- **性能**：变更记录查询与约束校验不改变 14 行首屏基线；滚动验收沿用 001 方法。

## Complexity Tracking

无违规项，本节留空。

## Risks

- **主键变更影响面**：所有行写接口、审计 target、样例数据都要同步；漏改会在测试中暴露（跨表同名用例）。
- **options 结构破坏性变更**：001 的 enum 数组不再兼容；前端与加载脚本必须同批发布，旧库直接重建。
- **变更记录写入量**：一次更新 N 个字段写 N 条；单表 ≤500 行、单次写入字段数有限，不构成性能风险。
- **003 依赖**：计算字段需要 `computed_values` 与重算钩子；002 只预留 `origin=human-request` 与 `change_kind=recompute/override` 取值，不实现。
