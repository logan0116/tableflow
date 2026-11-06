# Tasks: 只读状态看板（v0）

**Input**: Design documents from `/specs/001-readonly-dashboard/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/api.md](./contracts/api.md)

**Tests**: 本 feature 未要求 TDD。按 plan.md 的 Testing 决策，只保留后端两个 pytest 文件作为验收证据（接口契约、样例脚本），不写前端测试框架。

**Organization**: 按 spec 的三条用户故事分组，每条故事可独立完成与独立验证。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1 / US2 / US3）
- 每条任务都给出确切文件路径

## Path Conventions

- 后端：`backend/src/tableflow/`、`backend/scripts/`、`backend/tests/`
- 前端：`frontend/src/`、`frontend/src/components/`
- 数据：`data/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 两个工程的骨架与依赖锁定

- [X] T001 [P] 创建后端 uv 工程：`backend/pyproject.toml`（运行时依赖 fastapi、uvicorn；开发依赖 pytest、httpx）与 `backend/src/tableflow/__init__.py`
- [X] T002 [P] 创建前端 Vite 工程：`frontend/package.json`、`frontend/vite.config.ts`（`/api` 代理到 `http://localhost:8000`）、`frontend/tsconfig.json`、`frontend/index.html`、`frontend/src/main.tsx`
- [X] T003 [P] 安装并锁定依赖：`cd backend && uv sync`（生成 `backend/uv.lock`）、`cd frontend && npm install`（生成 `frontend/package-lock.json`）
- [X] T004 [P] 仓库忽略规则：在 `.gitignore` 增加 `data/*.db`、`data/*.db-wal`、`data/*.db-shm`、`node_modules/`、`dist/`、`.venv/`、`__pycache__/`
- [X] T005 [P] 样例数据 `data/seed.example.json`：2个项目、共14行，覆盖 `text` / `number` / `datetime` / `enum` 四种类型，并含 1 个 `visible: 0` 的字段

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 数据库、只读连接、查询、接口骨架、样例脚本——所有用户故事都依赖

**⚠️ CRITICAL**: 本阶段完成前不得开始任何用户故事

- [X] T006 配置模块 `backend/src/tableflow/config.py`：数据库路径读取环境变量 `TABLEFLOW_DB`，默认 `data/tableflow.db`
- [X] T007 只读连接 `backend/src/tableflow/db.py`：以 URI `file:...?mode=ro` 打开，连接后执行 `PRAGMA query_only=ON`；启动时校验 `PRAGMA journal_mode` 返回 `wal`，否则报错退出
- [X] T008 [P] 表结构与建库函数 `backend/src/tableflow/db.py`：按 data-model.md 建 `projects(id TEXT PK, name TEXT NOT NULL)`、`fields(id TEXT PK, table_id TEXT NOT NULL REFERENCES projects(id), name TEXT NOT NULL, type TEXT NOT NULL, options TEXT NULL, "order" INTEGER NOT NULL, visible INTEGER NOT NULL DEFAULT 1 CHECK(visible IN (0,1)))`、`row_records(id TEXT PK, table_id TEXT NOT NULL REFERENCES projects(id), data TEXT NOT NULL)`，以及索引 `idx_fields_table(table_id, "order")`、`idx_row_records_table(table_id, id)`；`type` 不加 CHECK 约束
- [X] T009 [P] 响应模型 `backend/src/tableflow/schemas.py`：`ProjectOut`、`FieldOut`、`RowOut`、`ProjectsOut`、`TableOut`，字段与 contracts/api.md 一致（`options` 为 `null` 或数组）
- [X] T010 只读查询 `backend/src/tableflow/repository.py`：`list_projects()` 返回全部项目；`get_table(project_id)` 返回字段（仅 `visible = 1`，按 `order` 升序、`id` 兜底）与行（按 `id` 升序），项目不存在返回 `None`
- [X] T011 FastAPI 应用骨架 `backend/src/tableflow/app.py`：注册路由、全响应加 `Cache-Control: no-store`、404 → `{"detail":"项目不存在"}`、数据库异常 → 503 `{"detail":"数据存储不可用"}`
- [X] T012 样例写入脚本 `backend/scripts/seed_data.py`：全量替换三张表；写入前校验 `row_records.data` 的键都属于同一项目的 `fields.id`，出现未知键报错退出且不写入；结束打印项目数、字段数、行数；支持 `--projects` / `--rows` 参数生成规模数据（用于 SC-005 的 20项目/500行 验证）
- [X] T013 [P] 样例脚本测试 `backend/tests/test_seed.py`：写入计数正确、未知键报错且库未被修改、重复执行计数不累加
- [X] T014 [P] 接口骨架测试 `backend/tests/test_api.py`：`GET /api/health` 返回 200 `{"status":"ok"}`；`POST /api/projects` 返回 405；响应头含 `Cache-Control: no-store`

**Checkpoint**: 库能建、样例能写、服务能起——用户故事可以开始

---

## Phase 3: User Story 1 - 打开即见当前状态 (Priority: P1) 🎯 MVP

**Goal**: 打开页面即拉取并渲染某项目的当前数据行，含加载、错误、数据三态

**Independent Test**: 改库中某值 → 重开页面看到新值；停掉后端 → 显示错误与重试且无旧数据

### Implementation for User Story 1

- [X] T015 [US1] 表格端点 `backend/src/tableflow/app.py`：`GET /api/projects/{project_id}/table`，调用 `repository.get_table`，返回 `project` + `fields` + `rows`，项目不存在返回 404
- [X] T016 [P] [US1] 前端接口层 `frontend/src/api.ts`：`fetchTable(projectId)` 使用 `fetch(..., { cache: 'no-store' })`，非 2xx 抛错并携带后端 `detail`；请求超时 5 秒（AbortController），超时按错误态处理
- [X] T017 [P] [US1] 响应类型 `frontend/src/types.ts`：与 contracts/api.md 对齐的 `Field` / `Row` / `TableResponse` 类型
- [X] T018 [US1] 三态容器 `frontend/src/App.tsx`：加载中显示中文提示；错误显示中文提示 + 重试按钮且清空已渲染数据；成功才渲染表格
- [X] T019 [US1] 表格组件 `frontend/src/components/DataTable.tsx`：TanStack Table `getCoreRowModel` 生成行模型，渲染原生 `<table>/<thead>/<tbody>/<tr>/<td>`，表头 `position: sticky`；列顺序直接用接口返回顺序；不设固定高度、不裁剪行（行数超出视口时由页面滚动查看，对应 FR-010）
- [X] T020 [P] [US1] 单元格渲染 `frontend/src/components/Cell.tsx`：`text` 原样、`number` 按原值、`datetime` 按浏览器本地时区（含时间 `YYYY-MM-DD HH:mm`，不含时间 `YYYY-MM-DD`）、`enum` 查 `options` 的 `value→label`；未识别类型按 `text` 渲染；空值显示空单元格
- [X] T021 [US1] 中文文案与文本选择 `frontend/src/App.tsx`：所有界面文案中文；不设置 `user-select: none`，单元格文本可选中复制
- [X] T022 [US1] 表格端点契约测试 `backend/tests/test_api.py`：字段按 `order` 升序、`visible = 0` 字段不返回、空项目返回 `rows: []` 且 `fields` 照常返回、未知项目 404

**Checkpoint**: 单项目看板可用，US1 可独立验收

---

## Phase 4: User Story 2 - 在多个项目之间切换 (Priority: P2)

**Goal**: 列出全部项目并支持切换，切换后只显示所选项目的数据

**Independent Test**: 两个项目来回切换，数据与列各自正确；切到空项目显示"暂无数据"且保留列头

### Implementation for User Story 2

- [X] T023 [US2] 项目列表端点 `backend/src/tableflow/app.py`：`GET /api/projects` 返回 `{"projects":[{"id","name"}]}`，按 `id` 升序
- [X] T024 [US2] 项目切换组件 `frontend/src/components/ProjectSwitcher.tsx`：列出项目名、高亮当前项、点击切换；项目多时可横向滚动
- [X] T025 [US2] 接入切换 `frontend/src/App.tsx`：首屏先取项目列表并默认选中第一个；切换时立即清空上一项目的行并显示加载提示，直到新数据到达（FR-013）；用请求序号或 AbortController 丢弃过期响应，只渲染当前所选项目（FR-014）
- [X] T026 [US2] 空项目状态 `frontend/src/App.tsx`：`rows` 为空时渲染保留列头的表格 + 中文"暂无数据"提示，不显示错误
- [X] T027 [US2] 项目列表端点契约测试 `backend/tests/test_api.py`：返回全部项目、空库返回空数组、响应头含 `no-store`

**Checkpoint**: US1 + US2 同时可用

---

## Phase 5: User Story 3 - 增删列只改数据 (Priority: P3)

**Goal**: 列的增删改只动数据，刷新即生效，无代码改动与重新部署

**Independent Test**: 在库中加一条 `fields` 记录并补值 → 刷新出现新列；删除该记录 → 刷新该列消失；`visible = 0` → 该列不显示但数据仍在

### Implementation for User Story 3

- [X] T028 [US3] 字段可见性与排序断言 `backend/tests/test_api.py`：新增 `visible = 0` 字段不返回、`order` 变更后返回顺序随之变化、删除 `fields` 行后该列从响应消失而 `row_records` 不变
- [X] T029 [US3] 前端无业务列名硬编码检查 `frontend/src/`：检索源码中不出现样例数据的列名与字段 id；列标题、顺序、可见性全部来自接口响应，检查结论记录在 quickstart 执行记录中
- [X] T030 [US3] 执行 quickstart V3 三步验证（加列 / 删列 / `visible = 0`）并记录结果，确认期间无代码改动、无服务重启；注意不要重跑 `seed_data.py`（全量替换会覆盖手工改动）

**Checkpoint**: 三条用户故事均可独立验收

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 验收口径、文档与边界核验

- [X] T031 [P] 运行说明 `README.md`：安装、样例初始化、启动后端与前端、验收入口（指向 quickstart.md）
- [ ] T032 [P] 性能验收记录 `specs/001-readonly-dashboard/quickstart.md`：按 V5 记录首屏 5 次中位数（目标 ≤500ms）、按 V6 记录滚动平均帧率与长任务（目标 ≥50fps、无 >50ms）
- [X] T033 宪法逐条核验：`POST /api/projects` 返回 405；两个业务接口响应头含 `Cache-Control: no-store`；前端源码无 `localStorage` / `sessionStorage` / `indexedDB` 写入业务数据；后端无写路由与写接口占位（原则 I、II、VII）；页面无 canvas 承载表格、依赖无 AG Grid / Handsontable / DataTables（原则 IV）；无 i18n 依赖与 locales 目录（原则 VI）
- [ ] T034 全流程回归：按 `specs/001-readonly-dashboard/quickstart.md` 的 V1–V7 逐条执行并记录结果；先用 `seed_data.py --projects 20 --rows 500` 造规模数据核对 SC-005，并核对 SC-006（打开到确认状态 ≤2 步）
- [X] T035 提交与清理：确认 `data/*.db*`、`node_modules/`、`dist/` 未入库；按产物拆分提交

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，可立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1，**阻塞全部用户故事**
- **User Story 1 (Phase 3)**: 依赖 Phase 2；无跨故事依赖
- **User Story 2 (Phase 4)**: 依赖 Phase 2 与 US1 的表格组件（复用 DataTable）
- **User Story 3 (Phase 5)**: 依赖 Phase 2 与 US1 的渲染链路（验证列驱动）
- **Polish (Phase 6)**: 依赖全部用户故事完成

### Within Each User Story

- 后端端点先于前端接入（T015 先于 T016–T021）
- 前端类型与接口层（T016、T017）可并行，之后才是容器与组件
- 测试任务写在实现之后，用于固化契约，不做 TDD 前置

### Parallel Opportunities

- Phase 1 的 T001–T005 全部可并行
- Phase 2 的 T008、T009、T013、T014 可并行（T010、T011 依赖 T008/T009）
- US1 中 T016 与 T017 可并行；T020 可与 T019 并行
- US2 与 US3 在 US1 完成后可并行推进

---

## Parallel Example: User Story 1

```bash
# 前端接口层与类型定义可同时开始：
Task: "前端接口层 frontend/src/api.ts"
Task: "响应类型 frontend/src/types.ts"

# 表格组件与单元格渲染可同时开始：
Task: "表格组件 frontend/src/components/DataTable.tsx"
Task: "单元格渲染 frontend/src/components/Cell.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1 Setup
2. 完成 Phase 2 Foundational（阻塞项，必须一次做完）
3. 完成 Phase 3 US1
4. **停下验收**：按 quickstart V1 验证"改值刷新见新值 + 停服务报错不残留旧数据"
5. 可作为 MVP 演示

### Incremental Delivery

1. Setup + Foundational → 地基就绪
2. US1 → 独立验收（单项目看板）
3. US2 → 独立验收（多项目切换）
4. US3 → 独立验收（增删列只改数据）
5. Polish → 性能与边界核验，交付

---

## Notes

- [P] 表示不同文件、无未完成依赖
- [Story] 标签用于回溯到 spec 的用户故事
- 每个故事独立可测；不要在 US1 里提前实现 US2 的切换逻辑
- 每个任务完成即提交，按产物路径拆分
- 避免：同一文件并发改动（`app.py`、`App.tsx`、`test_api.py` 是串行热点）
