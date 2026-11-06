# Feature Specification: 字段体系与单向关联（v0.3.0）

**Feature Branch**: `002-field-system`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "把 fd_system 的两张需求表从双向关联改为单向关联（版本表为唯一挂载点，依赖变更需求表删除「所属版本」列）；行 id 改用业务编号（UD-01 / 7.0.1）；状态类字段全部 enum 化并支持状态色 tone；数字/日期格式显式声明；字段级约束由写接口校验；新增业务变更记录；独立规格需求补齐 speckit-clarify/analyze/checklist 三态与宪法版本、验收状态、负责人、优先级。"

## Clarifications

### Session 2026-11-06

- Q: 关联方向如何收敛？ → A: 版本管理表是唯一挂载点：版本表用两个 relation 字段分别指向独立规格需求与依赖变更需求；依赖变更需求表 MUST 删除「所属版本」字段，MUST NOT 保留任何反向关联。
- Q: 行 id 用什么？ → A: 业务编号（如 `UD-01`、`7.0.1`）。行 id 在表内唯一，`row_records` 主键改为 `(table_id, id)`；跨表同名由 relation 字段的目标表消歧。
- Q: 枚举状态色怎么存？ → A: `options` 项含 `tone`（`neutral` / `info` / `success` / `warning` / `danger`），可选 `color` 覆盖；前端只按 `tone` 或 `color` 渲染，不硬编码业务值。
- Q: 百分比数值怎么存？ → A: 存百分数本身（`12.5` 表示 12.5%）；渲染只加 `%` 与小数位，不在读侧换算。
- Q: 日期「仅日期 / 含时间」怎么声明？ → A: `datetime` 字段的 `options.with_time` 显式声明；缺省按含时间处理，兼容 001。
- Q: 业务变更记录与写审计的区别？ → A: 写审计记录接口调用（技术留痕）；业务变更记录记录字段级旧值/新值（业务留痕）。两者 MUST 同事务落库。
- Q: 人怎么改状态？ → A: 人侧仍然只有 GET；前端「改状态」入口只发起经 Agent 写接口的变更请求，审计标记 `origin=human-request`（宪法 v6.0.0 原则 I）。具体入口在 003 交付，002 只保证 enum 与审计字段就绪。
- Q: 旧数据怎么办？ → A: v0.3.0 不保留 001 的随机行 id 与双向关联字段；demo 数据用加载脚本重建，不做自动迁移。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 单向关联：版本表是唯一挂载点 (Priority: P1)

用户打开「版本管理」表，看到「需求关联（独立）」「需求关联（依赖）」两列，格子里是目标需求的业务编号；打开「依赖变更需求」表，不再有「所属版本」列。关联只从一个方向挂载，不会出现两边各挂一次、彼此不一致的情况。

**Why this priority**: 双向关联会产生两个事实来源：改了一边另一边不动，看板就无法回答"这个版本包含哪些需求"。先收敛方向，后续的计算字段才有唯一可信的入口。

**Independent Test**: 用模板重建 fd_system 后，检查版本表有 2 个 relation 字段、依赖变更需求表 0 个 relation 字段；用写接口尝试创建反向 relation，返回失败。

**Acceptance Scenarios**:

1. **Given** fd_system 项目已按新模板重建，**When** 用户打开「版本管理」表，**Then** 表中有「需求关联（独立）」与「需求关联（依赖）」两个 relation 列，列中标签为业务编号。
2. **Given** 用户打开「依赖变更需求」表，**When** 查看列头，**Then** 不存在「所属版本」列；`fields` 表中 `fd-dep` 下也没有该字段。
3. **Given** 依赖变更需求表已存在指向版本管理表的 relation，**When** Agent 尝试在依赖变更需求表上再创建指向版本管理表的 relation 字段，**Then** 写接口返回 `failed`，不落库，并留下失败审计。
4. **Given** 版本 `7.0.1` 关联了依赖需求 `UD-01`，**When** 用户点击该标签，**Then** 只读弹层显示 `UD-01` 的字段与值。

---

### User Story 2 - 行 id 采用业务编号 (Priority: P1)

Agent 用 `UD-01`、`7.0.1` 这样的业务编号作为行 id 写入数据；看板上的关联标签直接显示业务编号，人不需要再对照一张随机 id 映射表。

**Why this priority**: 行 id 是关联标签的唯一来源。id 不可读，关联就不可读；这是 003 计算字段可核对的前提。

**Independent Test**: 在同一张表写入 `UD-01` 两次，第二次失败；在两张不同表各写入 `7.0.1`，两行都可读且互不覆盖；用非法 id（空、含空格、含 `/`）写入失败。

**Acceptance Scenarios**:

1. **Given** 表「独立规格需求」已存在，**When** Agent 以 id `UD-05` 写入一行，**Then** 读接口返回该行 id 为 `UD-05`，关联标签显示 `UD-05`。
2. **Given** 同表已存在 id `UD-05`，**When** Agent 再写入 id `UD-05`，**Then** 返回 `failed`，不落库。
3. **Given** 表 A 与表 B 各有一行 id `7.0.1`，**When** 分别读取两张表，**Then** 两行都正确返回；relation 字段按目标表解析，不串行。
4. **Given** Agent 提交空 id、含空格的 id 或含 `/` 的 id，**When** 写接口校验，**Then** 返回 `failed`，不落库。
5. **Given** 某行已存在，**When** Agent 试图通过更新接口修改行 id，**Then** 返回 `failed`（id 不可变）。

---

### User Story 3 - 状态字段 enum 化与状态色 (Priority: P1)

所有状态类字段都是 enum：取值、中文标签、状态色都写在 `options` 里。看板按 `tone` 渲染成带色标签，前端代码里没有任何 `released`、`待办` 这类业务值。

**Why this priority**: 状态色与状态语义必须来自数据。写死在前端，新增一个状态就要改代码发版，违背 schema 驱动。

**Independent Test**: 读取字段定义，所有状态字段 `type=enum` 且 `options.items` 每项含 `value/label/tone`；前端源码 grep 不到业务状态值；改一条 options 的 tone，刷新后颜色变化且无需改代码。

**Acceptance Scenarios**:

1. **Given** 版本管理表，**When** 用户查看「发布状态」列，**Then** 单元格渲染为带色标签，颜色由该选项的 `tone` 决定。
2. **Given** 某选项 `tone=danger`，**When** 渲染该值，**Then** 标签使用危险色；`tone` 未知时回退 `neutral`，不报错。
3. **Given** 独立规格需求表，**When** 查看字段定义，**Then** speckit-constitution/specify/plan/task/implement 与 speckit-clarify/analyze/checklist 全部为 enum，取值为「未开始 / 进行中 / 完成」三态；独立需求状态为 enum（待启动 / 实现中 / 已完成 / 已阻塞）。
4. **Given** 某 enum 字段 `constraints.enum_strict=true`，**When** Agent 写入不在 options 内的值，**Then** 返回 `failed`，不落库。
5. **Given** 某 enum 字段未开启 `enum_strict`，**When** 读取到 options 外的历史值，**Then** 原值显示，不报错。

---

### User Story 4 - 数字与日期格式显式声明 (Priority: P2)

数字列可以声明小数位、百分比、单位；日期列可以声明只显示日期或日期加时间。格式只影响显示，不改变落库值。

**Why this priority**: 同一个数字，有人要看 `12.35 台`，有人要看 `12.35%`；格式属于字段定义，不属于前端代码。

**Independent Test**: 造 `decimals=2`、`percent=true`、`unit="台"`、`with_time=false` 四种字段，读取固定值，核对渲染文本；读接口返回的仍是原始值。

**Acceptance Scenarios**:

1. **Given** number 字段 `options={"decimals":2,"unit":"台"}`，值为 `12.3456`，**When** 渲染，**Then** 显示 `12.35 台`。
2. **Given** number 字段 `options={"percent":true,"decimals":1}`，值为 `66.666`，**When** 渲染，**Then** 显示 `66.7%`。
3. **Given** datetime 字段 `options={"with_time":false}`，值为 `2026-11-10T00:00:00+08:00`，**When** 渲染，**Then** 显示 `2026-11-10`。
4. **Given** datetime 字段 `options={"with_time":true}`，值为 `2026-11-10T09:30:00+08:00`，**When** 渲染，**Then** 显示 `2026-11-10 09:30`。
5. **Given** 值缺失或无法解析，**When** 渲染，**Then** 显示空单元格，不报错。

---

### User Story 5 - 字段级约束由写接口校验 (Priority: P1)

Agent 定义字段时可以声明必填、数值范围、枚举严格、关联目标必须存在。写接口在落库前校验；读侧不校验、不阻断历史数据。

**Why this priority**: 约束写在字段定义里，所有写入都走同一套校验；否则每个 Agent 各自实现一遍，数据质量无法保证。

**Independent Test**: 对 5 类约束各造一次非法写入，全部返回 `failed` 且不落库；合法写入通过；读侧读到历史非法值仍能显示。

**Acceptance Scenarios**:

1. **Given** 字段 `constraints.required=true`，**When** Agent 新建行时缺少该字段或值为空，**Then** 返回 `failed`，不落库。
2. **Given** 字段 `constraints={"min":0,"max":100}`，**When** 写入 `-1` 或 `101`，**Then** 返回 `failed`，不落库。
3. **Given** 字段 `constraints.enum_strict=true`，**When** 写入 options 外的值，**Then** 返回 `failed`，不落库。
4. **Given** 字段 `constraints.relation_must_exist=true`，**When** 写入不存在的目标行 id，**Then** 返回 `failed`，不落库。
5. **Given** 更新行时只提交部分字段，**When** 校验 required/min/max，**Then** 按「旧值 + 本次提交」合并后的值校验。

---

### User Story 6 - 业务变更记录 (Priority: P1)

每次 Agent 改数据，系统记录「谁、何时、哪张表、哪一行、哪个字段、旧值、新值」。人与 Agent 都能查到一条数据的变更历史；它和写审计是两份记录：审计回答"调用过什么"，变更记录回答"数据怎么变的"。

**Why this priority**: 看板要能解释"这个状态为什么是现在这样"。只有技术审计，人看不懂；只有业务记录，无法追接口调用。

**Independent Test**: 一次更新两个字段，产生两条业务变更记录，旧值/新值正确；一次失败写入产生 0 条业务变更记录，但产生 1 条失败审计。

**Acceptance Scenarios**:

1. **Given** 版本 `7.0.1` 的发布状态从 `planned` 改为 `released`，**When** 写入成功，**Then** 业务变更记录新增一条：操作者、时间、表 `fd-ver`、行 `7.0.1`、字段「发布状态」、旧值「计划中」、新值「已发布」。
2. **Given** 新建一行且写了 3 个字段，**When** 写入成功，**Then** 产生 3 条记录，旧值为空。
3. **Given** 删除一行，**When** 删除成功，**Then** 对该行每个非空字段产生一条记录，新值为空。
4. **Given** 一次写入因约束校验失败，**When** 事务回滚，**Then** 业务变更记录 0 条，写审计 1 条 `failed`。
5. **Given** 行 `7.0.1` 有 5 条变更记录，**When** 调用只读查询接口，**Then** 按时间倒序返回，默认最多 50 条。
6. **Given** 用户打开关联行明细，**When** 查看「变更记录」区域，**Then** 以只读列表显示最近 20 条，无编辑入口。

---

### User Story 7 - 独立规格需求补齐治理字段 (Priority: P2)

独立规格需求表补齐 speckit-clarify / analyze / checklist 三态，以及宪法版本、验收状态、负责人、优先级。一个 spec 推进到哪一步、按哪版宪法验收、谁负责，都在表里看得到。

**Why this priority**: 002/003/004 三个 spec 要在同一张表里被追踪；缺这些字段，发布判定只能靠口头同步。

**Independent Test**: 读取 002 行，能看到 `speckit-clarify/analyze/checklist` 三态、宪法版本 `v6.0.0`、验收状态、负责人、优先级；缺省时显示空单元格。

**Acceptance Scenarios**:

1. **Given** 独立规格需求表已按新模板重建，**When** 查看字段定义，**Then** 存在 `i-clarify`、`i-analyze`、`i-checklist`（enum 三态）、`i-constitution-version`（text）、`i-acceptance`（enum）、`i-owner`（text）、`i-priority`（enum）。
2. **Given** 002 行已写入治理字段，**When** 用户打开看板，**Then** 宪法版本显示 `v6.0.0`，验收状态显示「未验收」，负责人与优先级按写入值显示。
3. **Given** 某行未写治理字段，**When** 渲染，**Then** 显示空单元格，不报错。

---

### Edge Cases

- relation 目标行被删除：该标签显示「关联已失效」，页面不报错。
- relation 值为空数组或 `null`：显示空单元格。
- 同表重复 id：写接口拒绝；已有重复数据的旧库不自动迁移，直接重建。
- 跨表同名 id：允许；relation 按字段声明的目标表解析。
- 行 id 含非法字符（空格、`/`、`:`、中文）：写接口拒绝。
- enum 的 `tone` 未知或缺失：按 `neutral` 渲染。
- `decimals` 超出 0–6：创建/更新字段时拒绝，不静默截断。
- `with_time` 不是布尔：创建/更新字段时拒绝。
- required 字段在历史行中缺失：读侧照常显示空单元格，不阻断读取。
- 业务变更记录只记录数据行字段变化，不记录表/字段定义变更（后者由写审计覆盖）。
- 一次写入影响多行（如批量重算）：业务变更记录按「行 × 字段」逐条记录。

## Requirements *(mandatory)*

### Functional Requirements

**读侧（人）**

- **FR-001**: 系统 MUST 继续以 relation 字段的目标行 id 作为标签；v0.3.0 起该 id 为业务编号，因此标签可直接阅读。
- **FR-002**: 依赖变更需求表 MUST NOT 返回「所属版本」字段；该字段 MUST 从 `fields` 数据中删除。
- **FR-003**: enum 字段 MUST 按选项的 `tone` 渲染为带色标签；`tone` 未知或缺失时 MUST 回退 `neutral`，MUST NOT 报错。
- **FR-004**: number 字段 MUST 按 `decimals`（0–6，四舍五入）、`percent`、`unit` 渲染；MUST NOT 改变接口返回的原始值。
- **FR-005**: datetime 字段 MUST 按 `with_time` 渲染：`false` 输出 `YYYY-MM-DD`，`true` 输出 `YYYY-MM-DD HH:mm`；无法解析时 MUST 原样显示。
- **FR-006**: 系统 MUST 提供只读接口 `GET /api/tables/{table_id}/rows/{row_id}/changes?limit=50`，按时间倒序返回该行业务变更记录。
- **FR-007**: 行明细弹层 MUST 以只读列表展示该行最近 20 条业务变更记录，MUST NOT 提供编辑、删除或回滚入口。
- **FR-008**: 空值、非法值、关联失效 MUST 显示为空单元格或「关联已失效」，MUST NOT 使页面报错。
- **FR-009**: 界面文案 MUST 全部为中文。

**写侧（Agent）**

- **FR-010**: 写接口 MUST 拒绝双向关联：同一项目内，若目标表已有 relation 字段指向当前表，则当前表创建/更新指向该目标表的 relation 字段 MUST 返回 `failed`。
- **FR-011**: relation 字段的 `options.table_id` MUST 指向同项目内已存在的表格（允许自关联）。
- **FR-012**: 行 id MUST 由 Agent 显式提供，MUST 匹配 `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`；空 id 或非法字符 MUST 返回 `failed`。
- **FR-013**: 行 id MUST 在表内唯一；`row_records` 主键 MUST 为 `(table_id, id)`，允许跨表同名。
- **FR-014**: 行 id 创建后 MUST 不可变；更新接口 MUST 拒绝修改 id。
- **FR-015**: 字段 `options` MUST 统一为 JSON 对象；enum 的取值表 MUST 位于 `options.items` 数组，每项 MUST 含 `value`、`label`、`tone`；`tone` MUST 属于 `neutral` / `info` / `success` / `warning` / `danger`；可选 `color` MUST 为 `{bg,fg}` 且值为合法颜色字符串。
- **FR-016**: number 字段的 `options` MUST 支持 `decimals`（整数 0–6）、`percent`（布尔）、`unit`（长度 ≤8 的字符串）；越界或类型错误 MUST 返回 `failed`。
- **FR-017**: datetime 字段的 `options` MUST 支持 `with_time`（布尔，缺省 `true`）；类型错误 MUST 返回 `failed`。
- **FR-018**: 字段 `options.constraints` MUST 支持 `required`（布尔）、`min` / `max`（数字）、`enum_strict`（布尔）、`relation_must_exist`（布尔）；`constraints` 适用于所有字段类型。
- **FR-019**: 写接口 MUST 在落库前校验字段级约束；更新行时 MUST 按「旧值 + 本次提交」合并后的值校验；校验失败 MUST 不落库并返回 `failed`。
- **FR-020**: 系统 MUST 新增 `business_changes` 表，记录 `actor`、`origin`、`occurred_at`、`table_id`、`row_id`、`field_id`、`field_name`、`old_value`、`new_value`、`change_kind`、`reason`。
- **FR-021**: 每次行创建、更新、删除 MUST 对每个发生变化的字段写一条业务变更记录；创建时旧值为空，删除时新值为空。
- **FR-022**: 业务变更记录与数据变更 MUST 在同一事务内落库；写入失败 MUST 回滚全部业务变更记录，但写审计 MUST 保留失败记录。
- **FR-023**: 独立规格需求表 MUST 新增 `i-clarify`、`i-analyze`、`i-checklist` 三个 enum 字段，取值 MUST 为「未开始 / 进行中 / 完成」。
- **FR-024**: 独立规格需求表 MUST 新增 `i-constitution-version`（text）、`i-acceptance`（enum：未验收 / 已验收 / 不通过）、`i-owner`（text）、`i-priority`（enum：P0 / P1 / P2 / P3）。
- **FR-025**: 所有状态类字段 MUST 为 enum，至少覆盖：发布状态、文档状态、独立需求状态、speckit-constitution/specify/plan/task/implement、speckit-clarify/analyze/checklist、依赖需求状态、回归状态、验收状态、优先级。
- **FR-026**: 字段类型或 options 变更后，历史值不合法时读侧 MUST 回退显示原值或空值，MUST NOT 报错，MUST NOT 因读失败阻断整张表。
- **FR-027**: 写审计 MUST 记录 `origin`（`agent` / `human-request` / `seed`），用于区分人发起与 Agent 自主写入；人侧路由 MUST 仍然只有 GET。
- **FR-028**: 计算字段类型由 003 引入；002 MUST NOT 改变 `v-dev`、`v-bug`、`v-cond` 的业务语义，只负责 enum、格式、约束、变更记录与治理字段。

### Key Entities

- **字段（Field）**：新增 `options` 的结构化约定——enum 的 `options.items[]`、number 的格式、datetime 的 `with_time`、relation 的 `table_id`、所有类型的 `constraints`。
- **数据行（Row）**：id 为业务编号，表内唯一，跨表可同名；id 不可变。
- **业务变更记录（BusinessChange）**：一次字段级变化的业务留痕，含操作者、来源、时间、表、行、字段、旧值、新值、变更类型与原因。
- **关联挂载点（Relation Mount）**：同一对表只允许一个方向的 relation 字段；fd_system 模板中版本管理表是唯一挂载点。
- **枚举选项（EnumOption）**：`value` / `label` / `tone` / 可选 `color`；状态语义与颜色都在数据里。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: fd_system 与 tableflow 两个项目中，依赖变更需求表指向版本管理表的 relation 字段数为 0；反向创建 relation 的测试用例 100% 返回 `failed`。
- **SC-002**: 同表重复 id 的写入 100% 返回 `failed`；两张表各写一行 `7.0.1` 后，两次读取都返回 `7.0.1` 且数据不串。
- **SC-003**: 所有状态类字段（FR-025 清单）`type=enum` 且每个选项都含 `tone`；前端源码中业务状态字面量（`released` / `planned` / `待办` / `已完成` 等）命中数为 0。
- **SC-004**: 格式用例逐条通过：`12.3456` + `decimals=2` → `12.35 台`；`66.666` + `percent=true,decimals=1` → `66.7%`；`with_time=false` → `2026-11-10`；`with_time=true` → `2026-11-10 09:30`。
- **SC-005**: 5 类字段约束各有一个非法写入用例，全部返回 `failed` 且数据库中无新增行；合法写入用例全部通过。
- **SC-006**: 一次更新两个字段产生 2 条业务变更记录，旧值/新值逐字段正确；一次失败写入产生 0 条业务变更记录、1 条 `failed` 审计。
- **SC-007**: 行明细弹层展示的变更记录为只读，页面中不存在针对变更记录的写控件（DOM 中无对应按钮/输入框）。
- **SC-008**: 首屏与滚动基线不回退：14 行首屏 ≤500ms，关闭硬件加速滚动 ≥50fps，无 >50ms 长任务。
- **SC-009**: `cd backend && .venv/bin/pytest -q` 全绿；`cd frontend && npx tsc --noEmit` 零错误。

## Assumptions

- 行 id 由 Agent 提供，系统不自动生成业务编号；需要改编号时按「删旧行 + 建新行」处理，两步都留审计与变更记录。
- 「编号」列（`i-id` / `d-id`）与行 id 通常一致，但 v0.3.0 不强制校验一致性，避免把展示字段变成第二主键。
- 枚举的 `tone` 是 UI 语义，不是业务值；默认色板在前端，`options.color` 可覆盖具体颜色。
- `percent=true` 时存储值为百分数本身（`12.5` 表示 12.5%），避免读侧换算产生舍入漂移。
- 业务变更记录只覆盖数据行字段；表/字段定义变更由写审计覆盖。
- v0.3.0 不做旧库自动迁移：demo 数据用加载脚本重建；需要保留的旧数据由 Agent 重新写入。
- 人经 Agent 改状态的入口由 003 交付；002 只保证 enum、`origin` 与审计字段就绪。
- 目标浏览器与 001 一致：近两年 Chrome / Edge 桌面版；日期时间按浏览器本地时区显示。

## 未来范围

- 计算字段（count / percent / sum / rollup / and）由 003 交付；界面视觉打磨由 004 交付。
- 权限体系、多用户协作、视图体系、用户可编辑表达式、跨表任意聚合仍属宪法 v6.0.0 非目标，不在本 spec 范围。
