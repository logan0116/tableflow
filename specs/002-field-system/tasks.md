# Tasks: 字段体系与单向关联（v0.3.0）

**Input**: Design documents from `/specs/002-field-system/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、宪法 v6.0.0

**Tests**: 非 TDD。新增 `backend/tests/test_field_system.py` 作为契约证据，并扩展 001 的三个测试文件；前端不引入测试框架。

**Organization**: 按 spec 的七条用户故事分组：US1 单向关联（P1）、US2 业务编号（P1）、US3 enum 与状态色（P1）、US4 数字/日期格式（P2）、US5 字段级约束（P1）、US6 业务变更记录（P1）、US7 治理字段（P2）。

## Format: `[ID] [P?] [Story] Description`

- `[P]`：可并行（不同文件、无未完成依赖）
- `[Story]`：仅用户故事阶段使用
- 每条任务必须带具体文件路径

## 验证命令

- 后端：`cd backend && .venv/bin/pytest -q`
- 前端：`cd frontend && npx tsc --noEmit`

> 沙箱内禁止 `uv run`（需要写 `~/.cache/uv`）；一律使用 `backend/.venv/bin/python` 与 `backend/.venv/bin/pytest`。

## Phase 1: Setup

- [ ] T001 确认依赖与基线：`backend/pyproject.toml`、`frontend/package.json` 不新增依赖；先跑 `cd backend && .venv/bin/pytest -q` 记录 001 基线
- [ ] T002 确认样例加载顺序：`data/load_fd_system.py`、`data/load_tableflow.py`、`data/load_specs.py`、`data/load_backlog.py` 均按「项目 → 表 → 字段 → 行」执行，relation 目标表先建

## Phase 2: Foundational（阻塞全部故事）

- [ ] T003 重建表结构 `backend/src/tableflow/db.py`：`row_records` 改为复合主键 `(table_id, id)`；新增 `business_changes` 表与 `idx_business_changes_row`；`write_audit` 增加 `origin TEXT NOT NULL DEFAULT 'agent'`
- [ ] T004 [P] 响应模型 `backend/src/tableflow/schemas.py`：新增 `BusinessChangeOut`、`ChangesOut`；`FieldOut.options` 保持 `Any` 但补注释；`RowOut.id` 注释为业务编号
- [ ] T005 读查询 `backend/src/tableflow/repository.py`：`get_table` / `get_row_detail` 按 `(table_id, id)` 取行；新增 `list_changes(table_id, row_id, limit)` 按 `id DESC`；options 解析做容错（坏 JSON 回退 `{}`）
- [ ] T006 字段 options 校验器 `backend/src/tableflow/write_service.py`：统一入口 `_validate_options(conn, table_id, field_type, options)`，按 type 分派到 enum/number/datetime/relation/text；返回规范化后的 options
- [ ] T007 行 id 校验 `backend/src/tableflow/write_service.py`：新增 `_validate_row_id(row_id)`，正则 `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`；创建必填、表内唯一；更新时出现 `id` 键即拒绝
- [ ] T008 业务变更记录写入 `backend/src/tableflow/write_service.py`：新增 `_record_changes(conn, ...)`，支持 `create` / `update` / `delete`，逐字段写 `business_changes`；与数据变更同事务
- [ ] T009 路由调整 `backend/src/tableflow/app.py`：行更新/删除改为 `PATCH|DELETE /api/agent/tables/{table_id}/rows/{row_id}`；`target` 记为 `"{table_id}/{row_id}"`；新增 `GET /api/tables/{table_id}/rows/{row_id}/changes`
- [ ] T010 [P] 测试夹具 `backend/tests/conftest.py`（或 `test_field_system.py` 内 helper）：临时库、创建项目/表/字段/行的辅助函数，统一使用业务编号

## Phase 3: US1 单向关联（P1）

**Goal**: 版本表是唯一挂载点，依赖变更需求表没有「所属版本」列。

**Independent Test**: 模板重建后 `fd-dep` 的 relation 字段数为 0；反向创建 relation 返回 `failed`。

- [ ] T011 [US1] 双向关联拒绝 `backend/src/tableflow/write_service.py`：创建/更新 relation 字段前查询同项目内是否存在「目标表 → 当前表」的 relation，存在则 `WriteError`；允许自关联
- [ ] T012 [US1] 模板收敛 `data/template_fd_system.py`：删除依赖变更需求表的 `d-version` 字段；版本表保留 `v-indep` / `v-dep`；确认两张需求表无任何 relation
- [ ] T013 [US1] 加载脚本同步 `data/load_fd_system.py`、`data/load_tableflow.py`：删除 `d-version` / `tf-d-version` 字段与行值；版本行 relation 值改业务编号
- [ ] T014 [US1] 契约测试 `backend/tests/test_field_system.py`：`test_relation_is_single_direction`（反向创建 failed、无落库、有失败审计）、`test_no_reverse_relation_in_template`
- [ ] T015 [US1] 读侧核对 `backend/tests/test_api.py`：`GET /api/tables/fd-dep/table` 的 fields 不含「所属版本」；版本表 relation 标签为业务编号

## Phase 4: US2 行 id 采用业务编号（P1）

**Goal**: 行 id 为 `UD-01` / `7.0.1` 这类业务编号，表内唯一、跨表可同名、不可变。

**Independent Test**: 同表重复 id 失败；两张表各写 `7.0.1` 都可读；非法 id 失败。

- [ ] T016 [US2] 行写入改造 `backend/src/tableflow/write_service.py`：`create_row` 强制业务编号 id；`update_row` / `delete_row` 接收 `table_id` 参数并按复合主键定位；`update_row` 拒绝 `id` 键
- [ ] T017 [US2] 复合主键读写 `backend/src/tableflow/repository.py`：所有行查询带 `table_id`；relation 解析只在目标表内查 id
- [ ] T018 [P] [US2] 样例数据 `data/seed.example.json` 与 `backend/src/tableflow/seed.py`：行 id 改业务编号（版本 `7.0.1`、需求 `UD-01` 等），relation 值同步
- [ ] T019 [P] [US2] 加载脚本 `data/load_specs.py`：002/003/004、v0.3.0、DEP-01 行改用业务编号（如 `002-AR`、`v0.3.0`、`DEP-01-BR`）；删除行改用 `DELETE /api/agent/tables/tf-indep/rows/{row_id}` 新路径
- [ ] T020 [US2] 契约测试 `backend/tests/test_field_system.py`：`test_row_id_format`、`test_row_id_unique_within_table`、`test_row_id_same_across_tables`、`test_row_id_immutable`
- [ ] T021 [US2] 接口测试 `backend/tests/test_agent_api.py`：行更新/删除新路径 200；旧路径 `/api/agent/rows/{id}` 返回 404/405；审计 target 为 `"{table_id}/{row_id}"`

## Phase 5: US3 状态字段 enum 化与 tone（P1）

**Goal**: 所有状态字段为 enum，选项含 `tone`，前端按 tone 渲染，无业务值硬编码。

**Independent Test**: 字段定义全部为 enum；改 options 的 tone 后刷新颜色变化；前端 grep 无业务状态值。

- [ ] T022 [US3] enum 校验 `backend/src/tableflow/write_service.py`：`options.items` 非空数组；`value`/`label`/`tone` 必填；`tone ∈ {neutral,info,success,warning,danger}`；`color` 可选 `{bg,fg}`
- [ ] T023 [US3] 模板 enum 化 `data/template_fd_system.py`：按 plan §6 清单把发布状态、文档状态、独立需求状态、speckit 五态、clarify/analyze/checklist、依赖需求状态、回归状态、验收状态、优先级全部改为 enum + tone
- [ ] T024 [P] [US3] 加载脚本 `data/load_fd_system.py`、`data/load_tableflow.py`、`data/load_specs.py`、`data/load_backlog.py`：状态值改为 enum value（如 `todo`/`done`），options 使用对象结构；`load_backlog.py` 若已被 `load_specs.py` 清退则标记废弃
- [ ] T025 [P] [US3] 前端类型 `frontend/src/types.ts`：新增 `EnumOption`、`FieldOptions`（含 `items`/`constraints`）；`Field.options` 改为 `FieldOptions`
- [ ] T026 [US3] 状态标签 `frontend/src/components/Cell.tsx` + `frontend/src/styles.css`：enum 按 `tone` 加类名渲染底色/文字色；`tone` 未知回退 `neutral`；`color` 存在时以内联样式覆盖
- [ ] T027 [US3] 契约测试 `backend/tests/test_field_system.py`：`test_enum_requires_tone`、`test_enum_rejects_unknown_tone`、`test_enum_strict`；`backend/tests/test_seed.py` 断言所有状态字段 type=enum
- [ ] T028 [US3] 硬编码检查：`frontend/src` 中 grep `released|planned|待办|已完成|未开始` 命中数为 0（命令写入验收记录）

## Phase 6: US4 数字/日期格式（P2）

**Goal**: number 支持 decimals/percent/unit，datetime 支持 with_time；格式只影响显示。

**Independent Test**: 固定值逐条核对渲染文本；接口返回原值。

- [ ] T029 [US4] 格式校验 `backend/src/tableflow/write_service.py`：number `decimals` 0–6 整数、`percent` 布尔、`unit` ≤8；datetime `with_time` 布尔、缺省 true；非法返回 `failed`
- [ ] T030 [P] [US4] 前端类型 `frontend/src/types.ts`：`NumberOptions` / `DatetimeOptions` 判别字段
- [ ] T031 [US4] 单元格格式化 `frontend/src/components/Cell.tsx`：number 按 `decimals` 四舍五入、`percent` 加 `%`、`unit` 前加空格；datetime 按 `with_time` 输出 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:mm`；非法值原样/空
- [ ] T032 [US4] 契约测试 `backend/tests/test_field_system.py`：`test_number_options_bounds`、`test_datetime_with_time_type`；读接口断言返回原始值而非格式化值

## Phase 7: US5 字段级约束（P1）

**Goal**: required / min / max / enum_strict / relation_must_exist 在写侧校验，更新按合并值校验。

**Independent Test**: 5 类非法写入全部 failed 且不落库；合法写入通过；读侧历史非法值可显示。

- [ ] T033 [US5] 约束校验 `backend/src/tableflow/write_service.py`：`_validate_constraints(conn, table_id, fields, merged_values)`；required 视 `None`/空串/缺失为空；min/max 仅 number；enum_strict 查 `items`；relation_must_exist 逐个查目标表
- [ ] T034 [US5] 合并值校验 `backend/src/tableflow/write_service.py`：`update_row` 先取旧值合并再校验 required/min/max；校验失败不写库
- [ ] T035 [US5] 模板声明约束 `data/template_fd_system.py`：编号、版本号、状态等关键字段加 `required`/`enum_strict`；数字字段加合理 `min`
- [ ] T036 [US5] 契约测试 `backend/tests/test_field_system.py`：`test_required`、`test_min_max`、`test_enum_strict`、`test_relation_must_exist`、`test_update_uses_merged_values`，逐条断言不落库与失败审计

## Phase 8: US6 业务变更记录（P1）

**Goal**: 每次行变化按字段写业务变更记录；与写审计分离；只读查询与弹层展示。

**Independent Test**: 改 2 字段产生 2 条；失败写入 0 条；读接口倒序。

- [ ] T037 [US6] 变更记录落库 `backend/src/tableflow/write_service.py`：`create_row` 每字段一条（旧值空）；`update_row` 只记变化字段；`delete_row` 每非空字段一条（新值空）；`field_name` 取快照；`origin` 透传
- [ ] T038 [US6] 事务一致性 `backend/src/tableflow/write_service.py`：变更记录与数据在同一 `run_write` 事务；异常时 `rollback` 全部业务变更记录，仅保留失败审计
- [ ] T039 [US6] 只读接口 `backend/src/tableflow/app.py` + `backend/src/tableflow/repository.py`：`GET /api/tables/{table_id}/rows/{row_id}/changes`，`limit` 默认 50、上限 200，行不存在 404，返回倒序
- [ ] T040 [P] [US6] 前端接口 `frontend/src/api.ts` + `frontend/src/types.ts`：`fetchRowChanges(tableId, rowId, limit)`、`BusinessChange` 类型
- [ ] T041 [US6] 明细弹层 `frontend/src/components/RelationModal.tsx` + `frontend/src/styles.css`：只读展示最近 20 条（时间、操作者、字段、旧值→新值），无编辑/回滚控件
- [ ] T042 [US6] 契约测试 `backend/tests/test_field_system.py` + `backend/tests/test_api.py`：创建/更新/删除的条数与旧新值；失败写入 0 条；倒序与 limit；读接口 no-store

## Phase 9: US7 独立规格需求治理字段（P2）

**Goal**: 补齐 speckit-clarify/analyze/checklist 三态与宪法版本、验收状态、负责人、优先级。

**Independent Test**: 002 行可读出 7 个新字段；缺省为空。

- [ ] T043 [US7] 模板字段 `data/template_fd_system.py`：新增 `i-clarify`、`i-analyze`、`i-checklist`（enum 三态）、`i-constitution-version`（text）、`i-acceptance`（enum）、`i-owner`（text）、`i-priority`（enum）
- [ ] T044 [US7] 加载数据 `data/load_specs.py`、`data/load_tableflow.py`：为 002/003/004 写入宪法版本 `v6.0.0`、验收状态「未验收」、负责人、优先级
- [ ] T045 [US7] 契约测试 `backend/tests/test_seed.py` + `backend/tests/test_api.py`：新字段存在且类型正确；002 行读回治理值；缺省行显示空

## Phase 10: Polish

- [ ] T046 [P] 文档更新 `README.md`：字段 options 结构、行 id 规则、单向关联、业务变更记录、行写接口新路径
- [ ] T047 [P] 验收指南 `specs/002-field-system/quickstart.md`：V1–V10 手工步骤（单向关联、业务编号、enum 色、格式、约束、变更记录、治理字段）
- [ ] T048 宪法逐条核验（`backend/src/tableflow/app.py`、`frontend/src`）：人侧只有 GET、写接口全部有审计、origin 可区分、无缓存、无 canvas、无 i18n、无业务值硬编码、无计算字段实现
- [ ] T049 后端全量回归：`cd backend && .venv/bin/pytest -q`，要求 0 failed
- [ ] T050 前端类型门禁：`cd frontend && npx tsc --noEmit`，要求 0 error
- [ ] T051 性能回归（入口 `frontend/src/App.tsx`）：按 001 方法测 14 行首屏 ≤500ms、滚动 ≥50fps、无 >50ms 长任务
- [ ] T052 数据重建与核对：删除 `data/tableflow.db*`，用 `backend/.venv/bin/python backend/scripts/seed_data.py` 重灌，或运行新增的 `data/migrate_v030.py`（删库 → 重建 → 重灌，不做旧数据转换）；核对 fd_system/tableflow 两项目无反向 relation
- [ ] T053 提交与清理：按产物拆分提交（schema / 字段校验 / 前端 / 数据 / 文档），确认 `.gitignore` 覆盖 `data/*.db*`

## Dependencies & Execution Order

- Phase 1 → Phase 2（阻塞）→ US1 / US2 / US3 / US4 / US5 / US6 / US7 → Polish
- US2 的复合主键是 US1、US6 的前置；US3 的 options 对象是 US4、US5 的前置；US6 依赖 US2 的行定位
- US7 只依赖 Phase 2 与 US3 的三态定义
- 串行热点：`backend/src/tableflow/write_service.py`、`backend/src/tableflow/db.py`、`data/template_fd_system.py`、`frontend/src/components/Cell.tsx`
- 可并行：测试文件、加载脚本、前端类型与样式（在 schema 稳定后）

## Notes

- 002 不实现计算字段：`v-dev` / `v-cond` 在本阶段仍是 text，003 负责改为 `computed` 并落 `computed_values`；`v-bug` 在 003 由 `v-bug-open` + `v-bug-clear` 取代
- 旧库不迁移：001 的随机行 id 与 enum 数组形态在 v0.3.0 废止
- 行 id 由 Agent 提供，系统不自动生成；改编号按「删旧建新」处理
