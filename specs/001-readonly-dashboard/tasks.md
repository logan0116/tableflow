# Tasks: TableFlow 多维表格看板（v0）

**Input**: Design documents from `/specs/001-readonly-dashboard/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[data-model.md](./data-model.md)、[contracts/api.md](./contracts/api.md)、[contracts/agent-api.md](./contracts/agent-api.md)

**Tests**: 非 TDD。后端三个 pytest 文件作为契约与审计证据；前端不引入测试框架。

**Organization**: 按 spec 的三条用户故事分组：US1 多表浏览（P1）、US2 Agent 定义与写入（P2）、US3 关联与明细（P3）。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 确认后端依赖与 uv.lock：`backend/pyproject.toml` 已含 fastapi/uvicorn/pytest/httpx，`uv sync` 可复现
- [X] T002 确认前端依赖与锁文件：`frontend/package.json` 已含 react/vite/typescript/@tanstack/react-table
- [X] T003 确认忽略规则：`.gitignore` 覆盖 `.venv/`、`node_modules/`、`dist/`、`data/*.db*`

## Phase 2: Foundational（阻塞全部故事）

- [X] T004 重建表结构 `backend/src/tableflow/db.py`：`projects`、`tables`、`fields`、`row_records`、`write_audit` 五张表与索引（列定义见 data-model.md §1–§6）
- [X] T005 连接层 `backend/src/tableflow/db.py`：读连接（mode=ro + query_only）、写连接（WAL + foreign_keys）、`check_same_thread=False`
- [X] T006 [P] 响应模型 `backend/src/tableflow/schemas.py`：`ProjectOut`、`TableSummaryOut`、`FieldOut`、`RowOut`、`TableOut`、`RowDetailOut`
- [X] T007 读查询 `backend/src/tableflow/repository.py`：`list_projects`、`list_tables(project_id)`、`get_table(table_id)`（visible=1、order 升序、过滤隐藏列的值）、`get_row_detail(table_id, row_id)`
- [X] T008 样例脚本 `backend/src/tableflow/seed.py` 与 `backend/scripts/seed_data.py`：新格式（项目→表格→字段/行）；校验 relation 的 `options.table_id` 同项目、relation 值为字符串数组；全量替换业务四表
- [X] T009 [P] 样例数据 `data/seed.example.json`：2 个项目，其中一个含「任务」「人员」两张表并用 relation 互相关联

## Phase 3: US1 项目内浏览多张表格（P1）

- [X] T010 [US1] 项目接口 `backend/src/tableflow/app.py`：`GET /api/projects`
- [X] T011 [US1] 表格列表接口 `backend/src/tableflow/app.py`：`GET /api/projects/{project_id}/tables`，按 order 升序
- [X] T012 [US1] 表格数据接口 `backend/src/tableflow/app.py`：`GET /api/tables/{table_id}/table`，返回 table + fields + rows；不存在 404
- [X] T013 [P] [US1] 前端类型 `frontend/src/types.ts`：Project / TableSummary / Field / Row / TableResponse
- [X] T014 [P] [US1] 前端接口层 `frontend/src/api.ts`：`fetchProjects`、`fetchTables`、`fetchTable`（no-store，5s 超时）
- [X] T015 [US1] 表格切换组件 `frontend/src/components/TableTabs.tsx`：列出项目内表格、高亮当前、点击切换
- [X] T016 [US1] 三级导航 `frontend/src/App.tsx`：项目 → 表格 → 数据；切换表格立即清空旧行并显示加载提示，用请求序号丢弃过期响应
- [X] T017 [US1] 契约测试 `backend/tests/test_api.py`：项目/表格列表排序、字段 visible 与 order、空表、未知表 404、no-store 头

## Phase 4: US2 Agent 定义表与字段并写入（P2）

- [X] T018 [US2] 写服务 `backend/src/tableflow/write_service.py`：创建/重命名/删除表格（删除级联字段与行）
- [X] T019 [US2] 写服务 `backend/src/tableflow/write_service.py`：新增/修改/删除字段；relation 字段校验目标表同项目
- [X] T020 [US2] 写服务 `backend/src/tableflow/write_service.py`：新增/更新/删除数据行；relation 值必须为字符串数组
- [X] T021 [US2] 审计 `backend/src/tableflow/write_service.py`：每次写入（成功/失败/未知）写一条 `write_audit`，含 agent_id、action、target、payload、result
- [X] T022 [US2] 写路由 `backend/src/tableflow/app.py`：`/api/agent/*` 九个端点，要求请求头 `X-Agent-Id`，返回三态；校验失败 400 且不落库
- [X] T023 [P] [US2] 写接口测试 `backend/tests/test_agent_api.py`：建表→加字段→写行→读回；校验失败不落库；缺 `X-Agent-Id` 拒绝；审计条数与 result 正确
- [X] T024 [US2] 写接口契约文档 `specs/001-readonly-dashboard/contracts/agent-api.md`：请求/响应/错误/三态语义与审计字段

## Phase 5: US3 关联字段与明细查看（P3）

- [X] T025 [US3] 单行明细接口 `backend/src/tableflow/app.py`：`GET /api/tables/{table_id}/rows/{row_id}`，返回该行字段与值（只读）
- [X] T026 [P] [US3] 关联单元格 `frontend/src/components/Cell.tsx`：`relation` 类型渲染目标行 id（顿号分隔），可点击
- [X] T027 [US3] 明细弹层 `frontend/src/components/RelationModal.tsx`：点击标签拉取目标行明细，只读展示；目标行不存在显示"关联已失效"
- [X] T028 [US3] 接入弹层 `frontend/src/components/DataTable.tsx`：关联标签点击后打开弹层，弹层关闭后回到表格
- [X] T029 [US3] 关联测试 `backend/tests/test_api.py`：relation 字段透传、目标行明细接口、目标行被删后明细 404
- [X] T030 [US3] 关联样例核对 `data/seed.example.json`：任务表的"负责人"指向人员表的行，读接口返回数组

## Phase 6: Polish

- [X] T031 [P] 更新 `README.md`：三级结构、读写两套接口、关联语义、启动与验收
- [X] T032 [P] 更新 `specs/001-readonly-dashboard/quickstart.md`：V1–V8 验收步骤（多表/关联/写接口/审计）
- [X] T033 宪法逐条核验：人侧只有 GET、写接口全部有审计、no-store、无 canvas、无 i18n、无 localStorage、无写接口占位
- [ ] T034 全流程回归：按 quickstart 逐条执行并记录
- [ ] T035 性能验收：首屏 ≤500ms、滚动 ≥50fps、弹层 ≤300ms（DevTools 手工测量）
- [X] T036 提交与清理：`.gitignore` 生效、按产物拆分提交

## Dependencies & Execution Order

- Phase 1 → Phase 2（阻塞）→ US1 → US2 → US3 → Polish
- US2 依赖 US1 的读接口（写完后要用读接口验证）
- US3 依赖 US1 的表格渲染与 US2 的字段定义（relation 字段由写接口创建）
- `app.py`、`repository.py`、`App.tsx`、`test_api.py` 为串行热点

## Notes

- 数据模型已从"项目=表"改为"项目→表→字段/行"，旧库不可复用，需重新 seed
- 写接口只覆盖表/字段/行三类；不做权限、协作、视图（宪法非目标）
