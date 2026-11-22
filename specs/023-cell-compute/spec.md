# Feature Specification: 计算字段条件表达式（v0.7.0）

**Feature Branch**: `023-cell-compute`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 023-AR。`board@4` 把版本发布闸门收到六个四态枚举节点上（`specs/019-test-contract/board@4.yaml` 第142–143、244–255行）：`ver.stage_done = and(六个节点 == done)`、`ver.gate = and(ver.stage_done)`。`and` 的条件项取值规则从未写成契约，配置期只校验"equals 非空"，取值类型写错（`枚举 == 5`、`枚举 == "Done"`）照样 200 落库、之后永远算假。本规格把 `and(字段 == 取值)` 固化为封闭、类型安全的条件表达式，作为六节点闸门落地的前提。

## 背景与问题证据

| 现状 | 证据 | 后果 |
|---|---|---|
| 条件项只有"等于"，取值类型无规则 | `backend/src/tableflow/calculation.py` 第657–674行的 `_compute_and` 用 `value != condition["equals"]` 比较；第323–342行的 `and` 校验只判 `equals` 非空 | 配置期 `{"field_id": <enum>, "equals": 5}` 返回 200（改动前实测），重算永远为假，闸门永久不开且无人察觉 |
| 实现能力大于契约描述 | `backend/tests/test_formula.py` 第220–231行的 `test_and` 早已用 `v-doc == "done"`（枚举）通过；`board@4` 的早期草案曾写"board@3 的 and 只接受布尔字段"（该说明已在本轮更正） | 契约与实现各说一套：六节点闸门能不能落地，只能靠翻代码判断 |
| 六节点是四态枚举，布尔字段接不住 | `board@4.yaml` 第184–243行（六个 `ver.stage.*` 均为 enum，取值 `todo/doing/done/failed`） | 没有 `== 取值` 就只能补六个中间布尔字段：字段表膨胀，新增节点还得改公式 |
| 写错取值静默生效 | 同上：枚举取值大小写写错（`"Done"`）是永远为假的配置，校验与重算都不报错 | 配置错误被当成业务事实"未完成"，排查方向被带偏 |

## Clarifications

### Session 2026-11-22

- Q: 为什么不做通用表达式（`!=`、`>`、括号、`or`、脚本）？ → A: 六节点闸门只需要"全部等于"。通用表达式会让配置校验、幂等重算、审计失去边界，也与 `010` 的 kind 封闭原则冲突。`and` 就是"条件项全部成立的合取"，条件项只有"等于"。
- Q: 条件项取值要不要类型校验？ → A: 要，且不做隐式强转。类型不符（`数字 == "2"`、`枚举 == 5`）或枚举取值不在声明域内（`"Done"`）一律配置期 `400`，不落库；"2" 与 2 不是同一个取值，强转只会掩盖写错。
- Q: 枚举取值域校验会不会太严（将来加枚举值）？ → A: 只校验条件取值在**当前声明域**内。新增枚举值不影响既有条件；把选项改小导致旧条件失效时，配置更新会当场 `400`——这正是需要的暴露时机。
- Q: 条件能引用哪些字段？ → A: 本表字段，包括同表计算字段（取有效值，人工覆盖优先）。不能引用 relation 字段：关联值是行 id 数组，"等于某个标量"永远不成立，属于配置错误。
- Q: 条件字段为空（null）怎么算？ → A: `null` 与任何取值都不相等，条件判否。沿用 `010`："没填"不等于"已满足"。
- Q: `stage_done` 要先建中间布尔字段承接吗？ → A: 不要。`board@4` 早期草案的"落地前先用一个布尔中间字段承接"随本规格作废：`stage_done` 直接 `and(六个 stage == done)`，`gate` 再 `and(stage_done == true)`。
- Q: 既有 `and`/`rollup`/`count`/`ratio` 口径要不要一起改？ → A: 不改。空集、悬空、重算时机、闸门覆盖规则全部沿用 `010`/`016`；本次只给 `and` 的条件项补类型规则并锁定用例。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 六个枚举节点汇成一个布尔 (Priority: P1)

版本行的六个四态节点各是 `todo/doing/done/failed`，`stage_done` 用一条 `and` 配置把它们汇成一个布尔：六个都 `done` 才为真。`failed` 不是 `done`，`doing`、`todo`、空值都判否。

**Why this priority**: 这是 `board@4` 发布闸门的地基。没有它，`ver.gate` 只能继续挂在三个旧布尔上，六节点的推进记录对发布资格不起作用。

**Independent Test**: 建一条六节点全 `done` 的行、一条任一节点 `doing` 的行、一条节点为空的行，读 `stage_done` 落库值。

**Acceptance Scenarios**:

1. **Given** 版本行六个节点均为 `done`，**When** 读取 `and(六个节点 == done)`，**Then** 值为 `true`，`computed_values` 落库值也是布尔真。
2. **Given** 六个节点中任一个为 `doing` 或 `todo`，**When** 读取同一字段，**Then** 值为 `false`。
3. **Given** 某节点为 `failed`（失败待返工），**When** 读取同一字段，**Then** 值为 `false`——`failed` 与 `done` 不相等，返工未完成不得放行。
4. **Given** 某行一个节点都没填（`null`），**When** 读取同一字段，**Then** 值为 `false`，不把"没数据"当成"已完成"。
5. **Given** 六个节点全 `done` 的 `stage_done`，**When** 用 `and(stage_done == true)` 建 `gate` 并打 `gate: true`，**Then** `gate` 为真；任一节点退回 `doing` 并重算后，`stage_done` 与 `gate` 同时转假。

### User Story 2 - 写错的条件在配置期就失败 (Priority: P1)

条件项取值必须落在条件字段的取值域内：枚举只能是声明域里的字符串，数字只能是数字，布尔计算字段只能是 `true/false`，文本/日期时间只能是字符串，`rollup min/max` 只能是数字或字符串。写错一律 `400`，不留下字段、也不留下计算值。

**Why this priority**: 永远为假的配置比报错危险得多——它看起来"在跑"，结论却恒为"未完成/未达"，而且和真实业务状态无法区分。

**Independent Test**: 逐条提交类型不符的 `and` 配置（`枚举 == 5`、`枚举 == "Done"`、`数字 == "2"`、`布尔计算 == 1`、`relation == "C1"`），全部期望 `400`，且字段表、`computed_values` 均无新增。

**Acceptance Scenarios**:

1. **Given** 一个四态枚举字段，**When** 提交 `{"field_id": <enum>, "equals": 5}` 或 `equals: true`，**Then** 返回 `400`，错误信息指明类型不符；字段不落库。
2. **Given** 同一枚举字段（取值 `todo/doing/done/failed`），**When** 提交 `equals: "Done"`（大小写写错、不在域内），**Then** 返回 `400`，错误信息列出现有取值；字段不落库。
3. **Given** 一个 `number` 字段，**When** 提交 `equals: "2"`，**Then** 返回 `400`；提交 `equals: 2` 则配置成功，计算按数字严格相等。
4. **Given** 一个输出布尔的 `and` 计算字段，**When** 把它的条件写成 `equals: 1`，**Then** 返回 `400`（布尔字段只能等于 `true/false`）。
5. **Given** 一个 relation 字段，**When** 把它当条件字段提交，**Then** 返回 `400`，错误信息说明关联值是数组、不能与标量比较。
6. **Given** 结构非法的条件（空数组、`equals` 为 `null`、引用不存在的字段、条件项不是对象），**When** 提交，**Then** 仍返回 `400`（与改动前一致），且不落库。

### User Story 3 - 既有计算口径与闸门规则不变 (Priority: P1)

`and` 仍是"条件项全部成立的合取"，可以引用同表计算字段（按依赖拓扑序先算被引用者，依赖成环 `400`）；`rollup`/`count`/`percent`/`sum`/`ratio` 的空集与悬空语义、闸门字段拒绝人工覆盖、写后同事务重算，全部与 `010`/`016` 一致。

**Why this priority**: 六节点闸门要在既有引擎上落地，不能为了加条件表达式把已交付的判定口径改掉。

**Independent Test**: 跑既有 `test_formula.py`/`test_computation_010.py`/`test_ratio_016.py` 全绿；新增用例只覆盖 `and` 条件项与六节点场景。

**Acceptance Scenarios**:

1. **Given** 既有布尔/数字条件（`and(rollup == true)`、`and(count == 3)`、`and(number == 2)`），**When** 重算，**Then** 取值与改动前一致。
2. **Given** `and` 引用同表计算字段（如 `and(stage_done == true)`），**When** 重算 `gate`，**Then** 使用被引用字段的有效值（人工覆盖优先），被引用者先于引用者计算。
3. **Given** 计算字段依赖成环，**When** 提交配置，**Then** 返回 `400`，不落库。
4. **Given** 打 `gate: true` 的 `and` 字段，**When** 提交人工覆盖设值，**Then** 返回 `400` 且整体回滚（`010`）；提交 `value=null` 清除仍允许。
5. **Given** 行写入改变某个节点状态，**When** 写事务提交，**Then** 依赖它的 `and` 字段在同一事务内重算并落库，读侧不计算。

### User Story 4 - 契约与实现对齐 (Priority: P2)

`board@4` 的 `ver.stage_done`、`ver.gate` 能以本规格定义的两条配置直接落地，不再需要中间布尔字段；`board@4` 早期草案"board@3 的 and 只接受布尔字段"的说明已按实现更正。

**Independent Test**: 按 `board@4` 的两条公式建字段，六节点全 `done` 的版本行读 `stage_done=true`、`gate=true`；无需任何额外布尔字段。

**Acceptance Scenarios**:

1. **Given** 版本表已按 `board@4` 建出六个四态节点，**When** 按公式建 `stage_done` 与 `gate`，**Then** 两个字段都能建成，且字段表里没有为承接六节点而新增的中间布尔字段。
2. **Given** 上述配置，**When** 六节点全 `done`，**Then** `stage_done` 与 `gate` 均为真；任一节点非 `done`，两者均为假。

## Requirements *(mandatory)*

- **FR-001**: `and` 的 `conditions` MUST 是非空数组；条件项 MUST 形如 `{"field_id": <本表字段id>, "equals": <取值>}`。
- **FR-002**: 所有条件项同时成立时结果为真，任一不成立为假；条件字段值为 `null` 时该项 MUST 判否（`null` 与任何取值都不相等）。
- **FR-003**: 条件项取值 MUST 落在条件字段的取值域内，且 MUST NOT 做隐式类型强转：枚举 MUST 是声明域内的字符串；`number` MUST 是数字（排除布尔）；文本与日期时间 MUST 是字符串；输出布尔的 `and`/布尔 `rollup` MUST 是布尔；`rollup min/max` MUST 是数字或字符串。
- **FR-004**: 条件项 MUST NOT 引用 relation 字段（关联值是数组，与标量相等恒不成立）。
- **FR-005**: 非法条件 MUST 返回 `400`，并且同一请求 MUST NOT 落库任何字段或计算值。
- **FR-006**: `and` MUST 支持引用同表计算字段，被引用者按依赖拓扑序先算；依赖成环 MUST 返回 `400`，不落库。
- **FR-007**: 计算字段 `options.gate` MUST 仍只允许打在布尔判定字段（`and` 或布尔 `rollup`）；闸门字段 MUST 拒绝人工覆盖设值（`400` 且整体回滚），清除覆盖仍允许（沿用 `010`）。
- **FR-008**: 行创建/更新/删除后 MUST 在同一事务内重算受影响表并落库；读侧 MUST NOT 计算（沿用 `010`）。
- **FR-009**: `board@4` 的 `ver.stage_done`、`ver.gate` MUST 能以本规格的配置直接落地：`stage_done = and(六个 ver.stage.* == done)`、`gate = and(stage_done == true)`；MUST NOT 依赖中间布尔字段。
- **FR-010**: MUST NOT 引入用户可写表达式、算术运算、`!=`/`>`/`<` 等比较运算符、`or`/`not` 逻辑或跨表条件；计算 `kind` 仍封闭为 `count / percent / sum / rollup / and / ratio`。
- **FR-011**: 既有 `and`/`rollup`/`count`/`percent`/`sum`/`ratio` 的取值、空集与悬空语义 MUST 保持不变；不新增路由、不改写接口形状。

## Key Entities

- **fields.options（type=computed，kind=and）**：`conditions[]`（每项 `field_id` + `equals`）、`gate`、`allow_override`、`true_label`/`false_label`。
- **computed_values**：`and` 结果按布尔落库（`value`），人工覆盖规则沿用 `010`。
- **row_records.data**：条件字段的取值来源；未填写的键即 `null`。

## 实现落点

- `backend/src/tableflow/calculation.py`：`_validate_condition_equals`（第223行起）按字段取值域校验条件取值；`validate_computed_options` 的 `and` 分支（第323–342行）在配置期调用它；`_compute_and`（第657–674行）保持严格相等与 `null` 判否的语义。
- `backend/tests/test_cell_compute_023.py`：六节点成立/不成立、状态变化后重算、`and` 引用计算字段、闸门覆盖拒绝、非法条件 `400` 不落库。

## Success Criteria *(mandatory)*

- **SC-001**: `cd backend && .venv/bin/python -m pytest -q` 全绿；新增 023 用例覆盖"`and(枚举 == done)` 成立"与"不成立"两种结果。
- **SC-002**: 六节点全 `done` → `stage_done=true`；任一节点为 `doing`/`todo`/`failed`/`null` → `false`；节点变化后无需额外调用重算即翻转。
- **SC-003**: 类型不符与枚举域外取值共 10 类非法条件全部 `400`，字段表与 `computed_values` 零新增。
- **SC-004**: 既有 010/016 用例不改一行仍通过，`and`/`rollup`/`count`/`ratio` 口径无回归。

## Non-Goals

- 用户可写表达式、行内算术、`or`/`not`、比较运算符与括号（`019` 已明确排除，本规格不引入）。
- 跨表任意聚合或跨表条件（沿用 `010` 的 kind 封闭原则）。
- 六节点串行推进与节点闸门一致性写入校验（`board@4` 的写入期校验，属 `019` 实现/`020` 接口范围）。
- `board@4` 建表、`case`/`run` 两表与存量迁移（`019` 实现）。
- 空集/悬空/重算时机等既有口径的调整（`010` 不变）。
- `board@4.yaml` 契约文件本身的修订（属 `019` 文档 owner；本规格只报告早期草案的说明与实现不符，该说明已由队长更正）。
