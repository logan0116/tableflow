# Feature Specification: tf_update需求登记技能（v0.6.0）

**Feature Branch**: `009-tf-update`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求009-AR：`tf_update` skill接收用户口述需求，按`board@1`判定树完成分类（新规格/变更单/就地改/不进看板），登记到看板并挂到目标版本；必须给出可核验依据（规格编号+场景号）；不写spec、不改验收状态、不猜版本号。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 分类无判据 | `specs/008-board-contract/board@1.yaml` `classify`之前，旧口径"是否需要独立spec"没有输入、没有第三类、没有横切情形 | 需求落错表，事后返工 |
| 依据不可核验 | 看板`tf-indep`历史行的`条款`只写一句需求，指不到规格与场景 | 无法判断"这条到底被覆盖没有"，也无法在评审时复核 |
| 重复登记 | 同一需求两次口述会导致各建一行，行id冲突或语义重复 | 版本`就绪`被重复行拖住，统计失真 |
| 版本靠猜 | 口述里通常没有版本号，Agent按"最近提到"或"下个版本"猜 | 需求挂错版本，发布范围错 |
| 写失败当成功 | 写接口三态：`success`/`failed`(400)/`unknown`(503)；只看HTTP 200或只看行id就宣布完成 | 行没落库却报成功 |

`unknown`的证据：`backend/src/tableflow/app.py:146`把`exc.unknown`映射为503与`{"result":"unknown"}`；`unknown`不得当成功（见`skills/tableflow-board/SKILL.md`写接口一节）。

## Clarifications

### Session 2026-11-19

- Q: 判定树用哪一棵？ → A: 只用`specs/008-board-contract/board@1.yaml`的`classify.order`五分支，顺序即优先级：`in_place` → `change` → `new_spec` → `cross` → `out_of_board`。
- Q: 分类依据写什么？ → A: `<规格编号>#US<n>-AS<m>`（如`007-AR#US1-AS2`）；`new_spec`写`新增条款`并列出比对过的规格编号；`out_of_board`写`不改产品行为`+落点（构建/环境/文档）。
- Q: "指不到就只问一个问题"具体是什么？ → A: 只输出一条提问，且只问一件事："这条需求要改/新增哪份规格的哪个场景？"；不问版本、不问优先级、不问负责人。
- Q: 编号怎么分配？ → A: `indep`取现有最大`NNN-AR`的NNN+1；`dep`沿用项目现有编号前缀取最大序号+1；演练用`≥090`的保留号段，结束后删除。
- Q: 幂等怎么判？ → A: 先读后写。目标行已存在且条款归一化后一致 → `already_registered`（不重复写）；行存在但条款不同 → `failed`（冲突，不覆盖）。
- Q: 挂哪个版本？ → A: 由人明确给出（口述或任务单里的版本号）；没给就`failed`并只问一个问题，不自动选版本、不按"最早planned"推断、不新建版本行、不改`发布状态`。目标版本还须满足两条：发布状态是`planned`，且不晚于最近一个已发布版本的一律拒绝（V060-02）。
- Q: 失败重试几次？ → A: `failed`(400) 不重试（重试只会得到同样的400）；`unknown`(503) 先回读，回读判不清才允许原样重试一次。
- Q: 为什么不动验收状态？ → A: 验收是需求方的判定；登记只负责"需求进看板、挂对版本"。置`accepted`另有前置（`implement=done`，见`board@1.rules.spec_done_precondition`）。
- Q: 需求横跨"新增能力"与"改已accepted规格"怎么办？ → A: 拆一行`indep`与一行`dep`，影响面互相引用（`board@1.classify.note`）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 分类可复核 (Priority: P1)

用户口述一条需求，技能读看板现状与`specs/*/spec.md`，按判定树给出唯一一张表的结论，并附可点开的依据（规格编号+场景号）。

**Why this priority**: 分类错了，后面的登记、挂版本、回归全部白做；依据不可核验，评审时无法复核。

**Independent Test**: 取三条真实需求（改已accepted规格、改未accepted规格、全新能力），各自给出唯一结论且依据能指到`spec.md`里的场景编号。

**Acceptance Scenarios**:

1. **Given** 需求改变一份`accepted`规格的行为或验收口径，**When** 走判定树，**Then** 结论为`change`（`dep`开一行），依据指向该规格的具体场景。
2. **Given** 需求被一份尚未`accepted`的规格的场景覆盖，**When** 走判定树，**Then** 结论为`in_place`（改该规格与`indep`行，不新建行）。
3. **Given** 现有规格都不覆盖，需要新条款或新场景，**When** 走判定树，**Then** 结论为`new_spec`（`indep`新增一行），依据写`新增条款`并列出比对过的规格编号。
4. **Given** 一次改动横切多份`accepted`规格，**When** 走判定树，**Then** 结论为`cross`（一张`dep`挂多份规格，影响面分别写清）。
5. **Given** 需求不改变产品行为（构建/部署/环境/文档），**When** 走判定树，**Then** 结论为`out_of_board`，只记录版本变更说明建议，不写看板。
6. **Given** 依据指不到任何规格编号与场景号，**When** 尝试登记，**Then** 技能停止写操作，只输出一条提问"这条需求要改/新增哪份规格的哪个场景？"，且不建行。

---

### User Story 2 - 登记幂等 (Priority: P1)

同一需求重复执行不会产生第二行；中断后重跑能补齐而不是复制。

**Why this priority**: 看板的`就绪`是逐行判定，重复行直接污染统计；口述需求天然会重复。

**Independent Test**: 对同一口述连续执行两次，第二次返回`already_registered`且行数不变。

**Acceptance Scenarios**:

1. **Given** 目标行已存在且条款归一化后一致，**When** 再执行，**Then** 返回`already_registered`（含已存在行id），不发起写请求。
2. **Given** 目标行id已存在但条款不同，**When** 执行，**Then** 返回`failed`并说明冲突，MUST NOT覆盖已有行。
3. **Given** 第一次执行在写入后、挂版本前中断，**When** 重跑，**Then** 回读发现行已存在，只补挂版本，不重复建行。
4. **Given** 演练号段（`≥090`）的行，**When** 演练结束，**Then** 行被删除且回读确认不存在。

---

### User Story 3 - 版本挂载确定 (Priority: P1)

需求登记后挂到**人明确指定的目标版本**；没给版本就拒绝登记并追问，绝不自动挑版本，也不改版本自身状态。

**Why this priority**: 版本决定了发布范围；猜错版本比不挂更难发现。

**Independent Test**: 给一个`planned`且晚于最近已发布版本的版本号，登记后挂到该版本；不给版本号重跑，返回`failed`与一条提问，且一行都没写。

**Acceptance Scenarios**:

1. **Given** 人给出了版本号且该版本`planned`、晚于最近已发布版本，**When** 登记，**Then** 挂到该版本，不改它的`发布日期`与`发布状态`。
2. **Given** 人没给版本号，**When** 执行，**Then** 返回`failed`并只输出一条提问（列出当前`planned`版本），MUST NOT写任何行。
3. **Given** 目标行已挂在该版本关联里，**When** 重跑，**Then** 关联数组不变（不重复追加）。
4. **Given** 登记的是`dep`变更单，**When** 挂载，**Then** 写入版本的`需求关联（依赖）`，且挂载后该版本`回归通过`转否（`change.regress=todo`），报告里点明这一后果。

---

### User Story 4 - 三态与回读 (Priority: P1)

每次写操作都有明确终态：`success`/`failed`/`unknown`；`unknown`不得当成功，必须回读判定。

**Why this priority**: 三态是tableflow写接口的既有契约，错判会让"行没落库"变成"已登记"。

**Independent Test**: 用已存在的行id触发`failed`(400)，用回读确认无副作用；`unknown`分支以只读回读规则验证（生产不诱发503）。

**Acceptance Scenarios**:

1. **Given** 写接口返回`success`，**When** 回读目标行，**Then** 关键字段（行id、条款、验收状态）与预期一致，才报告`success`。
2. **Given** 写接口返回`failed`(400)，**When** 处理，**Then** 原样报错、不重试、不把失败描述成"已登记"。
3. **Given** 写接口返回`unknown`(503)，**When** 处理，**Then** 立即GET回读目标行：存在且字段一致→按`success`处理并标注"由回读确认"；不存在→按`failed`处理；回读本身失败→保留`unknown`。
4. **Given** 写后回读发现字段与预期不一致，**When** 生成报告，**Then** 终态为`failed`并列出差异字段，不宣称完成。

---

### User Story 5 - 边界受约束 (Priority: P2)

技能只做"需求进看板、挂对版本"，不越界改规格文件与验收状态。

**Why this priority**: 越界会破坏"契约→规格→看板"的单向链路，且验收判定权不在Agent。

**Independent Test**: 执行完整流程后，`specs/`下文件mtime不变，目标行`验收状态`仍为`pending`，看板无新增表/字段。

**Acceptance Scenarios**:

1. **Given** 分类结果为`in_place`，**When** 登记，**Then** 只更新`indep`行与`条款`/`规格目录`等记录字段，MUST NOT改`specs/`下任何文件。
2. **Given** 任何分类结果，**When** 登记完成，**Then** 目标行`验收状态`仍为`pending`，MUST NOT写`accepted`。
3. **Given** 执行前后对比看板结构，**When** 校验，**Then** 表数与字段数不变，MUST NOT建表、建字段、改计算字段配置。

### Edge Cases

- 口述需求同时含"新能力"与"改已accepted规格"：拆一行`indep`与一行`dep`，`影响面`互相引用。
- 一次改动横切多份accepted规格：一张`dep`挂多份规格，影响面分别写清。
- 目标行id已被占用但内容无关（如演练行）：报冲突并给出占用行，不静默改写。
- 版本关联里已有悬空行id（被引用行已删除）：挂载时保留原数组并追加，不清理他人数据。
- 写接口不可达：终态`unknown`，报告里给"回读命令"供人复核。

## Requirements *(mandatory)*

- **FR-001**: 技能MUST以`specs/008-board-contract/board@1.yaml`的`classify.order`五分支作为唯一判定树，顺序即优先级。
- **FR-002**: 分类结论MUST附依据`<规格编号>#US<n>-AS<m>`；`new_spec` MUST写`新增条款`并列出比对过的规格编号；`out_of_board` MUST写不改产品行为的落点。
- **FR-003**: 依据指不到任何规格与场景时，技能MUST停止写操作，只输出一条提问，且MUST NOT建行。
- **FR-004**: 技能MUST先读后写：写前读目标表，按行id与条款归一化值判重。
- **FR-005**: 重复执行MUST返回`already_registered`且不新增行；行id冲突但条款不同MUST返回`failed`且不覆盖。
- **FR-006**: `indep`新行编号MUST取现有最大`NNN-AR`的NNN+1；演练MUST使用`≥090`保留号段并在结束后删除。
- **FR-007**: 目标版本MUST由人明确给出；缺失时MUST返回`failed`并只问一个问题，MUST NOT自动选版本。目标版本MUST存在、MUST为`planned`、MUST晚于最近一个已发布版本，任一不满足即`failed`且不写行（V060-02）。
- **FR-008**: 挂载MUST走版本行的relation字段数组（`indep`→`需求关联（独立）`/`独立需求关联`，`dep`→`需求关联（依赖）`/`依赖需求关联`；按名称解析，兼容board@1与board@2两种叫法），已包含目标行时MUST NOT重复追加。
- **FR-009**: 每次写操作MUST归入`success`/`failed`/`unknown`三态；`unknown` MUST以GET回读判定，MUST NOT直接当成功。
- **FR-010**: `success`判定MUST包含回读校验（行id、条款、验收状态、版本关联四项），任一不符即`failed`。
- **FR-011**: 技能MUST NOT修改`specs/`下任何文件，MUST NOT写`验收状态`，MUST NOT建表、建字段、改计算字段配置。
- **FR-012**: 登记`dep`时MUST填`条款`（点到规格编号与场景号）、`关联的独立规格需求`、`影响面`、`回归状态=todo`。
- **FR-013**: 报告MUST输出分类结论、依据、登记动作、目标版本、写接口三态、回读结果六个字段，供人直接复核。
- **FR-014**: 技能MUST在报告中给出本次所有写请求的审计口径（`X-Agent-Id`、`X-Origin`），使每次变更可追溯到执行者。

## Success Criteria *(mandatory)*

- **SC-001**: 对三条真实需求（改已accepted规格 / 改未accepted规格 / 全新能力）各产出唯一结论，依据可指到`spec.md`场景编号或`新增条款`。
- **SC-002**: 同一口述连续执行两次，第二次返回`already_registered`，看板行数不变。
- **SC-003**: 对`failed`(400) 与`unknown`(503) 两种响应，报告分别给出"不重试"与"回读判定"的处理结论，无"失败当成功"表述。
- **SC-004**: 演练行（`≥090`号段）在结束后被删除，回读返回不存在，`v0.6.0`行计算字段与执行前一致。
- **SC-005**: 执行完整流程后`specs/`下文件未变，目标行`验收状态`仍为`pending`，表数与字段数不变。

## Non-Goals

- 不写`spec.md`/`tasks.md`（规格的撰写是speckit流程，不是登记技能）。
- 不改`验收状态`、不置`accepted`、不做发布动作。
- 不猜版本号、不新建版本、不改`发布状态`。
- 不建表、建字段、改计算字段配置（010/011的范围）。
- 不做需求优先级排序、排期与工作量估算。

## Key Entities

- **分类结论（Classification）**：`in_place`/`change`/`new_spec`/`cross`/`out_of_board`五选一，附依据串。
- **登记动作（Registration）**：`indep`新建行、`dep`开单、`in_place`就地改；幂等键是"行id + 归一化条款"。
- **目标版本（TargetVersion）**：人明确指定的`planned`版本行id，且必须晚于最近一个已发布版本；不由技能推断。
- **回读校验（Readback）**：写后用GET比对四项字段，决定终态。
- **三态（WriteOutcome）**：`success`/`failed`/`unknown`，来源是写接口响应体，不是HTTP码。
