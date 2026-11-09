# Implementation Plan: 关联条目显示字段配置化（v0.4.1）

**Branch**: `006-relation-display` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-relation-display/spec.md`

## Summary

把关联条目弹层「挑哪一列当标题、哪一列当状态」从硬编码列名数组改成 relation 字段的 `options.display_field` / `options.status_field` 配置；未配置时只显示编号列，不猜。配套一个幂等迁移脚本给 6 个项目 18 个 relation 字段补配置。后端不改，`options` 本来就是 JSON 透传。

## Technical Context

**Language/Version**: TypeScript 5.x（前端）；Python 3.12（迁移脚本）

**Primary Dependencies**: React 18、Vite、TypeScript、@tanstack/react-table；不新增依赖

**Storage**: 不改表结构；`fields.options` 追加两个可选键

**Testing**: `npx tsc --noEmit`；`pytest` 回归；DOM 核对 + 手工点击验收

**Target Platform**: Chrome / Edge 桌面浏览器

**Project Type**: web application

**Performance Goals**: 关联弹层点击到显示 ≤300ms（001 基线）

**Constraints**: 无新依赖、无后端改动、无新视图、中文单语

**Scale/Scope**: 改 2 个前端文件 + 1 个迁移脚本；6 项目 18 个 relation 字段补配置

## Constitution Check

*GATE: 对照宪法 v7.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 迁移通过 Agent 写接口执行，落审计 | PASS |
| II 无读缓存 | 不改数据获取路径 | PASS |
| III Schema 驱动 | 字段选择改由 `options` 配置驱动，前端不再出现业务列名字面量 | PASS（修复原有违规） |
| IV DOM 表格 | 仍是原生 table，无 canvas/虚拟滚动 | PASS |
| V 固定技术栈 | 不新增依赖 | PASS |
| VI 中文单语 | 文案全部中文，列头取自数据 | PASS |
| VII 边界收敛 | 只做字段配置化，不做多列配置/排序/筛选 | PASS |

无违规项。

## Project Structure

```text
frontend/src/
├── types.ts                        # RelationOptions 加 display_field / status_field
└── components/RelationListModal.tsx # 按配置选列，删除 TITLE_NAMES / STATUS_NAMES

data/
└── migrate_relation_display.py     # 幂等迁移：6 项目 18 个 relation 字段补配置

specs/006-relation-display/
├── spec.md
├── plan.md
└── tasks.md
```

## 实现要点

### 1. 类型

```ts
export interface RelationOptions {
  table_id?: string;
  /** 关联条目列表里用作「名称」列的字段 id（目标表）。 */
  display_field?: string;
  /** 关联条目列表里用作「状态」列的字段 id（目标表）。 */
  status_field?: string;
  constraints?: FieldConstraints;
}
```

### 2. 选列逻辑

```ts
function resolveColumns(field: Field, targetFields: Field[]) {
  const options = optionObject<RelationOptions>(field.options);
  const byId = new Map(targetFields.map((f) => [f.id, f]));
  return {
    display: options?.display_field ? byId.get(options.display_field) ?? null : null,
    status: options?.status_field ? byId.get(options.status_field) ?? null : null,
  };
}
```

列头用字段 `name`；`display` 缺失不渲染第二列，`status` 缺失不渲染第三列。

### 3. 迁移脚本

对每个 relation 字段：读目标表字段，按表结构规则选：
- `display_field` = 目标表第二个 `text` 字段（第一个是编号）
- `status_field` = 目标表第一个 `enum` 字段

脚本先打印映射供核对，再 PATCH 字段；已存在同值则跳过（幂等）。

## 验收方法

1. `npx tsc --noEmit`、`.venv/bin/pytest -q`。
2. grep `TITLE_NAMES|STATUS_NAMES` 命中 0。
3. 浏览器点开「版本管理」→「需求关联（依赖）」核对三列；点开未配置字段核对只有编号列。
4. 迁移脚本重复执行，二次运行输出「无需变更」。

## 风险

| 风险 | 应对 |
|---|---|
| 迁移把配置写错字段 | 脚本先打印 18 条映射，人工核对后再写；写入后可回滚（PATCH 覆盖） |
| 旧数据无配置导致弹层退化 | 迁移脚本覆盖全部现存 relation 字段；新建字段由 Agent 按约定写入 |
| 列头过长挤压弹层 | 列头取字段 name，弹层宽度沿用 004 的 `min(760px, 92vw)` |
