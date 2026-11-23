# Feature Specification: 开发节点完成 speckit 实现侧全流程

**Feature Branch**: `042-implement-full-flow`

**Created**: 2026-11-23

**Status**: Draft

**Input**: 需求 042-AR

## 背景与问题证据

| 项 | 现状 | 影响 |
|---|---|---|
| 开发节点不做实现 | `tf-dev-implement` 的说明写明"不写代码、不跑构建"，只校验 `tasks.md` 全部勾选并写完成状态 | 勾选是文档记录，不能证明实现存在、也不能证明单测通过 |
| 实现侧三段无驱动者 | plan / tasks / implement 三阶段没有任何技能驱使其产生 `plan.md`、`tasks.md`、代码与单测 | 026–031 六个目录有 `spec.md` 与已勾选的 `tasks.md`，`plan.md` 全部缺失 |
| 阶段字段无写入者 | 八个阶段字段里只有 `speckit-implement状态` 有写入者 | 36.3% 的空值不是漏填，是没有通道 |

原设计中开发节点应完成 speckit 的实现侧全流程，现状只落实了"检查勾选"这一步。本需求把设计补齐，并明确 **spec 侧归版本需求设计节点、实现侧归开发节点** 的分工。

## Clarifications

### Session 2026-11-23

- Q: 全流程是否包含 specify？ → A: 不包含。spec 由版本需求设计节点驱动并产出；开发节点负责 plan → tasks → implement。原因是测试设计节点（第 2 节点）要从 `spec.md` 派生用例，spec 必须在它之前存在。
- Q: 开发节点要写代码吗？ → A: 要。除生成 `plan.md`、`tasks.md` 外，还要产出实现与单测，并以单测通过作为 implement 阶段的证据。
- Q: 现有"有 tasks 无 plan"的规格怎么办？ → A: 不允许直接置 done。必须先补 `plan.md` 并回链场景号，再重新确认任务清单。

## User Scenarios & Testing

### User Story 1 - 开发节点跑完实现侧三段 (Priority: P1)

开发节点一次执行，依次完成计划、任务拆分与实现，并把三段产物与证据留下。

**Why this priority**: 这是当前最大的缺口，也是"任务从哪来"无法回答的原因。

**Independent Test**: 对一份有 `spec.md`、无 `plan.md` 的规格执行开发节点，应生成 `plan.md` 与 `tasks.md`，产出实现与单测，并写入三个阶段状态。

**Acceptance Scenarios**:

1. **Given** 一份规格有 `spec.md` 但无 `plan.md`，**When** 执行开发节点，**Then** 先生成 `plan.md` 并回链 spec 的场景号，再生成 `tasks.md`，最后产出实现与单测
2. **Given** 三份产物齐备且单测通过，**When** 收口，**Then** `speckit-plan状态`、`speckit-task状态`、`speckit-implement状态` 均置 done
3. **Given** 单测未通过，**When** 尝试收口，**Then** 拒绝，`speckit-implement状态` 保持 doing 或 failed
4. **Given** `tasks.md` 已勾选但未生成 `plan.md`，**When** 执行开发节点，**Then** 拒绝并提示先补计划

### User Story 2 - 版本需求设计节点产出 spec (Priority: P1)

spec 侧三个阶段由第 1 节点驱动，产出可供第 2 节点派生用例的 `spec.md`。

**Why this priority**: 第 2 节点依赖 `spec.md`，spec 必须在开发之前存在。

**Independent Test**: 对一个只有需求条款、没有规格目录的版本执行第 1 节点，应产出 `spec.md` 并写入 spec 侧三个状态。

**Acceptance Scenarios**:

1. **Given** 某需求的规格目录为空，**When** 执行版本需求设计节点，**Then** 依据需求条款产出 `spec.md`，并按 039 校验结构
2. **Given** 规格结构未达下限，**When** 执行第 1 节点，**Then** 拒绝推进，`speckit-specify状态` 保持未完成
3. **Given** 项目已有宪法且本次沿用，**When** 记录 constitution 阶段，**Then** 写入宪法版本号与未修改标记
4. **Given** spec 已产出，**When** 执行第 2 节点，**Then** 能按验收场景派生用例

### User Story 3 - 八个阶段字段全部有写入者 (Priority: P1)

**Why this priority**: 只要还有字段没有写入者，就只能手工填，状态依旧不可信。

**Independent Test**: 遍历八个阶段字段，每个都能指出由哪个节点或技能在什么条件下写入。

**Acceptance Scenarios**:

1. **Given** 八个阶段字段清单，**When** 查询写入者，**Then** 每个字段都指向确定的节点与触发条件
2. **Given** 一次完整交付，**When** 收口，**Then** 八个阶段状态全部有值，且每个值都对应产物或明确的豁免说明
3. **Given** 某阶段因不适用而跳过，**When** 记录，**Then** 取值 `na` 并写明不适用理由

### User Story 4 - 单个规格完成不自动推进版本 (Priority: P2)

**Acceptance Scenarios**:

1. **Given** 本版第一份规格走完全流程，**When** 查询版本六节点，**Then** 只有本版全部规格完成时开发节点才可以推进
2. **Given** 本版部分规格未完成，**When** 尝试推进开发节点，**Then** 拒绝并列出未完成的规格编号

## Requirements

### Functional Requirements

- **FR-001**: 开发节点 MUST 依次驱动 plan → tasks → implement 三个阶段
- **FR-002**: 开发节点 MUST 产出 `plan.md`，且每条计划项回链 `spec.md` 的场景号
- **FR-003**: 开发节点 MUST 产出 `tasks.md`，且每条任务回链计划项或场景号
- **FR-004**: 开发节点 MUST 产出实现与单测，并以单测通过作为 `speckit-implement状态` 置 done 的证据
- **FR-005**: 开发节点 MUST 拒绝在缺少 `plan.md` 的情况下依据已勾选的 `tasks.md` 置实现完成
- **FR-006**: 版本需求设计节点 MUST 驱动 constitution / clarify / specify 三个阶段并产出 `spec.md`
- **FR-007**: 八个阶段字段 MUST 各自有确定的写入者，不存在只能手工填写的字段
- **FR-008**: 任一阶段置 done MUST 校验其产物存在且通过验证
- **FR-009**: 阶段可因不适用取 `na`，但 MUST 写明不适用理由
- **FR-010**: 开发节点置 done MUST 要求本版本全部规格完成，不得以单份规格完成代替
- **FR-011**: 阶段失败后 MUST 允许返工，返工完成后重新推进，保留失败记录

### Edge Cases

- 历史规格已有 `tasks.md` 但无 `plan.md` 时，补做 `plan.md` 需回填任务与场景的对应关系，不得只建空文件
- 一份规格的实现被拆分到多次执行完成时，三次阶段状态只在最后一次收口时置 done，中途保持 doing
- 实现过程中发现 spec 有误需要修改时，必须回到第 1 节点修订规格并让第 2 节点重新派生用例，不得在开发节点私自改 spec
- 单测通过但任务清单仍有未勾选项时，不得置 implement 完成
- 某规格无代码产物（纯流程或纯文档需求）时，implement 阶段以文档产物与检查结论作为证据，但须写明豁免理由

## Success Criteria

- **SC-001**: 开发节点执行后，`plan.md` 与 `tasks.md` 同时存在且互相回链，缺失情况为 0
- **SC-002**: 八个阶段字段的空值不再出现（不适用填 `na`），自动化写入覆盖率 100%
- **SC-003**: 单测未通过时无法把 `speckit-implement状态` 置为 done
- **SC-004**: 第 1 节点产出的 `spec.md` 能满足第 2 节点派生用例且符合 039 的结构下限

## Key Entities

- **计划（plan.md）**：实现方案，逐条回链规格场景号
- **任务（tasks.md）**：可勾选的执行项，逐条回链计划项或场景号
- **实现产物**：代码与单元测试，构成 implement 阶段的证据
- **阶段写入者**：某个阶段状态的产生者，由节点与技能共同确定
- **豁免说明**：某阶段不适用时的书面理由，与 `na` 取值配套
