# v0.6.2验证报告（t12，2026-11-19）

验证人：qa。窗口：12:53–12:57。范围：012交互协议、013用户管理（兼容期）、前两版修复回归。
证据目录：`.tmp-shots/qa-v062/`（脚本与日志可逐条重跑；不修改源码、不写线上业务行、不执行git写操作）。

## 一、结论

| 范围 | 结论 | 一句话依据 |
|---|---|---|
| 012交互协议 | **通过（可据以实现）** | 按文档“客户端实现清单”实跑读-写-幂等补偿-变更-删除全流程成功；48条规则/10缺口/12场景/6SC结构齐全；抽检13条规则行为与文档一致 |
| 013用户管理（兼容期） | **通过** | 18个验收场景逐条复现通过：旧`X-Agent-Id`调用零变化、key识别与审计、401不回退、负责人自动填充边界、CLI生命周期、旧库迁移幂等 |
| 前两版修复回归 | **通过** | pytest 133 passed；`calculation.py`已回到v0.6.0基线`e10b97aa…`；`check_contracts.py`两契约OK且`--pre-write`拒绝重复键、目标未变；V060-04 400→200 复现 |
| 缺陷登记 | 3条（均为低，文档/可复现性） | 见第六节 |

**版本判断：v0.6.2可发布。** 3条低缺陷不阻塞发布，建议随文档修订一并处理。

## 二、验证基线

| 项 | 值 |
|---|---|
| `backend/src/tableflow/app.py` | `024c94cb1fb1c5b7e30fc0a69d65ae5b2139d61af5f29067ca3aec1780c94221` |
| `backend/src/tableflow/auth.py` | `3ac783fab042e58300641c35fc968ad62840e8197ee0ebd3541802863192f450` |
| `backend/src/tableflow/calculation.py` | `e10b97aa94fd46ccd48b539244c464951fc37d57c01e4530da98e751d535f719`（V061-04已回基线） |
| `backend/src/tableflow/write_service.py` | `39b0b1029ae85d2a4b002fa8b99529107fd2e7ed18d3fdda00f087fff498bc7e` |
| `backend/src/tableflow/db.py` | `f0a82cf331acc4d76e9febc61c34ff0670b47159971593c9ea65bc8af3f3b625` |
| `backend/src/tableflow/contracts.py` | `17ef16dc3fe48134b1b30ac6866f847f0215835ce2aec9486dffacb306113aa7` |
| `specs/012-protocol/spec.md` | `e6daee4e22a5ae2a850aeb4dda6ac8b723fa88f11d9d047d9c4c61a041fac99c` |
| `specs/013-user-management/spec.md` | `d9a3e050160eaa2c4a0109f1819b0c3e2a8a3fc3b810cb707ac6696b04502a6c` |
| 后端回归 | `133 passed, 1 warning in 5.07s`（`pytest.log`） |

## 三、012交互协议核对

### 3.1 结构与规模

| 项 | 文档声明 | 核对结果 |
|---|---|---|
| 规则数 | 48条（P-001…P-048） | 48个唯一编号（P-001…P-040在规则表，P-041…P-048在审计章节），无缺号 |
| 落地缺口 | 10项（G1…G10） | 10项，且G1（幂等）、G2（unknown路径）、G3（并发版本）、G4（审计查询）与实测一致 |
| 用户故事/场景 | 4 US / 12 AS | 4 US / 12 AS（US1 3、US2 3、US3 3、US4 3） |
| 成功标准 | 6条 | SC-001…SC-006齐全 |

### 3.2 “可据以实现”实跑（按文档客户端实现清单）

在临时库按清单实现一个客户端，一次跑通：读表 → 建行 → 重试同键 → 回读对账 → 同值PATCH两次 → 查变更 → 删除 → 再删 → 回读404。

| 步 | 结果 |
|---|---|
| 读表 | `GET /api/tables/t-ver/table` 返回2字段1行 |
| 建行 | `200 {"result":"success"}` |
| 重试同键（`Idempotency-Key`） | `400 行 id 已存在：C1`（表头被忽略→证实G1“无幂等落点”），按配方回读对账 |
| 回读 | `200`，字段值与预期一致 |
| 同值PATCH两次 | 两次`200`，`business_changes`不新增（2→2） |
| 变更查询 | `limit=2`按id倒序`[2,1]` |
| 删除→再删→回读 | `200`→`400 行不存在`→`404`，符合“删除以最终不存在为成功” |
| 锁冲突 | 持`BEGIN IMMEDIATE`期间经HTTP写→`503 {"detail":"数据存储不可用"}`；DB层第二连接→`OperationalError: database is locked`；释放后写`200` |

### 3.3 规则抽检（13条）

| 规则 | 实测 | 与文档一致 |
|---|---|---|
| P-003 人侧路径只有GET | `POST /api/projects` → `405 {"detail":"Method Not Allowed"}`，审计增量0 | 是 |
| P-004 缺`Content-Type` | `422` | 是 |
| P-006 全部响应`no-store` | 读与写响应均`cache-control: no-store` | 是 |
| P-007 变更查询limit与倒序 | `limit=2`两条且id递减；`limit=0`/`201`→`422` | 是 |
| P-009 身份优先级/缺身份 | 仅`X-Agent-Id`成功且`key_id=NULL`；两者都缺→`400`且错误含`X-Agent-Id`，审计留failed | 是 |
| P-010 无效key | `401`，业务数据未写，不回退 | 是 |
| P-011 非法`X-Origin` | `400`并列出合法枚举 | 是 |
| P-014 行id不可变 | `PATCH`带`id`→`400` | 是 |
| P-015 未知字段/写计算字段 | 均`400` | 是 |
| P-016 PATCH合并与同值不记变更 | 同值两次不新增`business_changes` | 是 |
| P-018 删除被引用表 | `400 表格仍被 relation 字段引用，请先删除：t-ref.版本` | 是 |
| P-019 无批量写 | 批量路径`404` | 是 |
| P-041/P-042 审计字段与枚举 | `write_audit`10列（含`key_id`）；action枚举14项（12写动作+`key.issue`/`key.revoke`） | 是 |

### 3.4 验收场景与SC

| 项 | 结论 | 证据 |
|---|---|---|
| US1-AS1 五类响应终态分类 | 通过（4类实测+超时按文档） | `400 failed`/`401 failed`/`422 failed`/`503 detail unknown`/`200 success`；超时属客户端规则未模拟 |
| US1-AS2 建行幂等补偿 | 通过 | 重复建行`400`→回读对账，不重复写 |
| US1-AS3 读改写期望值校验 | 未验证 | 客户端侧规则，服务端无对应行为 |
| US2-AS1 超时→unknown | 未验证 | 需客户端网络层模拟 |
| US2-AS2 同值PATCH | 通过 | 两次200、变更不增 |
| US2-AS3 删除不存在的行 | 通过 | `400`+回读404，按最终不存在定案 |
| US3-AS1 成功写审计与变更计数 | 通过 | 建行：`write_audit`+1、`business_changes`+2（非空字段2） |
| US3-AS2 非法写 | 通过 | `400`、审计+1 failed且error非空、`business_changes`+0 |
| US3-AS3 失败鉴权审计 | 通过 | 缺身份`agent_id='-'`；无效key`agent_id`为请求携带值，均`key_id`空 |
| US4-AS1 两写同字段后者覆盖 | 通过（顺序等价） | 两次PATCH同字段→两条`update`、读回为后值 |
| US4-AS2 持锁写冲突 | 通过 | `503 detail` + DB层`OperationalError` |
| US4-AS3 读改写自检 | 未验证 | 客户端侧规则 |
| SC-001 第三方仅凭文档完成全流程 | 通过 | 3.2节实跑 |
| SC-002 每条规则判定方式可执行 | 部分通过 | 抽检13条可执行；锁冲突“400数据库错误”形态未复现（见V062-02） |
| SC-003 三态判定树六样例 | 部分通过 | 5类实测，连接超时未模拟 |
| SC-004 幂等现状配方 | 通过 | 重复建行/同值PATCH/二次删除三配方均验证 |
| SC-005 审计完整性 | 通过 | 成功+1、非法+1、422不增 |
| SC-006 与013字段语义一致 | 通过 | `agent_id`/`key_id`/`origin`两文一致，无第二种定义 |

## 四、013用户管理逐条（18场景）

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 旧调用建行 | 通过 | `success`；审计`agent_id=agent-old`、`key_id=NULL` |
| US1-AS2 旧调用不填负责人 | 通过 | 负责人保持空 |
| US1-AS3 无凭据 | 通过 | `400`且错误含`X-Agent-Id`；读接口无凭据`200` |
| US2-AS1 有效key建行 | 通过 | 审计`key_id=k-xxxx`、`agent_id=zhang.qa` |
| US2-AS2 key优先于X-Agent-Id | 通过 | 同时带时以label为准 |
| US2-AS3 业务变更actor | 通过 | `business_changes.actor=zhang.qa` |
| US2-AS4 库内无明文 | 通过 | 仅SHA-256（64位hex）与key_id；`list`不回显明文 |
| US3-AS1 不存在key | 通过 | `401 result=failed`、行未写、审计failed |
| US3-AS2 已吊销key | 通过 | `401 错误含key_id`，`list`显示“已吊销” |
| US3-AS3 无效key+合法X-Agent-Id | 通过 | 仍`401`，未回退 |
| US4-AS1 key建行自动填负责人 | 通过 | 负责人=`zhang.qa`；`business_changes`含`create` |
| US4-AS2 显式负责人优先 | 通过 | 显式`hand`保留 |
| US4-AS3 更新不填/旧调用不填 | 通过 | 更新后负责人保持原值`b`，不被覆盖 |
| US4-AS4 多候选/无字段/relation不填 | 通过 | 两个`-owner`字段→不填；无负责人字段→不造；relation负责人→不填 |
| US5-AS1 issue | 通过 | 打印`key_id`与明文各一次；`list`含label |
| US5-AS2 revoke | 通过 | 吊销后`401`，`list`显示已吊销 |
| US5-AS3 list无明文 | 通过 | 输出不含明文key |
| US5-AS4 audit | 通过 | 可见`key.issue`事件与最近写审计的`key_id` |
| 边界：同label两把key独立 | 通过 | 吊销第二把→第二把401、第一把仍200 |

补充：旧库升级幂等实测——以仓库`data/tableflow.db`旧库副本启动两次：自动建`api_keys`、给`write_audit`补`key_id`，旧141条审计保留，二次启动不重复建、不报错（FR-012）。
HTTP路由清单未新增（18条，无key管理路由），符合FR-013。

## 五、前两版修复回归

| 项 | 结论 | 证据 |
|---|---|---|
| `pytest -q` | 通过 | `133 passed` |
| V061-04 计算基线 | 通过 | `calculation.py` sha `e10b97aa…`（与v0.6.0基线一致） |
| V061-03 契约校验/原子写 | 通过 | `check_contracts.py`默认校验两契约OK exit0；`--pre-write`合法内容→原子写入且内容一致；重复键→exit1、目标未变、无残留临时文件 |
| V060-04 悬空编辑 | 通过 | 改无关字段`200`、显式悬空`400`、缺必填`400` |
| V061-05 解释器文档 | 通过 | 三个ms SKILL.md均有“运行环境（脚本解释器）”节 |
| V061-07 关闭约定 | 通过 | ms-summary新增`【原剩余事项】`段落约定与自检 |
| V061-01/06 014无spec | 已由t20补齐 | `specs/014-ms-skills/{spec.md,tasks.md}`已存在（本轮未复核其内容） |
| V061-02 关闭写入期校验 | 按契约延后 | 本轮未见实现，属“后续需求实现”，不计回归 |

## 六、缺陷登记（V062-01…03，均为低）

### V062-01 [低] 012协议中的代码行号引用已漂移

- 现象：012写于12:35，`write_service.py`在12:36被后续改动（013与V060-04修复同窗口）；文中行号前后漂移，前段约+4行、后段约+14行。例：
  - 文档“`行 id 已存在`（`write_service.py:816`）”→实际第830行；
  - 文档“`update_row`（`write_service.py:834-891`）”→实际第848–908行；
  - 文档“`delete_row`（`write_service.py:893-926`）”→实际第908行起；
  - 文档“`_validate_row_id`（`write_service.py:697-701`）”→实际第701–702行；
  - 文档“`payload`截断（`write_service.py:73`）”→实际第77行；
  - 文档“`_validate_values`（`write_service.py:703-722`）”→实际第707–727行。
- 复现：`grep -n "行 id 已存在\|def update_row\|def delete_row" backend/src/tableflow/write_service.py` 与文档第28/29/167/168/171行对照。
- 影响：按行号核对证据的人会找不到位置；行为结论不受影响。
- 建议：改为符号引用（函数名/常量名），或每次契约/代码变更后复核。

### V062-02 [低] 012“锁冲突两种形态”中400形态未能复现

- 现象：文档称写事务阶段锁冲突映射为`400 failed`（`数据库错误：database is locked`）；本轮两种探针（直接持`BEGIN IMMEDIATE`、预置WAL后持锁）经HTTP写入均得到`503 {"detail":"数据存储不可用"}`，仅DB层第二连接得到`OperationalError: database is locked`。400形态有代码路径（`write_service.py`的`sqlite3.Error`→`WriteError("数据库错误：…")`），但未找到可复现时序。
- 影响：SC-002“每条规则判定方式可执行”对该条不成立；客户端据`400数据库错误`做“可重试失败”的分支缺少现场样例。
- 建议：文档补一条可复现命令（例如锁发生在写事务阶段的构造），或把两种形态合并表述为“503 detail 为主”。

### V062-03 [低] 013 SC-001的数字已过时

- 现象：SC-001写“新增后`120 passed`（013前基线`108 passed`）”；当前实际`133 passed`（后续任务新增用例）。
- 影响：无功能影响；按SC核对的人会以为测试数不符。
- 建议：SC写“≥120全绿”或随用例更新数字。

## 七、未验证与风险

| 项 | 状态 | 原因 |
|---|---|---|
| 012 US1-AS3/US4-AS3 读改写自检 | 未验证 | 客户端侧规则，服务端无对应行为 |
| 012 US2-AS1 超时→unknown | 未验证 | 需客户端网络层模拟 |
| 012 SC-003 连接超时样例 | 未验证 | 同上 |
| 014 spec内容（t20） | 未复核 | 不在t12范围；V061-01已由t20补齐文件 |
| 011关闭写入期校验 | 未实现 | 契约明示后续需求（V061-02） |

## 八、证据清单（`.tmp-shots/qa-v062/`）

| 文件 | 内容 |
|---|---|
| `pytest.log` | 133 passed |
| `verify_012_013.py` / `verify_012_013.log` | 012探针 + 013十八场景逐条复现（含CLI issue/list/revoke/audit、多负责人、旧调用、无效/吊销key、审计计数） |
| `verify_012_client.py` / `verify_012_client.log` | 客户端实现清单实跑（读-写-幂等补偿-同值PATCH-变更-删除）+ 其余协议探针 + 锁冲突 |
| `probe_audit.py` | 012 US3 审计计数（成功+1/非法+1/422不增） |
| `probe_lock400.py` | 锁冲突400形态复现尝试（未复现，503） |
| `pin-final.txt` | 本轮源码与文档sha256 |
| `migration_old_db.log` | 旧库升级幂等探针（迁移前无api_keys/无key_id、141条审计保留、二次启动不重复建） |
