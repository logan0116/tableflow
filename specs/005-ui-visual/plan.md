# Implementation Plan: 界面视觉打磨（v0.4.0）

**Branch**: `005-ui-visual` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-ui-visual/spec.md`

## Summary

在 004 的界面基础上做三件事：把结构色加深到可辨识（纯 CSS 变量）；把默认列宽从固定 110px 改为「类型基础宽 + 表头估算宽」；把页头改成「项目 › 表」面包屑、表格卡片加面板感、明细弹层改竖向键值对。不引入依赖、不动接口、不改业务数据，性能基线不变。

## Technical Context

**Language/Version**: TypeScript 5.x + Node 24（前端）；后端不改

**Primary Dependencies**: React 18、Vite、TypeScript、@tanstack/react-table（已引入）；不新增依赖

**Storage**: 不变。列宽记忆仍为 `tableflow.ui.columnWidths.v1`，密度 `tableflow.ui.density.v1`

**Testing**: 前端不引入测试框架；`npx tsc --noEmit` 类型门禁；计算样式与对比度核对；截图 + VL 模型视觉评审；后端 `pytest` 回归门禁

**Target Platform**: Chrome / Edge 桌面浏览器，Linux 局域网访问

**Project Type**: web application（仅前端）

**Performance Goals**: 14 行首屏 ≤500ms；滚动 ≥50fps、无 >50ms 长任务；列宽估算 <5ms/表

**Constraints**: DOM 表格、无 canvas/虚拟滚动/重型表格库；无新依赖；中文单语；不改接口契约；浅色单主题

**Scale/Scope**: 单表 ≤500 行、≤20 列；改 6 个文件、1 个样式表

## Constitution Check

*GATE: 对照宪法 v7.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 只改渲染层，不新增任何写接口或本地写控件 | PASS |
| II 无读缓存 | 业务数据仍每次现拉；localStorage 只存列宽与密度，键名与内容不变 | PASS |
| III Schema 驱动 | 列宽按 `field.type` 与 `field.name` 推导，不硬编码任何业务列名或状态值 | PASS |
| IV DOM 表格 | 仍是原生 table + TanStack Table；对比度、圆角、阴影、过渡均为 CSS；无 canvas/虚拟滚动 | PASS |
| V 固定技术栈 | 不新增依赖；字体用系统已安装字族，不打包字体文件 | PASS |
| VI 中文单语 | 新增文案全部中文；无 i18n | PASS |
| VII 边界收敛 | 只做本 spec 列明的 3 组能力；深色主题、移动端、视图体系、列显示配置均不触碰 | PASS |

无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/005-ui-visual/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
frontend/src/
├── styles.css                       # 结构色变量、卡片、过渡、链接、弹层键值对
├── App.tsx                          # 页头面包屑 + 行数计数
├── components/
│   ├── DataTable.tsx                # 默认列宽估算 + 表头 title
│   ├── RelationModal.tsx            # 竖向键值对 + Esc/遮罩关闭
│   └── RelationListModal.tsx        # 跟随卡片与弹层样式
├── field-utils.ts                   # 列宽估算辅助（字符宽近似）
└── ui-prefs.ts                      # 不改（键名与结构保持）
```

## 实现要点

### 1. 结构色（`styles.css` 变量）

```css
--color-border: #c9d1d9;        /* 容器边框 1.50:1 */
--color-border-soft: #e3e8ee;   /* 行分隔线 1.25:1 */
--color-header: #f0f3f6;        /* 表头带 1.13:1 */
--color-hover: #e6f0fb;         /* 悬停底 1.16:1 */
--color-zebra: #f7f9fb;         /* 斑马纹保持极淡 */
```

对比度按 WCAG 相对亮度公式计算，验收脚本见 tasks T015。

### 2. 列宽估算（`field-utils.ts`）

```ts
const TYPE_BASE = {
  number: 100, datetime: 132, enum: 124,
  relation: 156, text: 168, computed: 120,
};

// 中文 14px/字、西文 7.5px/字符，加 24px 内边距
function estimateHeaderWidth(name: string): number {
  let px = 0;
  for (const ch of name) px += /[\u4e00-\u9fff]/.test(ch) ? 14 : 7.5;
  return px + 24;
}

function defaultColumnWidth(field, isFirst): number {
  const base = field.type === "computed"
    ? (isNumericField(field) ? 100 : 120)
    : TYPE_BASE[field.type] ?? 168;
  const width = Math.max(base, estimateHeaderWidth(field.name));
  return clamp(width + (isFirst ? 16 : 0), 88, 320);
}
```

只在 `visibleFields` 变化时用 `useMemo` 计算一次，与行数无关。

### 3. 页头（`App.tsx`）

```tsx
<header className="page-header">
  <h1>
    <span className="crumb-project">{projectName}</span>
    <span className="crumb-sep">›</span>
    <span className="crumb-table">{tableName}</span>
  </h1>
  <span className="page-count">共 {total} 条</span>
</header>
```

项目/表名取自现有 `projects` / `tables` 状态，不新增请求。

### 4. 卡片与弹层（`styles.css` + `RelationModal.tsx`）

- 卡片：`border-radius: 10px; box-shadow: 0 1px 2px rgba(15,23,42,.06), 0 1px 8px rgba(15,23,42,.04)`
- 最大高：`calc(100vh - 200px)`，`@media (max-height: 600px)` 退化为 `70vh`
- 弹层：`display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr))`，每项为「字段名 + 值」两行块；值 `white-space: pre-wrap; overflow-wrap: anywhere`
- 关闭：`useEffect` 监听 `keydown` Esc + 遮罩 `onMouseDown` 判定

## 验收方法

1. 计算样式：浏览器 `getComputedStyle` 读四个色值，按 WCAG 公式算对比度，对照 spec SC-001。
2. 截图对比：1280×800 下「版本管理」「独立规格需求」两表，改前改后各一张；VL 模型评审层次与可读性。
3. 类型与回归：`cd frontend && npx tsc --noEmit`；`cd backend && .venv/bin/pytest -q`。
4. 性能：14 行首屏 ≤500ms、滚动帧率 ≥50fps（沿用 001 方法）。

## 风险

| 风险 | 应对 |
|---|---|
| 列宽估算偏大导致横向滚动增加 | 上限 320px；先按类型基础宽兜底，表头估算只做加法 |
| 结构色加深后整体偏灰 | 只动 4 个变量，其余色值不动；截图对比确认 |
| 弹层改布局影响关联列表弹层 | 两者共用 `.modal` 基础样式，键值对类名独立（`.kv-*`） |
| 字体栈改动在无 PingFang 的 Linux 上回退 | 栈内保留 `Noto Sans CJK SC` 与 `Microsoft YaHei` |
