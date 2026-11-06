# Implementation Plan: 界面体验打磨（v0.3.0）

**Branch**: `004-ui-polish` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-ui-polish/spec.md`

## Summary

在不改接口与业务数据的前提下，把看板从"能看"打磨到"好扫"：enum 按 tone 渲染状态标签；数字右对齐 + 等宽；首列 sticky + 纯 CSS 横向滚动阴影；加载骨架；五种空状态区分；行密度两档 + 斑马纹；列宽按「表 + 字段」记忆到 localStorage（只存 UI 偏好）。所有视觉改动走 CSS 变量与通用组件，不引入新依赖，不硬编码业务值。

## Technical Context

**Language/Version**: TypeScript 5.x + Node 24（前端）；后端不改

**Primary Dependencies**: React 18、Vite、TypeScript、@tanstack/react-table（已引入）；不新增依赖

**Storage**: 浏览器 localStorage，仅 `tableflow.ui.columnWidths.v1` 与 `tableflow.ui.density.v1`；业务数据仍每次现拉

**Testing**: 前端不引入测试框架；`npx tsc --noEmit` 作为类型门禁；DOM/计算样式核对 + quickstart 手工验收；后端 `pytest` 作为回归门禁

**Target Platform**: Chrome / Edge 桌面浏览器（近两年版本），Linux 局域网访问

**Project Type**: web application（仅前端）

**Performance Goals**: 14 行首屏 ≤500ms；关闭硬件加速滚动 ≥50fps、无 >50ms 长任务；列宽拖拽不触发数据请求

**Constraints**: DOM 表格、无 canvas/虚拟滚动/重型表格库；localStorage 只存 UI 偏好；中文单语；不改变接口契约

**Scale/Scope**: 单表 ≤500 行、≤20 列；本 spec 新增 4 个组件/模块、改 4 个现有文件、1 个样式表

## Constitution Check

*GATE: 对照宪法 v6.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 不新增任何写接口；本 spec 只改渲染；003 的人发起入口不在本 spec 扩展 | PASS |
| II 无读缓存 | 业务数据仍每次现拉；localStorage 只存列宽/密度，键名 `tableflow.ui.*`，内容不含业务值 | PASS |
| III Schema 驱动 | 状态色按 `options.items[].tone`；数字对齐按 `type`；不硬编码业务列名或状态值 | PASS |
| IV DOM 表格 | 仍是原生 table + TanStack Table；sticky/阴影/斑马纹均为 CSS；无 canvas/虚拟滚动 | PASS |
| V 固定技术栈 | 不新增依赖；沿用 React + Vite + TypeScript | PASS |
| VI 中文单语 | 新增文案全部中文；无 i18n 库 | PASS |
| VII 边界收敛 | 只做已列明的 7 项视觉能力；不做移动端、主题、视图体系、列显示配置 | PASS |

无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/004-ui-polish/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── styles.css                  # 设计令牌、状态标签、sticky、滚动阴影、斑马纹、骨架、空状态
│   ├── types.ts                    # ComputedMeta（003 已加则复用）、UiDensity
│   ├── ui-prefs.ts                 # 新增：localStorage 读写与净化（列宽、密度）
│   ├── hooks/
│   │   ├── useColumnWidths.ts      # 新增：列宽状态、恢复、持久化、重置
│   │   └── useDensity.ts           # 新增：密度状态与持久化
│   ├── components/
│   │   ├── DataTable.tsx           # 列宽、sticky、斑马纹、密度、滚动容器
│   │   ├── Cell.tsx                # 数字对齐、computed 布尔、覆盖标记
│   │   ├── EnumTag.tsx             # 新增：tone/color 状态标签
│   │   ├── TableSkeleton.tsx       # 新增：表头 + 8 行骨架
│   │   ├── EmptyState.tsx          # 新增：五种状态统一展示
│   │   ├── TableToolbar.tsx        # 新增：密度切换、重置列宽
│   │   ├── ProjectSwitcher.tsx     # 不变
│   │   ├── TableTabs.tsx           # 不变
│   │   └── RelationModal.tsx       # 只读，003 已扩展
│   ├── App.tsx                     # 状态机接入骨架/空状态/工具栏
│   └── api.ts                      # 不变
└── package.json                    # 不变（不新增依赖）
```

**Structure Decision**: UI 偏好独立成 `ui-prefs.ts` + 两个 hook，避免 localStorage 读写散落在组件里；视觉组件（EnumTag / TableSkeleton / EmptyState / TableToolbar）保持无业务逻辑，只接收 props。

## Design Details

### 1. 设计令牌（`frontend/src/styles.css`）

```css
:root {
  --surface: #ffffff;
  --surface-alt: #f7f8fa;
  --surface-hover: #eef4ff;
  --border: #e5e7eb;
  --text: #1f2329;
  --text-muted: #6b7280;

  --tone-neutral-bg: #f2f3f5;  --tone-neutral-fg: #4e5969;
  --tone-info-bg:    #e8f3ff;  --tone-info-fg:    #1d4ed8;
  --tone-success-bg: #e8f7ee;  --tone-success-fg: #1a7f37;
  --tone-warning-bg: #fff7e6;  --tone-warning-fg: #b45309;
  --tone-danger-bg:  #fdecec;  --tone-danger-fg:  #b42318;

  --row-height-comfortable: 44px;
  --row-height-compact: 30px;
  --col-min: 48px;
  --col-max: 600px;
}
```

- 颜色只在这里定义；组件通过 `enum-tone-*` 类消费，不写死色值。
- 数值与颜色对比度按 WCAG AA 校准（正文 ≥4.5:1）。

### 2. 状态标签（`EnumTag.tsx` + `Cell.tsx`）

```tsx
<EnumTag tone={option.tone} color={option.color} label={option.label} />
```

- 类名：`enum-tag enum-tone-{tone}`；`tone` 不在五个值内 → `neutral`。
- `color` 合法时内联 `style={{ background, color }}` 覆盖；非法（非 `#rgb/#rrggbb`）忽略。
- 布尔计算字段复用 `EnumTag`：`true` → `success` + `true_label`，`false` → `danger` + `false_label`。
- 覆盖标记：`computed_meta[fieldId].overridden` 为真时追加 `enum-tag-overridden` 小标记「已覆盖」，`title` 显示原因。

### 3. 数字对齐（`Cell.tsx` + `DataTable.tsx`）

- number 与 computed number 单元格加 `cell-number`：`text-align: right; font-variant-numeric: tabular-nums; font-feature-settings: "tnum";`。
- 列头按字段类型加 `th-number` 右对齐；computed 的 number kind（count/percent/sum）同样右对齐。
- 空值仍渲染 `<span className="cell-number" />`，保持列宽。

### 4. 首列 sticky + 滚动阴影（`DataTable.tsx` + `styles.css`）

- 第一列（`order` 最小且 `visible=1`）的表头与单元格加 `is-first`：
  ```css
  .is-first { position: sticky; left: 0; z-index: 2; background: var(--row-bg, var(--surface)); }
  thead .is-first { z-index: 3; }
  ```
- 行底色通过 CSS 变量传递，保证 sticky 首列与整行一致：
  ```css
  tbody tr { --row-bg: var(--surface); }
  tbody tr:nth-child(even) { --row-bg: var(--surface-alt); }
  tbody tr:hover { --row-bg: var(--surface-hover); }
  ```
- 滚动阴影纯 CSS（不监听 scroll）：
  ```css
  .table-wrap {
    overflow-x: auto;
    background:
      linear-gradient(to right, var(--surface), transparent) left center / 16px 100% no-repeat local,
      linear-gradient(to left, var(--surface), transparent) right center / 16px 100% no-repeat local,
      radial-gradient(farthest-side at 0 50%, rgba(0,0,0,.12), transparent) left center / 12px 100% no-repeat scroll,
      radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.12), transparent) right center / 12px 100% no-repeat scroll;
  }
  ```
- `table-layout: fixed` + 每列显式宽度，避免 sticky 与自动布局互相挤压。
- 实现注意：行底色会遮挡容器背景渐变；优先用容器 `padding-inline` 让阴影落在内容区外，或用不接收指针事件的覆盖层；无论哪种都 MUST NOT 改为监听 scroll 事件。

### 5. 骨架与空状态（`TableSkeleton.tsx` / `EmptyState.tsx` / `App.tsx`）

- 骨架：`<table>` 结构，1 行表头（字段名占位条）+ 8 行占位；列数 = 当前字段数；`aria-hidden="true"`。
- 空状态枚举：`loading` / `no-projects` / `no-tables` / `no-rows` / `no-fields` / `error`；文案固定：
  - 加载中：骨架（表格区）/「加载中…」（项目与表格区）
  - 暂无项目 / 暂无表格 / 暂无数据 / 暂无字段
  - 读取失败：显示「读取失败」+「重试」按钮
- 空状态组件不接收任意文案，避免同一个词在不同场景复用。

### 6. 行密度与斑马纹（`TableToolbar.tsx` + `useDensity.ts`）

- 容器 `data-density="comfortable|compact"`，CSS 设 `--row-height`。
- 舒适 44px、紧凑 30px；切换只改状态，不发请求。
- 持久化键 `tableflow.ui.density.v1`，值 `"comfortable"|"compact"`；非法值回退舒适。
- 斑马纹用 `nth-child(even)` + CSS 变量，与 sticky 首列共用 `--row-bg`。

### 7. 列宽记忆（`ui-prefs.ts` + `useColumnWidths.ts` + `DataTable.tsx`）

- TanStack Table 开启 `enableColumnResizing`、`columnResizeMode: "onChange"`、`defaultColumn: { size: 160, minSize: 48, maxSize: 600 }`；首列默认 200。
- 表头渲染 resize handle（`header.getResizeHandler()`），拖拽实时更新。
- 存储结构：
  ```json
  {
    "<tableId>": { "<fieldId>": 240 }
  }
  ```
- 净化规则：
  - 解析失败 → `{}`；非对象 → `{}`。
  - key 必须匹配 `^[A-Za-z0-9._-]{1,64}$`；值必须为 48–600 的整数。
  - 总条目 ≤200；超出按写入时间淘汰最旧（实现为按对象插入顺序裁剪）。
  - 序列化后 ≤16KB；超限只保留最近 100 条。
- 写入 debounce 300ms；`try/catch` 静默失败。
- 恢复：`useColumnWidths(tableId, fields)` 在表切换时读取并应用到 `column.setSize`；字段不存在的条目忽略。
- 重置：清空当前 tableId 的条目，列宽回默认。

## Performance

- 滚动阴影纯 CSS，无 scroll 监听；sticky 只用 `position: sticky`。
- 列宽拖拽只更新 TanStack 列尺寸，不请求数据；debounce 写 localStorage。
- 斑马纹/hover 只切 CSS 变量，不触发 React 重渲染。
- 验收方法沿用 001：DevTools Performance 录制 5 秒滚动，确认 ≥50fps 且无 >50ms 长任务；首屏 5 次中位数 ≤500ms。

## Testing

- **类型门禁**：`cd frontend && npx tsc --noEmit`，0 error。
- **后端回归**：`cd backend && .venv/bin/pytest -q`，0 failed（本 spec 不改后端）。
- **DOM/样式核对**：按 spec 的 Acceptance Scenarios 逐条用 DevTools 检查类名、计算样式、`scrollLeft`、localStorage 内容。
- **localStorage 净化**：手工写入损坏 JSON、越界宽度、200+ 条目，确认回退且不报错。
- **性能**：按 001 方法复测首屏与滚动。
- **quickstart**：新增 `specs/004-ui-polish/quickstart.md`，V1–V8 手工步骤。

## Complexity Tracking

无违规项，本节留空。

## Risks

- **sticky 与斑马纹背景冲突**：首列必须用行级 `--row-bg`，否则偶数行/hover 会出现白块；用截图逐行核对。
- **列宽与固定布局**：`table-layout: fixed` 会让长文本换行变多；需要设置合理默认宽度并允许拖拽，避免行高失控。
- **列宽持久化污染**：字段 id/表 id 不是业务值，但仍按白名单正则净化；不存字段名与行值。
- **localStorage 容量**：200 条记录（每项目最多 10 表 × 20 列）可能接近上限；超限裁剪到 100 条并保持可用。
- **性能回退**：sticky + 阴影在低端机可能掉帧；若 <50fps，优先降级阴影（保留 sticky）并记录偏差。
- **与 003 的耦合**：`computed_meta` 由 003 提供；004 只读取，缺失时按未覆盖处理。
