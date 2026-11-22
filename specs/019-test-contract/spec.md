# Feature Specification: 看板测试体系契约 board@4（六表）

**Feature Branch**: `019-test-contract`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 019-AR。看板停在 board@3 四张表，测试域的输出没有落点：SE 的规格有 `indep`、变更单有 `dep`、缺陷有 `bug`，而测试的**用例、执行记录**在 tableflow 里无处安放，只能挤在 MeterSphere 那个缺「计划↔用例关联写入端点」的实例里（`specs/014-ms-skills/spec.md` 实测 18 个候选路径全 500）。结果是谁都答不上「这条验收场景在本版本跑过没有」。本规格把契约从四表扩到六表，并给版本表加六节点进度，使测试进度可判定。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 测试域输出无落点 | board@3 四表只有 `bug` 承载测试产出；用例与执行记录没有表 | 执行结果留在 MS，与规格、缺陷两张皮 |
| MS 实例关联链断裂 | 18 个候选关联端点全 `500 No static resource`；`/run` 无关联行 id 可用 | 回写无从下手，计划内用例数恒为 0 |
| 场景与实际执行无法对上 | 用例散在 MS，规格场景号没有成为任何表的键 | 无法回答「这条场景跑过没有」「哪一版跑过」 |
| 版本进度靠口头 | 版本表只有三布尔，没有阶段记录 | 说不清版本卡在开发还是卡在测试 |
| 空集与完成判定口径不一 | 四表时代 `empty_set` 为真；引入用例后若不定义，会出现「没测也说完成」 | 判定失真 |

## Clarifications

### Session 2026-11-22

- Q: 为什么不设测试计划表？ → A: 版本直接持有执行记录。一个版本的执行范围就是「本版纳入的用例集合」，计划这一层不承载额外信息；关联用例的动作即建一条执行记录行。删掉计划表后，执行清单的弹窗改由版本行承担。
- Q: 用例表是真源吗？ → A: 不是。`specs/<dir>/spec.md` 的 Acceptance Scenario 是唯一真源，用例是派生投影，以场景号作幂等键。
- Q: 六节点是人工填还是派生？ → A: 人工 enum（四态），但加写入期校验防止绕过自动判定；条件表达式的汇总计算留给 023。
- Q: 进度和结论要不要分开？ → A: 必须分开。`run.state` 管「跑没跑」，`run.result` 管「跑得怎么样」；版本表三个用例字段只消费 `state`。
- Q: 没纳入本版的用例算漏测吗？ → A: 不算。进度只统计本版已纳入的用例；覆盖率由「测试设计」节点把关，不由计算字段兜底。
- Q: 用例执行情况表要不要进导航？ → A: 不进（`kind=detail`），只经版本行弹窗展示。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 契约落到数据层 (Priority: P1)

任意一个已迁移项目按 `board@4.yaml` 建出六张表，字段名、类型、顺序、关系方向、表级 kind 全部与契约一致。

**Why this priority**: 这是后面五条需求的共同地基。契约不落地，其他一切都是纸上约定。

**Independent Test**: 对一个项目的六张表逐字段比对契约，差异为 0；检视 `run` 表的 kind 与导航可见性。

**Acceptance Scenarios**:

1. **Given** `specs/019-test-contract/board@4.yaml`，**When** 按契约对一个项目建表，**Then** 存在 `ver`/`indep`/`dep`/`case`/`run`/`bug` 六张表，每张表的字段数、字段名、类型、顺序与契约一致。
2. **Given** 六张表已建，**When** 校验全部 relation 字段的 `target`，**Then** 得到 8 条边（ver→indep/dep/bug/run、run→case、case→indep、dep→indep、bug→indep），且任何一对表之间只有一条边。
3. **Given** `run` 表，**When** 读取表元数据，**Then** 其 kind 为 `detail`，不进表导航，但仍可经接口按 id 读取单行。
4. **Given** `case` 表的全部行，**When** 校验行 id 格式，**Then** 每条都匹配 `<规格号>-US<n>-AS<m>`，且能解析出对应的规格编号并在 `indep` 表中找到该行。

### User Story 2 - 用例从规格场景派生且幂等 (Priority: P1)

一份规格的验收场景能稳定派生为用例，重复同步不产生重复行，规格删场景时能被发现而不是静默留在看板上。

**Why this priority**: 用例是执行记录的锚点；派生不幂等会造成用例膨胀与结果错位。

**Independent Test**: 对同一份规格连续跑两次派生，第二次新建 0 条；改动一条场景后重跑，该用例就地更新。

**Acceptance Scenarios**:

1. **Given** 一份 spec 含 N 条 Acceptance Scenario，**When** 执行派生，**Then** 生成 N 条用例，行 id 即场景号（如 `008-US1-AS1`），且每条 `case.indep` 指向来源规格。
2. **Given** 已派生过一次，**When** 再次执行派生，**Then** 新建 0 条；名称或步骤有变化的用例就地更新，其余不变。
3. **Given** 某规格已派生过，**When** 该 spec 删掉一条场景后重跑派生，**Then** 报告该用例「源场景已不存在」，不静默保留、也不无提示删除。
4. **Given** 一条用例被多个版本纳入，**When** 执行派生更新其步骤，**Then** 各版本的执行记录不受影响（记录只引用用例 id，不复制用例内容）。

### User Story 3 - 执行记录与版本进度可判定 (Priority: P1)

版本表能回答「本版要跑多少条、已跑多少条、是否跑完」，且进度与结论互不污染。

**Why this priority**: 这是整个测试体系给出版本发布资格的直接依据。

**Independent Test**: 一个版本纳入 10 条用例、执行 4 条，读出「用例总数 10、已完成 4、用例是否完成=否」。

**Acceptance Scenarios**:

1. **Given** 一个 planned 版本与一条已存在的用例，**When** 把该用例纳入本版，**Then** 生成一条 `run` 行（`state=todo`、`result` 为空）并把其 id 追加到 `ver.runs`；回读版本行能查到该执行记录。
2. **Given** 版本纳入 10 条用例、其中 4 条已执行，**When** 重算计算字段，**Then** 用例总数为 10、已完成用例数为 4、用例是否完成为假。
3. **Given** 10 条全部执行完毕，**When** 重算，**Then** 已完成用例数为 10、用例是否完成为真；任一条 `result=fail` 不改变这三个字段。
4. **Given** 一条执行记录 `state=todo`，**When** 直接写 `result=pass` 而不改 state，**Then** 返回 400，且该行两个字段读回均不变。
5. **Given** 一个版本未纳入任何用例，**When** 重算，**Then** 用例总数为 0、已完成用例数为 0、用例是否完成为真（空集语义）。
6. **Given** 同一版本同一用例已有一条执行记录，**When** 再次纳入同一用例，**Then** 返回 400 或就地复用该行，不产生第二条记录。

### User Story 4 - 六节点串行推进且不能绕过闸门 (Priority: P1)

版本进度的六个节点按固定顺序推进，且人工改节点状态不能绕过自动判定。

**Why this priority**: 六节点直接决定发布条件；能绕过的闸门等于没有闸门。

**Independent Test**: 前序未完成时把后序节点置 `done` 返回 400；有未关闭缺陷时把「测试验收」置 `done` 返回 400。

**Acceptance Scenarios**:

1. **Given** 版本六节点全为 `todo`，**When** 把「开发」置 `done`，**Then** 返回 400，错误信息指出前序节点未完成。
2. **Given** 「版本需求设计」到「开发验收」五个节点均为 `done`，**When** 把「测试」置 `done` 而本版用例尚未全部执行，**Then** 返回 400，指出用例未执行完。
3. **Given** 用例已全部执行、但本版 Bug 管理集合内仍有未关闭缺陷，**When** 把「测试验收」置 `done`，**Then** 返回 400，指出缺陷未清零。
4. **Given** 「开发验收」节点，**When** 本版规格尚有未验收的就把它置 `done`，**Then** 返回 400。
5. **Given** 某节点为 `failed`，**When** 推进其后一个节点，**Then** 返回 400；把失败节点改回 `doing` 后重新置 `done`，才允许继续。
6. **Given** 六节点全部 `done`，**When** 重算 `stage_done` 与 `gate`，**Then** 两者均为真；任一节点退回非 `done`，两者转假。

### User Story 5 - 存量迁移不丢数据 (Priority: P2)

已迁到 board@3 的项目在加两表、加版本表字段后，原有数据逐字段不变，已发布版本的发布条件不下降。

**Why this priority**: 八个项目在用，迁移出错会直接影响发布判断。

**Independent Test**: 迁移前后对四张老表逐行逐字段比对，差异 0；已 released 版本的六节点读回均为 `done`。

**Acceptance Scenarios**:

1. **Given** 一个 board@3 项目，**When** 执行迁移，**Then** 新增 `case`/`run` 两表与版本表十一个字段（六个节点、六节点汇总、测试用例关联、用例总数、已完成用例数、用例是否完成），四张老表的行数与字段值完全不变。
2. **Given** 一个 `released` 版本，**When** 迁移完成，**Then** 其六节点均为 `done`，`gate` 仍为真；`planned` 版本的六节点为 `todo`。
3. **Given** 迁移中途失败，**When** 重跑迁移，**Then** 不重复建表、不覆盖已有行，最终状态与一次成功相同。

### User Story 6 - 一致性门禁认得 board@4 (Priority: P1)

门禁按 board@4 校验全部项目与模板产物，缺表、字段漂移、闸门标记错误都能被指出。

**Why this priority**: board@4 落地后若门禁仍按 board@3 跑，会产生大量假失败或假通过。

**Independent Test**: 对一个缺 `run` 表的项目跑门禁，期望失败并指名缺表。

**Acceptance Scenarios**:

1. **Given** 全部已迁移项目，**When** 跑门禁，**Then** 六表字段名/类型/顺序、relation 的显示列与状态列、闸门标记差异均为 0。
2. **Given** 一个项目缺 `run` 表，**When** 跑门禁，**Then** 失败并指出缺失的表。
3. **Given** 一个项目的版本表仍是 board@3 的 15 字段，**When** 跑门禁，**Then** 失败并逐字段列出差异。
4. **Given** 模板脚本的产物，**When** 用同一门禁校验，**Then** 差异为 0。

## Requirements *(mandatory)*

- **FR-001**: 契约 MUST 以 `specs/019-test-contract/board@4.yaml` 为唯一来源，定义六表的字段名、类型、顺序、枚举、必填与闸门标记。
- **FR-002**: relation 字段 MUST 单向且无环；任何一对表之间 MUST 只有一条边；`run` MUST NOT 存在指向版本的字段。
- **FR-003**: `run` 表 MUST 标为 `detail`，不进表导航；`case`/`ver`/`indep`/`dep`/`bug` MUST 为 `board`。
- **FR-004**: 用例 MUST 由规格验收场景派生，行 id MUST 为场景号；重复派生 MUST 幂等（新建 0 条）；源场景消失 MUST 被报告。
- **FR-005**: 每条用例 MUST 指向一份存在的规格（`case.indep` 非空且目标存在）。
- **FR-006**: 纳入用例 MUST 走两步写入（建 `run` 行 → 追加到 `ver.runs`），客户端 MUST 回读版本行确认第二次写入。
- **FR-007**: 同一版本内同一用例 MUST 只有一条执行记录；重跑 MUST 就地更新。
- **FR-008**: `run.state` 与 `run.result` MUST 一致：`state=todo` 时 `result` 为空，`state=done` 时 `result` 非空，否则 400。
- **FR-009**: 版本表的用例总数、已完成用例数、用例是否完成 MUST 只由 `ver.runs` 与 `run.state` 计算，MUST NOT 消费 `run.result`。
- **FR-010**: 六节点 MUST 串行推进；后序节点置 `done` MUST 校验前序均 `done` 且无 `failed`。
- **FR-011**: 节点置 `done` MUST 校验一致性：「测试」要求用例全部执行、「测试验收」要求缺陷清零与变更回归通过、「开发验收」要求本版规格全部 accepted。
- **FR-012**: `gate` MUST 等于六节点全部 `done` 之与；三布尔 MUST 降为展示字段，不再参与 `gate`。
- **FR-013**: 空集 MUST 沿用 board@3 语义：无关联行时数量为 0、布尔为真。
- **FR-014**: 迁移 MUST 幂等，MUST NOT 改动四张老表的既有字段值；已 `released` 版本的六节点 MUST 初始化为 `done`。
- **FR-015**: 一致性门禁 MUST 支持 board@4，并保留对 board@3 项目的识别能力（迁移未完成的项目应被报出而不是误判为通过）。

## Non-Goals

- 不实现条件表达式与行内算术（那是 023 的范围；本规格只在 `stage_done` 处标注依赖）。
- 不定义新表的接口形态与错误码（那是 020 的范围）。
- 不做界面视图、角色切换（021/022）。
- 不做六个角色技能（024）。
- 不迁移 MeterSphere 里的历史执行数据；MS 只保留"历史台账"身份。
- 不改 `bug`/`dep`/`indep` 三张老表的字段口径（除版本表两个 Bug 字段改名）。
- 不改计算引擎的既有口径（空集、悬空、重算时机沿用 010）。

## Success Criteria

- 八个项目按 board@4 校验差异为 0；模板脚本产物同样为 0。
- 同一份规格连续派生两次，第二次新建 0 条用例。
- 版本纳入 10 条用例、执行 4 条时，三个用例字段读出 10 / 4 / 否。
- 有未关闭缺陷时，把「测试验收」置 `done` 被拒（400）。
- 迁移前后四张老表逐行逐字段一致，已发布版本 `gate` 不下降。
- 缺 `run` 表的项目被门禁指出，而不是静默通过。
