# Feature Specification: 看板操作技能重构

**Feature Branch**: `041-board-skills-refactor`

**Created**: 2026-11-23

**Status**: Draft

**Input**: 需求 041-AR

## 背景与问题证据

| 技能 | 现状 | 问题 |
|---|---|---|
| `tf-update` | 承担需求登记与变更单登记 | 与 `classify` 规则脱节：只校验版本先后，不校验 033 的 C1/C2/C3；且登记是"写一行挂一个版本"，无法表达拆分与放弃 |
| `tf-status` | 只读报告版本距离发布还差什么 | 判定口径停留在 board@3（仍按 spec_done / change_done / bug_clear 三布尔），与 board@4 的 `gate = and(stage_done)` 不一致 |
| `ms-update` / `ms-implement` / `ms-summary` | 读写 MeterSphere 的用例与执行结果 | MeterSphere 资产迁移需求已取消，这三个技能失去对象，继续保留会误导使用者 |

本需求把这五个技能废弃，用新技能替代其中仍需要的两项能力：**需求登记**与**版本状态报告**。

## Clarifications

### Session 2026-11-23

- Q: 废弃是指删除还是保留只读？ → A: 删除。保留会造成"到底该用哪个"的歧义。
- Q: 新技能与规则校验的关系？ → A: 所有新技能在动手前必须执行 040 定义的规则自检，使用与引擎同源的规则定义。
- Q: 需求登记能力拆成几个技能？ → A: 一个，按 `classify` 的五种情况（in_place / change / new_spec / cross / out_of_board）分派，不按表分派。

## User Scenarios & Testing

### User Story 1 - 用新技能登记需求与变更单 (Priority: P1)

登记入口要能按 `classify` 的判定规则自动决定落在哪张表、挂到哪个版本，并在动手前完成规则校验。

**Why this priority**: 登记是流程入口，入口不对，后面的规则全部失效。

**Independent Test**: 用新技能登记一条改既有规格的需求，应被判定为 change 并创建依赖需求行，而不是新建独立需求。

**Acceptance Scenarios**:

1. **Given** 一条需求改的是尚未验收的规格，**When** 用新技能登记，**Then** 判定为 in_place，直接改 spec 与该需求行，不新建行
2. **Given** 一条需求改的是已验收的规格，**When** 登记，**Then** 判定为 change，在依赖需求表建行并挂到指定版本
3. **Given** 一条需求与既有规格都不重叠，**When** 登记，**Then** 判定为 new_spec，在独立需求表建行
4. **Given** 一次登记会违反 C1 或 C3，**When** 提交，**Then** 在发请求前失败并给出冲突信息
5. **Given** 一条需求不改变产品行为，**When** 登记，**Then** 判定为 out_of_board，提示记入版本变更说明而不进看板

### User Story 2 - 用新技能出发布就绪报告 (Priority: P1)

**Why this priority**: 现报告口径与 board@4 不符，会给出错误的可发布结论。

**Independent Test**: 对 v0.7.3 出报告，结论必须是不可发布且指出失败用例。

**Acceptance Scenarios**:

1. **Given** v0.7.3 有 1 条失败用例，**When** 出报告，**Then** 结论为不可发布，并列出失败用例号与规则依据
2. **Given** 一个六节点全 done 的版本，**When** 出报告，**Then** 结论为可发布，并列出六节点状态
3. **Given** 报告中的任一判定，**When** 质疑，**Then** 能给出复算口径与数据来源
4. **Given** 报告涉及的规则来自 040 的清单，**When** 规则更新，**Then** 报告口径随之更新，不改技能代码

### User Story 3 - 五个旧技能被彻底移除 (Priority: P1)

**Why this priority**: 留着旧技能，使用者会继续按旧口径操作。

**Independent Test**: 在仓库与全局技能目录中检索这五个名字，均无残留。

**Acceptance Scenarios**:

1. **Given** 重构完成，**When** 检索 `tf-update`、`tf-status`、`ms-update`、`ms-implement`、`ms-summary`，**Then** 仓库与全局目录均无残留
2. **Given** 某处文档仍引用旧技能名，**When** 检查，**Then** 检查报告把它列为待修引用
3. **Given** 旧技能的职责，**When** 逐条对照新技能，**Then** 每一项都有明确承接者或明确废止说明

### User Story 4 - 新技能覆盖登记与报告之外的必要操作 (Priority: P2)

**Acceptance Scenarios**:

1. **Given** 需要拆分或放弃一条需求，**When** 执行，**Then** 有对应技能入口，且校验 034 的前置条件
2. **Given** 需要执行历史清理，**When** 执行，**Then** 有对应技能入口，且校验 036 已生效

## Requirements

### Functional Requirements

- **FR-001**: `tf-update`、`tf-status`、`ms-update`、`ms-implement`、`ms-summary` MUST 被删除，仓库与全局技能目录均不得残留
- **FR-002**: 新登记技能 MUST 依据 `classify` 的判定规则自动分派五种情况，不要求调用方指定
- **FR-003**: 新登记技能 MUST 在发请求前执行 040 定义的规则自检
- **FR-004**: 新报告技能 MUST 按 board@4 口径判定，`发布条件 = and(六节点全部 done)`
- **FR-005**: 新报告技能 MUST 只读，不得写入看板
- **FR-006**: 新报告技能 MUST 对每条判定给出复算口径与数据来源
- **FR-007**: 所有新技能 MUST 使用与引擎同源的规则定义，不得各自实现
- **FR-008**: 拆分与放弃 MUST 有对应技能入口，并校验 034 定义的前置条件
- **FR-009**: 历史清理 MUST 有对应技能入口，并校验 036 已生效
- **FR-010**: 技能文档中的交叉引用 MUST 同步更新，不得继续指向已删除的技能

### Edge Cases

- 登记时目标版本尚不存在：拒绝并提示先建版本，不得自动建
- 登记时既有规格与被登记需求指向同一能力但条款表述不同：需人工确认后才建行，不得自动判为重复
- 报告技能在目标版本数据缺失时（如未挂任何需求），应输出"无法完整判定"而不是臆断为可发布
- 拆分与放弃涉及已发布版本时，技能必须拒绝并在说明中指向 034 的相应条款
- 旧技能仍被定时任务或其他仓库引用时，删除前须先确认引用方，避免静默失效

## Success Criteria

- **SC-001**: 五个旧技能在仓库与全局目录中零残留，交叉引用全部更新
- **SC-002**: 新登记技能对五种 classify 情况的判定与契约定义完全一致
- **SC-003**: 新报告技能对 v0.7.3 给出的结论为不可发布，且能指出失败用例
- **SC-004**: 技能侧规则校验与引擎侧结果逐条一致

## Key Entities

- **登记技能**：按 classify 分派需求落点，含规则自检
- **报告技能**：只读输出发布就绪结论、依据与数据来源
- **规则自检**：技能执行前对 040 规则清单的一次性校验
- **废止技能**：被删除的五个技能，保留废止说明与职责承接表
