# Feature Specification: 测试列弹层显示执行结果

**Feature Branch**: `043-run-result-column`
**Created**: 2026-11-24
**Status**: Draft

## 背景与问题证据

版本表的「测试」列点击后弹出关联条目清单，当前只显示两列：编号、用例号、执行状态。执行状态只有「未执行/已执行」，看不出这一条到底通过还是失败——必须再点进明细才能判断。

`run` 表本身有 `执行结果`（pass/fail/blocked/skip），relation 的 options 已经配了 `display_field`（用例号）与 `status_field`（执行状态），但缺少承载结果的配置项，前端因此没有渲染入口。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 弹层里直接看到执行结果 (Priority: P1)

评审一个版本时，点开「测试」列就能判断哪几条失败，不必逐条点明细。

**Why this priority**: 执行状态只说明跑没跑，结果才说明过没过；两者缺一，弹层的信息量不足以支持判断。

**Independent Test**: 打开任一有用例的版本，点「测试」列，清单里能看到每条的执行结果。

**Acceptance Scenarios**:

1. **Given** 版本收录了用例且执行结果非空，**When** 点开「测试」列，**Then** 清单显示编号、用例号、执行状态、执行结果四列
2. **Given** 某条执行结果为 `pass`，**When** 查看清单，**Then** 该行结果显示「通过」标签，而不是原始枚举值
3. **Given** 某条执行结果为 `fail`，**When** 查看清单，**Then** 该行结果显示「失败」标签，与「已执行」状态并列可见

### User Story 2 - 结果为空与结果列缺失都不能出错 (Priority: P2)

未执行的用例没有结果；未配置结果列的旧项目也不能因为这次改动崩掉或显示空列。

**Why this priority**: 空值与本版未迁移的项目是真实存在的数据形态，显示层必须能区分「没有结果」与「字段不存在」。

**Independent Test**: 对一条未执行的用例与一个未配置 `result_field` 的项目分别打开清单，都不报错。

**Acceptance Scenarios**:

1. **Given** 某条用例尚未执行、执行结果为空，**When** 查看清单，**Then** 结果列显示占位符 `—`，不显示空标签
2. **Given** 目标表未配置 `result_field`，**When** 点开清单，**Then** 只显示原有列，不出现空的第五列
3. **Given** 关联的执行行已失效，**When** 查看清单，**Then** 该行标记为关联失效，结果列同样显示占位符

### Edge Cases

- 执行结果字段不是枚举（例如被改成文本）时，按原值直接显示，不套标签
- 关联清单为空（版本没收录用例）时，弹层显示空态，不请求目标表
- 同一版本内既有 `done` 又有 `todo` 的执行行时，两类行都能正确渲染结果列

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: relation 字段的 options MUST 支持 `result_field`，指向目标表的结果字段 id
- **FR-002**: 弹层 MUST 按 `result_field` 渲染一列，列名取该字段的名称
- **FR-003**: 结果值为空时 MUST 显示占位符 `—`，不得显示空标签或 `null`
- **FR-004**: 结果列 MUST NOT 替代状态列；两者同时存在时都要显示
- **FR-005**: 未配置 `result_field` 时 MUST 保持原有列，不渲染空列（向后兼容）
- **FR-006**: `ver.测试用例` 的 options MUST 配置 `result_field: tf-r-result`，并在契约文档中登记

### Key Entities

- **relation options**：`table_id`、`display_field`、`status_field`，本需求新增 `result_field`
- **run 行**：`执行状态`（todo/done）与 `执行结果`（pass/fail/blocked/skip）是两个独立字段

## Success Criteria *(mandatory)*

### Measurable Outcomes

- 打开任一有用例的版本，弹层能同时看到执行状态与执行结果，无需进入明细
- 未配置 `result_field` 的项目，弹层列数与改动前一致
- 未执行的用例显示 `—` 而不是空白或报错

## Non-Goals

- 不改变执行结果的枚举值域
- 不在主表「测试」列上增加结果聚合（只改弹层）
- 不新增表或字段，只扩展 relation options
