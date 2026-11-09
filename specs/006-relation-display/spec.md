# Feature Specification: 关联条目显示字段配置化（v0.4.1）

**Feature Branch**: `006-relation-display`

**Created**: 2026-11-10

**Status**: Draft

**Input**: v0.4.0 验收时发现的既存问题：`RelationListModal` 用硬编码列名数组挑选目标表的「标题」「状态」字段，与宪法原则 III「前端 MUST NOT 硬编码业务列名」冲突；同时目标表「状态」字段为 `text` 类型时 `enumItems` 返回空数组，状态列渲染为空白。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 硬编码业务列名 | `frontend/src/components/RelationListModal.tsx` 第 20-21 行定义 `TITLE_NAMES = ["标题","条款","名称","姓名","设备","任务"]`、`STATUS_NAMES = ["状态","发布状态","回归状态"]`，据此挑字段 | 违反宪法原则 III；改表结构就要改前端代码 |
| 状态列空白 | `tableflow` 项目的 `tf-indep.tf-i-status` 是 `text` 类型，`pickStatusField` 命中后 `enumItems` 返回 `[]`，`statusOption` 为 `null` | 关联条目弹层第三列为空，用户看不到状态 |

## Clarifications

### Session 2026-11-10

- Q: 字段选择怎么配置？ → A: `relation` 字段的 `options` 增加可选 `display_field` 与 `status_field`（值为目标表的字段 id），由 Agent 写入；前端只读配置，不猜。
- Q: 未配置时怎么回退？ → A: 不按列名猜测。`display_field` 缺失时只显示编号列；`status_field` 缺失时不显示状态列。
- Q: 列头文案从哪来？ → A: 用被配置字段自身的 `name`（如「条款」「回归状态」），不再写死「标题」「状态」。
- Q: 状态字段不是 enum 怎么办？ → A: `status_field` 指向非 enum 字段时按纯文本渲染，不套标签。
- Q: 配置的字段已被删除？ → A: 忽略该配置并回退（与 004 列宽记忆同一策略），不报错。
- Q: 存量数据怎么迁移？ → A: 一次性脚本给 6 个项目的 18 个 relation 字段补配置：目标表为 `*-indep` 的取 `<p>-i-clause` / `<p>-i-implement`，目标表为 `*-dep` 的取 `<p>-d-clause` / `<p>-d-regress`。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 配置驱动显示 (Priority: P1)

点开版本表的「需求关联（依赖）」，弹层按该 relation 字段的配置显示：编号、条款、回归状态。列头是目标字段自己的名字，状态列按 enum 的 tone 着色。

**Why this priority**: 这是宪法原则 III 的合规修复，也是当前状态列空白的直接原因。

**Independent Test**: 给某 relation 字段配 `display_field=条款字段`、`status_field=enum 字段`，打开弹层核对三列；改配置后刷新，列随之变化且不改前端代码。

**Acceptance Scenarios**:

1. **Given** relation 字段配置了 `display_field`，**When** 渲染关联条目列表，**Then** 第二列列头为该字段的 `name`，值为 `displayText` 结果。
2. **Given** relation 字段配置了 `status_field` 且该字段是 enum，**When** 渲染，**Then** 第三列列头为该字段 `name`，值渲染为 `EnumTag`。
3. **Given** `status_field` 指向非 enum 字段，**When** 渲染，**Then** 按纯文本显示，不套标签。
4. **Given** 前端源码，**When** grep `TITLE_NAMES` / `STATUS_NAMES`，**Then** 命中数为 0。

---

### User Story 2 - 缺失配置的回退 (Priority: P2)

某个 relation 字段还没配显示字段时，弹层只显示编号列，不报错、不按列名乱猜。

**Why this priority**: 保证新增字段与旧数据不会因缺配置而崩溃或显示错乱。

**Independent Test**: 造一个只配了 `table_id` 的 relation 字段，点开弹层，只有编号列。

**Acceptance Scenarios**:

1. **Given** relation 字段只有 `table_id`，**When** 打开弹层，**Then** 只显示编号列，无报错。
2. **Given** 配置的 `display_field` 在目标表已不存在，**When** 打开弹层，**Then** 忽略该配置，回退为只显示编号列。
3. **Given** 目标行已删除（关联失效），**When** 打开弹层，**Then** 该行显示「关联已失效」且不可点击（沿用现有行为）。

---

### Edge Cases

- 目标行存在但 `display_field` 值为空：显示「—」。
- `status_field` 值为空：状态列留空，不显示标签。
- 关联 `rowIds` 为空数组：弹层显示「关联条目 · 0 项」，不报错。
- 目标表没有可见字段：只显示编号列。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `RelationOptions` MUST 支持可选 `display_field` 与 `status_field`，值为目标表字段 id；字段缺失或类型非法 MUST 忽略。
- **FR-002**: 关联条目列表第二列 MUST 使用 `display_field` 对应字段的 `name` 作为列头，值 MUST 使用 `displayText` 渲染。
- **FR-003**: `status_field` 指向 enum 字段时 MUST 渲染 `EnumTag`；指向非 enum 字段时 MUST 按纯文本渲染。
- **FR-004**: 未配置 `display_field` 时 MUST 只显示编号列；未配置 `status_field` 时 MUST 不显示状态列；MUST NOT 按字段名猜测。
- **FR-005**: 配置字段在目标表中不存在时 MUST 忽略并回退，MUST NOT 报错。
- **FR-006**: 前端源码 MUST NOT 出现用于字段选择的业务列名字面量（`标题`/`条款`/`状态` 等）。
- **FR-007**: 迁移脚本 MUST 为 6 个项目的 18 个 relation 字段补 `display_field` / `status_field`，MUST 可重复执行且结果一致（幂等）。
- **FR-008**: 本 spec MUST NOT 引入新依赖；`options` 为 JSON 透传，MUST NOT 改变接口契约与后端代码。
- **FR-009**: 界面文案 MUST 全部中文。

### Key Entities

- **关联显示配置（RelationDisplayOptions）**：`relation` 字段 `options` 里的 `display_field` 与 `status_field`，指向目标表字段 id。
- **迁移脚本（MigrateRelationDisplay）**：读取现有 relation 字段，按目标表结构补配置，幂等。

## Success Criteria *(mandatory)*

- **SC-001**: 前端源码 grep `TITLE_NAMES`、`STATUS_NAMES` 命中 0。
- **SC-002**: 打开「版本管理」表某行的「需求关联（依赖）」，弹层显示三列（编号 / 条款 / 回归状态），状态列有彩色标签。
- **SC-003**: 只配 `table_id` 的 relation 字段，弹层只显示编号列且无报错。
- **SC-004**: `cd frontend && npx tsc --noEmit` 零错误；`cd backend && .venv/bin/pytest -q` 全绿。
- **SC-005**: 关联弹层点击到明细显示 ≤300ms（沿用 001 基线）。

## Assumptions

- `relation` 的 `options` 在数据库里是 JSON 文本，新增键无需迁移表结构。
- 迁移脚本通过 Agent 写接口执行，每次写入落审计。
- 版本号定为 v0.4.1（PATCH）：缺陷修复与合规，不引入新能力。

## 未来范围

- 关联条目列表的多列配置（显示 3 列以上）、排序、筛选仍属宪法非目标，不在本 spec 范围。
