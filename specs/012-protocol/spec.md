# Feature Specification: Agent↔看板交互协议protocol@1（v0.6.2）

**Feature Branch**: `012-protocol`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 看板`012-AR`行条款："交互协议：在008与011的表设计完备后，定义Agent与看板之间的交互协议——请求与响应形态、错误码、幂等键、并发控制、写入审计口径，供skill与用户系统对接。不含具体业务实现。"

**协议对象**: `specs/011-bug-table/board@2.yaml`（四表：`ver`/`indep`/`dep`/`bug`），前置为008契约与011 bug表已落盘。本文只定义协议行为，不重复字段口径；字段口径以契约文件为准。新增表或字段不改变请求/响应形态，不需要升协议版本。

**基线**: `backend/`当前实现（v0.6.2开发分支，含010计算口径与013用户管理）；线上看板`http://192.168.1.155:8090`只用于只读核对。所有写行为探针在临时库（`TABLEFLOW_DB`指向临时文件）执行，未改线上数据。

## 结论速览

1. 协议可用，但**不是"带`X-Agent-Id`就完事"**：客户端必须按三态判定树分类响应，并把`503 detail`、网络超时一律当`unknown`回读，不能当成功。
2. **幂等键目前没有服务端落点**：`write_audit`没有幂等列、没有去重表、接口不认`Idempotency-Key`头。协议定义幂等键语义，同时给出"今天就能用"的业务键+回读补偿配方；服务端改造列为缺口`G1`。
3. **并发是"单写者+最后写入获胜"**：SQLite WAL单写者、无`busy_timeout`、无行版本/ETag/`If-Match`。锁冲突有两种形态：写事务阶段→`400 failed`（`数据库错误：database is locked`），连接阶段设WAL被锁→`503 {"detail":"数据存储不可用"}`。协议要求客户端串行化、退避重试与读改写自检；服务端改造列为`G3`。
4. **审计只覆盖"进入写处理器的请求"**：`405`/`422`与未匹配到写路由的`404`没有审计；`write_audit`只有本机CLI可查，`business_changes`有HTTP查询。远程审计查询列为`G4`。
5. **`unknown`目前没有产生路径**：`app.py`能把`exc.unknown`映射为`503 {"result":"unknown"}`，但没有任何调用点构造`WriteError(..., unknown=True)`（只有`errors.py:11`的文档字符串提到该参数）。协议把它定义为保留状态，并规定客户端如何从非信封5xx/超时自行判`unknown`（`G2`）。

## 背景与问题证据

| 现状 | 证据 | 后果 |
|---|---|---|
| 三态只在文档里，代码里没有制造`unknown`的路径 | `backend/src/tableflow/app.py:222-223`映射`exc.unknown`；`grep -rn "unknown=True" backend/src`只命中`errors.py:11`文档字符串，无调用点 | 客户端以为"503就是unknown"，而今天唯一的503是`{"detail":"数据存储不可用"}`；把503一律当unknown会误判"连接失败未执行"为"可能已提交" |
| 幂等没有协议 | 无`Idempotency-Key`解析、`write_audit`无该列（`db.py:55-66`）、无去重表；重复建行返回`400 failed`，错误"行 id 已存在"（`write_service.py:816`） | 超时重试靠猜：重试建行会拿到失败，客户端可能误报"未落库" |
| 并发无版本概念 | `db.py:127-133`只设WAL与外键，无`busy_timeout`；`update_row`是字段级合并（`write_service.py:834-891`），无前置条件 | 两个Agent同时改一行的不同字段都成功；改同一字段则后者静默覆盖，无冲突信号 |
| 锁冲突暴露为两种形态 | 临时库探针：连接A持`BEGIN IMMEDIATE`，连接B直连写入抛`OperationalError: database is locked`，经接口映射为`400 failed`（`write_service.py:146-153`）；同一场景走HTTP时，服务端连接阶段设WAL即被锁，返回`503 {"detail":"数据存储不可用"}` | 客户端把可重试的锁冲突当永久失败或当未知，业务动作半途停下 |
| 审计查不到 | `write_audit`无HTTP查询接口，只有`backend/scripts/tf_keys.py audit`（本机库）；`business_changes`有`GET .../changes`（`repository.py:203-233`） | "谁在何时改了什么"在远程无法自证，第三方对接只能靠本机运维 |
| 非信封响应混杂 | 临时库探针：缺身份/重复行→`400 {"result":"failed"}`；无效key→`401 {"result":"failed"}`；非法JSON→`422 {"detail":[...]}`；人侧写路由→`405 {"detail":...}`；存储不可用→`503 {"detail":...}`；读404→`404 {"detail":...}` | 客户端若只读`result`字段，会在422/503上抛异常或误判 |
| 客户端文档把三态简化成"状态码决定" | `skills/tableflow-board/SKILL.md:51`直接写`unknown`（503）；`specs/009-tf-update/spec.md:19/104`同；`skills/tf-update/SKILL.md:43/179`把一切503映射`unknown` | 实际503常是`{"detail":...}`而非result信封，且`400 数据库错误`（锁冲突）没有可重试分类；口径不细化会固化错误重试 |

## Clarifications

### Session 2026-11-19

- Q: 协议版本怎么表达？ → A: 文档记录`protocol@1`，看板`012-AR`的规格目录指向本文；不引入请求头协商（服务端不校验未知头也无意义）；兼容规则是"只增可选字段/新增路径"，改语义必须新路径并升版本。
- Q: 什么情况算`unknown`？ → A: 只回答"请求已离开客户端，但无法从响应判定服务端是否提交"：连接中断、超时、无响应、非JSON的5xx、`503 detail`。`400/401/404/405/422`一律`failed`（未执行或被拒）。
- Q: `503 detail`为什么不算`failed`？ → A: 写依赖在处理器前后都可能失败（`get_write_conn`在处理器前，处理器内`sqlite3.Error`也会落到同一个`detail`信封），客户端无法区分"没执行"与"提交后审计失败"，已知信息不足，保守判`unknown`并回读。
- Q: 幂等键长什么样、谁生成？ → A: 客户端生成，请求头`Idempotency-Key`，1–64字符，建议UUIDv7或ULID；一个"意图"（一次逻辑写）一个键，重试复用，不得跨意图复用。
- Q: 幂等窗口多长？ → A: 24小时；过期同键视为新请求。服务端未实现，属`G1`。
- Q: 幂等冲突返回什么？ → A: 同键不同请求指纹（method+path+body哈希）返回`409 {"result":"failed","error":"幂等键冲突"}`；服务端未实现（`G1`）。
- Q: 并发冲突怎么暴露？ → A: 现状不暴露（最后写入获胜）。客户端必须串行化并做读改写自检；服务端改造建议`If-Match`/`expected`+`409`+`busy_timeout`（`G3`）。
- Q: 审计由谁写、客户端能不能补？ → A: 只由服务端在写事务内写；客户端不得提交审计字段，也没有入口。身份由服务端解析，`agent_id`/`key_id`不可由请求体覆盖。
- Q: 审计能查吗？ → A: `business_changes`可经HTTP查；`write_audit`只有本机CLI，远程查询与过滤是缺口（`G4`）。
- Q: 012与013怎么分工？ → A: 012定"审计记哪些字段、何时记、怎么查"与身份头的协议语义；013定"调用者如何被识别"的具体实现（key格式、SHA-256存储、签发/吊销CLI、label语义、负责人自动填充）。两者字段名一致：`agent_id`/`key_id`/`origin`。
- Q: 错误文本能做机器判定吗？ → A: 不能。机器判定只用HTTP状态与`result`；错误文本只用于人读与日志。服务端无`error_code`，属`G5`。
- Q: 读接口要不要鉴权？ → A: 现状无鉴权（人只读）。协议假定可信网络；暴露到不可信网络必须由网关前置鉴权（`G8`）。

## 使用者与验收场景

### User Story 1 - 第三方按文档实现客户端（Priority: P1）

一个没有本仓代码的客户端开发者，只读本文与`board@2.yaml`，能实现读写、三态判定、幂等补偿、并发串行与审计核对。

**Independent Test**: 按"客户端实现清单"逐步实现，用"示例会话"一节的curl在临时库跑通读-写-回读-变更记录四步。

**Acceptance Scenarios**:

1. **Given** 只读本文，**When** 实现响应分类，**Then** 对400/401/422/503detail/超时五类样例给出正确终态（failed/unknown）。
2. **Given** 只读本文，**When** 实现建行幂等，**Then** 重复提交同一行id时以回读结果定案，不重复写、不误报失败。
3. **Given** 只读本文，**When** 实现读改写，**Then** 在提交前校验关键字段期望值，冲突时放弃并重读。

### User Story 2 - 三态判定一致（Priority: P1）

所有Skill与用户系统对同一响应得出同一终态；`unknown`不得当成功，`failed`不得重试（可重试类除外）。

**Independent Test**: 对六种响应样例（200 success、400 failed、401、422、503 detail、连接超时）逐一分类，结果与判定树一致。

**Acceptance Scenarios**:

1. **Given** 写请求超时，**When** 客户端处理，**Then** 终态`unknown`并GET回读；不得直接报成功或失败。
2. **Given** 同一行重复PATCH同值两次，**When** 检查响应与变更记录，**Then** 两次都`200 success`，`business_changes`不新增。
3. **Given** 删除已不存在的行，**When** 处理`400`（错误"行不存在"），**Then** 按"删除意图以最终不存在为成功"判定，不重试覆盖。

### User Story 3 - 审计可核对（Priority: P1）

每次成功写入恰好一条成功审计，字段级变化恰好对应`business_changes`；失败写入无业务数据但有失败审计。

**Independent Test**: 临时库上执行一次建行+一次非法写，读`write_audit`与`business_changes`计数与内容。

**Acceptance Scenarios**:

1. **Given** 成功建行，**When** 查审计，**Then** `write_audit`新增1条`success`且`business_changes`按非空字段数新增。
2. **Given** 非法字段键写入，**When** 查审计，**Then** 无业务数据、审计新增1条`failed`且`error`非空。
3. **Given** 以失败鉴权写入，**When** 查审计，**Then** 审计`agent_id`为请求携带值或`-`、无业务数据。

### User Story 4 - 并发不静默覆盖（Priority: P2）

同一版本的多步操作由单写者串行执行；两个客户端同时改一行时，至少能通过读回发现不一致，不出现"两边都报成功、数据只剩一份"的事后惊讶。

**Independent Test**: 两个连接同时PATCH同一行的同一字段，读回值与`business_changes`，确认后写覆盖前写且两条变更都在；客户端自检能发现期望值不符。

**Acceptance Scenarios**:

1. **Given** 两个在途写同一行同一字段，**When** 都返回成功，**Then** 后写覆盖前写，`business_changes`有两条`update`。
2. **Given** 连接A持有写事务，**When** 连接B写入，**Then** B在无等待下收到锁错误（现状），协议要求客户端退避重试并回读。
3. **Given** 客户端读改写，**When** 提交前发现关键字段已变，**Then** 放弃提交并重新决策。

### Edge Cases

- `503 detail`出现在写请求上：无法区分"未执行"与"提交后审计失败"，一律按`unknown`回读，不按`failed`直接放弃。
- `400`且错误以`数据库错误：`开头：事务已回滚，按可重试失败退避重试，重试后仍需回读。
- HTTP 200但响应体不是JSON（代理/网关改写）：按`unknown`处理，回读定案。
- 重复建资源但内容与首次不一致：按冲突处理，`failed(conflict)`，不覆盖已有数据。
- 二次删除同一行：按"删除意图以最终不存在为成功"定案，不把`400`直接报成"没删掉"。
- `422`请求无审计：不能用"审计里没有"推断"服务端没收到"，只能按HTTP状态判`failed`并修请求。
- 两个客户端改同一行的不同字段：字段级合并会让两边都成功，读回能发现两侧值都在；改同一字段则后写覆盖，读回只能看到后写值。
- `recompute`返回`changed=0`：成功但无变化，不代表配置或数据有问题。
- 关联目标行先被删除再写入引用：`400`（错误"关联目标行不存在"），按P-036顺序重做，不先建目标行不重试。

## 协议正文

**图例**：现状列`满足`=现有接口无需改动即可按本协议工作；`部分`=接口可用但语义需客户端补偿或存在风险；`缺口`=需服务端改造，编号见"落地差距清单"。

### 1. 版本与兼容

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-001 | 协议标识为`protocol@1`，与`board@2`配套；标识写入文档，不通过请求头协商 | 部分（无协商，但文档可追溯） | 本文与`board@2.yaml`并存且互相引用；看板`012-AR`的规格目录为`specs/012-protocol/`，本文即该目录交付物 |
| P-002 | 兼容规则：只允许新增可选字段/新增路径；删除字段、改变已有字段语义必须新增路径并升协议版本 | 满足 | 对照`/api/agent`路径清单与响应字段：只增不减 |
| P-003 | 写操作必须走`/api/agent/*`；`/api/*`人侧路径只有GET | 满足 | `curl -i -X POST /api/projects`应返回`405 {"detail":"Method Not Allowed"}` |

### 2. 传输约定

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-004 | 请求与响应均为UTF-8 JSON；写请求必须带`Content-Type: application/json` | 满足 | 任意写请求省略Content-Type时服务端返回`422`（FastAPI默认），带则正常 |
| P-005 | 服务端时间统一ISO8601、`+08:00`、秒级；客户端不得用本地时钟判断先后 | 满足（`write_service.py:47-49`） | 读任意`business_changes.occurred_at`，格式为`2026-11-19T12:22:16+08:00` |
| P-006 | 所有响应带`Cache-Control: no-store`，读侧不缓存 | 满足（`app.py:55-59`） | `curl -i`任意GET，响应头含`cache-control: no-store` |
| P-007 | 读表一次返回全部字段与行，无分页；变更记录有`limit`（1–200，默认50，按id倒序） | 满足（`repository.py:203-233`） | `GET /api/tables/tf-bug/table`一次返回12字段；`GET .../changes?limit=2`最多2条且id递减 |
| P-008 | 读接口无鉴权，协议假定可信网络；暴露到不可信网络必须由网关前置鉴权 | 缺口（G8） | 不带任何头`curl /api/projects`应200；公网部署须有网关鉴权配置 |

### 3. 身份与来源

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-009 | 身份头优先级：有效`X-API-Key`→`agent_id`=key的label、`key_id`=key id；无key→`agent_id`=`X-Agent-Id`、`key_id`为空；两者都无→`400 {"result":"failed"}`且错误含`X-Agent-Id` | 满足（`auth.py`，`app.py:98-103`） | 分别用有效key、仅`X-Agent-Id`、两者都不带写一次，核对响应与审计三条记录 |
| P-010 | 出示无效或已吊销的key必须`401 failed`，不得回退到`X-Agent-Id` | 满足 | 带`X-API-Key: tfk_bogus`+合法`X-Agent-Id`写一行：`401`、数据未写、审计`failed` |
| P-011 | `X-Origin`可选，取值`agent`/`human-request`/`seed`，缺省`agent`；非法值`400 failed` | 满足 | 带`X-Origin: robot`写一次：`400`且错误列出合法枚举 |
| P-012 | 审计身份只由服务端解析，客户端不得在请求体中提交`agent_id`/`key_id`/审计行 | 满足（无此入参） | 请求体塞`agent_id`不改变审计；审计该列与头部一致 |
| P-013 | 012与013分工：012定审计字段集合/时机/查询契约与身份头语义；013定key格式、摘要存储、签发吊销、label语义、负责人自动填充 | 满足（013已并入HEAD） | 本文与`specs/013-user-management/spec.md`字段名一致（`agent_id`/`key_id`/`origin`），无同名字段两种定义 |

### 4. 请求形态

**请求体形态（写接口；路径里的id优先，body.id可省但必须一致）**

| 方法/路径 | 请求体 | 说明 |
|---|---|---|
| `POST /api/agent/projects` | `{id?, name}` | 建项目；`id`省略则服务端生成 |
| `DELETE /api/agent/projects/{project_id}` | 无 | 级联删表/字段/行 |
| `POST /api/agent/projects/{project_id}/tables` | `{id?, name, order?}` | 建表；`order`省略则追加 |
| `PATCH /api/agent/tables/{table_id}` | `{name?, order?}` | 改名/改序 |
| `DELETE /api/agent/tables/{table_id}` | 无 | 被relation引用时拒绝 |
| `POST /api/agent/tables/{table_id}/fields` | `{id?, name, type, options?, order?, visible?}` | 建字段；computed建后自动重算 |
| `PATCH /api/agent/fields/{field_id}` | `{name?, type?, options?, order?, visible?}` | 改字段；改后重算依赖方 |
| `DELETE /api/agent/fields/{field_id}` | 无 | 删字段 |
| `POST /api/agent/tables/{table_id}/recompute` | 无 | 手动重算本表及依赖方 |
| `POST /api/agent/tables/{table_id}/rows/{row_id}` | `{id?, values}` | 建行；`values`键为字段id |
| `PATCH /api/agent/tables/{table_id}/rows/{row_id}` | `{values?, overrides?}` | 合并更新；覆盖计算字段 |
| `DELETE /api/agent/tables/{table_id}/rows/{row_id}` | 无 | 硬删除 |

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-014 | 行写路径为`/api/agent/tables/{table_id}/rows/{row_id}`；`row_id`是业务编号，匹配`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`，创建后不可改；`body.id`若给必须与路径一致 | 满足（`write_service.py:697-701,834-840`） | 提交含`id`不同的body→`400`；PATCH带`id`→`400`，错误"行 id 不可变" |
| P-015 | `values`的键必须是该表字段id；未知键`400 failed`；`type=computed`只读；relation值为目标行id字符串数组；`null`/`""`/`[]`视为空 | 满足（`write_service.py:703-722`） | 写`{"values":{"nope":1}}`→`400 未知字段键`；写computed字段→`400 计算字段不能直接写入` |
| P-016 | PATCH为合并语义：给出的字段覆盖、未给出的保留；约束在合并后整行校验；值未变化的字段不产生`business_changes` | 满足（`write_service.py:834-891`） | 同一行PATCH同值两次：两次`200`，`changes`条数不增 |
| P-017 | 覆盖计算字段用`overrides: {field_id: {value, reason}}`；`reason`必填；`gate: true`的字段只能`value: null`清除，设值`400` | 满足（010，`calculation.py:818-936`） | 覆盖非计算字段→`400`；缺reason→`400`；gate字段设值→`400 闸门字段…禁止人工覆盖` |
| P-018 | 删除为硬删除；表被relation引用时`400`并列出引用字段；删行不级联清理引用方，悬空由计算侧判未就绪 | 满足（`write_service.py:465-480,893-926`） | 删除被relation引用的表→`400`并列出引用字段；删行后读引用方行仍在且计算值按010规则变化 |
| P-019 | 不提供批量写；一次请求只写一个资源；请求体多余顶层键被忽略；跨资源一致性由客户端编排（见P-036） | 满足 | 不存在批量路径；body带多余键不影响写入结果（实测行内容只含`values`内字段） |

### 5. 响应形态与三态判定

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-020 | 成功：HTTP 200 + `{"result":"success"}`；写操作返回`{"result":"success","id":"<id>"}`；`recompute`返回`{"result":"success","rows":n,"fields":n,"changed":n}` | 满足（`app.py:225-227`） | 建行返回`{"result":"success","id":"..."}`；`POST .../recompute`返回三个计数 |
| P-021 | 失败：HTTP 400/401 + `{"result":"failed","error":"<中文说明>"}` | 满足 | 非法写入返回400/401且`result=failed` |
| P-022 | 未知（保留）：HTTP 503 + `{"result":"unknown","error":"..."}`；当前无产生路径（G2） | 缺口（G2） | 无调用点设置`unknown=True`（`errors.py:11`仅文档字符串）；`curl`无法构造该响应，只能按P-024从超时判unknown |
| P-023 | 非信封响应：`404/405/422/503`的`{"detail":...}`不属于三态信封；客户端按状态分类：4xx→`failed`，`503 detail`→`unknown`，其他5xx或非JSON→`unknown` | 满足（探针实测四类） | 对不存在的表GET→`404 detail`；非法JSON写→`422 detail`；停库或锁库后写→`503 detail` |
| P-024 | 三态判定按序：①200且`result=success`→success；②400/401/404/405/422→failed；③503且`result=unknown`→unknown；④503且`detail`→unknown；⑤其他5xx/超时/连接错误/非JSON→unknown；⑥其余→failed（未知响应形态保守判失败，不重试） | 部分（②③④⑤可判，⑥靠客户端） | 用六个样例（200/400/401/422/503detail/超时）逐一分类，与本节一致 |
| P-025 | 重试矩阵：`401`重试前先修凭据；`400`不重试（`error`以`数据库错误：`开头时可重试）；`404/405/422`修正请求后再发；`503`与网络错误按unknown先回读，回读无法定案才用同一幂等键重试一次 | 部分（依赖客户端纪律） | 锁冲突样例：`400 {"result":"failed","error":"数据库错误：database is locked"}`或`503 {"detail":"数据存储不可用"}`；按矩阵应退避重试 |
| P-026 | 错误文本只供人读；机器判定只用HTTP状态+`result`；服务端未提供`error_code`（G5） | 缺口（G5） | 同一语义的错误文本可能随版本改；客户端代码中不得出现`if "已存在" in error`这类判定 |
| P-027 | 响应不带请求标识；客户端必须把`Idempotency-Key`、时间、路径记入本地日志，作为对账线索（G6） | 缺口（G6） | 响应头无`X-Request-Id`；审计表无请求id列 |

### 6. 错误码表

| HTTP | `result` | 触发（示例） | 客户端处置 |
|---|---|---|---|
| 200 | `success` | 写入成功；recompute完成 | 按客户端清单第8步做回读校验，通过即终态success |
| 400 | `failed` | 缺身份；`X-Origin`非法；未知字段键；行id非法/不可变；行/表/项目/字段不存在；id已存在；type/options非法；relation目标不存在或跨项目；计算字段直写；覆盖非计算字段或缺reason；`allow_override=false`；gate字段设值；`body.id`不一致 | 不重试，修请求或按幂等配方回读对账 |
| 400 | `failed`（可重试类） | `error`以`数据库错误：`开头（含`database is locked`） | 指数退避重试≤3次，每次后回读 |
| 401 | `failed` | 无效key、已吊销key | 不重试，换key或走013签发流程 |
| 404 | 无（`detail`） | 读接口：项目/表/行不存在 | 按failed处理，核对id |
| 405 | 无（`detail`） | 对人侧路径发写请求 | 按failed处理，改走`/api/agent` |
| 422 | 无（`detail`） | JSON语法错误、body类型不符（FastAPI默认校验） | 按failed处理，修请求体；此类请求无审计 |
| 503 | 无（`detail`） | 存储不可用（读连接或写依赖失败）；锁冲突发生在连接阶段（设WAL被锁）也落此形态 | 按unknown处理，先回读再决定是否重试 |
| 503 | `unknown` | 保留：提交结果无法判定（当前无产生路径） | 按unknown处理，回读定案 |
| 5xx其他/超时/非JSON | 无 | 网关、代理、进程崩溃、网络中断 | 按unknown处理，回读定案 |

### 7. 幂等

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-028 | 客户端为每个"意图"生成`Idempotency-Key`（1–64字符，建议UUIDv7/ULID）；同一意图的所有重试复用同一键；不得跨意图复用 | 缺口（G1） | 抓包检查重试请求头一致；同一键不出现在两个不同业务动作的日志里 |
| P-029 | 服务端语义（目标）：24小时内同键同请求指纹（method+path+body哈希）返回首次响应（含`id`），不重复写业务数据与`business_changes`；同键异指纹返回`409 failed` | 缺口（G1） | 未实现前无法判定；实现后以"同键重放两次，第二次响应与首次逐字节一致且`changes`不增"判定 |
| P-030 | 服务端缺口清单：不解析该头、`write_audit`无幂等列、无去重表、无409语义 | 缺口（G1） | `grep -rn "Idempotency" backend/src`无命中；审计表无对应列 |
| P-031 | 过渡配方（建资源）：行id/表id/字段id即业务键；以同一合法请求体重放，收到`400`（错误"…已存在"）→GET回读，内容与意图一致记`success(reconciled)`，不一致记`failed(conflict)`且不覆盖 | 部分（可用） | 重复建同一行：第二次400，回读一致→客户端终态success且`changes`仅首次那批 |
| P-032 | 过渡配方（改/删/重算）：PATCH同值天然收敛（不新增`business_changes`）；覆盖类会每次新增`override`记录，只重试一次并回读；删除意图以"行最终不存在"为成功；`recompute`可重复调用 | 部分（可用） | PATCH同值两次`changes`不增；DELETE两次：第二次`400`（错误"行不存在"），回读不存在→success |
| P-033 | 审计需记录幂等键以便对账（目标：`write_audit.idempotency_key`） | 缺口（G1） | 实现后按`Idempotency-Key`能在审计中倒查一次意图的多条请求 |
| P-034 | 幂等键只覆盖逻辑写，不改变资源语义：同一键不得同时用于建行与改行 | 缺口（G1） | 同一键两种路径的请求应被409拒绝（目标） |

### 8. 并发控制

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-035 | 客户端串行化：同一行/同一表/同一字段同一时刻只有一个在途写；版本级动作（挂关联、改发布条件、批量登记）由单一写者执行 | 部分（靠纪律） | 客户端日志中同一资源无重叠在途请求；压测两客户端并发时业务结果可解释 |
| P-036 | 跨资源写顺序：先建被引用行（`ver`→`indep`/`dep`/`bug`），再写引用该行的relation；每步回读成功后再进行下一步；失败即停并报告已完成步骤 | 满足（relation约束要求目标行存在） | 先写引用后写目标→`400`（错误"关联目标行不存在"）；按顺序则全部`200` |
| P-037 | 读改写必须自检：读到的关键字段（状态/验收状态/回归状态/计数/关联数组）与决策时不一致，放弃提交并重新决策 | 部分（无服务端前置条件） | 模拟两人先后改同一行：后提交者若未自检则覆盖；自检者会中止 |
| P-038 | 服务端并发现状：WAL单写者、无`busy_timeout`、无行版本/ETag/`If-Match`、无`409`；后写覆盖前写 | 缺口（G3） | 双连接探针：A持`BEGIN IMMEDIATE`时B直连写抛`database is locked`、走接口写返回`503 detail`；同字段双写后读回为后写值 |
| P-039 | 锁冲突处理：①`400 failed`且`error`以`数据库错误：`开头，或②`503 detail`→都按可重试处理：指数退避（100ms起，≤3次）+每次回读；仍失败则报`failed(retryable)`并把回读结果一并报告；不得因锁冲突判`success` | 部分（可补偿） | 构造锁冲突（A持写事务）后按本规则重试：接口实测返回`503 detail`；解除锁后重试成功，回读一致 |
| P-040 | 禁止多客户端并发发布流程：`发布状态`、`验收状态`、版本关联的写只能由单一写者执行；其他人通过读接口观察 | 部分（靠纪律，G3） | 发布窗口内审计`action`无来自两个`agent_id`的交叉写 |

### 9. 写入审计口径

**P-041 `write_audit`字段（服务端每个写请求一条）**

| 字段 | 类型 | 含义 | 现状 |
|---|---|---|---|
| `id` | 自增整数 | 审计序号 | 满足 |
| `agent_id` | 文本 | 调用者身份：key的label或`X-Agent-Id`；鉴权失败时为请求携带值或`-` | 满足 |
| `key_id` | 文本/null | 发起请求的key标识；旧`X-Agent-Id`调用为null | 满足（013） |
| `origin` | 文本 | `agent`/`human-request`/`seed`，非法值记`agent` | 满足 |
| `action` | 文本 | 动作枚举（见P-042） | 满足 |
| `target` | 文本 | 目标：项目id/表id/字段id/`表id/行id`/`-` | 满足 |
| `payload` | 文本/null | 请求体JSON，截断至4000字符 | 满足（`write_service.py:73`） |
| `result` | 文本 | `success`/`failed`（`unknown`保留） | 满足 |
| `error` | 文本/null | 失败原因（中文，人读） | 满足 |
| `created_at` | 文本 | ISO8601`+08:00`秒级 | 满足 |

**判定方式**：`SELECT * FROM write_audit ORDER BY id DESC LIMIT 1`逐列对照；列集合与`db.py:55-66`一致，`payload`长度≤4000。

**P-042 `action`与`target`枚举**

| `action` | `target` | 触发 |
|---|---|---|
| `project.create` | `-` | 建项目 |
| `project.delete` | 项目id | 删项目 |
| `table.create` | 项目id | 建表 |
| `table.update` | 表id | 改表名/顺序 |
| `table.delete` | 表id | 删表 |
| `table.recompute` | 表id | 手动重算 |
| `field.create` | 表id | 建字段 |
| `field.update` | 字段id | 改字段 |
| `field.delete` | 字段id | 删字段 |
| `row.create` | `表id/行id` | 建行 |
| `row.update` | `表id/行id` | 改行/覆盖 |
| `row.delete` | `表id/行id` | 删行 |
| `key.issue` | `key_id` | 签发key（013 CLI） |
| `key.revoke` | `key_id` | 吊销key（013 CLI） |

**判定方式**：对每类写操作各执行一次，读审计`action`/`target`与上表一致；出现表外`action`视为协议外新增，需更新本文。

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| P-043 | 记的时机与原子性：成功审计与业务数据同事务提交；失败先回滚再单独提交失败审计；鉴权失败也留一条`failed`且`key_id`为空；未进入写处理器的请求（405/422/路由404）无审计 | 满足（`write_service.py:105-162,81-103`） | 成功写：数据与审计同时存在或同时不存在（人为断库验证）；422：无审计新增 |
| P-044 | `payload`不得包含key明文或任何凭据；客户端不得把密钥写进请求体 | 满足（key只在头） | `grep`审计payload无`tfk_` |
| P-045 | `business_changes`字段与触发：`occurred_at`/`actor`/`origin`/`table_id`/`row_id`/`field_id`/`field_name`/`old_value`/`new_value`/`change_kind`/`reason`；`change_kind∈create/update/delete/recompute/override`；仅真实变化记录（create只记非空值、update只记变化、delete记非空值、recompute记录计算值变化、override记覆盖）；与写审计同事务；一次PATCH可产生多条 | 满足（`write_service.py:628-662`，`calculation.py:712,728,843-855,920-930`） | 建行3个非空字段→3条`create`（计算字段首次取值另记`recompute`）；改1个字段→1条`update`；重算无变化→0条 |
| P-046 | 查询契约：`business_changes`经`GET /api/tables/{table_id}/rows/{row_id}/changes?limit=1..200`（默认50，按id倒序，行不存在404）；`write_audit`无HTTP接口，仅本机`python scripts/tf_keys.py audit --limit N` | 部分（G4：无远程查询、无过滤、无分页游标） | `GET .../changes?limit=2`返回≤2条且id递减；`curl /api/agent/audit`→404（未提供） |
| P-047 | 审计不可变：只增不改不删，无删除接口；保留期未定义（G9，建议永久保留并按年归档） | 部分（G9） | 无`DELETE /audit`路由；DB中无更新触发器/清理任务 |
| P-048 | 与013的字段约定：`agent_id`=key的label（旧调用为`X-Agent-Id`值）、`key_id`=key id（旧调用null）、`origin`由`X-Origin`决定；无效key的失败审计`agent_id`=请求携带的`X-Agent-Id`或`-`、`key_id`为空 | 满足（013已实现） | 有效key写一次：审计`agent_id`=label、`key_id`非空；无效key：`401`、`key_id`空 |

## 客户端实现清单（第三方按序实现）

1. 配置基址与凭据：`base`、`X-API-Key`（有）或`X-Agent-Id`（兼容）；每个写请求带`X-Origin`。
2. 实现`request(method,path,body)`：JSON编码、超时（建议10s）、记录`Idempotency-Key`与时间。
3. 实现三态判定`classify(response)`：按P-024顺序，返回`success|failed|unknown`及`retryable`标记。
4. 实现幂等封装`write(intent)`：生成键、调用、按P-031/P-032回读对账。
5. 实现串行队列：同一资源键（`table/row`）串行；版本级动作单写者。
6. 实现读改写自检：GET行→校验关键字段→PATCH，冲突则重读。
7. 实现锁冲突重试：P-039退避与上限。
8. 实现回读校验：写入后GET一次，比对意图字段；不一致即`failed`并列差异。
9. 实现审计核对：写后GET `changes`（需要业务留痕时）与本地日志对账；远程`write_audit`不可查，需记录"由运维CLI核对"。
10. 失败报告模板：`action`/`target`/三态/HTTP/`error`/已完成步骤/回读结论/幂等键。
11. 不得解析错误文本做判定；不得把`unknown`当成功；不得并发写同一版本。
12. 兼容两种服务端：旧实例忽略`X-API-Key`（按`X-Agent-Id`识别），新实例key优先；客户端同时携带两个头可平滑过渡。

## 示例会话（已有`tf-bug`表的环境；写步骤只在临时库执行）

```bash
H=(-H 'X-Agent-Id: agent-demo' -H 'X-Origin: human-request' -H 'Content-Type: application/json')

# 1 读契约对象
curl -s $TF_BASE/api/tables/tf-bug/table | head -c 200

# 2 建行（行id即幂等业务键）
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/tf-bug/rows/BUG-01 \
  -d '{"values":{"tf-b-id":"BUG-01","tf-b-title":"示例","tf-b-status":"open","tf-b-severity":"minor","tf-b-source":"test","tf-b-found":["v0.6.1"]}}'
# → {"result":"success","id":"BUG-01"}

# 3 重试建同一行（幂等配方：同一请求体重放 + 回读对账）
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/tf-bug/rows/BUG-01 \
  -d '{"values":{"tf-b-id":"BUG-01","tf-b-title":"示例","tf-b-status":"open","tf-b-severity":"minor","tf-b-source":"test","tf-b-found":["v0.6.1"]}}'
# → 400 {"result":"failed","error":"行 id 已存在：BUG-01"}
curl -s $TF_BASE/api/tables/tf-bug/rows/BUG-01   # 回读一致 → success(reconciled)

# 4 改状态（PATCH合并；同值重放不新增业务变更）
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/tf-bug/rows/BUG-01 \
  -d '{"values":{"tf-b-status":"fixing"}}'

# 5 查业务变更（写审计无HTTP，需运维CLI）
curl -s "$TF_BASE/api/tables/tf-bug/rows/BUG-01/changes?limit=5"
```

**注**：示例中的`v0.6.1`须是已存在的版本行；不存在时返回`400`（错误"关联目标行不存在"），这是P-036顺序约束的体现。

## 落地差距清单

| 编号 | 缺口 | 现状证据 | 影响 | 建议归属 |
|---|---|---|---|---|
| G1 | 幂等键无落点（无头解析/无列/无去重/无409） | `grep Idempotency backend/src`无命中；`db.py:55-66`无该列 | 重试只能靠客户端业务键回读；写审计无法按意图聚合 | 后端（新需求） |
| G2 | `unknown`无产生路径 | `app.py:222-223`有映射；无调用点设置`unknown=True`（`errors.py:11`仅文档字符串） | 客户端只能从超时/503detail推断；服务端无法主动表达"提交未知" | 后端（010/新需求） |
| G3 | 并发无前置条件、无`busy_timeout`、无409 | `db.py:127-133`；`write_service.py:834-891` | 锁冲突=503detail或400业务失败；同字段静默覆盖 | 后端（新需求） |
| G4 | `write_audit`无HTTP查询 | 仅`scripts/tf_keys.py audit` | 远程无法自证"谁写的"；第三方对接需运维配合 | 后端（新需求，可复用013口径） |
| G5 | 错误码非机器可读 | 只有中文`error`文本 | 客户端不敢按文本判定，错误处理粗放 | 后端（可与G1同批） |
| G6 | 响应无请求标识 | 无`X-Request-Id`；审计无请求id列 | 三态定案后难以与审计行一一对应 | 后端（可与G1同批） |
| G7 | 协议版本无协商 | 无版本头 | 未来不兼容变更只能靠新路径；客户端无法声明期望版本 | 暂不处理（P-002已够用） |
| G8 | 读接口无鉴权 | 所有人可读 | 暴露到不可信网络即泄露业务数据 | 部署（网关） |
| G9 | 审计保留期未定义 | 无清理任务/无保留配置 | 长期磁盘增长或误删风险 | 运维（后续） |
| G10 | 422/503非信封 | FastAPI默认`detail` | 客户端需额外分支；清单已覆盖 | 不阻塞（P-023/P-024已规定） |

## 验收判定

- **SC-001**: 第三方仅凭本文+`board@2.yaml`可完成"读表→建行→回读→改状态→查变更"全流程，无需读后端源码。
- **SC-002**: 协议正文每条规则均有编号（P-001…P-048）且"判定方式"列可执行；抽检任取10条，按列操作可得到所述结果。
- **SC-003**: 三态判定树用六个样例（`200 success`、`400 failed`、`401`、`422`、`503 detail`、连接超时）验证，分类全部正确。
- **SC-004**: 幂等现状以P-031/P-032配方验证：重复建行不重复写、同值PATCH不新增`business_changes`、二次DELETE按"最终不存在"定案；P-029服务端语义在G1落地前判定为"缺口未实现"。
- **SC-005**: 审计完整性：成功写1行→`write_audit`+1且`business_changes`按非空字段数+`n`；非法写→业务数据不变且审计+1；422→审计不增。
- **SC-006**: 与013交叉核对：`agent_id`/`key_id`/`origin`三字段在本文与`specs/013-user-management/spec.md`中语义一致，无第二种定义。

## 非目标

- key的签发、吊销、存储与CLI（013）。
- 字段口径、状态定义、完成判据（`board@2.yaml`）。
- 计算语义与空集/悬空规则（010）。
- MS同步与交互产品（014）。
- 服务端实现改造：本文只定义协议；G1–G6、G9需另立需求。
- 存量Skill与脚本改造（按本文"客户端实现清单"逐步对齐）。
- 审计归档/保留期策略（G9）。
- 读接口鉴权的实现（G8，部署层解决）。

## Key Entities

- **意图（Intent）**：一次逻辑上只做一次的业务写；由`Idempotency-Key`标识，重试复用。
- **三态（Outcome）**：`success`/`failed`/`unknown`；由HTTP状态+`result`判定，不由错误文本判定。
- **写审计（write_audit）**：服务端生成的请求级记录，10字段，只增不改；覆盖进入写处理器的每个请求。
- **业务变更（business_changes）**：字段级旧值/新值记录，5种`change_kind`，与写审计同事务。
- **可重试失败（retryable failed）**：`400`且`error`以`数据库错误：`开头的失败，或`503 detail`；退避重试后仍需回读。
- **单写者（single writer）**：同一资源/版本在任一时刻只允许一个客户端持有写权。
