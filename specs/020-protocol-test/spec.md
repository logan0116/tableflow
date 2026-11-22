# Feature Specification: 测试域新表写入协议（020）

**Feature Branch**: `020-protocol-test`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 `020-AR`。board@4 新增 `case`（测试用例）与 `run`（用例执行情况）两表，给版本表加 `ver.runs`。三张表/字段的写入语义如果只靠契约文字，会出现四种事故：进度字段与结论字段各说各话、两步写入第二步失败后无人知道留下了一条悬空记录、同一用例被重复纳入导致进度分母翻倍、行 id 随手填导致"同版本同用例"根本无法识别。本文把这些写入协议写死，并落到 `backend/src/tableflow/run_protocol.py`。

**协议对象**: `specs/019-test-contract/board@4.yaml` 的 `run` 表与 `ver.runs` 字段；信封与三态判定沿用 `specs/012-protocol/spec.md`（protocol@2）。本文规则编号接 012 的 `P-048` 续编为 `P-049…P-068`（文中 `P-0xx` 小于 049 的一律指 012 的规则）；**不新增路径、不新增响应字段、不改 400/401/503 的判定**。012 的 Clarifications 已明确"新增表或字段不改变请求/响应形态，不需要升协议版本"，故本文仍属 protocol@2。

**基线**: `backend/` 当前实现（v0.6.5，含 010 计算口径、012 协议、013 用户管理）；`run` 表与 `ver.runs` 由 019 的迁移落库（`board@4.yaml` 的 `migrations.add-case-run` / `ver-add-stage-and-runs`）。所有写行为探针在临时库（`TABLEFLOW_DB` 指向临时文件）执行。

**实现落点**:

| 落点 | 内容 |
|---|---|
| `backend/src/tableflow/run_protocol.py` | 执行记录表识别、`state`/`result` 一致性、行 id 形状、`case_no` 一致、执行清单去重与不跨版本 |
| `backend/src/tableflow/write_service.py` | `create_row` / `update_row` 接线（校验在任何落库语句之前）、重复纳入的 400 文案 |
| `backend/tests/test_run_protocol_020.py` | 19 条用例，逐条覆盖本文 US1–US4 |

## 结论速览

1. **状态与结果必须同生同灭**：`state=todo` 时 `result` 必须为空，`state=done` 时 `result` 必须非空；新建与更新两条路径都校验，更新取**合并后的整行**。不一致返回 400，`run` 行与版本行都零写入，业务变更记录不增，失败审计照记（P-043）。
2. **行 id 是"同版本同用例"唯一的幂等键**：执行记录行 id 固定为 `<版本号>--<用例号>`（`v0.7.0--008-US1-AS1`），创建时校验形状；`run.case_no` 必须等于行 id 的用例号后缀。形状不写死，重复纳入就没有可靠的碰撞点。
3. **重复纳入的选择写死为 400**：服务端只认行 id 碰撞，第二次 POST 返回 400（错误指明"已纳入本版本"），零写入、不产生第二条记录；**"就地复用"是客户端行为**——收到 400 后按 012 的 P-031 回读该行，继续第二步，不新建行。选 400 而不是服务端 merge 的理由见 Clarifications。
4. **两步写入没有服务端原子性**：协议@2 的 P-019"一次请求只写一个资源"不变，`POST run` 与 `PATCH ver.runs` 是两个独立事务。第一步先提交，第二步失败时**第一步的提交必须能被回读发现**（`GET /api/tables/<run>/rows/<run_id>` 200）；客户端不得把第二步失败报成"没写进去"，也不得重放第一步。
5. **执行清单不得重复、不得跨版本**：提交给 `ver.runs` 这类指向执行记录表的 relation 值时，重复 id 返回 400；版本行的清单只允许收录 `<本行版本号>--<用例号>`。两条都由写侧校验，零写入。

## 背景与问题证据

| 现状 | 证据 | 后果 |
|---|---|---|
| 进度与结论是两个字段，写侧无一致性校验 | `write_service._validate_values` 只校验枚举值域；`board@4.yaml` 的 `rules.run_state_result_consistency` 要求"写入期校验"，此前只写在契约里 | 可以写出 `state=todo` + `result=pass`：版本表显示"未执行"，明细显示"通过"，两者都"合法" |
| 019 把该场景写成验收场景但还没有实现落点 | `specs/019-test-contract/spec.md` US3-AS4："`state=todo` 时直接写 `result=pass` 返回 400，且两字段读回不变" | 规格与代码两张皮；门禁只查字段，查不出这类行为缺失 |
| 两步写入无失败语义 | `board@4.yaml` 的 `conventions.run_two_step_write` 只写"客户端必须回读"，没定义"第二步失败后第一次写入叫什么、怎么被看到" | 第二步失败时最自然的实现是"报失败、收工"，留下的悬空 run 行没有任何发现路径；且 `run` 表 `kind=detail` 不进导航（US1-AS3），界面也不会替人发现 |
| 重复纳入无协议 | 020 落地前重复 `POST` 同一行 id 一律 `400 {"result":"failed","error":"行 id 已存在：…"}`（`write_service.create_row`），对执行记录无专门文案 | 客户端无法区分"已经纳入过（可继续）"与"id 写错（不能继续）"，于是二选一都会错：要么重复建第二条，要么误判失败 |
| 新表行 id 无形状约束 | `_validate_row_id` 只要求 `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` | 行 id 可以叫 `RUN-1`、`x`、`v0.7.0_008-US1-AS1`；"同版本同用例只有一条记录"失去可判定的键 |
| 执行清单是普通 relation 数组 | `_validate_values` 只校验"字符串数组"，不查重复、不查来源版本 | 同一 run id 追加两次会让 `count(ver.runs)` 把进度分母算成 2；把 v0.8.0 的记录挂进 v0.7.0 也无任何信号 |
| `run.case_no` 是展示冗余 | `board@4.yaml` 的 `run.case_no` note："与 run.case 指向同一用例，属展示冗余，写入时由脚本同步" | 脚本写错时行 id 与 `case_no` 指向两条用例，弹层第二列与第三列对不上，且无人校验 |

## Clarifications

### Session 2026-11-22

- Q: 一致性校验放在接口层还是写服务层？ → A: 写服务层（`write_service.create_row` / `update_row` 内），因为接口只是一层薄路由，脚本与测试直连写服务时也必须受同一口径约束；校验在 `run_write` 的事务内、任何落库语句之前，失败由 `run_write` 回滚并记失败审计。
- Q: 怎么认定"这是 run 表"？ → A: 按**枚举值域**，不看表 id、字段 id/名称，也不看表级 `kind`（`kind` 落库属 019 实现范围，写协议不能依赖一个可能还没迁移的列）：表内同时存在值域恰为 `{todo,done}` 的 enum 字段，和值域是 `{pass,fail,blocked,skip}` 子集的 enum 字段。board@4 六表里只有 `run.state`/`run.result` 落在这两个值域上（`spec.stage` 含 doing/na、`ver.stage.*` 含 doing/failed，都不会误命中），所以迁移脚本怎么给字段起 id 都不影响识别——这比认 `-state`/`-result` 后缀更能扛 019 的实现自由度。候选不唯一时不猜（与 `_owner_field` 同一纪律），不启用本协议。
- Q: 重复纳入为什么选 400 而不是"服务端就地复用"？ → A: 两个理由。① 语义安全：`POST` 一旦对已存在行做"合并更新"，就等于允许一个建行请求隐式覆盖执行结果、证据、执行人——这是 012 P-019 明确拒绝的"静默部分写入"的同类危险；② 现状即此：行 id 已存在本来就 400，把它写死比新增一条"POST 撞 id 就 merge"的隐式规则代价小。代价是客户端多一步回读（012 P-031 已有配方），接受。
- Q: 客户端回读后拿到的行与本次意图不一致怎么办？ → A: 按 P-031：内容与意图一致 → `success(reconciled)` 并继续第二步；不一致（例如同一执行记录已被别人跑过）→ `failed(conflict)`，不覆盖、不新建第二条，报告差异。
- Q: 两步写入能不能服务端原子化？ → A: 本规格不新增端点、不改 P-019，故不能。缺口登记为 `G11`（建议后续需求提供"纳入用例"单端点或批量事务）。本文的职责是把失败语义写清，使非原子性可被发现与对账。
- Q: 第一步成功后第二步失败，第一次写入算什么？ → A: 算"已提交但未纳入"的悬空执行记录：`run` 行存在且可回读（`GET` 200，`state=todo`），版本行 `ver.runs` 不含它。三态判定按 HTTP 分：第二步 400 → `failed`（但必须附"第一步已提交"与悬空行 id）；第二步 503/超时 → `unknown` 并回读版本行与原 run 行。
- Q: 悬空行要不要自动清理？ → A: 不自动。删行是硬删除（P-018），自动删会抹掉"曾经尝试纳入"的痕迹；清理由客户端在报告后按人工决定执行（DELETE 该 run 行）。
- Q: `run.case_no` 与行 id 不一致为什么不允许"以 relation 为准"自动纠正？ → A: 服务端没有"用例号真源"的角色：`run.case` 是行 id 引用，`run.case_no` 是展示冗余，两者都不是权威。允许自动纠正等于替脚本猜意图；直接 400 让写方给出自洽的值。
- Q: 重跑（同一用例第二次执行）怎么表达？ → A: `PATCH` 同一条 run 行（`state=done` + `result` + `evidence`/`executed_at`/`executor`），不新建行、不重复追加 `ver.runs`。这就是契约 `run_one_per_version_case` 的落法。
- Q: 为什么不校验 `ver.runs` 里的 run 行是否真的属于本版本（读 run 行 id 前缀）？ → A: 已经由"版本行清单只允许 `<本行版本号>--<用例号>`"覆盖：run 行 id 前缀即版本号，规则等价且无需二次查询。
- Q: 存量不合法数据怎么办？ → A: 存量 `state`/`result` 不一致的行，要求在同一次 `PATCH` 内修正（否则任何写都被拒——不一致的行本就不该继续被编辑）；存量行 id 形状不合法时不再用形状卡住编辑，只在 id 可解析时校验 `case_no` 一致（避免"协议上线即冻结老数据"）。

## 使用者与验收场景

### User Story 1 - 状态与结果一致 (Priority: P1)

写执行记录的人不能写出"没跑却已有结论"或"跑了却没结论"的行；任何写入口（新建、更新）都给出同一条 400 与同一条口径。

**Why this priority**: 版本表三个用例字段只消费 `state`，结论在 `result`；两者错位时版本进度就是假的。

**Independent Test**: 对一条 `state=todo` 的记录只 PATCH `result=pass`，得到 400，回读两字段均未变；同时提交 `state=done` 与 `result=pass` 得到 200。

**Acceptance Scenarios**:

1. **Given** 一条新执行记录，**When** 以 `state=todo`、`result` 为空提交，**Then** 200，`state=todo`、`result` 为空。
2. **Given** 一条新执行记录，**When** 以 `state=todo`、`result=pass` 提交，**Then** 400（`result=failed`，错误指出状态与结果不一致），`run` 表零写入、版本行 `runs` 不变、`business_changes` 不增。
3. **Given** 一条新执行记录，**When** 以 `state=done`、`result` 为空提交，**Then** 400，零写入。
4. **Given** 一条新执行记录，**When** 只给 `result=pass` 而不给 `state`，**Then** 400（有结论必须有执行状态），零写入。
5. **Given** 已存在 `state=todo`、`result` 为空的记录，**When** 只 PATCH `state=done`（不带 `result`），**Then** 400，回读整行不变。
6. **Given** 同一条记录，**When** 在同一请求里提交 `state=done` 与 `result=pass`，**Then** 200，回读两字段均为提交值。
7. **Given** 一条被直接落库的存量不一致行（`state=todo` + `result=pass`），**When** 只 PATCH 无关字段，**Then** 400；**When** 同一请求内把两字段改自洽，**Then** 200。

### User Story 2 - 两步写入失败可发现 (Priority: P1)

把用例纳入版本是两步。第二步失败时，第一步写入必须留下可回读的痕迹，客户端报告里必须能指出"记录已存在但版本看不到"。

**Why this priority**: 这是"报成功就完事"与"诚实报告"的分界线；`run` 表不进导航，一旦回读路径没写死，悬空记录就永久失联。

**Independent Test**: 第一步 200；第二步用不存在的执行记录 id 追加得到 400；随后 `GET` 第一步建的行得到 200 且 `state=todo`，版本行 `runs` 仍为空；修好第二步后版本行能看到该记录。

**Acceptance Scenarios**:

1. **Given** 一个 `planned` 版本与一条已存在用例，**When** `POST` 一条执行记录（`state=todo`），**Then** 200，`GET /api/tables/<run>/rows/<run_id>` 能读到 `state=todo`。
2. **Given** 第一步已成功，**When** 第二步 `PATCH ver.runs` 引用了不存在的执行记录 id，**Then** 400（`result=failed`），版本行零写入（`runs` 不变）。
3. **Given** 第二步失败，**When** 客户端按 id 回读执行记录，**Then** 200 且字段与第一步提交一致——第一次写入可被发现，不得报告"未写入"。
4. **Given** 第二步失败后修正引用，**When** 再次 `PATCH ver.runs`，**Then** 200，回读版本行 `runs` 含该 id。
5. **Given** 第一步成功、第二步尚未成功，**When** 客户端重放第一步，**Then** 400（"已纳入本版本"），不得产生第二条执行记录。

### User Story 3 - 同版本同用例只有一条记录 (Priority: P1)

同一版本内同一用例的重复纳入有确定答案：服务端 400、零写入；客户端按回读复用既有行；任何路径都不产生第二条执行记录，也不重复计数。

**Why this priority**: 进度分母（`ver.case_total`）直接由 `ver.runs` 计算，重复登记会让"10 条用例"变成 11 条，"跑完 10 条"永远不成立。

**Independent Test**: 连续两次 `POST` 同一执行记录 id，第二次 400；`run` 表仍 1 行、版本行 `runs` 不变。再对版本行提交重复数组与跨版本 id，均 400。

**Acceptance Scenarios**:

1. **Given** 一条执行记录已存在，**When** 再次 `POST` 同一 id，**Then** 400 且错误指明"已纳入本版本（执行记录已存在）"，`run` 表仍 1 行。
2. **Given** 该记录已被追加进 `ver.runs`，**When** 再次 `POST` 同一 id，**Then** 400，版本行 `runs` 不变（不重复追加）。
3. **Given** 版本行的 `runs` 提交值含重复 id，**When** `PATCH`，**Then** 400（"不得重复纳入"），版本行零写入。
4. **Given** 版本 `v0.7.0`，**When** 提交 `v0.8.0--008-US1-AS1` 到它的 `runs`，**Then** 400（"只能收录本版本"），版本行零写入。
5. **Given** 同一条执行记录需要重跑，**When** `PATCH` 该行（`state=done` + `result` + 证据），**Then** 200，`run` 表行数不变，`ver.runs` 不变。

### User Story 4 - 行 id 与用例号自洽 (Priority: P2)

执行记录的行 id 形状固定、`case_no` 与行 id 后缀一致；不满足即 400，零写入；非执行记录表不受这套规则影响。

**Why this priority**: 行 id 是重复纳入的碰撞点、是弹层第一列、是缺陷回溯键；形状漂移会让前述所有判定失效。

**Independent Test**: 用 `RUN-01` 建执行记录得到 400；`case_no` 与 id 后缀不一致得到 400；在字段形状不匹配的普通表上写 `x-state=open`+`x-result=pass` 得到 200；把字段 id 起成 `r2-progress`/`r2-outcome` 的执行记录表仍受同一套校验。

**Acceptance Scenarios**:

1. **Given** 执行记录行 id 不是 `<版本号>--<用例号>`，**When** `POST`，**Then** 400，零写入。
2. **Given** 行 id 为 `v0.7.0--008-US1-AS1`、`case_no` 为 `008-US1-AS2`，**When** `POST`，**Then** 400（"用例号必须与行 id 的用例号一致"），零写入。
3. **Given** 一张普通表有 `x-state`（值域 `open/closed`）与 `x-result` 字段，**When** 写入 `open` + `pass`，**Then** 200（不套用执行记录协议，不误伤既有表）。
4. **Given** 执行记录行 id 合法、`case_no` 与后缀一致，**When** `POST`，**Then** 200。
5. **Given** 执行记录表的字段 id 起成 `r2-progress`/`r2-outcome`（非 `-state`/`-result`），**When** 写入 `todo` + `pass`，**Then** 仍按值域识别并 400（一致性规则不因命名而静默失效）。
6. **Given** 用例号字段 id 不是 `<前缀>-case_no` 而是 `r2-caseid`（名称为「用例号」），**When** 提交与行 id 后缀不一致的值，**Then** 400（按名称兜底识别）。

### Edge Cases

- 第二步失败是 503（存储不可用/锁冲突）：第一步是否提交未知，按 012 P-024 判 `unknown`，回读 run 行与版本行定案；不得直接重放第一步。
- 第一步失败但客户端超时：按 012 P-031 用同一行 id 回读——行存在即视为幂等成功并继续；行不存在才重试建行。
- `run.case` 关联目标不存在：400（"关联目标行不存在"，P-036 顺序约束），零写入。
- `run.evidence` 为空而 `result=pass`：本规格不拒（契约只说"应有"，未定义写入期强校验）；由测试验收节点的人工判定与评审把关。
- 存量行 id 不合法：`PATCH` 不再按 id 形状拒绝，只在其可解析时校验 `case_no`；新建一律按新形状。
- 执行清单里混入"合法前缀但记录不存在"的 id：先过形状与前缀规则，再由 `relation_must_exist` 给出 400（校验顺序见 P-056）。
- 019 实施时字段 id 可能与契约示例不同（如 `r2-progress`/`r2-outcome`）：识别按枚举值域，不按字段 id；`case_no` 先认 `-case_no` 后缀、再认名称「用例号」，都认不出就跳过该项校验而不是猜。
- 同一用例在两个版本各一条记录：允许（行 id 前缀不同），版本行清单互不收录对方（P-059）。
- `recompute` 不涉及本协议：计算字段只消费 `state`/`runs`，重算不触发写侧校验（P-009 不变）。

## Requirements *(mandatory)*

- **FR-001**: 执行记录行 id MUST 为 `<版本号>--<用例号>`，版本号匹配 `v<主>.<次>.<修>`；新建时不符 MUST 400 且零写入。
- **FR-002**: `run.case_no` MUST 与行 id 的用例号后缀一致；不一致 MUST 400 且零写入。
- **FR-003**: `state=todo` 时 `result` MUST 为空；`state=done` 时 `result` MUST 非空；`result` 非空而 `state` 为空 MUST 400。
- **FR-004**: 一致性校验 MUST 覆盖新建与更新两条路径；更新 MUST 取合并后的整行校验。
- **FR-005**: 一致性校验 MUST 在任何落库语句之前完成；失败 MUST 400、MUST NOT 产生 `run` 行写入、MUST NOT 改动版本行、MUST NOT 新增 `business_changes`；失败审计 MUST 照 P-043 记录。
- **FR-006**: 纳入用例 MUST 走两步写入：先 `POST run`（`state=todo`）→ 回读 → 读版本行 → `PATCH ver.runs` 追加 → 回读版本行。
- **FR-007**: 第二步失败时，第一步的提交 MUST 可经 `GET /api/tables/<run>/rows/<run_id>` 回读发现（200 且字段一致）；协议 MUST 禁止把该情形报告为"未写入"。
- **FR-008**: 同版本同用例重复纳入 MUST 返回 400（服务端行为固定），MUST NOT 产生第二条执行记录；客户端 MUST 按 P-031 回读复用既有行。
- **FR-009**: 提交给 `ver.runs` 的 id 数组 MUST NOT 含重复项；版本行的清单 MUST 只含 `<本行版本号>--<用例号>`；违反 MUST 400 且零写入。
- **FR-010**: 执行记录表 MUST 按枚举值域识别（存在值域恰为 `{todo,done}` 的 enum 字段，且存在值域 ⊆ `{pass,fail,blocked,skip}` 的 enum 字段）；MUST NOT 依赖表 id、字段 id/名称或表级 `kind`；候选多义时 MUST NOT 猜。`run.case_no` 的定位 MUST 先认 id 后缀 `-case_no`、再认名称「用例号」，都找不到时 MUST NOT 猜（跳过该项校验）。
- **FR-011**: 本规格 MUST NOT 新增路径、MUST NOT 新增响应字段、MUST NOT 改变 400/401/503 的三态判定。
- **FR-012**: 重跑 MUST 是对同一条执行记录的 `PATCH`，MUST NOT 新建行、MUST NOT 重复追加 `ver.runs`。

## 协议正文

**图例**：现状列`满足`=现有实现无需改动即符合本协议；`已实现（020）`=本次落地的写侧校验；`缺口`=需服务端改造，编号见"落地差距清单"。

### 1. 范围与兼容

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-049 | 本文只定义 `case`/`run` 两表与 `ver.runs` 的写侧语义；信封、三态、幂等配方、并发纪律沿用 `protocol@2`（012 的 P-001…P-048），本文不重复也不修改 | 满足（protocol@2 未升版） | 对照 012 的 P-019/P-020/P-021/P-024：400 仍是 `{"result":"failed","error":"…"}`，无新增顶层键 |
| P-050 | 执行记录行 id 固定为 `<版本号>--<用例号>`：版本号 `v<主>.<次>.<修>`（`^v\d+\.\d+\.\d+$`），用例号即场景号；创建后不可改（P-014） | 已实现（020） | `POST /api/agent/tables/<run>/rows/RUN-01` → `400`（错误"执行记录行 id 必须是「<版本号>--<用例号>」"）；`POST …/rows/v0.7.0--008-US1-AS1` → `200` |
| P-051 | `run.case_no` 是展示冗余，MUST 等于行 id 的用例号后缀；不一致 400 | 已实现（020） | `case_no=008-US1-AS2` + 行 id `v0.7.0--008-US1-AS1` → `400`（错误"用例号必须与执行记录行 id 的用例号一致"） |
| P-052 | 行 id 形状只对"新建执行记录"强校验；存量行 id 不合法不阻断其编辑（可解析时才校验 `case_no`） | 已实现（020） | 直接落库的 `RUN-1` 行仍可 `PATCH state=done, result=pass` → `200`；新建 `RUN-1` → `400` |

### 2. 状态与结果一致性

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-053 | `state=todo` ⇒ `result` 为空；`state=done` ⇒ `result` 非空（`pass/fail/blocked/skip` 之一）；`result` 非空而 `state` 为空 ⇒ 400 | 已实现（020） | 新建 `todo`+`pass` → 400；新建 `done`+空 → 400；新建只给 `result=pass` → 400；新建 `todo`+空 → 200 |
| P-054 | 更新取**合并后的整行**校验：只提交 `result` 不改 `state` → 400；只把 `state` 改 `done` 不带 `result` → 400；两字段同请求提交 → 200 | 已实现（020） | `PATCH {"values":{"tf-r-result":"pass"}}`（原 `state=todo`）→ 400 且回读两字段不变；`PATCH {"state":"done","result":"pass"}` → 200 |
| P-055 | 识别口径：枚举值域（存在值域恰为 `{todo,done}` 的 enum 字段 + 存在值域为 `{pass,fail,blocked,skip}` 子集的 enum 字段）；不依赖表 id、字段 id/名称或 `kind`；候选多义时不启用 | 已实现（020） | 普通表 `x-state(open/closed)` + `x-result(pass/fail)` 写 `open`+`pass` → 200（不误伤）；字段 id 为 `r2-progress`/`r2-outcome` 的执行记录表写 `todo`+`pass` → 400（照样识别） |
| P-056 | 校验时机、顺序与零写入：本协议校验在任何 `INSERT/UPDATE` 之前，且**先于**必填/枚举/关联存在性约束（故跨版本、重复数组、状态不一致的错误先于"关联目标行不存在"出现）；失败 400、`run` 行不变、版本行不变、`business_changes` 不增；失败审计照记（P-043） | 已实现（020） | 失败后 `SELECT count(*) FROM row_records WHERE table_id='<run>'` 不增；`business_changes` 该表计数不变；`write_audit` 末条 `failed` 且 `error` 含"不一致" |

### 3. 两步写入与失败语义

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-057 | 纳入顺序：① `POST run`（`state=todo`、`result` 空）② 回读该行 ③ 读版本行取当前 `runs` ④ `PATCH ver.runs` = 旧数组 + 新 id ⑤ 回读版本行确认含该 id；任一步失败即停，报告已完成步骤 | 已实现（两步可执行；无单端点） | 按顺序五步全 200，版本行回读含 id；跳步（先 PATCH 后建行）第二步 400（"关联目标行不存在"） |
| P-058 | 第二步失败（400/503/超时）时，第一步的提交**已独立持久**：`run` 行存在、`state=todo`，版本行 `runs` 不含它。这是一条**悬空执行记录**，MUST 经 `GET /api/tables/<run>/rows/<run_id>` 回读发现（`run` 表 `kind=detail` 不进导航，回读是唯一发现路径） | 已实现（020；读取路径 019 US1-AS3） | 第一步 200 → 第二步引用不存在 id 得 400 → `GET` 该 run 行 200 且 `state=todo` → 版本行 `runs` 为空 |
| P-059 | 第二步失败的报告格式：达到三态终态时 MUST 附 `{run_id, first_step:"submitted", second_step:<http 与 error>, ver_runs_readback:[…]}`；MUST NOT 报"未纳入"或"未写入"；MUST NOT 重放第一步（P-062 会 400） | 满足（客户端纪律） | 客户端报告样例含悬空行 id 与版本行回读数组；日志中第一步只出现一次 |
| P-060 | 悬空行不自动清理；清理是显式 `DELETE` 该 run 行（硬删除，P-018），删前必须在报告里留痕 | 满足 | 第二步失败后 `run` 表仍有该行；显式 DELETE 后 404 |
| P-061 | 非原子性登记为缺口 `G11`：服务端不提供"纳入用例"单端点/跨资源事务；提议见差距清单 | 缺口（G11） | `POST /api/agent/tables/<ver>/rows/<ver>/runs` 不存在（404 `detail`）；只有两步走法 |

### 4. 重复纳入与执行清单

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-062 | 同版本同用例重复纳入 = **400**（服务端行为固定）：行 id 已存在 → `400`，错误"该用例已纳入本版本（执行记录已存在）"；零写入、不产生第二条记录 | 已实现（020；文案针对执行记录表） | 连续两次同 body 的 `POST`：第二次 400，错误含"已纳入本版本"；`run` 表仍 1 行 |
| P-063 | 客户端处理重复纳入 = **就地复用**：400 后按 012 的 P-031 回读该行；内容与本次意图一致 → `success(reconciled)` 并继续第二步；不一致 → `failed(conflict)`，不覆盖、不新建 | 满足（P-031 配方） | 回读行 `state/result/case` 与意图逐字段一致才算 reconciled；不一致示例：别人已置 `state=done` 而意图是 `todo` |
| P-064 | 提交的 run-list relation 数组 MUST NOT 含重复 id（同一版本两条同一记录） | 已实现（020） | `PATCH ver.runs ["v0.7.0--008-US1-AS1","v0.7.0--008-US1-AS1"]` → 400（"不得重复纳入"），版本行零写入 |
| P-065 | 版本行的清单 MUST 只含 `<本行版本号>--<用例号>`；别版本的记录挂进来 → 400 | 已实现（020） | `PATCH v0.7.0 的 runs` 含 `v0.8.0--008-US1-AS1` → 400（"只能收录本版本"） |
| P-066 | 重跑 = `PATCH` 同一条记录（`state=done`+`result`+证据/时间/执行人），不新建、不重复追加；同一执行记录的状态与结果仍受 P-053/P-054 约束 | 满足 | `run` 行数不变；`ver.runs` 不变；`PATCH` 后回读 `state/result` 为提交值 |
| P-067 | `run` 表可读性：`kind=detail` 不进表导航，但 `GET /api/tables/<run>/table`、`GET …/rows/<id>`、`GET …/rows/<id>/changes` 均按 P-007/P-046 可用 | 满足（019 US1-AS3 + 现有读接口） | 三个 GET 均 200；导航可见性属 021，本文不重复 |
| P-068 | 错误文本只供人读；机器判定只用 HTTP 状态与 `result`（P-026 不变） | 满足 | 客户端代码不得出现 `if "已纳入" in error` 这类判定 |

## 客户端实现清单（纳入用例，按序）

1. 生成执行记录行 id：`<版本号>--<用例号>`；`case_no` 取同一用例号。
2. `POST` 执行记录，body `{"values":{case_no, case:[用例id], state:"todo"}}`。
3. 分类响应：200 → 继续；400 且 intent 未变化 → 回读该行，按 P-063 判 `success(reconciled)`；400 且内容不同 → `failed(conflict)`；503/超时 → 回读定案（P-024/P-031）。
4. `GET` 版本行，取当前 `runs` 数组（读改写自检，P-037）。
5. 数组追加新 id；若新 id 已在数组里，不要重复追加（重复值会被 P-064 拒）。
6. `PATCH` 版本行 `{"values":{"runs":[…]}}`。
7. 分类第二步：200 → `GET` 版本行回读确认含该 id；400 → 记 `failed` 并附悬空行 id 与回读数组；503/超时 → `unknown`，回读版本行与 run 行定案。
8. 第二步最后失败时，报告里必须写：`run_id`、`first_step=submitted`、第二步 HTTP 与 error、版本行 `runs` 回读值。不要重放第一步。
9. 已纳入后重跑：跳过 2–6，直接 `PATCH` 该执行记录（`state=done`、`result`、证据）。
10. 不得解析错误文本做判定；不得把 `unknown` 当成功；不得在一个版本上并发执行纳入（P-035/P-040）。

## 示例会话（临时库；`<ver>`/`<run>`/`<case>` 为表 id）

```bash
H=(-H 'X-Agent-Id: agent-demo' -H 'Content-Type: application/json')

# 1 建执行记录（state=todo，result 必须为空）
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/<run>/rows/v0.7.0--008-US1-AS1 \
  -d '{"values":{"tf-r-case_no":"008-US1-AS1","tf-r-case":["008-US1-AS1"],"tf-r-state":"todo"}}'
# → {"result":"success","id":"v0.7.0--008-US1-AS1"}

# 2 状态与结果不一致：todo 直接带 pass
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<run>/rows/v0.7.0--008-US1-AS1 \
  -d '{"values":{"tf-r-result":"pass"}}'
# → 400 {"result":"failed","error":"执行状态与执行结果不一致：state=todo 时 result 必须为空…"}
#   回读仍是 state=todo、result 空

# 3 第二步：把 run id 追加到版本行（先读后写）
curl -s $TF_BASE/api/tables/<ver>/rows/v0.7.0            # 取 runs 当前值
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-runs":["v0.7.0--008-US1-AS1"]}}'
# → {"result":"success","id":"v0.7.0"}

# 4 第二步写坏引用（记录不存在）→ 400，且第一步的写入仍可回读
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-runs":["v0.7.0--999-US1-AS9"]}}'
# → 400 {"result":"failed","error":"关联目标行不存在：<run>/v0.7.0--999-US1-AS9"}
curl -s $TF_BASE/api/tables/<run>/rows/v0.7.0--008-US1-AS1   # 200，state=todo → 悬空行可发现

# 5 重复纳入（同版本同用例第二次 POST）→ 400，零写入
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/<run>/rows/v0.7.0--008-US1-AS1 \
  -d '{"values":{"tf-r-case_no":"008-US1-AS1","tf-r-case":["008-US1-AS1"],"tf-r-state":"todo"}}'
# → 400 {"result":"failed","error":"该用例已纳入本版本（执行记录已存在）：v0.7.0--008-US1-AS1；请回读该行后继续，不新建第二条记录"}

# 6 重跑：PATCH 同一条记录，不新建
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<run>/rows/v0.7.0--008-US1-AS1 \
  -d '{"values":{"tf-r-state":"done","tf-r-result":"pass","tf-r-evidence":"logs/020/AS1"}}'
# → 200；run 表行数不变，ver.runs 不变
```

## 落地差距清单

| 编号 | 缺口 | 现状证据 | 影响 | 建议归属 |
|---|---|---|---|---|
| G11 | 两步写入无服务端原子性（无跨资源事务/批量端点） | `app.py` 无"纳入用例"路由；P-019"一次请求只写一个资源" | 第二步失败必留悬空行，只能靠回读与人工清理 | 后端（后续需求） |
| G12 | 悬空行无查询接口 | 只能按已知 run id 单行 `GET`；无"列出未挂进任何版本清单的执行记录"接口 | 批量对账要客户端自己差集扫描 | 后端（可复用 P-046 口径） |
| G13 | 幂等键仍无落点（继承 012 的 G1） | `write_audit` 无幂等列、不解析 `Idempotency-Key` | 重复纳入的补偿依赖行 id 业务键 + 回读（本文已写死） | 后端（新需求） |

## 非目标

- 不实现界面（用例视图、版本行弹窗属 021）。
- 不属于 019 的范围：不建表、不迁移存量项目、不改 `ver` 六节点与计算字段口径。
- 不实现六节点串行/闸门校验（025），不实现条件表达式（023）。
- 不新增接口路径、不加批量写、不改 400/401/503 三态与审计字段集合。
- 不迁移 MeterSphere 历史执行数据。
- 不定义"通过率"口径：版本表只统计进度，结论留在 `run.result`。
- 不把 G11/G12/G13 在本需求内实现。

## Success Criteria

- **SC-001**: 新建执行记录时四类组合（`todo`+空、`done`+结论、`todo`+结论、只有结论无状态）分别 200/200/400/400，且 400 时 `run` 表与版本行零写入、`business_changes` 不增。
- **SC-002**: 更新路径两类（只改 `result`、只改 `state=done`）均 400 且回读整行不变；同请求提交两字段 200。
- **SC-003**: 第一步 200、第二步 400 后，`GET` 第一步建的行 200 且字段一致（悬空行可发现）；修正后版本行回读含该 id。
- **SC-004**: 同版本同用例第二次 `POST` 400 且 `run` 表仍 1 行；版本行 `runs` 不重复；重复数组与跨版本 id 各自 400 且零写入。
- **SC-005**: 行 id 形状与 `case_no` 一致性各有一条 400 用例；字段形状不匹配的普通表写入 200（无假阳性）；非惯例字段 id 的执行记录表仍被识别并受同一校验（防 019 实施自由度导致规则静默失效）。
- **SC-006**: `cd backend && .venv/bin/python -m pytest -q` 全绿（本文新增 19 条用例，逐条映射见下表）。

## 验收判定（场景 → 测试）

| 场景 | 测试（`backend/tests/test_run_protocol_020.py`） |
|---|---|
| US1-AS1 / AS2 / AS3 / AS4（新建） | `test_create_todo_without_result_ok` / `test_create_todo_with_result_rejected_zero_write` / `test_create_done_without_result_rejected_zero_write` / `test_create_result_without_state_rejected` |
| US1-AS5 / AS6 / AS7（更新与存量） | `test_patch_state_done_without_result_rejected` / `test_patch_state_done_with_result_ok` / `test_patch_fix_inconsistent_legacy_row_in_one_request` |
| US1 补充（019 US3-AS4） | `test_patch_result_without_state_rejected` |
| US2-AS1…AS5（两步写入） | `test_two_step_write_second_failure_keeps_first_write_readable` |
| US3-AS1 / AS2（重复纳入） | `test_duplicate_inclusion_second_post_is_400_and_single_row` / `test_duplicate_after_inclusion_is_400` |
| US3-AS3 / AS4（清单去重/跨版本） | `test_run_list_rejects_duplicate_ids` / `test_run_list_rejects_other_version_record` |
| US4-AS1 / AS2 / AS3（行 id 与形状识别） | `test_run_id_must_encode_version_and_case` / `test_case_no_must_match_run_id_suffix` / `test_non_run_table_with_state_result_names_is_untouched` |
| US4-AS4 / AS5 / AS6（命名鲁棒性） | `test_run_table_detected_by_value_domain_not_field_id` / `test_run_table_detected_by_value_domain_still_enforces_row_id` / `test_case_no_fallback_by_field_name` |
| US3-AS5（重跑共用路径） | `test_patch_state_done_with_result_ok`（PATCH 同一条记录不新建） |

## Key Entities

- **执行记录行 id（run id）**：`<版本号>--<用例号>`，版本内同一用例的幂等键；创建后不可改。
- **悬空执行记录（orphan run）**：第一步已提交、第二步未成功，版本行的 `runs` 看不到、但 `GET` 单行能读到的执行记录；只能显式删除或补第二步。
- **执行清单（ver.runs）**：版本行持有的执行记录 id 数组；进度三个字段的唯一输入，不得重复、不得跨版本。
- **状态/结果对（state/result）**：进度与结论两个字段，必须同生同灭；进度只消费 `state`。
- **就地复用（reconciled reuse）**：重复纳入收到 400 后回读既有行继续第二步的客户端行为，不新建行。
