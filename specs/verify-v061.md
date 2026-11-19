# v0.6.1验证报告（t10，2026-11-19）

验证人：qa。验证窗口：12:42–12:48。范围：011bug表、014三个MSskill、v0.6.0的8条缺陷修复回归。
证据目录：`.tmp-shots/qa-v061/`（脚本与日志可逐条重跑；不修改源码、不写线上业务行、不执行git写操作）。

## 一、结论（先行）

| 范围 | 结论 | 一句话依据 |
|---|---|---|
| 011bug表与board@2 | **通过**：15个验收场景14通过、1未验证 | 契约四表16/16/9/12、53语义键无重复、闸门4；线上`tf-bug`12字段与契约逐项一致；建表脚本新建/幂等/冲突/不碰三表均实测通过 |
| 014三个MSskill | **有条件通过**：三skill实测证据齐、可复现；8个验收面7通过、1未验证 | ms-update/ms-implement/ms-summary的证据与自述一致；`ms_summary --dry-run`、轴2合并、关闭需确认均独立复现；计划↔用例关联为0，`/run`回写链未验证 |
| v0.6.0修复回归 | **通过**：8条逐条复核 | pytest123 passed；V060-02四条拒绝规则实测；V060-04 400→200且显式悬空仍400；契约rev3/rev2与闸门迁移已落；skill零旧口径 |
| 缺陷登记 | 7条（1高4中2低） | 均可复现，见第五节 |

总体判断：**011与014的交付物可用，v0.6.0的8条缺陷修复经复核有效**；主要缺口是014没有spec（无验收场景可核对、看板统计为空），以及011的"关闭缺陷写入期校验"属于契约明示的后续实现项。

## 二、验证基线（按队长2026-11-19口径）

| 项 | 值 |
|---|---|
| 工作目录 | `/home/mozinodey/PycharmProjects/tableflow` |
| `specs/008-board-contract/board@1.yaml`（rev3） | `142ccf067ab372858a2cb898e78506f7a6dcc8adeb86a1e16210d6d507930537`（队长给定口径基线） |
| `specs/011-bug-table/board@2.yaml`（rev2） | `d45d159f149497e3269ee4d5445e11fef808ba3683c66b99b4688fa9b4b088a1`（队长给定口径基线） |
| `backend/src/tableflow/calculation.py` | `f22191bdb0f71e8f2fdc75496dc57db29c29c11adfc47e72d110c766306ec5b9` |
| `backend/src/tableflow/write_service.py` | `39b0b1029ae85d2a4b002fa8b99529107fd2e7ed18d3fdda00f087fff498bc7e` |
| `backend/tests/test_repair_v060.py` | `fd131be273cf5137ea11ec29d1abf8cd7bdddc42798da8ee8247e6d79be164f3` |
| `skills/tableflow-board/SKILL.md` | `40d8dac50270e45cc7409a679ce93eb7e59403ecef91f62f035cac3d97782175` |
| `skills/tf-update/SKILL.md` | `4b98f11f0cf226ae5d3443c9643738d272773b488609f099957e8072d71cdbef` |
| `skills/ft-status/SKILL.md` | `1d1a6b947db38e5c3bce534f13e1a021cada67ce49aec00e34907b3be85440c1` |
| `skills/ms-summary/assets/ms_summary.py` | `6b7c767257b4881daf46672a62fa091d4f2138995edfe99453934a9f4d74c981` |
| 后端回归 | `123 passed, 1 warning in 4.50s`（12:47，`pytest.log`） |
| 线上看板 | `http://192.168.1.155:8090`（只读GET；服务端仍为旧代码，010/013未部署） |

队长口径（本轮按此判定）：
1. 契约哈希以本节新值为准；旧值`f872e9ce`/`6594c5e9`作废（t19把`migrations.gate-tag-existing`改为“已执行”，其余内容未变）。
2. **线上闸门禁覆盖尚未生效**（线上跑旧代码）；不得据此判“gate已生效”。正确判据是仓库内两用例+部署后的`--probe-override`。
3. `v0.2.0`保持`planned`是队长决定，**不登记为缺陷**（`ft-status`把它列为“数据异常”属报告行为，不是缺陷）。

## 三、011bug表逐条

spec：`specs/011-bug-table/spec.md`（4个US共15个验收场景/17FR/5SC）。契约：`board@2.yaml`（四表16/16/9/12，53语义键无重复，闸门4，`row_id`齐全，`gate_mapping`与`status_values_scope`在`conventions`，`migrations.gate-tag-existing`状态“已执行”，`executed_fields`7项）。

| 场景 | 结论 | 证据 |
|---|---|---|
| US1-AS1 bug表12字段、key互不重复且以`bug.`开头 | 通过 | `board@2.yaml`解析：bug 12字段，53键全局无重复 |
| US1-AS2 线上`tf-bug`字段id/名称/类型与契约一致 | 通过 | `compare_bug.py`：12对12，名称/类型/枚举/关联目标/必填逐项核对“无问题” |
| US1-AS3 `specs`→indep、`found`/`fix`→ver且同项目 | 通过 | 线上`tf-b-indep`→`tf-indep`、`tf-b-found`/`tf-b-fix`→`tf-ver`，同属`tableflow` |
| US2-AS1 未解决数只排除`closed` | 通过 | `ft_status v0.6.1`：“上一版本v0.6.0的缺陷1个，未closed 0个”，bug闸门判是 |
| US2-AS2 置`closed`须有修复版本+证据，或证据写明不修复且剩余事项为空 | **未验证** | 契约注明“写入期校验，后续需求实现”；实测临时实例写`BUG-99`（closed、无证据、无修复版本、rest空）返回success（V061-02） |
| US2-AS3 已`closed`不再计入且历史证据无改动 | 通过 | BUG-01状态closed；`changes`保留12:37创建与12:39关闭全部字段留痕 |
| US2-AS4 枚举无`na`/`wontfix`，终态只有`closed` | 通过 | 线上枚举4值open/fixing/verifying/closed |
| US3-AS1 上一版本Bug集合按`found`取、不按fix/发布状态 | 通过 | `ft_status v0.6.1`按`found==v0.6.0`取到1个；契约规则原文一致 |
| US3-AS2 未解决数计数条件`status != closed` | 通过 | 同上（closed的BUG-01未计入） |
| US3-AS3 上一版本无缺陷时未解决0、就绪为真 | 通过 | `ft_status v0.6.2`：“上一版本v0.6.1无缺陷（集合为空，空集为真）” |
| US3-AS4 自动聚合未实现时两个数字字段口径一致、类型仍`number` | 通过 | 契约`ver.bug_total/bug_open`仍`number`，`bug_aggregate_impl`列为非目标 |
| US4-AS1 无`tf-bug`时脚本建表并建12字段、回读通过 | 通过 | 临时实例（18094）：`bug_create_1.log`建表+12字段，回读“12字段与契约一致，行数=0”，exit0 |
| US4-AS2 再次执行不产生新字段、退出码0 | 通过 | `bug_create_2.log`：12个`[skip]`，exit0；线上`--dry-run`同样12跳过、新建0 |
| US4-AS3 同id但配置不符时报冲突、非0退出、不修改 | 通过 | 把`tf-b-status`改名“状态X”后执行：exit1，报“名称状态X≠状态”，字段未被改回 |
| US4-AS4 建表后现有三表字段/行/计算值不变 | 通过 | 临时实例建表前后三表快照一致；线上三表字段集合与`tf011/*.after1.json`一致 |

成功标准：

| 条目 | 结论 | 证据 |
|---|---|---|
| SC-001 board@2可解析、bug12字段、键全局无重复 | 通过 | 53键、无重复、四表16/16/9/12 |
| SC-002 线上`tf-bug`逐项一致、无契约外字段 | 通过 | `compare_bug.py`“核对问题：无” |
| SC-003 脚本连续执行两次第二次全跳过 | 通过 | 线上`--dry-run`12跳过；临时实例第二次12跳过、exit0、字段数仍12 |
| SC-004 现有三表前后字段集合与行集合无差异 | 通过 | 临时实例前后快照一致；线上字段集合与建表后快照一致 |
| SC-005 `011-AR`场景数/任务总数与spec/tasks一致 | 通过 | spec 15个`Given`、tasks 18个`T`；线上`011-AR`=15/18 |

## 四、014三个MSskill

说明：`specs/`下**没有014的spec目录**（V061-01），因此按“技能自述+实测证据”核对，无法做场景级验收。

| 项 | 结论 | 证据 |
|---|---|---|
| ms-update 平台现状 | 通过 | 独立跑`ms_sync.py --report`：项目用例260、模块`TF·tableflow v0.6.0`65条、用例名保留场景号 |
| ms-update 计划存在 | 通过 | `--report`与`ms_run.py --list`均读到计划`tableflow v0.6.0·契约与技能验收`（`1744872984176246784`） |
| ms-update 幂等/写后读回 | 未独立复跑 | 只在t4记录中（`新建0/更新0/跳过65`）；本轮不向共享MS写入 |
| ms-implement 计划内关联 | 通过（缺口确认） | `ms_run.py --list`：“关联用例 0 条”，与t4自述一致 |
| ms-implement `/run`回写链 | **未验证** | 计划内无关联行，无`id`可回写；MS无关联写入API（t4已实测18路径500） |
| ms-summary 扫描口径 | 通过 | `ms_summary.py --dry-run`独立复现：23条→ERROR0/BLOCKED待判定7/SUCCESS16，与`final-dryrun.log`一致 |
| ms-summary 轴1（执行记录id去重） | 通过 | `final-apply.log`：同记录重跑“跳过｜已消费→BUG-01”，0新增 |
| ms-summary 轴2（缺陷实体合并） | 通过 | 独立跑`--defect-file defect-02-merge-demo.json --dry-run`：“合并到 BUG-01（追加MS用例100338，复现+1）” |
| ms-summary 真写与回读 | 通过 | 线上`tf-bug/BUG-01`：12字段、status=closed、severity=major、source=test、specs=[014-AR]、found=[v0.6.0]、fix=[]、ms=100337；`changes`有两批审计（12:37创建、12:39关闭） |
| ms-summary 关闭需人确认 | 通过 | `--close BUG-01 --reason …`未加`--confirm-close`：输出“关闭需人确认：加--confirm-close才会写closed”，未写入 |
| ms-summary 执行证据 | 通过 | `.tmp-shots/ms-evidence/008-US1-AS1/{check.log,result.json}`，sha256前16位`81f0d4d419c575ca`/`cf6696ba0297d77d`与`runlog.jsonl`一致 |

## 五、v0.6.0的8条缺陷修复回归

| 缺陷 | 结论 | 复核证据 |
|---|---|---|
| V060-01 契约与skill口径冲突 | 通过 | skill对齐board@2：53字段名0缺失、旧ver字段名（开发进度/测试进度/未清Bug数/Bug已清空/回归通过/文档状态）命中0、无“没有第四张表”；`specs/008-board-contract/conflicts-t007.md`16条冲突+改写记录 |
| V060-02 挂版本规则 | 通过 | 四条拒绝实测：无version→failed+提问且不写行（404）；`v0.2.0`→“不晚于最近已发布v0.3.0”拒绝；`v0.3.0`→“只能挂planned”；`v9.9.9`→不存在；人指定`v0.6.0`→success+挂载+回读四项；清理后404 |
| V060-03 闸门标记 | 通过（契约侧；线上生效待部署） | 契约`conventions.gate_mapping`+`migrations.gate-tag-existing`（已执行，7项目`发布条件`补`gate:true`）；线上字段已见`gate:true`，但服务端为旧代码，**禁覆盖线上未生效**（队长口径）；仓库内`tests/test_computation_010.py`的gate用例通过 |
| V060-04 悬空后行不可编辑 | 通过 | 独立复现：删被引用行后改无关字段200（修前400）；显式提交悬空id仍400；清空关联200；必填缺失400、超max400（`verify_repair_v060.py`）；`tests/test_repair_v060.py`3例通过 |
| V060-05 契约未声明行id字段 | 通过 | 四表`row_id`齐全（ver.version/spec.id/change.id/bug.id） |
| V060-06 status跨域同名歧义 | 通过 | `conventions.status_values_scope`：同域互斥、跨域可同名、引用带域前缀 |
| V060-07 sum空集浮点 | 通过 | 契约`rules.empty_set_numbers`声明sum=0.0/count=0；复验落库`'0'`/`'0.0'`/`true`/`null`，与契约一致 |
| V060-08 010 SC-003证据不足 | 通过 | `specs/010-computation/spec.md`新增“SC-003的核验方法与基线”（基线7项目22表192行、sha256`b4e353c5…`） |

补充回归：`verify_010.py`重跑US1–US4逐条通过，输出与我v0.6.0验收日志逐行一致；`check_008.py`在board@1 rev3上通过（16/16/9、41键无重复、闸门4）。

## 六、缺陷登记（V061-01…07）

> bug表（011）已上线，但本轮按任务要求先写本文件；如需登记进`tf-bug`，可用`skills/ms-summary`的`--defect-file`通道（本条不代写）。

### V061-01 [高] 014没有spec，验收与看板统计缺依据

- 现象：`specs/`下无014目录（`001…013`、`015`存在）；`skills/ms-update|ms-implement|ms-summary`已交付并实测。看板`014-AR`的`场景数`/`任务总数`为空（`011-AR`为15/18），`场景总数=sum`偏小。
- 复现：`ls specs/ | grep 014`（无输出）；`GET /api/tables/tf-indep/table`中`014-AR`两个数字字段为`None`。
- 影响：014的3个skill无验收场景可核对，只能按自述与证据验证；看板统计与“按spec流程”要求脱节。
- 建议承接方：doc（补`specs/014-ms-skills/spec.md`与tasks）或队长明确014豁免并回填看板两列。

### V061-02 [中] 011的“关闭缺陷写入期校验”未实现

- 现象：契约`rules.bug_closed_evidence`要求置`closed`时满足其一（修复版本+可核验证据，或证据写明不修复且剩余事项为空），但写接口无校验：临时实例写入`BUG-99`（closed、证据空、修复版本空、剩余事项空）返回`success`。
- 复现：见`.tmp-shots/qa-v061/`同法脚本（POST `/api/agent/tables/tf-bug/rows/BUG-99`，values含`tf-b-status=closed`、`tf-b-evidence=""`、`tf-b-fix=[]`）。
- 说明：契约已标注“写入期校验，后续需求实现”，故记为**未实现项**而非回归；BUG-01的实际关闭数据合规（证据+rest空）。
- 建议承接方：另立需求（011后续）实现；本轮不必热修。

### V061-03 [中] 契约文件编辑窗口不可解析，连带建表脚本失败

- 现象：12:45:19时`board@2.yaml`第399行`current: '…`单引号未闭合，YAML解析失败（`ParserError`），`create_bug_table.py`因此exit1；12:45:40后恢复（新sha`d45d159f…`）。
- 复现：`bug_create_1.log`（首次失败堆栈）与`bug_create_2.log`（恢复后成功）。
- 影响：契约被多人并发编辑时，任何读取方（脚本/skill/验证）都会短暂失败。
- 建议承接方：契约编辑改原子写（临时文件+rename），提交前跑一次`yaml.safe_load`。

### V061-04 [低] `calculation.py`基线漂移，修复报告称“未改”

- 现象：v0.6.0验证基线为`e10b97aa…`（12:22），当前为`f22191bd…`（12:39）；t9报告第十节称“calculation.py最终未改”。
- 影响：行为复验一致（`verify_010`输出逐行相同、pytest123 passed），但缺少diff记录，重放验证时无法确认只改了注释/格式。
- 建议：t9补充“改了什么再撤回”的说明，或恢复基线sha并重跑。

### V061-05 [低] MS三个skill默认用系统`python3`，backend venv下直接失败

- 现象：用`backend/.venv/bin/python`运行`ms_sync.py`/`ms_run.py`报`ModuleNotFoundError: No module named 'cryptography'`（`ms_env`→`ms_client`依赖）；换`/usr/bin/python3`后正常。
- 复现：`ms_sync_report.log`首段堆栈。
- 建议：技能页写明“用系统python3（含cryptography）运行”，或提供`requirements`。

### V061-06 [低] 看板`014-AR`两列统计为空

- 现象：`场景数`/`任务总数`为`None`，而`011-AR`为15/18。
- 影响：`场景总数`/`任务总数`求和偏小，`ft-status`的拆分建议可读性下降。
- 建议：与V061-01一并处置。

### V061-07 [低] BUG-01关闭时清空`剩余事项`，原待办只留证据文本

- 现象：创建时`剩余事项`=“待建tableflow独立MS项目后迁出；当前以模块…隔离”，关闭时被清空（契约要求closed时rest为空）；`changes`里可见create/update两笔。
- 影响：符合契约，但“待办去哪了”只能从证据文本里读。
- 建议：后续在契约或skill中约定“关闭时把原待办写入证据固定段落”（ms_summary已部分这么做）。

## 七、未验证与风险

| 项 | 状态 | 原因 |
|---|---|---|
| 014全部验收场景 | 未验证 | 无spec（V061-01） |
| ms计划↔用例关联与`/run`回写 | 未验证 | MS版本无关联写入API；计划内0行（与t4自述一致） |
| 011 US2-AS2关闭写入期校验 | 未验证 | 未实现（V061-02） |
| 线上闸门禁覆盖生效 | 未验证 | 线上旧代码未部署；按队长口径以仓库用例+部署后`--probe-override`判定 |
| 012/013 | 本轮外 | 属t12范围；013代码已在仓库（pytest123含其用例） |

## 八、证据清单（`.tmp-shots/qa-v061/`）

| 文件 | 内容 |
|---|---|
| `compare_bug.py` | 契约bug表↔线上`tf-bug`逐字段核对 |
| `create_bug_dryrun.log` | 线上`--dry-run`：12跳过、新建0 |
| `bug_create_1.log`/`bug_create_2.log`/`bug_create_conflict.log` | 临时实例建表、幂等、冲突（含12:45:19解析失败堆栈） |
| `temp_three_tables_before.json` | 建表前三表快照（与建表后比对一致） |
| `verify_repair_v060.py` | V060-04独立复现（400→200、显式悬空仍400、必填/min/max仍400） |
| `verify_010_after.log` | 010验收重跑（与v0.6.0日志逐行一致） |
| `tf_update_runner.py`/`tf_update_v060.log` | V060-02四条拒绝+成功登记+清理 |
| `ms_run_list.log`/`ms_sync_report.log`/`ms_summary_dryrun.log` | 014三skill只读复核 |
| `ft_status_runner.py`/`ft_status_v061.log` | 015同步board@2后的v0.6.1报告（含bug闸门） |
| `pytest.log`/`pin-final.txt` | 123 passed；本轮sha固定点 |

## 九、给队长的建议

1. V061-01（014无spec）是v0.6.1唯一的“高”：要么补spec并回填看板两列，要么明确豁免并写入交付说明，否则014无法按spec流程验收。
2. V061-02按契约“后续需求实现”延后，不阻塞本轮；011的其余口径已与线上一致。
3. V061-03建议立即改契约写入方式（原子写+提交前解析），避免并发编辑再次打断脚本。
4. 部署010/013后补两次探针：`--probe-override`（闸门禁覆盖）与`ft-status v0.6.1`（bug闸门），以线上事实替换“未验证”。
5. `v0.2.0`按队长决定保持`planned`，本报告不登记为缺陷。

---

## 十、修复记录（t11，2026-11-19）

> 承接第六节7条缺陷。本轮未写线上业务行（仅只读GET与本地临时文件）；契约文本未改（board@1/board@2保持t19后的`142ccf06…`/`d45d159f…`）。
> 归属：V061-01/06已由`t20`（ms）承接补`specs/014-ms-skills`；本任务只修后端/仓库门禁与skill文档类缺陷。

### 10.1 逐条处置

| 缺陷 | 结论 | 动作与证据 |
|---|---|---|
| V061-01[高] | 已由`t20`关闭（只读核对） | `specs/014-ms-skills/{spec.md,tasks.md}`已落盘；看板`014-AR`回填场景数22/任务总数28、`implement=done`、验收仍pending。本任务未改014文件 |
| V061-02[中] | 按契约延后（不热修） | 契约`rules.bug_closed_evidence`明标“写入期校验，后续需求实现”，本报告亦建议另立需求；本轮不改写接口 |
| V061-03[中] | **已修复** | 新增`backend/src/tableflow/contracts.py`（重复键报错的YAML加载、结构断言、`write_contract_atomic`先校验后`tmp+os.replace`）；新增`backend/scripts/check_contracts.py`（默认校验两契约；`--pre-write`校验通过才原子替换）；新增`backend/tests/test_contracts.py`10例。复验：CLI对两契约exit0；`--pre-write`对重复键内容exit1且原文件未变、临时文件已清理 |
| V061-04[低] | **已修复** | `calculation.py`恢复v0.6.0基线`e10b97aa…`。根因：t9为V060-07加的docstring块在回退时吞掉了结束`"""`前的换行，末行变成`…仍允许。"""`（差异只在docstring，行为不变）。修复后sha256=`e10b97aa94fd46ccd48b539244c464951fc37d57c01e4530da98e751d535f719`，git blob=`330b679`与`tf-v060.patch`的postimage一致；pytest全绿 |
| V061-05[低] | **已修复（文档）** | `skills/ms-update|ms-implement|ms-summary/SKILL.md`各加“运行环境（脚本解释器）”：用系统`python3`，venv缺`cryptography`。实测`ms_sync.py --report`：`/usr/bin/python3`exit0（用例总数260），`backend/.venv/bin/python`exit1（`ModuleNotFoundError: cryptography`） |
| V061-06[低] | 已由`t20`关闭（只读核对） | 看板`014-AR`两列已回填：场景数22、任务总数28（只读GET，与spec/tasks一致） |
| V061-07[低] | **已修复（脚本自动）** | `skills/ms-summary/SKILL.md`关闭段改为**脚本自动**：`ms_summary.py --close` 先取 `rest` 原文写进证据 `【原剩余事项】<原文>`，再追加 `【关闭】<理由>` 并清空 `rest`；`readback()` 新增必含子串校验（原 rest 非空时证据须含该段）。演练见 `.tmp-shots/ms-014/close-merge.log`：临时行 BUG-02 写→关→读回→删除，空 rest 分支与负向校验各验一次；BUG-01 未变（36 条变更记录，最新仍 12:39:14） |

### 10.2 重跑结果（2026-11-19 13:0x）

| 命令 | 结果 | 日志 |
|---|---|---|
| `cd backend && .venv/bin/python -m pytest -q` | `133 passed, 1 warning`（t9后123 + 契约用例10） | `.tmp-shots/repair-v061/pytest.log` |
| `python3 backend/scripts/check_contracts.py` | 两契约exit0：YAML可解析、无重复键、结构完整（含row_id/gate_mapping/status_values_scope/migrations） | `contracts-cli.log` |
| `check_contracts.py --pre-write`（重复键内容） | exit1“拒绝写入：重复键”；目标文件未改写、无残留临时文件 | `pre-write.log` |
| `calculation.py`哈希 | `e10b97aa…`（v0.6.0基线）；git blob `330b679`=patch postimage | `sha256sum`/Python blob计算 |
| `ms_sync.py --report`（V061-05） | 系统python3 exit0（260条）；backend venv exit1（cryptography缺失） | `interpreter-real.log`、`venv-report.err` |

### 10.3 未闭环与需队长决策

1. V061-01/06：已由`t20`关闭（014 spec落盘、`014-AR`=22/28）；本任务只读核对，未代改。
2. V061-02：保持“未实现”，待011后续需求；若提前热修，会改变`closed`写入行为，需另开任务。
3. V061-05 为文档约定；V061-07 已由 t22 落地为脚本自动（含读回校验），不再是人工步骤。

### 10.4 本轮改动文件与sha256

| 文件 | sha256 |
|---|---|
| `backend/src/tableflow/calculation.py` | `e10b97aa94fd46ccd48b539244c464951fc37d57c01e4530da98e751d535f719` |
| `backend/src/tableflow/contracts.py` | `17ef16dc3fe48134b1b30ac6866f847f0215835ce2aec9486dffacb306113aa7` |
| `backend/scripts/check_contracts.py` | `e7971c60449bd11c6bb7511c6122d483c5c04f1f4d6c180a5e49adb7551f6c29` |
| `backend/tests/test_contracts.py` | `f5bdcd87aba9a82f80d123c922affe12a99c17ab6bf40eeade04a2df8fafeb53` |
| `skills/ms-update/SKILL.md` | `736db687a876de2851d2f4e680b182a9d8267121f0c6cbfd699220c513b59e8d` |
| `skills/ms-implement/SKILL.md` | `ff5b0dc6cd94480b41671196f1171e28604c4a9a805d5b662abf8d024a585510` |
| `skills/ms-summary/SKILL.md` | `5164e68686427f2feb723802a48a877d4c86ee70a680c2f577c2ac140b34b7b9` |
| `skills/ms-summary/assets/ms_summary.py` | `23b721e9c89c19a4aa4fa0b929c000ac3283719d1a9d25c0667f1833888ba8ecd` |
| `specs/008-board-contract/board@1.yaml`（未改，复核） | `142ccf067ab372858a2cb898e78506f7a6dcc8adeb86a1e16210d6d507930537` |
| `specs/011-bug-table/board@2.yaml`（未改，复核） | `d45d159f149497e3269ee4d5445e11fef808ba3683c66b99b4688fa9b4b088a1` |

### 10.5 复核补充（2026-11-19，按ms对t20的交叉核对）

- **V061-07 最终形态**：t22 已把 `ms_summary.py --close` 改为自动并入 `【原剩余事项】` 并加读回必含校验，`SKILL.md` 措辞同步为“脚本自动”。sha256：SKILL.md `5164e686…`、脚本 `23b721e9…`（§10.4 表已同步）。
- **V061-01/06状态更新**：`t20`已完成——`specs/014-ms-skills/{spec.md,tasks.md}`落盘，看板`014-AR`场景数22/任务总数28、`implement=done`（只读GET核对）；缺陷关闭，不代改、不验收。
- 其它skill（`ms-update`/`ms-implement`）本轮未再改动；契约文件未动。
