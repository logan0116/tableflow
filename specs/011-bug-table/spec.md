# Feature Specification: bug表与board@2契约（v0.6.1）

**Feature Branch**: `011-bug-table`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 看板`011-AR`行条款："bug表设计：在看板新增第四张表<前缀>-bug（一行=一个缺陷），定义字段、状态枚举与完成判定，并把契约从board@1扩展到board@2；同时约定版本表上一版本Bug三个字段的数据来源。不含MS同步与交互协议。"

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 缺陷没有落点 | `specs/008-board-contract/board@1.yaml`第17行把"bug表"写进`out_of_scope`，三表之外无缺陷表；线上`GET /api/tables/tf-bug/table`返回`404`（2026-11-19实测） | 一个缺陷只活在聊天记录或测试工具里，修没修、修在哪版无从查，无法回放 |
| 版本闸门有一根腿悬空 | `board@1.yaml`第135-147行：`bug_total`/`bug_open`是`number`且注明"bug表落地前人工填报"，`bug_ready=and(bug_open==0)`；而`bug_open`没有任何表能产出 | 发布条件里"上一版本Bug就绪"靠人填数，填错就放行，等于没有闸门 |
| 完成判据无法收敛到一处 | `board@1.yaml`第295行只定"已解决=总数−未解决数"，没有定义"一个缺陷算不算解决" | 同一条缺陷在测试、开发、发布三处可能有三种说法 |
| skill与契约冲突 | `tableflow-board`技能第111行仍写"没有第四张表……任务与Bug不进看板"，第210行把"Bug、缺陷"列为dep的反例；`specs/008-board-contract/spec.md`FR-010已约定011落地时同步修改 | 按skill办事的人会把缺陷记到别处，契约与操作口径分叉 |
| 缺陷与规格的关系未定 | `board@1.yaml`没有bug与indep的关联定义 | 一个缺陷可能横跨多份规格，缺陷也可能暂时归不到任何规格 |

## Clarifications

### Session 2026-11-19

- Q: 缺陷完成判据用什么？ → A: 单字段`状态=closed`，与`spec.acceptance`、`change.regress`同构；不另设"是否解决"第二判据。
- Q: "不修复/风险接受"怎么表达？ → A: 仍记`closed`，修复版本留空，证据写结论与依据，剩余事项置空；与`board@1`"确认不受影响也记`passed`，理由写证据"同一做法。不引入`na`或`wontfix`，避免终态分裂。
- Q: 缺陷与规格是什么关系？ → A: `relation`多对多，可空；空数组即"暂未归因"，不阻塞缺陷流转，也不自动改任何判定。
- Q: 版本表怎么挂接？ → A: `发现版本`必填单值是唯一挂接键；`修复版本`只记录修在哪一版，不参与判定；版本表按"发现版本=上一版本"取集合，总数与未解决数都从该集合派生。
- Q: "上一版本"怎么算？ → A: 按版本号`v<主>.<次>.<修>`语义序取严格小于当前版本号的最大版本；不看发布时间（可为空）、不看发布状态，无上一版本时集合为空。
- Q: 严重度进不进发布闸门？ → A: 不进。发布条件只数"未解决数=0"；严重度是记录字段，避免同一问题两个真相。
- Q: 版本表三个Bug字段要改类型吗？ → A: 不改。`bug_total`/`bug_open`仍是`number`，`bug_ready`仍按`bug_open==0`判定；自动聚合的实现另立需求，本契约只定口径与填报方式。
- Q: 缺陷要不要走需求分类树？ → A: 不走。发现缺陷直接进bug表；缺陷引发的规格改动才按需求分类（改已`accepted`规格→dep）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 缺陷有唯一落点（Priority: P1）

任何人或Agent打开`<前缀>-bug`表，一行就是一个缺陷：编号、标题、状态、严重度、来源、关联规格、发现版本、修复版本、证据、剩余事项、MS用例号、负责人，共12个字段。

**Why this priority**: 没有落点，后续的完成判定、版本挂接、剩余缺陷统计都无处附着。

**Independent Test**: 读一次`GET /api/tables/tf-bug/table`，字段集合与`board@2.yaml`的`bug`表逐字段一致（12个），且无多余字段。

**Acceptance Scenarios**:

1. **Given** `board@2.yaml`的`bug`表，**When** 解析，**Then** 字段数为12，`key`互不重复且都以`bug.`开头。
2. **Given** 线上表`tf-bug`，**When** 读取，**Then** 字段id为`tf-b-<短名>`，名称、类型与契约一致。
3. **Given** 契约中的`bug.specs`/`bug.found`/`bug.fix`，**When** 核对，**Then** 目标表分别为`indep`与`ver`，且都在同一项目内。

### User Story 2 - 缺陷完成判据单字段且覆盖"不修复"（Priority: P1）

一个缺陷是否算完成，只看`状态`：`closed`即完成，其余即未解决；"修复发布"与"明确不修复"都记`closed`，差别写进证据与修复版本。

**Why this priority**: 判据唯一才能被统计与闸门复用；"不修复"若另开状态，就出现两个终态、两套数。

**Independent Test**: 造四条缺陷（open/fixing/verifying/closed），再按`bug.status==closed`统计，未解决数为3；把一条不修复缺陷置`closed`且不填修复版本后，未解决数降为2。

**Acceptance Scenarios**:

1. **Given** 状态枚举`open`/`fixing`/`verifying`/`closed`，**When** 统计未解决数，**Then** 只排除`closed`，其余三个都计入。
2. **Given** 一条缺陷要置`closed`，**When** 走写入期校验，**Then** 必须满足其一：修复版本有值且证据可核验，或证据写明不修复结论与依据且剩余事项为空。
3. **Given** 一条缺陷已被置`closed`，**When** 读取版本表上一版本未解决数，**Then** 该缺陷不再计入，且历史证据无改动。
4. **Given** 契约，**When** 检查`bug.status`的枚举，**Then** 不含`na`/`wontfix`，终态只有`closed`。

### User Story 3 - 版本表挂接与上一版本Bug口径（Priority: P1）

版本表的"上一版本Bug总数/未解决数/就绪"有明确来源：以`发现版本`为挂接键，取"发现版本=上一版本"的缺陷集合，总数数集合大小、未解决数数状态不是`closed`的行，就绪=未解决数0，空集为真。

**Why this priority**: 这是发布条件里唯一还没有数据来源的一项；口径不定，"就绪"永远停在人工填报。

**Independent Test**: 建版本`v1.0.0`与`v1.0.1`，在`v1.0.0`下挂两条缺陷（一条closed、一条open），核对`v1.0.1`的上一版本Bug总数为2、未解决数为1、就绪为否；再把open那条置closed，就绪转是。

**Acceptance Scenarios**:

1. **Given** 版本`vX`与语义序紧邻的上一版本`vY`，**When** 计算上一版本Bug集合，**Then** 集合为`{bug | bug.found == vY}`，不按修复版本、不按发布状态筛选。
2. **Given** 上述集合，**When** 计算未解决数，**Then** 计数条件为`bug.status != closed`；`closed`的行不计入。
3. **Given** 上一版本无任何缺陷，**When** 读取就绪，**Then** 未解决数为0、就绪为真，含义是"上一版本无缺陷"，不是"已验证"。
4. **Given** 自动聚合尚未实现，**When** 填报版本表两个数字字段，**Then** 口径与本条一致，字段类型保持`number`不变。

### User Story 4 - 线上可重入建表（Priority: P1）

一次性脚本在线上`tableflow`项目建出`tf-bug`表与12个字段，建后回读逐字段核对；重复执行只跳过、不新增也不删除。

**Why this priority**: 契约不落成线上表就只是文档；脚本若不可重入，二次执行会造重复字段，看板直接坏掉。

**Independent Test**: 连续执行脚本两次，第二次输出全部"跳过"，`GET /api/tables/tf-bug/table`的字段数仍为12。

**Acceptance Scenarios**:

1. **Given** 线上无`tf-bug`表，**When** 执行脚本，**Then** 建表并建12个字段，回读核对全部通过。
2. **Given** 线上已有`tf-bug`表与同名字段，**When** 再次执行，**Then** 不产生新字段，输出跳过清单，退出码0。
3. **Given** 已存在同id但名称/类型/配置与契约不符，**When** 执行脚本，**Then** 报冲突并以非0退出，不修改、不删除该字段。
4. **Given** 线上`tf-bug`表被建出，**When** 读取现有三表，**Then** 三表的字段、行、计算值均无变化。

### Edge Cases

- 一个缺陷横跨多份规格：`关联规格`填多个indep行，一次缺陷只占一行。
- 缺陷暂时归不到任何规格：`关联规格`为空数组，允许；归因后回填，不改变状态与判定。
- 不修复的缺陷：`closed`+修复版本留空+证据写依据+剩余事项为空；不得留着`open`占闸门，也不得删行抹掉发现版本。
- `发现版本`指向的版本行被删：与010的悬空口径一致，视为无法核验——版本表按集合口径统计时该缺陷不计入，但不得因为"看不见"而把闸门判真；修法是修缺陷行的挂接，不是删数据。
- `修复版本`早于`发现版本`：属录入错误，靠人工核对，不引入自动校验（避免与010的计算口径耦合）。
- 版本号无法解析（如`hotfix-1`）：视为无上一版本，集合为空、就绪为真，并在该版本`变更说明`里写明。
- 缺陷表为空：上一版本总数0、未解决0、就绪为真（空集语义）。

## Requirements *(mandatory)*

- **FR-001**: 契约从`board@1`扩展为`board@2`，新增`bug`表，其余三表的口径不变。
- **FR-002**: `bug`表12字段：`bug.id`/`bug.title`/`bug.status`/`bug.severity`/`bug.source`/`bug.specs`/`bug.found`/`bug.fix`/`bug.evidence`/`bug.rest`/`bug.ms_case`/`bug.owner`，每个字段都有`key`/`name`/`type`。
- **FR-003**: `bug.status`取值为`open`/`fixing`/`verifying`/`closed`，必填；`closed`是唯一完成判据与唯一终态。
- **FR-004**: `bug.severity`取值为`blocker`/`critical`/`major`/`minor`，必填；不参与任何闸门判定。
- **FR-005**: `bug.source`取值为`test`/`prod`/`review`/`user`，必填；只记录发现渠道。
- **FR-006**: `bug.specs`是指向`indep`的`relation`，可空（暂未归因）、可多值（多对多）。
- **FR-007**: `bug.found`是指向`ver`的`relation`，必填、单值，是版本表挂接的唯一键。
- **FR-008**: `bug.fix`是指向`ver`的`relation`，可空、单值；修复发布时填，不修复留空，不参与判定。
- **FR-009**: `bug.evidence`/`bug.rest`/`bug.ms_case`/`bug.owner`为记录字段；置`closed`时证据必须有可核验依据、剩余事项必须为空（写入期校验，后续需求实现）。
- **FR-010**: 契约声明`bug_done = status == closed`、`bug_flow = open → fixing → verifying → closed`、无`na`。
- **FR-011**: 契约声明版本表口径：`ver.bug_total = count(发现版本==上一版本)`、`ver.bug_open = count(发现版本==上一版本且状态!=closed)`、`ver.bug_ready = and(bug_open==0)`、空集为真。
- **FR-012**: "上一版本"按版本号语义序取紧邻的前一版本，不按发布时间；无法解析时视为无上一版本。
- **FR-013**: 版本表三个Bug字段的类型与判定规则不变（`number`/`number`/`computed`），自动聚合实现不在本需求范围。
- **FR-014**: 交付一次性建表脚本，在线上`tableflow`项目建`tf-bug`（order 4）与12个字段，建后回读逐字段核对。
- **FR-015**: 脚本可重入：已存在且配置一致则跳过；配置冲突则报错退出，不修改、不删除；重复执行不产生重复字段。
- **FR-016**: 不修改`backend/src/tableflow/`，不修改现有三表（`tf-ver`/`tf-indep`/`tf-dep`）的字段与行数据。
- **FR-017**: 看板只更新`011-AR`一行（阶段状态、场景数、任务总数、状态），不改其它行。

## Success Criteria *(mandatory)*

- **SC-001**: `board@2.yaml`可被YAML解析器读取，`bug`表字段数为12，`tables.*.fields[*].key`全局无重复。
- **SC-002**: 线上`GET /api/tables/tf-bug/table`返回12个字段，字段id、名称、类型、枚举、关联目标与`board@2.yaml`逐项一致；不存在契约外字段。
- **SC-003**: 建表脚本连续执行两次，第二次全部跳过（0次写入），字段数仍为12，退出码0。
- **SC-004**: 现有三表在脚本执行前后的字段集合与行集合无差异（只读快照比对）。
- **SC-005**: 看板`011-AR`行的场景数、任务总数与spec.md/tasks.md的实际条数一致，阶段状态与本需求实际进度一致。

## Non-Goals

- 自动聚合实现与重算（版本表`bug_total`/`bug_open`由脚本或人工按口径填报）。
- MS同步：把MS测试用例与缺陷双向同步（014）。
- 交互协议与错误码（012）。
- 用户管理与负责人自动填充（013）。
- 缺陷表与其它项目的存量迁移、字段改名。
- 修改`tableflow-board`技能文本（008 FR-010约定的事，本需求只交付契约与线上表；技能同步另行安排）。

## Key Entities

- **bug（缺陷）**：一行一个缺陷；`状态`是唯一完成判据。
- **发现版本（bug.found）**：缺陷最早出现的版本；版本表按它取"上一版本Bug"集合。
- **修复版本（bug.fix）**：缺陷被修复发布的版本；不参与判定，用于回答"修在哪一版"。
- **上一版本**：版本号语义序中紧邻当前版本的版本（不看发布状态与发布时间）；无则集合为空。
- **暂未归因**：`关联规格`为空数组的缺陷；允许存在，不阻塞流转。
