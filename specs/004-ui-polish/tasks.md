# Tasks: 界面体验打磨（v0.3.0）

**Input**: Design documents from `/specs/004-ui-polish/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、002 的 enum `tone` 已合入、003 的 `computed_meta` 已合入、宪法 v6.0.0

**Tests**: 前端不引入测试框架；`npx tsc --noEmit` 作为类型门禁，DOM/计算样式核对 + quickstart 手工验收；后端 pytest 作为回归门禁。

**Organization**: 按 spec 的七条用户故事分组：US1 状态色标签（P1）、US2 数字对齐（P1）、US3 首列 sticky（P2）、US4 加载骨架（P2）、US5 空状态（P2）、US6 行密度与斑马纹（P3）、US7 列宽记忆（P2）。

## Format: `[ID] [P?] [Story] Description`

- `[P]`：可并行（不同文件、无未完成依赖）
- `[Story]`：仅用户故事阶段使用
- 每条任务必须带具体文件路径

## 验证命令

- 后端：`cd backend && .venv/bin/pytest -q`
- 前端：`cd frontend && npx tsc --noEmit`

> 沙箱内禁止 `uv run`（需要写 `~/.cache/uv`）；一律使用 `backend/.venv/bin/python` 与 `backend/.venv/bin/pytest`。

## Phase 1: Setup

- [ ] T001 确认前置：`frontend/src/types.ts` 已有 `EnumOption`/`FieldOptions`/`ComputedMeta`；`frontend/src/components/Cell.tsx` 已按 tone 渲染基础标签；先跑 `cd frontend && npx tsc --noEmit` 记录基线
- [ ] T002 确认基线性能（`frontend/src/components/DataTable.tsx`）：按 001 方法记录当前 14 行首屏与滚动帧率，作为 004 对比基线

## Phase 2: Foundational（阻塞全部故事）

- [ ] T003 设计令牌 `frontend/src/styles.css`：新增颜色、tone 五色、行高、列宽上下限 CSS 变量；`prefers-reduced-motion` 降级规则
- [ ] T004 [P] UI 偏好模块 `frontend/src/ui-prefs.ts`：`readColumnWidths` / `writeColumnWidths` / `clearColumnWidths` / `readDensity` / `writeDensity`；JSON 解析失败、越界、超限、localStorage 不可用全部静默降级
- [ ] T005 [P] 列宽 hook `frontend/src/hooks/useColumnWidths.ts`：按 `tableId` 读取/恢复/写入/重置；debounce 300ms；字段删除后忽略条目
- [ ] T006 [P] 密度 hook `frontend/src/hooks/useDensity.ts`：`comfortable`/`compact` 状态与持久化；默认舒适
- [ ] T007 空状态组件 `frontend/src/components/EmptyState.tsx`：`kind` 枚举（`loading`/`no-projects`/`no-tables`/`no-rows`/`no-fields`/`error`），固定中文文案，仅 `error` 显示重试
- [ ] T008 骨架组件 `frontend/src/components/TableSkeleton.tsx`：表头 + 8 行占位，列数由 props 决定，`aria-hidden`，reduced-motion 静态

## Phase 3: US1 状态色标签（P1）

**Goal**: enum 按 tone 渲染标签，color 可覆盖，无业务值硬编码。

**Independent Test**: 5 种 tone 背景色不同；改 options tone 后颜色变化；grep 业务值 0 命中。

- [ ] T009 [US1] 标签组件 `frontend/src/components/EnumTag.tsx`：`enum-tag enum-tone-{tone}`；tone 未知回退 neutral；合法 `color={bg,fg}` 内联覆盖
- [ ] T010 [US1] 接入 `frontend/src/components/Cell.tsx`：enum 值改为渲染 `EnumTag`；布尔计算字段复用 `EnumTag`（是/否）；保留 `cell-nowrap`
- [ ] T011 [US1] 样式 `frontend/src/styles.css`：`.enum-tag` 基础样式 + 5 个 tone 类；对比度按 AA
- [ ] T012 [US1] 硬编码检查：`frontend/src` 中 grep `released|planned|dropped|待办|已完成|未开始` 命中数为 0，结果写入验收记录

## Phase 4: US2 数字右对齐与等宽（P1）

**Goal**: 数字列右对齐 + tabular-nums；列头同向。

**Independent Test**: 计算样式为 `text-align:right` 且 `font-variant-numeric: tabular-nums`。

- [ ] T013 [US2] 单元格 `frontend/src/components/Cell.tsx`：number 与 computed number（count/percent/sum）加 `cell-number` 类；空值也保留占位
- [ ] T014 [US2] 列头对齐 `frontend/src/components/DataTable.tsx`：按字段类型/computed kind 给 `th` 加 `th-number`
- [ ] T015 [US2] 样式 `frontend/src/styles.css`：`.cell-number` 与 `.th-number` 右对齐 + 等宽数字

## Phase 5: US3 首列 sticky 与横向滚动阴影（P2）

**Goal**: 首列固定，滚动阴影纯 CSS，斑马纹/hover 下无白块。

**Independent Test**: 滚动 200px 首列可见；scrollLeft 边界阴影消失；首列背景与行一致。

- [ ] T016 [US3] 首列标记 `frontend/src/components/DataTable.tsx`：第一个可见字段的表头与单元格加 `is-first`
- [ ] T017 [US3] sticky 样式 `frontend/src/styles.css`：`.is-first` sticky + `--row-bg`；表头 z-index 高于单元格
- [ ] T018 [US3] 滚动阴影 `frontend/src/styles.css`：`.table-wrap` 多层 background 渐变（local + scroll），不监听 scroll
- [ ] T019 [US3] 固定布局 `frontend/src/components/DataTable.tsx` + `frontend/src/styles.css`：`table-layout: fixed` + 显式列宽，避免 sticky 与自动布局冲突
- [ ] T020 [US3] 性能核对（`frontend/src/components/DataTable.tsx`）：连续滚动 5 秒，确认 ≥50fps、无 >50ms 长任务；结果写入验收记录

## Phase 6: US4 加载骨架（P2）

**Goal**: 表格加载中显示同构骨架，不闪空状态。

**Independent Test**: 延迟 1s，骨架存在且无「暂无数据」；返回后骨架移除。

- [ ] T021 [US4] 接入 `frontend/src/App.tsx`：表格 `loading` 状态渲染 `TableSkeleton`，列数取当前字段数；项目/表格区用轻量占位条
- [ ] T022 [US4] 骨架样式 `frontend/src/styles.css`：`.skeleton` 占位条与 shimmer；`prefers-reduced-motion` 下静态
- [ ] T023 [US4] 边界 `frontend/src/App.tsx`：字段数为 0 时不显示骨架，转 `no-fields` 空状态；加载失败不显示骨架

## Phase 7: US5 空状态区分（P2）

**Goal**: 五种状态文案互斥，仅失败有重试。

**Independent Test**: 五种场景文案两两不同；仅失败有重试按钮。

- [ ] T024 [US5] 接入 `frontend/src/App.tsx`：项目空 → `no-projects`；表格空 → `no-tables`；行空 → `no-rows`；失败 → `error` + 重试；加载 → 骨架/加载中
- [ ] T025 [US5] 样式 `frontend/src/styles.css`：`.empty-state` 统一排版；错误态与空态视觉区分（颜色/图标文字）
- [ ] T026 [US5] 回归 `frontend/src/App.tsx`：空表保留列头（`DataTable` 的空行逻辑）；空项目保留项目切换器

## Phase 8: US6 行密度两档与斑马纹（P3）

**Goal**: 舒适/紧凑切换，持久化；偶数行浅底，hover 覆盖。

**Independent Test**: 行高 ≥40 / ≤32；刷新保持；偶数行底色不同。

- [ ] T027 [US6] 工具栏 `frontend/src/components/TableToolbar.tsx`：密度切换按钮组 + 重置列宽入口（US7 复用）
- [ ] T028 [US6] 接入 `frontend/src/App.tsx` + `frontend/src/components/DataTable.tsx`：`data-density` 传给容器；切换不请求数据
- [ ] T029 [US6] 样式 `frontend/src/styles.css`：两档行高变量；斑马纹与 hover 通过 `--row-bg`；sticky 首列同步
- [ ] T030 [US6] 持久化 `frontend/src/hooks/useDensity.ts`：刷新后恢复；非法值回退舒适

## Phase 9: US7 列宽记忆（P2）

**Goal**: 拖拽列宽，按表+字段记忆，只存 UI 偏好。

**Independent Test**: 拖到 240px 刷新仍 240px；localStorage 只含 id 与数字；非法条目忽略。

- [ ] T031 [US7] 列宽接入 `frontend/src/components/DataTable.tsx`：`enableColumnResizing`、`columnResizeMode: "onChange"`、`defaultColumn` 48–600、首列 200
- [ ] T032 [US7] 拖拽手柄 `frontend/src/components/DataTable.tsx` + `frontend/src/styles.css`：表头 resize handle，`cursor: col-resize`，键盘不可达时不影响使用
- [ ] T033 [US7] 恢复与保存 `frontend/src/hooks/useColumnWidths.ts`：表切换读取并应用；拖动后 debounce 写入；字段不存在忽略
- [ ] T034 [US7] 重置入口 `frontend/src/components/TableToolbar.tsx`：清除当前表记忆并恢复默认
- [ ] T035 [US7] 净化核对：手工写入损坏 JSON、700px、0px、201 条记录，确认回退/钳制/裁剪且不报错；localStorage 内容与当前 10 行数据逐值比对，命中 0

## Phase 10: Polish

- [ ] T036 [P] 文档 `README.md`：状态色、列宽记忆、密度、骨架与空状态说明
- [ ] T037 [P] 验收指南 `specs/004-ui-polish/quickstart.md`：V1–V8 手工步骤（tone、数字对齐、sticky、骨架、空状态、密度、列宽、性能）
- [ ] T038 宪法逐条核验：localStorage 只存 UI 偏好、无 canvas/虚拟滚动/重型库、无业务值硬编码、无新依赖、中文文案
- [ ] T039 前端类型门禁：`cd frontend && npx tsc --noEmit`，要求 0 error
- [ ] T040 后端回归：`cd backend && .venv/bin/pytest -q`，要求 0 failed（本 spec 不改后端）
- [ ] T041 性能验收（`frontend/src/App.tsx`）：14 行首屏 ≤500ms、滚动 ≥50fps、无 >50ms 长任务；与 T002 基线对比
- [ ] T042 提交与清理：按产物拆分提交（样式令牌 / 组件 / hooks / 文档），确认未提交 `dist/`、`node_modules/`

## Phase 10: 行高上限（FR-031 补充，2026-11-09）

**Independent Test**: 最长文本单元格（「测试进度」MeterSphere 描述）渲染后行高 ≤40px（舒适）/ ≤28px（紧凑），文本单行省略号，`title` 含全文。

- [ ] T043 [US6] 单元格单行截断：`frontend/src/components/Cell.tsx` 增加 `truncate` 开关，text/datetime 分支输出 `title`；`DataTable.tsx` 主表传 `truncate`；`styles.css` 加 `.cell-text`（nowrap + ellipsis）与 `.table-frame tbody td { white-space: nowrap }`
- [ ] T044 [US6] 行高固定：`styles.css` 给两档密度加 `--row-height`（40px / 28px），`tbody td` 以之兜底，长文本不得撑高
- [ ] T045 [US6] 验收：155 线上取最长文本行，行高 ≤40px（舒适）/≤28px（紧凑），`title` 全文可读；关联明细弹层仍换行显示全文

## Dependencies & Execution Order

- Phase 1 → Phase 2（阻塞）→ US1 / US2 → US3 → US4 / US5 → US6 → US7 → Polish
- US3 依赖 US6 的 `--row-bg` 机制（可先做 US6 的变量，再做 US3 的 sticky）
- US7 依赖 US3 的固定布局；US6 的工具栏与 US7 的重置入口同一文件，需串行
- 串行热点：`frontend/src/styles.css`、`frontend/src/components/DataTable.tsx`、`frontend/src/App.tsx`
- 可并行：`EnumTag.tsx`、`EmptyState.tsx`、`TableSkeleton.tsx`、`ui-prefs.ts`、两个 hook

## Notes

- 004 不改接口、不改业务数据；只改渲染与 UI 偏好
- localStorage 键统一 `tableflow.ui.*`，内容只含表 id、字段 id 与数字，不含任何业务值
- 首列 sticky 只针对 PC 桌面；移动端适配仍属宪法非目标
- 计算字段的语义与落库由 003 交付；004 只负责视觉呈现与覆盖标记样式
