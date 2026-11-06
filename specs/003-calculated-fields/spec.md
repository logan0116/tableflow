# Feature Specification: 计算字段与发布判定（v0.3.0）

**Feature Branch**: `003-calculated-fields`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "引入五种计算字段 count / percent / sum / rollup / and；写侧计算并落库，读侧零计算；版本「开发进度」= 关联需求 speckit-implement 完成比例；版本「Bug已清空」= 数字 + 归零判定，允许手工覆盖；「发布条件」= 多条件 AND；明确计算刷新时机与失败语义；提供人经 Agent 改状态的入口。"

## Clarifications

### Session 2026-11-06

- Q: 计算字段是新的 `type` 还是 `type` 上的配置？ → A: 新增字段 `type=computed`，五种计算类型放在 `options.kind`（`count` / `percent` / `sum` / `rollup` / `and`）；`kind` 集合在数据层可枚举。
- Q: 百分比存什么？ → A: 存 0–100 的百分数（`66.7` 表示 66.7%），按 `decimals` 四舍五入；读侧只加 `%`。
- Q: 分母为 0 时 percent 返回什么？ → A: `null`（显示「—」），不写 0；`and` 中 `null` 与任何值都不相等，结果为否。
- Q: 读侧会不会兜底重算？ → A: 不会。读接口只读取 `computed_values` 中已落库的值（覆盖值优先），MUST NOT 做任何业务计算；缺失显示「—」。
- Q: 重算失败怎么办？ → A: 整个写请求失败并回滚：源数据、计算值、业务变更记录都不落库，写审计留一条 `failed`。MUST NOT 落部分结果，MUST NOT 用 0 掩盖失败。
- Q: 覆盖（override）怎么工作？ → A: 覆盖值带原因、操作者、时间，落审计与业务变更记录；重算不覆盖它；清除覆盖后立即重算。覆盖只允许作用于 `options.allow_override=true` 的计算字段。
- Q: 人怎么改状态？ → A: 人侧路由仍只有 GET；前端「申请变更 / 覆盖」入口调用 Agent 写接口，携带 `X-Origin: human-request` 与 `X-Agent-Id`，写接口照常校验、审计、三态。001 FR-013 的「前端无写控件」在 v0.3.0 细化为「前端无直接写业务数据的控件」。
- Q: 依赖可以成环吗？ → A: 不可以。`count/percent/sum/rollup` 只读目标表的非计算字段；只有 `and` 可以读同表计算字段。创建/更新时做环检测，成环即 `failed`。
- Q: 删除被引用的字段/表怎么办？ → A: 拒绝删除，返回 `failed`，要求先删计算字段或 relation 字段。避免留下悬空配置。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 五种计算字段可用且可解释 (Priority: P1)

Agent 可以定义 `count` / `percent` / `sum` / `rollup` / `and` 五种计算字段。每种字段的配置都写在 `fields.options` 里，值在写入时算好并落库；看板打开时直接读结果，不在浏览器里算。

**Why this priority**: 计算字段是 003 的地基。没有统一的计算语义与落库机制，后面的开发进度、Bug 清零、发布条件都无法可信。

**Independent Test**: 为五种 kind 各造一个字段，写入源数据，读取落库值与接口返回值；读接口在源数据被直接改动（不重算）后仍返回旧值，证明读侧不计算。

**Acceptance Scenarios**:

1. **Given** 版本表有 relation `v-dep` 指向依赖变更需求，**When** 定义 `count` 字段 `source=v-dep`，**Then** 关联 3 行时值为 `3`；关联 0 行时值为 `0`。
2. **Given** 独立规格需求有数字字段 `i-tasks`，版本表有 relation `v-indep`，**When** 定义 `sum` 字段 `source=v-indep, field_id=i-tasks`，**Then** 关联行任务数为 3、5 时值为 `8`。
3. **Given** 依赖变更需求有 enum `d-regress`，**When** 定义 `rollup` 字段 `aggregate=all, equals=passed`，**Then** 全部关联行通过时为「是」，任一未通过时为「否」。
4. **Given** 版本表有数字字段 `v-bug-open`，**When** 定义 `and` 字段条件 `v-bug-open == 0`，**Then** 0 时为「是」，2 时为「否」。
5. **Given** 五种字段已落库，**When** 直接修改源数据但不触发重算，**Then** 读接口仍返回落库值（读侧零计算）。
6. **Given** 计算字段缺少必要配置（如 `sum` 没有 `field_id`），**When** 创建字段，**Then** 返回 `failed`，不落库。

---

### User Story 2 - 版本开发进度 = speckit-implement 完成比例 (Priority: P1)

版本管理表的「开发进度」是一个 `percent` 计算字段：统计该版本关联的独立规格需求中，`speckit-implement` 状态为「完成」的比例，保留 1 位小数。

**Why this priority**: 发布判定的第一条件。比例必须由关联需求实时算出，不能靠人填字符串。

**Independent Test**: 造 3 条关联需求，2 条完成 → 显示 `66.7%`；全部完成 → `100.0%`；没有关联需求 → 显示「—」。

**Acceptance Scenarios**:

1. **Given** 版本 `7.0.1` 关联 3 条独立规格需求，其中 2 条 `i-implement=done`，**When** 打开看板，**Then** 开发进度显示 `66.7%`。
2. **Given** 3 条全部 `i-implement=done`，**When** 重算，**Then** 显示 `100.0%`。
3. **Given** 没有关联任何需求，**When** 重算，**Then** 值为 `null`，显示「—」，不显示 `0%`。
4. **Given** Agent 把一条需求的 `i-implement` 从 `doing` 改为 `done`，**When** 写入成功，**Then** 该版本开发进度在同一事务内更新，无需第二次请求。

---

### User Story 3 - Bug 已清空 = 数字 + 归零判定，允许手工覆盖 (Priority: P1)

版本表有数字字段「未清Bug数」与计算字段「Bug已清空」。未清Bug数为 0 时判定为「是」，否则为「否」。人可以经 Agent 入口覆盖判定结果（例如确认剩余 Bug 不影响发布），覆盖必须带原因并可清除。

**Why this priority**: 发布判定的第二条件。全自动判定在现实中会被"已知可接受 Bug"打破，必须留一个可审计的人工覆盖口。

**Independent Test**: 未清Bug数 0 → 是；2 → 否；覆盖为「是」后重算仍为「是」；清除覆盖后恢复按数字判定。

**Acceptance Scenarios**:

1. **Given** `v-bug-open=0`，**When** 重算 `v-bug-clear`，**Then** 值为「是」。
2. **Given** `v-bug-open=2`，**When** 重算，**Then** 值为「否」。
3. **Given** 覆盖 `v-bug-clear=是` 且原因「已知问题，不影响发布」，**When** 把 `v-bug-open` 改为 5 触发重算，**Then** 值仍为「是」，覆盖未被重算覆盖。
4. **Given** 已有覆盖，**When** 清除覆盖，**Then** 立即按当前 `v-bug-open` 重算。
5. **Given** 对非计算字段或未开启 `allow_override` 的计算字段提交覆盖，**When** 写接口校验，**Then** 返回 `failed`。
6. **Given** 覆盖缺少原因，**When** 写接口校验，**Then** 返回 `failed`。

---

### User Story 4 - 发布条件 = 多条件 AND (Priority: P1)

版本的「发布条件」是一个 `and` 计算字段，条件为：开发进度 = 100、回归通过 = 是、Bug已清空 = 是、文档状态 = 完成。四项全满足才为「是」。

**Why this priority**: 发布判定必须一眼可见，且每个条件都能追溯到具体字段；否则"能不能发"仍然靠人拍脑袋。

**Independent Test**: 四条件全满足 → 是；逐个置为不满足 → 否；条件值缺失（null）→ 否。

**Acceptance Scenarios**:

1. **Given** 开发进度 100、回归通过 是、Bug已清空 是、文档状态 完成，**When** 重算，**Then** 发布条件为「是」。
2. **Given** 上述任一条件不满足，**When** 重算，**Then** 发布条件为「否」。
3. **Given** 开发进度为 `null`（无关联需求），**When** 重算，**Then** 发布条件为「否」。
4. **Given** 修改文档状态为「完成」，**When** 写入成功，**Then** 发布条件在同一事务内重算。
5. **Given** 发布条件为「否」，**When** 用户查看行明细，**Then** 能看到每个条件的当前值（只读），不需要自己拼。

---

### User Story 5 - 刷新时机与失败语义明确 (Priority: P1)

计算值在写请求内更新：改源数据、改关联、删目标行、改字段定义、显式重算都会触发。任何一步失败，整次写入回滚，返回 `failed`，不留下半套数据。

**Why this priority**: 计算字段一旦出现"部分更新"，看板就会给出错误结论；失败语义必须先定死。

**Independent Test**: 注入一个非法计算配置或计算异常，写请求返回 `failed`，源数据与计算值均未变；修复后重算成功。

**Acceptance Scenarios**:

1. **Given** 修改版本行的 `v-bug-open`，**When** 写入成功，**Then** 同表所有依赖它的计算字段（`v-bug-clear`、`v-cond`）在同一事务内更新。
2. **Given** 修改独立规格需求的 `i-implement`，**When** 写入成功，**Then** 引用该表的版本计算字段（`v-dev`、`v-cond`）在同一事务内更新。
3. **Given** 删除一条被 relation 引用的目标行，**When** 删除成功，**Then** 引用方的 `count/percent/sum/rollup` 重算，悬空引用被忽略。
4. **Given** 计算过程中抛出异常，**When** 写请求结束，**Then** 返回 `failed`，源数据、`computed_values`、`business_changes` 全部回滚，写审计留 `failed`。
5. **Given** 提交结果未知（数据库错误），**When** 返回 `unknown`，**Then** 不得当作成功；后续可调用重算接口修复。
6. **Given** 计算配置合法但分母为 0，**When** 计算 percent，**Then** 落库 `null`，不视为失败。

---

### User Story 6 - 人经 Agent 改状态的入口 (Priority: P1)

人在看板上可以对允许人工申请的状态字段发起变更：选择新值、填写原因、提交。请求走 Agent 写接口，带 `X-Origin: human-request`，照常校验、落审计、返回三态。人侧仍然没有直接写业务数据的路由。

**Why this priority**: 完全只读无法支撑日常状态维护；但放开写又必须不破坏"写操作必留痕"的底线。入口只能是"人发起、Agent 执行"。

**Independent Test**: 从看板发起一次状态变更，数据变化；`write_audit` 与 `business_changes` 的 `origin` 均为 `human-request`；人侧路由清单仍只有 GET。

**Acceptance Scenarios**:

1. **Given** 某 enum 字段 `options.human_request=true`，**When** 用户点击单元格，**Then** 出现「申请变更」入口，列出 options 中的合法值。
2. **Given** 用户选择新值并填写原因，**When** 提交，**Then** 前端调用 Agent 写接口（带 `X-Agent-Id` 与 `X-Origin: human-request`），成功后刷新显示新值。
3. **Given** 提交缺少原因，**When** 前端校验，**Then** 不发起请求并提示原因必填。
4. **Given** 写入成功，**When** 查看审计，**Then** `write_audit.origin=human-request`，`business_changes.origin=human-request`，`actor` 为请求头中的 Agent 标识。
5. **Given** 用户尝试修改不允许人工申请的字段，**When** 打开单元格，**Then** 没有「申请变更」入口；对未开启 `allow_override` 的计算字段也没有「覆盖」入口。
6. **Given** 人侧路由清单，**When** 扫描后端，**Then** 只有 GET，MUST NOT 出现 `POST/PATCH/DELETE /api/*`（`/api/agent/*` 除外）。

---

### Edge Cases

- relation 目标行被删除：`count/percent/sum/rollup` 忽略悬空引用；`relation` 列显示「关联已失效」。
- `sum` 的源字段含非数字：配置在创建字段时拒绝（源字段必须是 number）；运行期遇到脏值按忽略处理，不失败。
- `rollup min/max` 的源字段类型不是 number/datetime：创建字段时拒绝。
- `rollup all/any/none` 缺 `equals`：创建字段时拒绝。
- `and` 条件为空数组、或 `equals=null`：创建字段时拒绝。
- 计算字段引用不存在的 relation / 字段：创建或更新字段时拒绝。
- 依赖成环（`and` 互相引用、或更新导致环）：拒绝并返回 `failed`。
- 删除被计算字段引用的字段 / relation：拒绝，要求先删计算字段。
- 删除被 relation 指向的表：拒绝，要求先删 relation 字段。
- 覆盖值类型与计算输出不匹配（如布尔字段覆盖为字符串）：拒绝。
- 覆盖字段不是计算字段：拒绝。
- 计算字段的 `visible=0`：仍然计算并落库，只是不返回给读接口。
- 一次写入影响多行：按「行 × 字段」逐条写业务变更记录。
- 读接口遇到 `computed_values` 缺行：返回 `null`，显示「—」，不触发计算。
- 重算接口重复调用：幂等，结果一致。

## Requirements *(mandatory)*

### Functional Requirements

**计算类型与配置**

- **FR-001**: 系统 MUST 支持字段 `type=computed`，`options.kind` MUST 属于 `count` / `percent` / `sum` / `rollup` / `and`；其他 kind MUST 返回 `failed`。
- **FR-002**: `count` 配置 MUST 含 `source`（本表 relation 字段 id）；可选 `where={field_id,equals}`；值 MUST 为目标表中存在且满足条件的关联行数。
- **FR-003**: `percent` 配置 MUST 含 `source`；可选 `where`、`decimals`（0–1，缺省 1）；值 MUST 为 `匹配行数 / 关联行数 × 100`，按 `decimals` 四舍五入；关联行数为 0 时值 MUST 为 `null`。
- **FR-004**: `sum` 配置 MUST 含 `source` 与 `field_id`（目标表的 number 字段）；可选 `decimals`、`unit`；值 MUST 为关联行该字段之和，缺失/非数字值忽略，无关联行时为 `0`。
- **FR-005**: `rollup` 配置 MUST 含 `source`、`field_id`、`aggregate`；`aggregate ∈ {all,any,none,min,max,count_distinct}`；`all/any/none` MUST 含 `equals` 且输出布尔；`min/max` 的源字段 MUST 为 number 或 datetime；`count_distinct` 输出数字。
- **FR-006**: `and` 配置 MUST 含非空 `conditions` 数组，每项 `{field_id,equals}`；`field_id` MUST 属于同表字段（可为计算字段）；比较 MUST 使用被引用字段的有效值（override 优先）；所有条件相等时值为 `true`，否则 `false`；`equals` MUST NOT 为 `null`。
- **FR-007**: 计算字段 MUST NOT 直接接受 Agent 写入的值；写接口在 `values` 中出现计算字段键 MUST 返回 `failed`。
- **FR-008**: 计算字段的 `options` 校验 MUST 在创建/更新字段时完成；引用不存在、类型不匹配、缺必填键 MUST 返回 `failed`。
- **FR-009**: 计算字段依赖 MUST 无环；创建/更新时 MUST 做环检测，成环 MUST 返回 `failed`。
- **FR-010**: `count/percent/sum/rollup` 的 `where.field_id` 与 `field_id` MUST 引用目标表的非计算字段；`and` 可以引用同表计算字段。

**写侧计算与落库**

- **FR-011**: 系统 MUST 新增 `computed_values` 表，按 `(table_id,row_id,field_id)` 存储 `value`、`computed_at`、`override_value`、`override_reason`、`override_by`、`override_at`。
- **FR-012**: 写请求 MUST 在数据变更后、提交前完成受影响计算字段的重算，并把结果写入 `computed_values`；重算与数据变更 MUST 在同一事务。
- **FR-013**: 重算范围 MUST 覆盖：源行变化、relation 值变化、目标行增删改、计算字段定义变化、被引用的普通字段定义变化。
- **FR-014**: 重算顺序 MUST 按依赖拓扑排序；同表 `and` 依赖的计算字段 MUST 先算。
- **FR-015**: 计算异常、配置非法、依赖缺失 MUST 使整次写入失败并回滚；MUST NOT 落部分计算值；MUST NOT 以 0 或空值掩盖失败。
- **FR-016**: 分母为 0、无关联行、悬空引用 MUST NOT 视为失败；按各 kind 的空值语义落库。
- **FR-017**: 系统 MUST 提供 `POST /api/agent/tables/{table_id}/recompute`，对指定表全量重算，要求 `X-Agent-Id`，落审计；重复调用 MUST 幂等。
- **FR-018**: 覆盖 MUST 通过 `PATCH /api/agent/tables/{table_id}/rows/{row_id}` 的 `overrides` 键提交；每项 MUST 含 `value` 与 `reason`；清除覆盖 MUST 传 `value=null`；覆盖与清除 MUST 落审计与业务变更记录。
- **FR-019**: 覆盖 MUST 只作用于 `options.allow_override=true` 的计算字段；其他字段 MUST 返回 `failed`；重算 MUST NOT 覆盖已有 override；清除 override 后 MUST 立即重算。
- **FR-020**: 删除被计算字段引用的字段或 relation 字段 MUST 返回 `failed`；删除被 relation 指向的表 MUST 返回 `failed`，要求先删 relation 字段。

**读侧**

- **FR-021**: 读接口 MUST 从 `computed_values` 读取有效值（`override_value` 优先），MUST NOT 执行任何业务计算。
- **FR-022**: 读接口 MUST 在行数据中合并计算字段值，并返回 `computed_meta`（`computed_at`、`overridden`、`override_reason`）供前端显示覆盖标记。
- **FR-023**: 计算值为 `null` 时 MUST 显示「—」；布尔计算字段 MUST 显示「是 / 否」，不显示 `true/false`。
- **FR-024**: 读接口遇到 `computed_values` 缺行时 MUST 返回 `null` 并正常响应，MUST NOT 触发计算或返回 5xx。

**业务字段（模板）**

- **FR-025**: 版本管理表 MUST 新增 `v-bug-open`（未清Bug数，number，`min=0`）；`v-bug-clear`（Bug已清空，computed and，允许 override）；`v-regress`（回归通过，computed rollup）；`v-dev`（开发进度，computed percent）；`v-cond`（发布条件，computed and）。
- **FR-026**: 版本管理表 MUST 提供示例计算字段 `v-dep-count`（count）、`v-scenes`（sum `i-scenes`）、`v-tasks`（sum `i-tasks`），用于覆盖五种 kind。
- **FR-027**: `v-dev` MUST 配置为 `percent(source=v-indep, where={i-implement=done}, decimals=1)`。
- **FR-028**: `v-bug-clear` MUST 配置为 `and(conditions=[{v-bug-open, equals:0}])`，`true_label=是`、`false_label=否`，并 MUST 设置 `allow_override=true`。
- **FR-029**: `v-regress` MUST 配置为 `rollup(source=v-dep, field_id=d-regress, aggregate=all, equals=passed)`。
- **FR-030**: `v-cond` MUST 配置为 `and`，条件为 `v-dev==100`、`v-regress==true`、`v-bug-clear==true`、`v-doc==done`。
- **FR-031**: 旧的 `v-bug`（text）MUST 被 `v-bug-open` + `v-bug-clear` 取代；`v-dev`、`v-cond` MUST 从 text 改为 computed。

**人经 Agent 改状态**

- **FR-032**: enum 字段 `options.human_request=true` 时，前端 MUST 提供「申请变更」入口；computed 字段 `options.allow_override=true` 时，前端 MUST 提供「覆盖」入口；两种入口 MUST 要求填写原因。
- **FR-033**: 变更请求 MUST 调用 Agent 写接口，携带 `X-Agent-Id` 与 `X-Origin: human-request`；写接口 MUST 校验 origin 取值并写入 `write_audit` 与 `business_changes`。
- **FR-034**: 人侧路由 MUST 仍然只有 GET；MUST NOT 新增面向人的直接写端点。
- **FR-035**: 写审计 MUST 记录 `origin`（`agent` / `human-request` / `seed`）；`business_changes.change_kind` MUST 记录 `create` / `update` / `delete` / `recompute` / `override`。

### Key Entities

- **计算字段（Computed Field）**：`type=computed` + `options.kind` + 依赖配置；值由写侧计算并落库。
- **计算值（ComputedValue）**：`(table_id,row_id,field_id)` 上的落库结果，含计算时间与覆盖信息。
- **覆盖（Override）**：对计算值的人工覆盖，带原因、操作者、时间；可清除。
- **变更请求（Human Request）**：人发起的、经 Agent 通道执行的状态变更；审计中 `origin=human-request`。
- **发布判定（Release Gate）**：由开发进度、回归通过、Bug已清空、文档状态四项 AND 组成。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 五种 kind 各至少 1 个 pytest 用例，输入与期望值明确：count 3/0、sum 8、rollup 是/否、and 是/否、percent 66.7/null。
- **SC-002**: 读侧零计算可验证：直接修改源表数据但不调用重算，读接口返回的仍是 `computed_values` 中的旧值；测试用例 100% 通过。
- **SC-003**: 开发进度：3 条关联需求 2 条完成 → `66.7%`；全部完成 → `100.0%`；0 条关联 → 「—」。
- **SC-004**: Bug已清空：0 → 是；2 → 否；覆盖为是后把数字改为 5，仍为是；清除覆盖后恢复为否。
- **SC-005**: 发布条件：四条件全满足 → 是；逐一把任一条件置为不满足 → 否；开发进度为 null → 否。
- **SC-006**: 失败回滚：注入计算异常，写请求 `failed`，源数据、`computed_values`、`business_changes` 均无变化，写审计有 1 条 `failed`。
- **SC-007**: 依赖成环：构造互相引用的 `and` 字段，100% 返回 `failed`，不落库。
- **SC-008**: 性能：单次写入 + 重算在单表 500 行规模下 ≤200ms（本机）；14 行首屏与滚动基线不回退。
- **SC-009**: 人发起入口：从看板提交一次状态变更，`write_audit.origin` 与 `business_changes.origin` 均为 `human-request`，覆盖率 100%。
- **SC-010**: `cd backend && .venv/bin/pytest -q` 全绿；`cd frontend && npx tsc --noEmit` 零错误。

## Assumptions

- 计算字段依赖 002 的字段 `options` 结构、`business_changes`、`origin` 与业务编号行 id；`type=computed` 由本 spec 引入。
- `percent` 的分子分母都只统计「目标行仍存在」的关联；悬空引用不计入分母。
- `all` / `none` 在空集合上为 `true`，`any` 在空集合上为 `false`；因此无依赖需求时「回归通过」为「是」，发布条件仍受开发进度 null 约束。
- 覆盖只支持标量值（number / boolean / string），不支持数组。
- `recompute` 接口用于修复未知结果或历史数据；正常写入不依赖它。
- 计算字段 `visible=0` 时仍计算、仍落库，只是读接口不返回。
- 人发起的状态变更只覆盖 enum 字段；其他字段的写入仍由 Agent 自主执行。
- 目标规模与 001/002 一致：≤20 项目、每项目 ≤10 表、单表 ≤500 行。

## 未来范围

- 用户可编辑表达式、跨表任意聚合、视图级计算仍属宪法 v6.0.0 非目标，不在本 spec 范围。
- 计算字段的界面视觉（状态标签、覆盖标记样式）由 004 统一打磨；003 只保证语义与最小可用展示。
