# Feature Specification: 规格结构完整性

**Feature Branch**: `039-spec-structure`

**Created**: 2026-11-23

**Status**: Draft

**Input**: 需求 039-AR

## 背景与问题证据

对 1417 份标准 speckit 规格（594 个开源仓库）的实测分布，与 tableflow 现有 32 份规格对照：

| 指标 | 社区中位 | 社区 p10 | tableflow 中位 | tableflow 所在分位 |
|---|---|---|---|---|
| 文件行数 | 158 | 98 | 154.5 | 48% |
| User Story | 3 | 2 | 4 | 51% |
| 验收场景 | 11 | 5 | 16 | 73% |
| Functional Requirement | 14 | 6 | **0** | **0%** |
| 边界情况 | 6 | 3 | **1.5** | **5%** |
| 成功标准 | 6 | 4 | 5 | 22% |
| 实体 | 4 | 0 | 3 | 27% |

章节出现率：Functional Requirements **25%**（社区 97%）、Edge Cases **50%**（社区 96%）、Success Criteria 97%（社区 99%）、Key Entities 56%（社区 89%）。

**结论：粒度不是问题，结构缺失才是。** 行数与 User Story 数都压在社区中位数上，落入"一场景一 spec"极端形态的为 0/32（社区 1.8%）。真正的偏离是没有功能需求章节与边界情况章节——所有要求都被塞进验收场景，导致场景数被迫膨胀而缺少规范层。

## Clarifications

### Session 2026-11-23

- Q: 场景多是不是就该拆成多份规格？ → A: 不是。场景数是抽样验证层的数量，与能力边界无关。
- Q: 功能需求与验收场景是什么关系？ → A: 功能需求是规范层（系统必须做什么），验收场景是抽样验证层；社区两者的比例中位数约为 1.2:1。
- Q: 结构下限是硬性还是建议？ → A: 硬性。达不到不允许进入开发节点。

## User Scenarios & Testing

### User Story 1 - 规格必须包含规范层与验证层 (Priority: P1)

一份规格要既说清"系统必须做什么"，也说清"怎么验证"，两者不能合并成一层。

**Why this priority**: 只有验收场景时，speckit 的计划与任务阶段没有可分解的规范主体，这两个阶段自然被跳过。

**Independent Test**: 对任一规格统计章节，缺少 Functional Requirements 或 Edge Cases 即判为不完整。

**Acceptance Scenarios**:

1. **Given** 一份只有验收场景、没有功能需求章节的规格，**When** 校验结构，**Then** 判为不完整并指出缺失章节
2. **Given** 一份规格同时含规范层与验证层，**When** 校验，**Then** 通过并给出各层条数
3. **Given** 一份规格的验收场景数远多于功能需求数，**When** 校验，**Then** 提示两者比例异常（场景与需求的中位比例约为 1.2:1）

### User Story 2 - 结构下限被强制 (Priority: P1)

**Why this priority**: 建议性的下限在赶工时会全部失效。

**Independent Test**: 构造一份低于任一下限的规格，进入开发节点时应被拒绝。

**Acceptance Scenarios**:

1. **Given** 一份规格只有 1 个 User Story，**When** 请求推进开发节点，**Then** 拒绝并指出低于下限
2. **Given** 一份规格有 5 条验收场景、6 条功能需求、3 条边界情况、2 个 User Story，**When** 校验，**Then** 通过
3. **Given** 一份规格缺少边界情况章节，**When** 校验，**Then** 拒绝

### User Story 3 - 现有规格按新标准补齐 (Priority: P2)

**Acceptance Scenarios**:

1. **Given** 现有 32 份规格中 24 份缺功能需求章节，**When** 生成差距报告，**Then** 逐份列出缺失项与补充建议
2. **Given** 一份规格已 accepted，**When** 按新标准补齐结构，**Then** 作为一次依赖需求执行，不改写原独立需求的验收结论

## Requirements

### Functional Requirements

- **FR-001**: 每份规格 MUST 包含 User Scenarios & Testing 章节，且至少 2 个 User Story
- **FR-002**: 每份规格 MUST 包含至少 5 条验收场景
- **FR-003**: 每份规格 MUST 包含 Functional Requirements 章节，且至少 6 条功能需求
- **FR-004**: 每份规格 MUST 包含 Edge Cases 章节，且至少 3 条边界情况
- **FR-005**: 每份规格 SHOULD 包含 Success Criteria 与 Key Entities 章节
- **FR-006**: 验收场景 MUST 写成可判定形式，包含前置条件、动作与预期结果
- **FR-007**: 功能需求 MUST 与验收场景建立可追溯关系，不得出现无场景覆盖的需求或无需求支撑的场景
- **FR-008**: 结构校验 MUST 在 specify 阶段执行，未通过不得置 `speckit-specify状态=done`
- **FR-009**: 结构校验 MUST 在版本需求设计节点复验，未通过不得推进该节点
- **FR-010**: 校验结果 MUST 报出每一层的实际条数与下限的差额
- **FR-011**: 已 accepted 的规格补齐结构 MUST 走依赖需求，不得直接改写原规格的验收结论

### Edge Cases

- 一份规格因拆分成两半，各自都不足下限时，应先合并成一份或把拆分粒度调大，不得为了凑数灌水
- 纯配置类或纯文档类变更不产生规格时，本需求不适用，应在依赖需求中写明豁免理由
- 场景与需求的追溯关系存在一对多时，以需求编号标注在场景上，允许多个场景覆盖同一条需求
- 功能需求数量远多于场景时（如社区 001 样本 196:30），属于以需求为主体的写法，不应被判为异常
- 结构齐全但内容为空壳（标题存在、条目为零）时，按缺失处理

## Success Criteria

- **SC-001**: 新增规格 100% 含 Functional Requirements 与 Edge Cases 章节
- **SC-002**: 结构不达下限的规格无法进入开发节点
- **SC-003**: 现有 32 份规格的差距报告可逐份列出缺失项，补齐进度可统计
- **SC-004**: 场景与需求的追溯关系可双向查询

## Key Entities

- **规范层**：Functional Requirements，描述系统必须做什么
- **验证层**：Acceptance Scenarios，对规范层做可执行的抽样验证
- **边界情况**：正常路径之外的情形，独立成章，不占用验收场景编号
- **结构下限**：进入开发节点前必须满足的最小规模与章节要求
