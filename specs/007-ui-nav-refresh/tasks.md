# Tasks: 左侧项目导航与全局刷新（v0.5.0）

**Input**: Design documents from `/specs/007-ui-nav-refresh/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、006 已合入

**Tests**: 前端不引入测试框架；`npx tsc --noEmit` 类型门禁；`npm run build`；浏览器手工验收；后端 `pytest` 回归门禁。

## Format: `[ID] [P?] [Story] Description`

## 验证命令

- 前端类型：`cd frontend && npx tsc --noEmit`
- 前端构建：`cd frontend && npm run build`
- 后端回归：`cd backend && .venv/bin/pytest -q`
- 对比度：`python3 scripts/contrast_check.py`
- 性能：`python3 scripts/perf_check.py http://127.0.0.1:5173/ --rows 14`

## Phase 1: 布局与导航

- [x] T001 `frontend/src/styles.css`：新增 `.app-shell`（Grid 216px + minmax(0,1fr)、max-width 1500、min-height 100vh）、`.sidebar`（sticky、100vh、内部滚动）、`.app-main`；移除 `.app`
- [x] T002 `frontend/src/components/ProjectNav.tsx`：新建竖排项目导航，项目按钮全宽、`aria-current="page"`、加载/空状态占位
- [x] T003 `frontend/src/App.tsx`：根结构改为侧栏 + `main.app-main`；引入 `ProjectNav`，删除 `ProjectSwitcher` 引用
- [x] T004 `frontend/src/components/ProjectSwitcher.tsx`：删除文件
- [x] T005 `frontend/src/styles.css`：删除 `.switcher` 规则，新增 `.project-nav` / `.brand` 样式

## Phase 2: 刷新链路

- [x] T006 `frontend/src/App.tsx`：移除 `reloadKey`，新增 `refreshAll()`（项目→表格→当前表），用 `useRef` 读最新选中值，回写前比对
- [x] T007 `frontend/src/App.tsx`：首次加载与项目/表格切换仍走 loading；刷新路径保留现有数据，不闪骨架
- [x] T008 `frontend/src/App.tsx`：筛选清空时机改为 `tableId` 变化；刷新保留筛选词
- [x] T009 `frontend/src/App.tsx`：页头右侧动作区加刷新按钮（`is-loading`、`disabled`、`aria-busy`），EmptyState 的「重试」复用 `refreshAll`
- [x] T010 `frontend/src/styles.css`：刷新按钮样式与旋转动画，`prefers-reduced-motion` 下关闭动画

## Phase 3: 验证

- [x] T011 `npx tsc --noEmit` 零错误、`npm run build` 成功
- [x] T012 `pytest -q` 全绿（不动后端，回归门禁）
- [x] T013 浏览器核验：项目在左侧且选中态正确；20项目时侧栏滚动；1280×800无横向溢出
- [x] T014 浏览器核验：停在第3张表 + 筛选词，点刷新后仍在第3张表、筛选词保留；Network 显示3个GET各1次
- [x] T015 浏览器核验：刷新中按钮禁点且 `aria-busy`；空态/错误态下按钮可点；项目被删时回退首项
- [x] T016 `python3 scripts/contrast_check.py` 5/5；`perf_check.py` 首屏与滚动不回退
- [x] T017 tableflow 看板回写：007-AR 场景数/任务数/implement=done；v0.5.0 测试进度与文档状态
- [x] T018 发布 v0.5.0：版本号四文件、构建、`git tag v0.5.0`、部署 155（发布前备份，不带`--seed`）
- [x] T019 DEP-03-BR：去掉`.app-shell`的`max-width`居中，1915×1070与1280×800双视口核验贴边与无溢出

## Dependencies

```text
T001..T005 → T006..T010 → T011..T016 → T017 → T018 → T019
```
