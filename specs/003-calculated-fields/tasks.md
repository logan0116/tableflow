# Tasks: 计算字段与发布判定（v0.3.0）

**Input**: Design documents from `/specs/003-calculated-fields/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、002-field-system 已合入、宪法 v6.0.0

**Tests**: 非 TDD。新增 `backend/tests/test_calculation.py`，扩展 002 的字段体系测试；前端不引入测试框架。

**Organization**: 按 spec 的六条用户故事分组：US1 五种计算字段（P1）、US2 开发进度（P1）、US3 Bug已清空与覆盖（P1）、US4 发布条件（P1）、US5 刷新与失败语义（P1）、US6 人经 Agent 改状态（P1）。

## Format: `[ID] [P?] [Story] Description`

- `[P]`：可并行（不同文件、无未完成依赖）
- `[Story]`：仅用户故事阶段使用
- 每条任务必须带具体文件路径

## 验证命令

- 后端：`cd backend && .venv/bin/pytest -q`
- 前端：`cd frontend && npx tsc --noEmit`

> 沙箱内禁止 `uv run`（需要写 `~/.cache/uv`）；一律使用 `backend/.venv/bin/python` 与 `backend/.venv/bin/pytest`。

## Phase 1: Setup

- [ ] T001 确认 002 前置已合入：`backend/src/tableflow/db.py` 有 `business_changes` 与 `write_audit.origin`；`write_service.py` 行接口按 `(table_id, id)` 定位；先跑 `cd backend && .venv/bin/pytest -q` 记录基线
- [ ] T002 核对模板现状：`data/template_fd_system.py` 中 `v-dev` / `v-bug` / `v-cond` 仍是 text；`data/load_fd_system.py` 与 `data/load_tableflow.py` 中对应行值仍为手写文本

## Phase 2: Foundational（阻塞全部故事）

- [ ] T003 表结构 `backend/src/tableflow/db.py`：新增 `computed_values` 表（`table_id`/`row_id`/`field_id`/`value`/`computed_at`/`override_*`，复合主键）与 `idx_computed_values_field`
- [ ] T004 计算模块骨架 `backend/src/tableflow/calculation.py`：新增 `validate_computed_options(conn, table_id, options)`，校验 `kind`、`source`、`where`、`field_id`、`aggregate`、`conditions`，并做引用存在性与类型检查
- [ ] T005 依赖图 `backend/src/tableflow/calculation.py`：`build_dependency_graph(table_fields)`、`topological_order(graph)`、`detect_cycle(graph)`；`and` 引用同表计算字段时建边
- [ ] T006 重算入口 `backend/src/tableflow/calculation.py`：`recompute_table(conn, table_id)`、`recompute_for_write(conn, table_id, touched_row_ids)`；按拓扑序计算并 upsert `computed_values`；返回变化行/字段供写变更记录
- [ ] T007 读侧合并 `backend/src/tableflow/repository.py`：`get_table` / `get_row_detail` 查询 `computed_values`，按 `override_value ?? value` 合并进 `values`，输出 `computed_meta`；MUST NOT 调用 `calculation`
- [ ] T008 响应模型 `backend/src/tableflow/schemas.py`：新增 `ComputedMetaOut`、`RecomputeOut`；`RowOut` 增加 `computed_meta`
- [ ] T009 写事务接线 `backend/src/tableflow/write_service.py`：行增删改成功后调用 `calculation.recompute_for_write`；`values` 中出现 `type=computed` 键 → `WriteError`；删除行/字段/表时清理 `computed_values`
- [ ] T010 路由与请求头 `backend/src/tableflow/app.py`：新增 `POST /api/agent/tables/{table_id}/recompute`；行 PATCH 接受 `overrides`；解析 `X-Origin`（缺省 `agent`，非法值 400）
- [ ] T011 [P] 测试夹具 `backend/tests/test_calculation.py`：临时库、建表/字段/行 helper、构造 relation 与计算字段的 helper

## Phase 3: US1 五种计算字段（P1）

**Goal**: count / percent / sum / rollup / and 语义正确，写侧落库，读侧零计算。

**Independent Test**: 五种 kind 各一个用例；直接改源数据不重算，读接口仍返回落库值。

- [ ] T012 [US1] `count` 实现 `backend/src/tableflow/calculation.py`：解析 `source` relation，过滤目标行存在性，支持 `where`；无关联行返回 `0`
- [ ] T013 [US1] `percent` 实现 `backend/src/tableflow/calculation.py`：分子/分母按 `where` 统计；`total=0` 返回 `null`；按 `decimals` 四舍五入
- [ ] T014 [US1] `sum` 实现 `backend/src/tableflow/calculation.py`：目标 number 字段求和；缺失/非数字忽略；无关联行返回 `0`
- [ ] T015 [US1] `rollup` 实现 `backend/src/tableflow/calculation.py`：`all/any/none` 输出布尔；`min/max` 输出 number/datetime；`count_distinct` 输出数字
- [ ] T016 [US1] `and` 实现 `backend/src/tableflow/calculation.py`：条件逐项比较；`null` 不等于任何 `equals`；输出布尔
- [ ] T017 [US1] 计算配置校验测试 `backend/tests/test_calculation.py`：缺 `source`/`field_id`/`aggregate`/`equals`、类型不匹配、空 `conditions` 全部 `failed`
- [ ] T018 [US1] 五 kind 用例 `backend/tests/test_calculation.py`：`test_count`、`test_percent`、`test_sum`、`test_rollup_all`、`test_and`，断言落库值与接口返回值
- [ ] T019 [US1] 读侧零计算用例 `backend/tests/test_calculation.py`：直接改源表数据不重算，`GET /api/tables/{t}/table` 仍返回旧计算值
- [ ] T020 [P] [US1] 模板示例字段 `data/template_fd_system.py`：新增 `v-dep-count`（count `v-dep`）、`v-scenes`（sum `v-indep.i-scenes`）、`v-tasks`（sum `v-indep.i-tasks`）
- [ ] T021 [US1] 计算值渲染 `frontend/src/components/Cell.tsx` + `frontend/src/types.ts`：`computed` 的 number 右对齐、布尔显示「是/否」、`null` 显示「—」；`FieldOptions` 增加 `ComputedOptions`

## Phase 4: US2 开发进度（P1）

**Goal**: 版本「开发进度」= 关联需求 `speckit-implement` 完成比例，1 位小数。

**Independent Test**: 3 条关联 2 条完成 → `66.7%`；全完成 → `100.0%`；无关联 → 「—」。

- [ ] T022 [US2] 模板 `data/template_fd_system.py`：`v-dev` 改 `type=computed`，配置 `percent(source=v-indep, where={i-implement=done}, decimals=1)`
- [ ] T023 [P] [US2] 加载脚本 `data/load_fd_system.py`、`data/load_tableflow.py`、`data/load_specs.py`：删除 `v-dev` / `tf-v-dev` 的手写文本值，交由重算生成
- [ ] T024 [US2] 用例 `backend/tests/test_calculation.py`：`test_dev_progress`（66.7 / 100.0 / null）、`test_dev_progress_updates_in_same_write`（改 `i-implement` 后同事务更新）
- [ ] T025 [US2] 前端百分比展示 `frontend/src/components/Cell.tsx`：computed percent 按 `decimals` 加 `%`；`null` 显示「—」

## Phase 5: US3 Bug已清空与覆盖（P1）

**Goal**: 数字「未清Bug数」+ 归零判定；覆盖带原因、可清除、重算不覆盖。

**Independent Test**: 0 → 是；2 → 否；覆盖为是后改数字仍为是；清除后恢复。

- [ ] T026 [US3] 模板 `data/template_fd_system.py`：删除 `v-bug`（text）；新增 `v-bug-open`（number，`min=0`）与 `v-bug-clear`（computed and，`true_label=是`、`false_label=否`、`allow_override=true`）
- [ ] T027 [P] [US3] 加载脚本 `data/load_fd_system.py`、`data/load_tableflow.py`、`data/load_specs.py`：移除 `v-bug` 手写值，写入 `v-bug-open`
- [ ] T028 [US3] 覆盖处理 `backend/src/tableflow/write_service.py` + `backend/src/tableflow/calculation.py`：校验字段为 computed 且 `allow_override=true`、`reason` 非空、值类型匹配；写 `override_*`；清除时立即重算；写审计与 `business_changes`（`change_kind=override`）
- [ ] T029 [US3] 用例 `backend/tests/test_calculation.py`：`test_bug_clear_zero/nonzero`、`test_override_wins_over_recompute`、`test_clear_override_recomputes`、`test_override_non_computed_failed`、`test_override_not_allowed_failed`、`test_override_requires_reason`
- [ ] T030 [US3] 覆盖标记 `frontend/src/components/Cell.tsx` + `frontend/src/components/DataTable.tsx`：读取 `computed_meta.overridden`，显示「已覆盖」小标记；`RelationModal.tsx` 显示覆盖原因

## Phase 6: US4 发布条件（P1）

**Goal**: 发布条件 = 开发进度、回归通过、Bug已清空、文档状态四项 AND。

**Independent Test**: 四条件全满足 → 是；任一不满足 → 否；开发进度 null → 否。

- [ ] T031 [US4] 模板 `data/template_fd_system.py`：新增 `v-regress`（rollup `v-dep.d-regress all passed`）；`v-cond` 改 `type=computed`，配置 `and([v-dev=100, v-regress=true, v-bug-clear=true, v-doc=done])`
- [ ] T032 [US4] 用例 `backend/tests/test_calculation.py`：`test_release_condition_all_true`、`test_release_condition_each_false`（4 个反例）、`test_release_condition_null_progress_false`
- [ ] T033 [US4] 条件明细 `frontend/src/components/RelationModal.tsx`：只读展示 `v-cond` 每个条件的当前值（从同行字段读取，不在前端计算）

## Phase 7: US5 刷新时机与失败语义（P1）

**Goal**: 重算覆盖全部触发；失败整体回滚；未知不当作成功；重算幂等。

**Independent Test**: 注入异常 → failed 且三方数据无变化；重复重算结果一致。

- [ ] T034 [US5] 触发矩阵 `backend/src/tableflow/write_service.py` + `backend/src/tableflow/calculation.py`：行增删改、relation 变化、目标行删除、字段定义变化、显式重算全部触发；按表全量重算受影响字段
- [ ] T035 [US5] 事务回滚 `backend/src/tableflow/write_service.py`：计算异常 → `rollback` 源数据、`computed_values`、`business_changes`；仅保留 `failed` 审计
- [ ] T036 [US5] 重算接口 `backend/src/tableflow/app.py`：`POST /api/agent/tables/{table_id}/recompute` 全量重算 + 引用方重算；要求 `X-Agent-Id`；幂等；落审计
- [ ] T037 [US5] 删除保护 `backend/src/tableflow/write_service.py`：删除被计算字段引用的字段/relation → `failed`；删除被 relation 指向的表 → `failed`
- [ ] T038 [US5] 用例 `backend/tests/test_calculation.py` + `backend/tests/test_agent_api.py`：`test_recompute_rollback`、`test_unknown_not_success`、`test_recompute_idempotent`、`test_delete_referenced_field_failed`、`test_delete_referenced_table_failed`、`test_dangling_relation_ignored`

## Phase 8: US6 人经 Agent 改状态（P1）

**Goal**: enum 字段可人工申请变更，请求走 Agent 写接口，审计 `origin=human-request`；人侧仍只有 GET。

**Independent Test**: 从看板提交一次状态变更，数据变化且两份记录 origin 均为 human-request；人侧路由无写方法。

- [ ] T039 [US6] 来源校验 `backend/src/tableflow/app.py` + `backend/src/tableflow/write_service.py`：解析 `X-Origin`，允许 `agent` / `human-request` / `seed`；写入 `write_audit.origin` 与 `business_changes.origin`
- [ ] T040 [US6] 入口开关 `backend/src/tableflow/write_service.py`：enum `options.human_request=true` 或 computed `options.allow_override=true` 才允许 `origin=human-request` 的写入；其他字段返回 `failed`
- [ ] T041 [P] [US6] 前端接口 `frontend/src/api.ts`：`submitHumanChange(tableId, rowId, fieldId, value, reason)`，带 `X-Agent-Id: agent-ui` 与 `X-Origin: human-request`
- [ ] T042 [US6] 变更弹窗 `frontend/src/components/ChangeDialog.tsx` + `frontend/src/components/DataTable.tsx` + `frontend/src/components/Cell.tsx`：点击允许人工申请的 enum 单元格，列出合法值、原因必填、提交后刷新
- [ ] T043 [US6] 用例 `backend/tests/test_agent_api.py`：`test_human_request_origin_recorded`、`test_human_request_requires_reason`、`test_human_request_rejected_on_other_fields`、`test_human_routes_only_get`
- [ ] T044 [US6] 路由清单核对：扫描 `backend/src/tableflow/app.py`，确认人侧 `/api/*` 只有 GET（`/api/agent/*` 除外），结果写入验收记录

## Phase 9: Polish

- [ ] T045 [P] 文档 `README.md`：计算字段五种 kind、读侧零计算、重算接口、覆盖语义、人经 Agent 改状态
- [ ] T046 [P] 验收指南 `specs/003-calculated-fields/quickstart.md`：V1–V10（五 kind、开发进度、Bug 覆盖、发布条件、失败回滚、人发起）
- [ ] T047 宪法逐条核验（`backend/src/tableflow/calculation.py`）：只实现五种 kind、无用户表达式、无跨表任意聚合、读侧无计算、失败回滚、覆盖可审计
- [ ] T048 后端全量回归：`cd backend && .venv/bin/pytest -q`，要求 0 failed
- [ ] T049 前端类型门禁：`cd frontend && npx tsc --noEmit`，要求 0 error
- [ ] T050 性能验收（`backend/src/tableflow/calculation.py`、`frontend/src/components/DataTable.tsx`）：单表 500 行写入 + 重算 ≤200ms；14 行首屏 ≤500ms、滚动 ≥50fps 复测
- [ ] T051 数据重建：删除 `data/tableflow.db*`，用 `backend/.venv/bin/python backend/scripts/seed_data.py` 重灌；核对 `v-dev` 与 `i-implement` 完成数一致（如 0/3 → `0.0%`）、`v-bug-open=0` 时 `v-bug-clear=是`、`v-cond` 与源数据一致
- [ ] T052 提交与清理：按产物拆分提交（schema / calculation / 前端 / 数据 / 文档），确认 `.gitignore` 覆盖 `data/*.db*`

## Dependencies & Execution Order

- Phase 1 → Phase 2（阻塞）→ US1 → US2 / US3 / US4 → US5 → US6 → Polish
- US1 的五种 kind 是 US2/US3/US4 的前置；US3 的 override 依赖 US1 的 `and`
- US4 依赖 US2 的 `v-dev`、US3 的 `v-bug-clear`
- US5 依赖 US1 的落库与重算骨架；US6 依赖 002 的 `origin` 与 `business_changes`
- 串行热点：`backend/src/tableflow/calculation.py`、`backend/src/tableflow/write_service.py`、`data/template_fd_system.py`
- 可并行：测试文件、前端组件、加载脚本（在计算配置稳定后）

## Notes

- 计算字段 `type=computed` 是 002 字段体系的扩展；`kind` 集合封闭，新增第六种必须先改宪法
- 读侧零计算是硬约束：`repository.py` 不允许 import `calculation.py`
- 覆盖只支持标量；覆盖原因必填；清除后立即重算
- 人侧路由仍只有 GET；「申请变更」只是调用 Agent 接口的 UI 入口
