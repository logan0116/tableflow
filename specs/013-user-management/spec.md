# Feature Specification: 用户管理（兼容期，v0.6.2）

**Feature Branch**: `013-user-management`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 看板`013-AR`行条款："用户管理：每个使用者配独立API key，服务端按key识别调用者并落进写入审计；负责人字段缺省由调用者身份填充，不再手填。含key的签发、吊销与审计查询。"

## 背景与问题证据

| 现状 | 证据 | 后果 |
|---|---|---|
| 写接口只有`X-Agent-Id` | `backend/src/tableflow/app.py`每个写接口取`X-Agent-Id`直接当审计身份；`skills/tableflow-board/SKILL.md`第233行、`skills/tf-update/SKILL.md`第43/154/317行都用它 | 任何调用方都能自称任意身份，审计可被冒名，无法回答"这次写入是谁" |
| 没有身份凭据 | `write_audit`只有`agent_id`文本 | 同一身份无法吊销、无法分人计量 |
| 负责人靠手填 | 7个项目15张表的`*-owner`字段全部为空或人工填 | 新建行经常漏填负责人，事后无人认领 |

约束：本次是**兼容期**，现有skill/脚本只带`X-Agent-Id`的调用方式必须原样可用；收紧为"必须带key"由后续需求决定。

## Clarifications

### Session 2026-11-19

- Q: 兼容期怎么判定调用者？ → A: 带`X-API-Key`优先，按key识别；不带key回退`X-Agent-Id`；两者都不带→400，错误信息保留`X-Agent-Id`字样（旧客户端据此提示）。
- Q: 带了无效key但`X-Agent-Id`合法，要不要回退？ → A: 不回退，401拒写。显式出示的凭据失败就必须失败，静默降级会把"认证失败"变成"匿名写入"。
- Q: key怎么存？ → A: 只存SHA-256摘要与`key_id`（`k-xxxxxxxx`）、label（调用者身份）、note、签发/吊销信息；明文只在签发时打印一次，列表不回显。
- Q: 审计怎么记？ → A: `write_audit`新增`key_id`列：key调用记该key的id，旧调用为`NULL`；`agent_id`与`business_changes.actor`统一填key的label（旧调用填`X-Agent-Id`值）。
- Q: 无效key的尝试要不要留痕？ → A: 要。写一条`result=failed`的审计（`agent_id`为请求里带的`X-Agent-Id`或`-`，`key_id`为空），业务数据不落。
- Q: 负责人字段怎么识别（不改字段类型）？ → A: 文本字段且字段id以`-owner`结尾（契约字段id规则`<前缀>-<v|i|d>-<短名>`）；没有时退一步认名称恰为"负责人"的文本字段。同表多个候选则不猜、不填。7个项目15个负责人字段全部符合该规则，无需存量迁移。
- Q: 什么时候填充负责人？ → A: 只在新**建行** 且该字段缺省/为空时填；显式值优先；**只对key鉴权的调用者填充**——旧`X-Agent-Id`是工具名不是人，填进"负责人"会污染人员语义，且会让旧脚本写入结果变化。更新行不填充。
- Q: key的管理入口是什么？ → A: 最小CLI `backend/scripts/tf_keys.py`（`issue`/`revoke`/`list`/`audit`）。签发与吊销本身也落`write_audit`（`key.issue`/`key.revoke`），审计可倒查。
- Q: 旧库怎么升级？ → A: 服务启动时幂等补表补列（`CREATE TABLE IF NOT EXISTS api_keys`、`ALTER TABLE write_audit ADD COLUMN key_id`），不需要单独迁移脚本；旧审计行保留且`key_id`为空。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 兼容期旧调用不被打断 (Priority: P1)

现有skill与脚本只带`X-Agent-Id`的写调用原样可用，写入内容与审计身份都不变。

**Why this priority**: 兼容期一旦打断旧调用，所有看板录入与演练流程立刻停摆。

**Independent Test**: 只带`X-Agent-Id`写入一行，读回数据、审计与业务变更记录，与改造前一致。

**Acceptance Scenarios**:

1. **Given** 只带`X-Agent-Id`的写请求，**When** 新建一行，**Then** 返回`success`，审计`agent_id`为该值、`key_id`为空。
2. **Given** 同样只带`X-Agent-Id`，**When** 新建行未填负责人，**Then** 负责人保持为空（旧调用写入结果与改造前逐字节一致）。
3. **Given** 不带任何凭据，**When** 调用写接口，**Then** 返回`400`且错误信息含`X-Agent-Id`；读接口不需要任何凭据。

### User Story 2 - key识别调用者并落审计 (Priority: P1)

带`X-API-Key`时，服务端按key识别调用者：审计写`key_id`与key的label，业务变更记录的actor也是该label。

**Why this priority**: 这是"谁写的"唯一可信来源，也是后续吊销与追责的基础。

**Independent Test**: CLI签发一把key，用它写一行，检查`write_audit.key_id`、`agent_id`与`business_changes.actor`。

**Acceptance Scenarios**:

1. **Given** 一把有效key，**When** 带`X-API-Key`新建行，**Then** 返回`success`，审计`key_id`为该key的id、`agent_id`为key的label。
2. **Given** 请求同时带有效key与`X-Agent-Id`，**When** 写入，**Then** 以key的label为准。
3. **Given** key写入成功，**When** 读业务变更记录，**Then** `actor`是key的label。
4. **Given** 签发完成后，**When** 查库或列表，**Then** 只有SHA-256摘要与key_id，看不到明文。

### User Story 3 - 无效或已吊销的key被拒 (Priority: P1)

出示了错误的key就必须失败：401、不写业务数据、留一条failed审计。

**Why this priority**: 静默降级等于把认证失败变成匿名写入，比没有认证更危险。

**Independent Test**: 分别用瞎编的key与已吊销的key写入，检查状态码、数据与审计。

**Acceptance Scenarios**:

1. **Given** 不存在的key，**When** 写请求，**Then** 返回`401`、`result=failed`，业务数据未写，审计留failed。
2. **Given** 已吊销的key，**When** 写请求，**Then** 返回`401`，错误信息带该key_id。
3. **Given** 无效key与合法`X-Agent-Id`同时带，**When** 写请求，**Then** 仍`401`，不回退成旧身份。

### User Story 4 - 负责人缺省由调用者身份填充 (Priority: P2)

key调用者新建行时，负责人字段缺省由key的label填充，不用再手填；显式值、旧调用与更新行都不受影响。

**Why this priority**: 让"谁建的谁负责"自动成立，减少无主行。

**Independent Test**: 用key新建不填负责人的行、显式填负责人的行、旧调用新建的行、更新行，四种情况分别核对负责人。

**Acceptance Scenarios**:

1. **Given** key调用者新建行且未填负责人，**When** 写入，**Then** 负责人等于key的label，并在业务变更记录留一条`create`。
2. **Given** 同一请求显式给了负责人，**When** 写入，**Then** 保留显式值。
3. **Given** 旧`X-Agent-Id`调用，或key调用者**更新** 已有行，**When** 写入，**Then** 不自动填充负责人。
4. **Given** 同表存在多个`-owner`字段或没有负责人字段，**When** key调用者新建行，**Then** 不猜、不造字段。

### User Story 5 - key生命周期与审计查询 (Priority: P2)

用最小CLI完成签发、吊销、列出，并能查最近的写审计（含key标识）。

**Why this priority**: 没有签发/吊销入口，key无法投入使用；没有审计查询，"落审计"无法核实。

**Independent Test**: 连续执行`issue`→`list`→用key写入→`revoke`→再写入→`audit`，逐步核对输出。

**Acceptance Scenarios**:

1. **Given** 执行`issue --label <身份>`，**When** 成功，**Then** 打印`key_id`与明文key各一次，`list`里能看到该label。
2. **Given** 已签发的key，**When** 执行`revoke --id`，**Then** 该key立刻401，`list`显示"已吊销"。
3. **Given** 已签发多把key，**When** 执行`list`，**Then** 不出现任何明文key。
4. **Given** 有写入与key操作，**When** 执行`audit`，**Then** 能看到最近写审计的`key_id`、身份、结果，以及`key.issue`/`key.revoke`事件。

### Edge Cases

- key明文只在签发时出现一次；重复`issue`同一label得到两把独立key，吊销互不影响。
- 审计里的`key_id`指向`api_keys.id`；key被吊销后审计行保留，仍可倒查。
- 同秒内多次签发：`key_id`随机生成，冲突时重抽。
- 负责人字段是`relation`类型时（如`tests/test_api.py`的`f2`）不参与填充，只认文本字段。
- 旧库没有`api_keys`表或`write_audit.key_id`列时，服务启动自动补齐；补列保留旧审计行。
- 迁移失败不阻断只读看板（告警到stderr），写侧因缺列会失败，需人工排查。

## Requirements *(mandatory)*

- **FR-001**: 写接口MUST接受`X-API-Key`；有效时按key识别调用者，`agent_id`与业务变更`actor` MUST为key的label。
- **FR-002**: 未带`X-API-Key`时MUST回退`X-Agent-Id`，写入内容与审计身份MUST与改造前一致。
- **FR-003**: 两者都缺时MUST返回`400`，错误信息MUST含`X-Agent-Id`；读接口MUST NOT要求凭据。
- **FR-004**: 无效key MUST返回`401`且`result=failed`，MUST NOT回退`X-Agent-Id`，MUST NOT写业务数据。
- **FR-005**: 401与400的鉴权失败MUST留一条`write_audit`（`result=failed`，`key_id`为空），审计写入MUST NOT因鉴权失败而丢。
- **FR-006**: `write_audit` MUST新增`key_id`；key调用记key的id，旧调用记`NULL`。旧审计行MUST保留。
- **FR-007**: `api_keys` MUST只存SHA-256摘要与`id`/`label`/`note`/`created_at`/`revoked_at`/`revoked_by`，MUST NOT存明文。
- **FR-008**: 新建行时，若表内负责人字段（文本且id以`-owner`结尾，或名称恰为"负责人"）缺省/为空，且调用者为key鉴权，MUST用key的label填充；显式值MUST优先；多候选MUST NOT填。
- **FR-009**: 旧`X-Agent-Id`调用与行更新MUST NOT自动填充负责人。
- **FR-010**: 提供CLI `issue`/`revoke`/`list`/`audit`；`issue` MUST打印明文一次，`list`/`audit` MUST NOT回显明文。
- **FR-011**: `issue`/`revoke` MUST落`write_audit`（action=`key.issue`/`key.revoke`），操作者身份取`--by`（缺省`cli`）。
- **FR-012**: 旧库升级MUST幂等：启动时补表`api_keys`、补列`write_audit.key_id`，重复执行不报错、不改数据。
- **FR-013**: 不新增HTTP路由；写接口路径、请求体与响应体`result`三态（`success`/`failed`/`unknown`）MUST保持不变；鉴权失败是新增的HTTP 401（body仍为`result=failed`），旧调用不会触发。

## Key Entities

- **api_keys**：`id`（`k-xxxxxxxx`）、`key_hash`（SHA-256，唯一）、`label`（调用者身份）、`note`、`created_at`、`revoked_at`、`revoked_by`。
- **write_audit**：每次写请求一条；新增`key_id`，`agent_id`记调用者身份，`result`三态，`error`留失败原因。
- **business_changes**：字段级业务留痕；`actor`与审计身份一致。
- **fields（text）**：负责人字段的识别规则见澄清；类型不变，仍是`text`。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `cd backend && .venv/bin/python -m pytest -q`全绿且用例数不少于`120`（013交付时为`120`，v0.6.2验证时为`133`）；013前基线`108`。
- **SC-002**: 四种情形各有用例：兼容期旧调用（`test_legacy_*`）、key审计（`test_api_key_*`/`test_key_takes_priority_*`）、无效key拒绝（`test_invalid_key_*`/`test_revoked_key_*`）、负责人填充（`test_owner_*`）；另含CLI与旧库迁移用例。
- **SC-003**: 现有skill/脚本调用方式不被打断：只带`X-Agent-Id`的写入成功，且审计`key_id`为空、负责人不被填充。
- **SC-004**: 线上仅更新看板`013-AR`行；其余业务数据、字段定义不动，`api_keys`与`key_id`由发布时启动迁移补齐。

## 非目标

- 不把"必须带key"设为强制（兼容期；收紧另立需求）。
- 不新增HTTP管理路由，不做key权限分级/按项目隔离/有效期。
- 不改字段类型，不做存量负责人字段回填（只影响新建行）。
- 不接SSO/OAuth、不做密码与登录态。
- 不改`skills/`与前端（由后续需求同步调用方式）。
