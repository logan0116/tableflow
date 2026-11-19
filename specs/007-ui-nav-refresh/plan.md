# Implementation Plan: 左侧项目导航与全局刷新（v0.5.0）

**Branch**: `007-ui-nav-refresh` | **Date**: 2026-11-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-ui-nav-refresh/spec.md`

## Summary

前端布局从单列改为「左侧项目导航 + 右侧内容」两栏：项目从页头下方的横向按钮迁到侧栏竖排导航，当前项目带选中态与 `aria-current="page"`；页头右侧新增「刷新」按钮，用一条显式刷新链（项目→当前项目表格→当前表格数据）取代原来的 `reloadKey` 副作用链，刷新时保留当前项目、表格与筛选关键字，旧内容不闪骨架。不新增依赖、不改后端接口与数据模型。

## Technical Context

**Language/Version**: TypeScript 5.6 + Node 24（前端）；后端不改

**Primary Dependencies**: React 18、Vite 6、@tanstack/react-table（已引入）；不新增依赖

**Storage**: 不变，仍无读缓存；UI 偏好键（列宽、密度）不动

**Testing**: 前端不引入测试框架；`npx tsc --noEmit` 类型门禁；`npm run build`；浏览器手工验收（布局、网络请求计数、刷新后状态保留）；后端 `pytest -q` 回归门禁；`scripts/contrast_check.py`

**Target Platform**: 桌面 Chrome / Edge，Linux 局域网访问

**Project Type**: web application（仅前端）

**Performance Goals**: 首屏 ≤500ms、滚动 ≥50fps 不回退；刷新只发3个GET，不重复请求

**Constraints**: DOM 表格；无新依赖；中文单语；不改接口契约；不做移动端适配；无读缓存

**Scale/Scope**: 20项目 / 每项目10表 / 单表500行；改2个组件、1个入口、1个样式表

## Constitution Check

*GATE: 对照宪法 v7.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 只改渲染层，不新增写接口或本地写控件；刷新只是 GET 重拉 | PASS |
| II 无读缓存 | 刷新即现拉；不引入 IndexedDB/localStorage 业务数据；localStorage 仍只存列宽与密度 | PASS |
| III Schema 驱动 | 导航与页头只用接口返回的 `id` 与 `name`，不硬编码项目名、列名、状态值 | PASS |
| IV DOM 表格 | 表格渲染不变，仍是原生 table + TanStack Table；布局与按钮均为 CSS | PASS |
| V 固定技术栈 | 不新增依赖，不改后端；仍是 FastAPI + SQLite + React + Vite | PASS |
| VI 中文单语 | 新文案「项目」「刷新」「刷新中」「暂无项目」全部中文；无 i18n | PASS |
| VII 边界收敛 | 明确不做移动端/窄屏适配；未引入视图体系、权限、附件等非目标能力 | PASS |

## Design

### 1. 两栏布局

- `.app-shell` 用 CSS Grid：`grid-template-columns: 216px minmax(0, 1fr)`，`min-height: 100vh`；不设 `max-width`，侧栏贴视口左缘、内容占满剩余宽度。
- 侧栏 `position: sticky; top: 0; height: 100vh; overflow-y: auto`，右侧边框用 `--color-border-soft`，与内容区分层；`align-items: start` 让 sticky 生效。
- 内容区 `min-width: 0`，防止宽表格把 Grid 列撑破；`padding` 沿用现有节奏。
- 不写 media query：桌面专用，窄窗口由内容区横向滚动兜底（宪法非目标）。

### 2. 组件

- 删除 `ProjectSwitcher.tsx`，新增 `ProjectNav.tsx`：竖排 `nav`，项目按钮全宽、左对齐、单行省略；选中态用 `background: #eef6ff` + `--color-accent`，`aria-current="page"`；`projects === null` 时显示「加载中…」，空列表显示「暂无项目」。
- 侧栏顶部品牌块：`TableFlow` + 「只读看板」，用 `border-soft` 分隔。
- 刷新按钮放在 `App` 页头动作区（行数统计同组），不单独建组件；`is-loading` 时图标旋转、文案「刷新中」、`disabled` 与 `aria-busy="true"`。

### 3. 刷新编排

把 `reloadKey` 从三个 `useEffect` 依赖里移除，改为显式 `refreshAll()`：

```text
fetchProjects → setProjects
  → 当前项目仍存在 ? 用它 : 列表首个
  → fetchTables(pid) → setTables
    → 当前表格仍存在 ? 用它 : 该项目首表
    → fetchTable(tid) → setTableState
```

- 用 `useRef` 记录最新 `projectId` / `tableId`，避免闭包读到过期值；成功回写前再比对一次，后发起的导航优先。
- 失败按阶段进入对应错误态（项目/表格/表格数据），与 EmptyState 的「重试」共用同一条链路。
- 刷新不清空 `projects` / `tables` / `tableState`；仅首次加载与切换项目/表格时进入 loading，避免刷新闪骨架。
- 筛选清空时机从「加载表格」改为「tableId 变化」，刷新保留关键字。
- 刷新只发3个GET（无表格项目只发2个），无重复请求。

### 4. 回退与边界

- 当前项目被删除 → 切到列表首个项目，其表格再按同样规则回退。
- 当前表格被删除 → 切到该项目首表。
- 项目为空/加载失败 → 侧栏保留占位，刷新仍可用。
- 刷新进行中按钮禁点，不产生并发刷新。

## Files

| 文件 | 改动 |
|---|---|
| `frontend/src/App.tsx` | 两栏布局、刷新链、页头动作区、筛选清空时机 |
| `frontend/src/components/ProjectNav.tsx` | 新增：左侧竖排项目导航 |
| `frontend/src/components/ProjectSwitcher.tsx` | 删除 |
| `frontend/src/styles.css` | `.app-shell` / `.sidebar` / `.project-nav` / 刷新按钮；移除 `.switcher` 与 `.app` |
| `specs/007-ui-nav-refresh/*` | 本规格、计划、任务与验收记录 |

## 风险与对策

| 风险 | 对策 |
|---|---|
| Grid 子项默认拉伸导致侧栏 sticky 失效 | 容器 `align-items: start`，侧栏自身 `height: 100vh` |
| 宽表格把内容区挤破 | 内容区 `min-width: 0`，表格容器保持 `overflow: auto` |
| 刷新与导航并发写回旧数据 | `useRef` 读最新选中值 + 回写前比对 |
| 刷新闪骨架导致体验倒退 | 刷新路径不置 loading，仅替换数据 |
| 表头高度变化影响首屏基线 | 页头结构不变，仅右侧加按钮；跑 `perf_check.py` 复核 |

## 验证方式

1. `cd frontend && npx tsc --noEmit`、`npm run build`。
2. `cd backend && .venv/bin/pytest -q`。
3. 本地起后端与 Vite，浏览器核验：侧栏选中态、项目切换、刷新后停在原表且筛选保留、网络请求计数、空/错误态按钮可用。
4. `python3 scripts/contrast_check.py`；`python3 scripts/perf_check.py` 复核基线。
