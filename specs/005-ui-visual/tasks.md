# Tasks: 界面视觉打磨（v0.4.0）

**Input**: Design documents from `/specs/005-ui-visual/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、004 已合入（列宽记忆/密度/sticky/骨架/空状态）

**Tests**: 前端不引入测试框架；`npx tsc --noEmit` 类型门禁；计算样式与对比度核对 + 截图与 VL 评审；后端 pytest 回归门禁。

**Organization**: 按 spec 三条用户故事分组：US1 结构层次（P1）、US2 列宽自适应（P1）、US3 页面层级与弹层（P2）。

## Format: `[ID] [P] [Story] Description`

- `[P]`：可并行（不同文件、无未完成依赖）
- 每条任务带具体文件路径

## 验证命令

- 前端：`cd frontend && npx tsc --noEmit`
- 后端：`cd backend && .venv/bin/pytest -q`
- 对比度：`python3 scripts/contrast_check.py`（T015 新建，读 styles.css 变量）

> 沙箱内禁止 `uv run`；一律用 `backend/.venv/bin/python` 与 `backend/.venv/bin/pytest`。

## Phase 1: Setup

- [x] T001 记录基线：`cd frontend && npx tsc --noEmit` 通过；`cd backend && .venv/bin/pytest -q` 记录通过数；截取改前「版本管理」「独立规格需求」两表截图存入 `.tmp-shots/`
- [x] T002 用 VL 模型评审改前截图，记录问题清单（层次、截断、留白），作为改后对比基线

## Phase 2: US1 结构层次（P1）

**Goal**: 表头带、行分隔线、容器边框、悬停底的对比度达到 spec 阈值，且只改 CSS 变量。

**Independent Test**: 计算四个色值对比度，逐项对照 1.12/1.25/1.50/1.15。

- [x] T003 [US1] `frontend/src/styles.css`：调整 `--color-border`、`--color-border-soft`、`--color-header`、`--color-hover` 四个变量到目标值
- [x] T004 [P] [US1] `frontend/src/styles.css`：表头加 `font-weight: 600` 与 `letter-spacing: .01em`；表头下边线使用 `--color-border`
- [x] T005 [P] [US1] `frontend/src/styles.css`：`tbody tr` 悬停加 `transition: background-color 80ms ease`；按钮加 `transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease`
- [x] T006 [US1] `frontend/src/styles.css`：`.relation-link` 去掉常驻下划线，改 `text-decoration: none` + `:hover { text-decoration: underline }`

## Phase 3: US2 列宽自适应（P1）

**Goal**: 默认列宽按类型与表头估算，表头不再无意义截断。

**Independent Test**: 打开「独立规格需求」表，5 个 speckit 列表头完整可区分。

- [x] T007 [US2] `frontend/src/field-utils.ts`：新增 `estimateHeaderWidth(name)` 与 `defaultColumnWidth(field, isFirst)`，含 88–320 钳制与类型基础宽表
- [x] T008 [US2] `frontend/src/components/DataTable.tsx`：用 `defaultColumnWidth` 替换 `size: index === 0 ? 140 : 110`；列宽计算放 `useMemo`，依赖 `visibleFields`
- [x] T009 [P] [US2] `frontend/src/components/DataTable.tsx`：表头 `.th-label` 加 `title={field.name}`，截断时可见全文
- [x] T010 [P] [US2] `frontend/src/components/DataTable.tsx`：`defaultColumn.size` 兜底改 168；拖拽下限保持 48、上限 600（004 行为不变）
- [x] T011 [US2] 验证记忆优先：已存列宽的表打开后不被默认值覆盖（`columnWidths` 状态优先于 `size`）

## Phase 4: US3 页面层级与弹层（P2）

**Goal**: 页头显示「项目 › 表」与行数；卡片有面板感；明细弹层竖向键值对。

**Independent Test**: 切换项目/表页头跟随；1280×800 与 1920×1080 下布局正常；60 字文本完整换行。

- [x] T012 [US3] `frontend/src/App.tsx`：`h1` 改为页头结构（项目名 › 表名），右侧「共 N 条 / M / N 条」；项目名与表名取自现有状态
- [x] T013 [US3] `frontend/src/styles.css`：`.page-header` 布局、`.crumb-*` 样式、`.page-count` 样式
- [x] T014 [P] [US3] `frontend/src/styles.css`：`.table-frame` 加圆角与浅阴影；`.table-wrap` 最大高改 `calc(100vh - 200px)`，`@media (max-height: 600px)` 退化 `70vh`
- [x] T015 [P] [US3] `frontend/src/components/RelationModal.tsx`：改为竖向键值对（`.kv-grid` / `.kv-item` / `.kv-label` / `.kv-value`）；值换行全文
- [x] T016 [P] [US3] `frontend/src/styles.css`：`.kv-*` 样式，`grid-template-columns: repeat(auto-fill, minmax(320px, 1fr))`
- [x] T017 [US3] `frontend/src/components/RelationModal.tsx`：Esc 关闭 + 遮罩 `onMouseDown` 关闭（避免拖选文本误关）
- [x] T018 [P] [US3] `frontend/src/styles.css`：字体栈显式加 `PingFang SC, Hiragino Sans GB, Noto Sans CJK SC, Microsoft YaHei`

## Phase 5: 验证与发布

- [x] T019 `cd frontend && npx tsc --noEmit` 零错误
- [x] T020 `cd backend && .venv/bin/pytest -q` 全绿
- [x] T021 计算四项对比度，对照 spec SC-001，结果记入 `specs/005-ui-visual/quickstart.md`
- [x] T022 截图改后两表 + 明细弹层，用 VL 模型评审，与 T002 基线对比
- [x] T023 性能复核：14 行首屏 ≤500ms、滚动 ≥50fps、无 >50ms 长任务
- [x] T024 `frontend/package.json`、`deploy/docker-compose.yml` 版本号升到 0.4.0
- [x] T025 更新 README 的版本与验收说明（如涉及）
- [x] T026 git commit + tag `v0.4.0`
- [ ] T027 部署 155：`bash deploy/deploy_155.sh`（不 seed）
- [ ] T028 tableflow 更新 005-AR 与 v0.4.0 状态，确认发布条件=是，发布状态改 released

## Dependencies

```text
T001 → T002 → T003..T006 (US1)
              T007 → T008 → T009..T011 (US2)
              T012..T018 (US3，可与 US2 并行)
T003..T018 → T019..T023 → T024..T028
```
