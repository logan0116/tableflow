# v0.6.0验证报告（t8，2026-11-19）

验证人：qa。验证窗口：12:11–12:26。范围：008契约、009 tf_update、010计算口径、015 ft_status。
证据目录：`.tmp-shots/qa-v060/`（脚本与日志可逐条重跑；不修改源码、不写线上业务行、不执行git写操作）。

## 一、结论（先行）

| 范围 | 结论 | 一句话依据 |
|---|---|---|
| 008契约board@1 | **有条件通过**：10个验收场景9通过、1未验证；FR-010不通过 | YAML可解析、字段16/16/9、闸门4个、差异清单可产出；但契约与看板skill口径冲突（V060-01） |
| 010计算口径 | **通过** | US1–US4共14个场景逐条独立复现通过；`pytest -q`为108 passed，与spec声明的基线一致 |
| 009 tf_update | **有条件通过** | 登记器脚本端到端跑通（新规格/变更单/幂等/冲突/清理）；分类判定依据与`unknown`三态未端到端验证 |
| 015 ft_status | **通过** | US1–US5共20个场景逐条验证通过（线上v0.6.0报告+本机副本边界场景）；全程只读 |
| 缺陷登记 | 8条 | 2高、2中、4低；均可复现（命令与输出见第五节） |

总体判断：**v0.6.0的四个需求在功能面可用，未发现会立刻造成数据错误的阻断缺陷**；但008的FR-010（契约与skill表述一致）不满足，且009的挂版本规则在当前线上会把需求挂到`v0.2.0`（V060-02），发布前应先处置。

## 二、验证基线（固定版本，避免源码流动导致误判）

| 项 | 值 |
|---|---|
| 工作目录 | `/home/mozinodey/PycharmProjects/tableflow` |
| HEAD | `54c0243`（v0.5.1文档提交） |
| `backend/src/tableflow/calculation.py` | `e10b97aa94fd46ccd48b539244c464951fc37d57c01e4530da98e751d535f719`（12:17定稿） |
| `backend/src/tableflow/write_service.py` | `64d9d2e61b9e1b37b93d82bf4b66e86b37871b67fc099dd9aee4bc5f42e737bd` |
| `backend/tests/test_computation_010.py` | `cc76a646a57bb2a2cf698f4c43d6d9d5e426a9a81bad2b7b612df5a2aceb63dc` |
| `specs/008-board-contract/board@1.yaml` | `e88c59852d5d1af840bb28565289570333a087864f1b3b2e3c4d7076b0c3c5c1` |
| `specs/008-board-contract/spec.md` | `bbf69c034dd6a931bd9674f19d530339c27c471dd6ca28abcb46d5ff178e4f66` |
| `specs/010-computation/spec.md` | `5a721ddfb8d23a78a6e382179867a8cb821b03955df79f35ac2fa5d60bc11e48` |
| `skills/tf-update/SKILL.md` | `4d05e2a14d922e767bb71f5aa26a5874a9af14bc0f6dac59f72b31eb41b0d5d9`（12:25更新后复验） |
| `skills/ft-status/SKILL.md` | `3d4b6b961af9318902a0c1b3772f96a7c192a98123d053e6a63594fa433baeb2`（12:25更新后复验） |
| 后端回归 | `108 passed, 1 warning in 4.15s`（12:22:39，`pytest-final.log`） |
| 线上看板 | `http://192.168.1.155:8090`，7项目21表192行（只读GET） |

时序说明：t8被派发时（12:11）009/010/015的spec与skill尚未生成，t1/t2正在实现。12:17–12:22三者相继落盘，本报告按落盘后的固定sha验证。12:23起013（用户管理）开始改`db.py`/`write_service.py`/`app.py`，不属于本报告范围（由t12验证），因此010的结论固定在12:22的sha上。12:25两个skill又更新了一版（调用方式改为`TF_PAYLOAD`/`FT_VERSION`，并补原因话术表），已用更新后的抽脚本复验：009的登记器、幂等、冲突、dep、清理全部重跑通过；015对线上v0.6.0重跑结论不变（附录`skill-v2-run1.log`、`ft-status-v060-v2.log`）。

## 三、008契约逐条

验收场景（`specs/008-board-contract/spec.md`，3个US共10个场景）：

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 字段16/16/9且每字段有key/name/type | 通过 | `check_008.log`：`{'ver': 16, 'indep': 16, 'dep': 9}`，41个语义键无重复，三要素齐全 |
| US1-AS2 闸门字段恰好4个 | 通过 | `ver.spec_ready`/`ver.change_ready`/`ver.bug_ready`/`ver.gate`，对应`board@1.yaml`117/132/146/151行 |
| US1-AS3 每个状态只回答一个问题 | 通过（有注） | 四个状态域各带唯一`question`；注：`stage`与`regress`字面共享`todo`/`doing`（跨域同名，见V060-06） |
| US2-AS1 fd_system能报出7个契约外字段 | 通过 | `compare_008_v2.log`：`开发进度`/`测试进度`/`文档状态`/`任务总数`4个契约未收录 + `未清Bug数`/`Bug已清空`/`回归通过`3个语义已变，合计7个 |
| US2-AS2 im_kg_desktop的`回归通过`类型不符 | 通过 | `imkg-v-regress`类型为`enum`，契约声明`computed` |
| US2-AS3 比对过程无任何写操作 | 通过 | `compare_008_v2.py`只发`GET /api/projects/*`、`GET /api/tables/*`，不带`X-Agent-Id` |
| US2独立测试 fd_system无前缀+缺`已勾选任务数` | 通过 | `fd-ver`17/17、`fd-indep`18/18、`fd-dep`7/7字段均无`<前缀>-v/i/d-`结构；`fd-indep`无`已勾选任务数` |
| US3-AS1 改已accepted规格→dep | 通过 | 线上`DEP-03-BR`挂`007-AR`，影响面写明`SC-001 两栏布局贴边与无横向溢出` |
| US3-AS2 新能力→indep新行 | 通过 | 线上`010-AR`为indep行，无同名dep行 |
| US3-AS3 不改产品行为→不进看板 | 通过 | 部署/CI/文档类改动无对应indep或dep行（`tf-indep`15行、`tf-dep`3行清单可核） |
| US3-AS4 依据指不到→只追问、不落行 | **未验证** | 判据追问由`tf-update`执行；skill文本要求“只问一个问题”，本轮无真实口述输入，未做追问演练 |
| Edge Cases（拆行/横切/取消） | **未验证** | 同US3-AS4，属技能执行面 |

需求条款与成功标准：

| 条目 | 结论 | 证据 |
|---|---|---|
| FR-001 契约文件路径 | 通过 | `specs/008-board-contract/board@1.yaml`存在，11KB |
| FR-002/003/004 三表字段数与关键字段 | 通过 | 16/16/9；含`独立需求总数/就绪`、`依赖需求总数/就绪`、`上一版本Bug总数/未解决数/就绪`、`发布条件` |
| FR-005 四个状态域 | 通过 | `status_definitions`含stage/acceptance/regress/release，各带`question` |
| FR-006 判定规则 | 通过 | `spec_done`/`change_done`/`empty_set`/`release_gate`齐备 |
| FR-007 分类判定树5分支+依据要求 | 通过 | `classify.order`5分支；`evidence_required`要求指到规格编号与场景号 |
| FR-008 非目标显式列出 | 通过 | `meta.out_of_scope`5项 |
| FR-009 语义键作比对主键、不要求改字段id | 通过 | `conventions.semantic_key`；实测fd_system无前缀字段仍能按语义键比对 |
| FR-010 契约与看板skill表述一致 | **不通过** | 三处冲突，见V060-01 |
| SC-001 YAML可解析、16/16/9、键无重复 | 通过 | 同上 |
| SC-002 能对任一项目产出差异清单 | 通过 | 7个项目21张表的差异清单已产出（`compare_008_v2.log`） |
| SC-003 判定树对三条真实需求给出唯一结论 | 通过 | 010-AR→`new_spec`（新增条款）；DEP-03-BR→`change`（挂007-AR，依据SC-001）；部署/CI→`out_of_board` |
| SC-004 契约不含接口/代码/迁移 | 通过 | `check_008.log`扫描`/api/`、`POST`、`curl`、`git`、`INSERT`、`migrat`、`def `：命中行“无” |

## 四、010计算口径逐条

独立复现脚本`verify_010.py`（自建临时库，不复用`tests/test_computation_010.py`），输出`verify_010.log`。

| 场景 | 结论 | 关键观测 |
|---|---|---|
| US1-AS1 空集count与sum为0 | 通过 | 读接口`count=0`、`sum=0.0`；落库`'0'`、`'0.0'` |
| US1-AS2 空集rollup all为真 | 通过 | 读接口`true`，落库`'true'` |
| US1-AS3 空集percent为null | 通过 | 读接口`null`，落库`NULL` |
| US2-AS1 悬空后rollup all仍为否 | 通过 | 删S2（不达标行）后`c-all=False`（关联仍含悬空id） |
| US2-AS2 依赖它的and闸门也为否 | 通过 | `c-gate=False` |
| US2-AS3 摘掉失效id后恢复为真 | 通过 | 关联改`["S1","S3"]`后`c-all=True`、`c-gate=True` |
| US2-AS4 悬空时count/percent仍只统计现存行 | 通过 | `count=2`、`percent=100.0` |
| US3-AS1 gate=true+allow_override=true仍拒绝覆盖 | 通过 | `400 闸门字段「c-gate2」禁止人工覆盖`；`override_value`为`None` |
| US3-AS2 数量类打gate、gate非布尔均400 | 通过 | `gate 只能标记布尔判定字段（and 或 rollup all/any/none）`；`gate 必须是布尔值` |
| US3-AS3 非闸门布尔字段仍可覆盖 | 通过 | 打`allow_override=true`的`and`字段覆盖返回`success` |
| US3-AS4 历史覆盖可用value=null清除 | 通过 | 直插历史覆盖后，`value:null`清除返回`success`，`override_value`回到`None` |
| US4-AS1 改源行→同事务重算 | 通过 | 改`S1`状态后读接口`count=2`、`all=False`，未调用recompute |
| US4-AS2 新增源行/挂关联/新建汇总行即时重算 | 通过 | 新增`S4`并挂入关联后`count=3` |
| US4-AS3 删除源行后重算 | 通过 | 删`S4`后`count=2` |
| Edge Cases | 部分通过 | 已验证：空集`none=true`/`any=false`/`count_distinct=0`、悬空`all/none`判否；未验证：`min`/`max`空集返回null、重复id不算悬空、非字符串项不阻断、闸门拒绝后同请求整体回滚 |
| SC-001 pytest全绿且108 passed | 通过 | `pytest-final.log`：`108 passed` |
| SC-002 11个用例按a/b/c/d分组 | 通过 | `test_a_*`1、`test_b_*`3、`test_c_*`4、`test_d_*`3 |
| SC-003 线上业务数据未被修改 | **证据不足** | 无改动前基线快照；当前21表192行，较v0.5.1记录的181行多11行，均为规划行（008–015-AR与v0.6.0/1/2），无删除证据（V060-08） |
| SC-004 改动可定位到四处代码 | 通过 | `calculation.py`221–222（gate布尔校验）、307–310（gate适用范围）、496–516（悬空判定）、954–957（闸门拒覆盖） |

## 五、009 tf_update与015 ft_status

### 5.1 009 tf_update（spec为5个US共21个场景）

实跑方式：任务要求“读为主、写后清理”。线上看板按约束只读，因此把`data/tableflow.db`复制为本机临时实例（`18091`端口），按`skills/tf-update/SKILL.md`的登记器脚本原文执行，结束后按skill的清理顺序摘关联、删行、删临时版本。日志：`skill-run-1.log`、`skill-run-2.log`、`skill-run-3.log`、`skill-run-4b.log`、`v020-before/after.json`。

| 项 | 结论 | 证据 |
|---|---|---|
| 新规格登记（new_spec） | 通过 | `090-AR`写入成功，自动挂到最早planned版本`v0.0.1-test`，回读四项（行存在/条款一致/验收pending/版本关联含行）全true |
| 变更单登记（dep） | 通过 | `DEP-090-BR`挂`001-AR`成功；首次用不存在的`007-AR`被400拒绝，符合`relation_must_exist`约束 |
| 幂等重跑 | 通过 | 同id同条款返回`already_registered`，未重复写 |
| 冲突id | 通过 | 同id不同条款返回`failed`“行 id 已被占用且条款不同，拒绝覆盖”，未覆盖原行 |
| 版本选择规则 | 通过 | 在副本上验证“最早planned”按发布时间升序选中`v0.0.1-test` |
| out_of_board分支 | 通过 | 脚本对`kind=out_of_board`直接拒绝（`kind 只能是 indep 或 dep`），未产生任何行 |
| 清理 | 通过 | 摘关联→删两行→删临时版本后，三处均404；`v0.2.0`行前后逐字段一致；行数恢复（ver3/indep4/dep1） |
| 分类判定（in_place/change/cross）与依据格式 | **未验证** | 需真实口述输入与LLM判定，本轮只验登记器 |
| `unknown`三态与回读 | **未验证** | 未注入503，脚本路径未实测 |
| 不写spec、不改验收状态 | 通过（静态+回读） | 脚本无文件写；回读`验收状态=pending`、`规格目录`只写字段值不落文件 |
| 12:25更新版复验 | 通过 | 改为`TF_PAYLOAD`调用后重跑：新规格/幂等/冲突/dep/清理全部通过（`skill-v2-run1.log`、`v020-before2.json`与`v020-after2.json`一致） |

### 5.2 015 ft_status（spec为5个US共20个场景）

实跑方式：线上`v0.6.0`只读执行；边界场景（可发布/验收被拒/变更单doing/悬空关联）在本机临时实例（`18092`端口，副本库）造数后执行。日志：`ft-status-v060.log`、`ft-status-v060.json`。

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 顶部结论+三项就绪+契约原文规则 | 通过 | 报告“不可发布：三项就绪中1项未满足，阻塞4行”，规则列为`board@1`原文 |
| US1-AS2 指出卡住行数与行id | 通过 | 列出`008-AR`/`009-AR`/`010-AR`/`015-AR` |
| US1-AS3 三项全真报可发布 | 通过 | 副本`v0.0.9-test`：“**可发布**：三项就绪中0项未满足，阻塞0行” |
| US1-AS4 未给版本号时按规则选版本并写明依据 | 通过 | 自动选中`v0.6.0`，报告写明“大于已发布最大版本的最小planned；已发布最大版本v0.5.1” |
| US2-AS1 implement=todo且pending的措辞 | 通过 | `008-AR`：“未开始实现（implement=todo）：须先 implement=done，再置 acceptance=accepted” |
| US2-AS2 done+pending的措辞 | 通过 | `009-AR`：“只差验收确认” |
| US2-AS3 rejected的措辞 | 通过 | 副本`003-AR`：“验收被拒（acceptance=rejected）：改实现与条款后重验” |
| US2-AS4 regress=doing的措辞+影响面摘要 | 通过 | `DEP-01-BR`：“已合入待验（regress=doing）：补验证后置passed”，影响面摘“契约测试；影响003全部场景” |
| US2-AS5 悬空关联单列且闸门判否 | 通过 | 副本`v0.0.7-test`：“悬空关联：DEP-999-BR”，`依赖需求就绪`判否 |
| US3-AS1 从条款抽取同版引用画依赖边 | 通过 | “015-AR → 008-AR、010-AR” |
| US3-AS2 可后移候选+被引用次数 | 通过 | `008-AR`候选；被引用次数008-AR=1、009-AR=0、010-AR=1、015-AR=0 |
| US3-AS3 两套方案含保留/移出与剩余阻塞行数 | 通过 | 方案A/B；方案A移出后剩余阻塞行2行 |
| US3-AS4 明确“迁版不改变结论”、下一版本取自版本表 | 通过 | “下一版本：v0.6.1”“迁版不改变本版闸门结论” |
| US4-AS1 只调用GET、不含/api/agent | 通过 | 脚本静态检查无POST/PATCH/DELETE，仅`GET /api/projects/*`、`GET /api/tables/*` |
| US4-AS2 执行后无新增变更记录 | 通过（静态） | 仅GET，写路径不存在；未在线上制造写入 |
| US4-AS3 动作为命令建议不代跑 | 通过 | 报告只列方案与命令指引 |
| US5-AS1 发布条件与契约差异 | 通过 | 列出“看板条件为[开发进度=100、回归通过=true、Bug已清空=true、文档状态=done]，契约为[三项就绪]” |
| US5-AS2 require字段冲突 | 通过 | 指出`回归通过`带行级`require(状态=已完成)`与契约单字段判定冲突 |
| US5-AS3 枚举多出na | 通过 | 列为偏差并说明判定影响 |
| US5-AS4 planned版本号小于已发布版本 | 通过 | 报“v0.2.0状态为planned，但版本号小于已发布最大版本v0.5.1” |

补充：015的“客户端重算”口径成立——线上服务仍为v0.5.1，010虽已落码但未部署，故以契约口径重算是正确做法。12:25更新版（`FT_VERSION`调用）对线上v0.6.0重跑，结论与逐条原因一致；此时008-AR已`implement=done`，话术变为“只差验收确认”（`ft-status-v060-v2.log`）。

## 六、缺陷登记（V060-01…08）

> bug表（011）尚未上线，先登记在此。每条含复现步骤与证据；“建议承接方”按当前任务图给出。

### V060-01 [高] 008 FR-010不通过：契约与看板skill口径冲突

- 现象：`skills/tableflow-board/SKILL.md`（v0.5.x口径）与`board@1`三处不一致：
  1. 字段清单：skill要求`开发进度`(126行)/`测试进度`/`未清Bug数`/`Bug已清空`/`回归通过`(130行)/`文档状态`/`任务总数`；契约改为`独立需求总数/就绪`、`依赖需求总数/就绪`、`上一版本Bug总数/未解决数/就绪`。
  2. 类型：skill 163行写“`speckit-implement状态`必须enum，其余阶段用text或enum均可”；契约16个字段中8个阶段状态全为`enum`。
  3. 第四张表：skill 111行“**没有第四张表**”；011将新增bug表，011落地时必须同步。
- 复现：`sed -n '111,131p;163p' skills/tableflow-board/SKILL.md` 与 `specs/008-board-contract/board@1.yaml` 对照。
- 影响：Agent按skill建字段会产出与契约不一致的结构，`就绪`闸门无从计算。
- 建议承接方：011（doc，契约侧）与ft-skills（skill侧）同步改；008的T007冲突清单应落盘到`specs/008-board-contract/`。

### V060-02 [高] tf_update按“最早planned”挂版本，当前线上会挂到v0.2.0

- 现象：线上`tf-ver`中`v0.2.0`仍为`planned`且发布时间`2026-11-30`；`v0.6.0/1/2`为`planned`但发布时间为空。skill规则“发布时间升序、空日期排最后”会把新需求挂到`v0.2.0`，而不是本轮目标`v0.6.0`。
- 复现（只读，不写看板）：
  ```bash
  python3 - <<'PY'
  import json,re,urllib.request
  B="http://192.168.1.155:8090"
  d=json.load(urllib.request.urlopen(B+"/api/tables/tf-ver/table"))
  sem=lambda v:(lambda m:tuple(map(int,m.groups())) if m else (999,999,999))(re.match(r"^v(\d+)\.(\d+)\.(\d+)$",v))
  nm={f["id"]:f["name"] for f in d["fields"]}
  val=lambda r,n:r["values"].get(next(f for f,i in nm.items() if i==n))
  p=[r for r in d["rows"] if val(r,"发布状态")=="planned"]
  p.sort(key=lambda r:(val(r,"发布时间") or "9999-12-31", sem(r["id"])))
  print([(r["id"],val(r,"发布时间")) for r in p]); print("选中:",p[0]["id"])
  PY
  # 输出：选中 v0.2.0
  ```
- 影响：新需求挂错版本，发布范围与`就绪`统计失真；本轮v0.6.0的后续登记会被挂到老版本。
- 建议承接方：009（ft-skills）把规则改为“排除早于最近已发布版本的planned”，并由队长把`v0.2.0`处置为`released`或`dropped`（人工决策，不代改）。

### V060-03 [中] 闸门标记未进契约、存量未打标，禁覆盖只靠默认值

- 现象：010用`options.gate=true`识别闸门（`calculation.py`221、307、954行），但`board@1`只有文档属性`gate: true`，未声明该映射；线上7个项目的`发布条件`等闸门字段均未打标（`allow_override`为空）。在存量迁移前，把字段配置改成`allow_override=true`再覆盖即可伪造“发布条件=是”（写接口有审计，但不是硬拦截）。
- 复现：`curl -s .../api/tables/fd-ver/table | jq '.fields[] | select(.name=="发布条件")'` → `options`无`allow_override`、无`gate`；本机副本上建同名`and`字段并开`allow_override=true`后可成功覆盖（`repro2.log`B段，pin sha下返回`success`）。
- 影响：闸门可被绕过，发布资格审计依赖人工比对配置变更。
- 建议承接方：011落地后新增“存量迁移”需求（给存量闸门字段打标），并在契约补`gate ↔ fields.options.gate`映射说明。

### V060-04 [中] 悬空关联使持有该关系的行无法编辑

- 现象：删除被关联行后，持有relation的行对“无关字段”的PATCH被400拒绝：`关联目标行不存在：t-spec/S1`；必须先或同时提交relation值（清空失效id）才能改。
- 复现：`repro2.py`A2段；步骤：建relation（`relation_must_exist=true`）→关联S1→删除S1→`PATCH v-ver` → 400；`PATCH v-specs=[]` → 200。
- 影响：数据修复路径不友好，人工修悬空时容易卡住；与003“删除被关联行允许”配套的修法只能整字段提交。
- 建议承接方：backend（010/002后续小修）：写校验只校验本次提交的字段，或提供“清除失效关联”入口。

### V060-05 [低] 契约未结构化声明行id字段

- 现象：`row_id`只写在`conventions.row_id`文本与各字段`note`里（如`ver.version`的“行 id”），`tables.*`无`row_id`键；机器读取者无法定位主键字段，`US2`差异清单需要人工猜。
- 建议：`tables.ver.row_id: ver.version`、`indep: spec.id`、`dep: change.id`。

### V060-06 [低] status_definitions跨域字面同名todo/doing

- 现象：`stage`与`regress`都含`todo`/`doing`，语义不同（阶段推进/未合入与待验）。若按US1-AS3“values集合互不重叠”字面理解则不满足。
- 建议：契约注明“同域互斥、跨域可同名”，或改用带前缀的取值。

### V060-07 [低] sum空集落库为0.0（float）

- 现象：`sum`空集落库`'0.0'`、读接口`0.0`；`count`落库`'0'`（int）。FR-002只要求“数字0”，但类型不统一，展示层可能显示`0.0`。
- 建议：`sum`无`decimals`时落int，或明确接受float并在展示层格式化。

### V060-08 [低] 010 SC-003证据不足：无法证实线上数据未被修改

- 现象：无改动前基线快照；当前21表192行，较v0.5.1记录的181行多11行（`008–015-AR`8行+`v0.6.0/1/2`3行，均为规划行），无删除证据，但“未被修改”无法用证据闭环。
- 建议：发布前记录行id清单与行数做基线，或由010补充“对比基线”的核验方法。

## 七、未覆盖与风险

| 项 | 状态 | 原因 |
|---|---|---|
| 008 US3-AS4与Edge Cases | 未验证 | 需真实口述输入触发`tf-update`的追问分支 |
| 009 分类判定（in_place/change/cross）、依据格式、编号分配 | 未验证 | 同上；本轮只验登记器脚本 |
| 009 `unknown`三态与回读确认 | 未验证 | 未注入503 |
| 010 Edge Cases 的min/max空集、重复id与非字符串脏值、闸门拒绝后整体回滚 | 未验证 | 时间与用例优先级；代码路径已在`tests/test_computation_010.py`覆盖，本轮未独立复核 |
| 014 ms_update/ms_implement/ms_summary | 未验证 | 任务要求“若已可用”；截至12:26未交付（`skills/`只有tableflow-board、tf-update、ft-status） |
| 011 bug表 | 未覆盖 | 本轮范围外（t3进行中） |
| 013用户管理 | 未覆盖 | 12:23起开始落地，属t12 |

## 八、证据清单（`.tmp-shots/qa-v060/`）

| 文件 | 内容 |
|---|---|
| `check_008.py` / `check_008.log` | 契约结构、状态域、判定树、非目标、SC-004扫描 |
| `compare_008_v2.py` / `compare_008_v2.log` | 7项目21表的契约差异清单（US2/T006证据） |
| `verify_010.py` / `verify_010.log` | 010四情形独立复现（US1–US4） |
| `repro.py` / `repro1.log`、`repro2.py` / `repro2.log` | 空集/悬空/禁覆盖/重算与悬空编辑锁死（V060-03、V060-04） |
| `pytest-final.log` | `108 passed` |
| `tf_update_runner.py`、`skill-run-1/2/3/4b.log`、`v020-before/after.json` | 009登记器实跑与清理前后对比（12:22版） |
| `tf_update_runner_v2.py`、`skill-v2-run1.log`、`v020-before2/after2.json` | 009登记器12:25更新版复验 |
| `ft_status_runner.py`、`ft-status-v060.log`、`ft-status-v060.json`、`setup_015.py` | 015线上报告与边界场景（12:22版） |
| `ft_status_runner_v2.py`、`ft-status-v060-v2.log` | 015 12:25更新版对线上v0.6.0重跑 |
| `live-v060-gate.png` | 线上`tableflow/版本管理`截图：v0.6.0为planned、开发进度25、需求关联008-AR+3 |
| `pin-final.txt`、`pin-before/after.txt` | 验证期间的源码sha256固定点 |

## 九、给队长的下一步建议

1. 先处置V060-02：把`v0.2.0`置为`released`/`dropped`（人工决策），否则009会把新需求挂到v0.2.0。
2. V060-01由011与010同步改skill，并在008的`tasks.md`落盘T007冲突清单。
3. V060-03/V060-04建议并入011后的“存量迁移/写校验”小需求，不在v0.6.0热修。
4. v0.6.0发布前重跑一次`pytest -q`并记录sha（013落地会改变基线），以免把013的改动算进v0.6.0。

---

## 十、修复记录（t9，2026-11-19）

> 承接第六节8条缺陷。本轮只改后端代码与文档，未写线上业务行（线上只做只读GET）；契约文件由doc的t15并行推进到board@1 rev3/board@2 rev2，本轮按t15定稿sha复验，契约归属t15。

### 10.1 逐条处置

| 缺陷 | 结论 | 动作 | 复验证据 |
|---|---|---|---|
| V060-01 | 已修复（复核） | `skills/tableflow-board/SKILL.md`已按board@2对齐；`specs/008-board-contract/conflicts-t007.md`记录16条冲突+4条同步改写；三处点名冲突与7个旧字段名字面命中均为0 | `repro_all.log`V060-01共7项PASS；`check_008_after.log` |
| V060-02 | 规则已修，数据处置待决策 | `skills/tf-update/SKILL.md`改为“版本必须由人指定”，拒绝不晚于最近已发布（v0.5.1）的版本，空版本直接拒绝 | `repro_all.log`：`v0.2.0`被拒（不晚于v0.5.1）、`v0.6.0`可登记 |
| V060-03 | 契约已声明，迁移未执行 | board@1 rev3/board@2 rev2新增`conventions.gate_mapping`与`migrations.gate-tag-existing`（owner=另立迁移需求）；后端`gate`拦截沿用010用例 | `check_board2_after.log`（4个闸门、`gate_mapping`在、`migrations`在）；`verify_010_after.log`US3四项PASS；线上7个“发布条件”字段`options.gate`仍为空 |
| V060-04 | 已修复（代码+3用例） | `write_service.update_row`只对本次提交的关系字段校验“目标行存在”；必填/min/max/enum仍按合并后整行校验 | `pytest-after.log`123 passed；`test_repair_v060.py`3例；`repro2_after.log`A2“改无关字段”400→200 |
| V060-05 | 已修复 | 契约`tables.*.row_id`：`ver.version`/`spec.id`/`change.id`（board@2另含`bug.id`） | `check_board2_after.log`；`repro_all.log`2项PASS |
| V060-06 | 已修复 | `conventions.status_values_scope`：同域互斥、跨域可同名、引用带域前缀 | `check_board2_after.log`；`repro_all.log`2项PASS |
| V060-07 | 契约接受浮点，不热修 | 契约rev3明确“`sum`空集落0.0、`count`落整数0”；已撤回本轮此前的“空集落整数0”代码改动，保持代码与契约一致 | `verify_010_after.log`落库`0.0`/`0`；`repro_all.log`5项PASS |
| V060-08 | 方法与基线已补 | `specs/010-computation/spec.md`新增“SC-003的核验方法与基线”；基线7项目22表192行，sha256`b4e353c55ab8595785fdc812dc086704d038717fcc3fb98c25438a78f8f2e279`，快照`.tmp-shots/repair-v060/baseline-2026-11-19.json` | `repro_all.log`2项PASS |

### 10.2 重跑结果（2026-11-19 12:42，按定稿sha）

| 命令 | 结果 | 日志 |
|---|---|---|
| `cd backend && .venv/bin/python -m pytest -q` | `123 passed, 1 warning in 4.56s` | `pytest-after.log` |
| `python3 .tmp-shots/qa-v060/check_008.py` | 字段16/16/9、语义键41无重复、闸门4、YAML可解析 | `check_008_after.log` |
| board@2结构核对 | 字段16/16/9/12、语义键53无重复、闸门4、`row_id`齐全、`migrations`1项 | `check_board2_after.log` |
| `verify_010.py`（010独立复现） | US1–US4逐条通过：空集`count='0'`/`sum='0.0'`/`rollup=true`/`percent=null`；悬空判否；闸门禁覆盖；写后重算 | `verify_010_after.log` |
| `repro2.py`（缺陷复现脚本） | A2悬空后改无关字段：400→200（V060-04已修） | `repro2_after.log` |
| `repro_all.py`（本轮逐条复验） | 31项PASS、0 FAIL | `repro_all.log` |

### 10.3 未闭环与需队长决策

1. V060-02：线上`v0.2.0`仍为`planned`（发布时间2026-11-30）。规则已能拒绝它，但`ft-status`仍会报“planned版本号小于已发布最大版本”；处置为`released`/`dropped`属人工决策，本轮未改看板。
2. V060-03：`migrations.gate-tag-existing`状态“未执行”。发布前若要硬拦截闸门覆盖，需先执行打标迁移；未执行时绕过需先改字段配置`allow_override=true`（写接口有审计），QA建议不在v0.6.0热修。
3. V060-07：接受`0.0`浮点后，展示层把空集显示成`0`或“—”的格式化未做。
4. V060-08：010执行窗口没有改动前基线，事后无法证明“未被修改”；本轮只提供向前核验方法。当前基线22表中`tableflow/tf-bug`（0行）为011新增，不属于010交付面。
5. 010非目标“不改relation写入校验”仍对010成立；V060-04是独立热修（改动`write_service.update_row`），不属于010交付。

### 10.4 本轮改动文件与sha256（2026-11-19 12:42）

| 文件 | sha256 | 归属 |
|---|---|---|
| `backend/src/tableflow/write_service.py` | `39b0b1029ae85d2a4b002fa8b99529107fd2e7ed18d3fdda00f087fff498bc7e` | t9（V060-04） |
| `backend/tests/test_repair_v060.py` | `fd131be273cf5137ea11ec29d1abf8cd7bdddc42798da8ee8247e6d79be164f3` | t9（V060-04回归） |
| `specs/010-computation/spec.md` | `62d0f5699e43d6374b49395e39d4dba87d9c30b643d9e8ed68c2d6b392f26374` | t9（V060-08；另加V060-03交叉引用） |
| `specs/008-board-contract/board@1.yaml` | `f872e9ce93e2e0078e4ac1747f45b215388b53dd1a76625e15b41e24f34fbcfc` | doc/t15定稿 |
| `specs/011-bug-table/board@2.yaml` | `6594c5e926f76ee512dd53ea40542efe2482b7a6bd25dfebcddf335e534bba72` | doc/t15定稿 |

说明：`calculation.py`最终未改——V060-07按契约接受0.0，已撤回“空集落整数0”的改动；回归证据目录`.tmp-shots/repair-v060/`（脚本与日志可重跑）。
