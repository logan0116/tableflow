# Tasks: MS三技能（ms_update / ms_implement / ms_summary）

**Input**: `specs/014-ms-skills/spec.md`（V061-01补录；spec由已交付实现与实测证据反推）

**范围**: `skills/ms-update/`、`skills/ms-implement/`、`skills/ms-summary/`三个技能与脚本；
不改`backend/`、不改`specs/008`与`specs/011`契约、不直写MS数据库。

## Phase 1: 口径与环境（前置）

- [x] T001定三skill写入边界：`ms-update`只写用例与计划、`ms-implement`只回写结果与证据、`ms-summary`只写缺陷；验证：三份`SKILL.md`的"不做什么"节与实现一致，无交叉写
- [x] T002定凭据口径：只经`ms_env`读`ms_creds.env`，不打印AK/SK、不发往非声明host；验证：`python3 ms_env.py`只输出AK前4位与长度，`_guard_host`拦截异host
- [x] T003定运行环境：必须系统`python3`（含`cryptography`），`backend/.venv/bin/python`报`ModuleNotFoundError`；验证：V061-05复现（`ms_sync_report.log`首段堆栈）
- [x] T004探明计划↔用例无关联写入端点（18个候选路径全`500 No static resource`），据此定"不直写DB、关联由人做"；验证：`ms_sync.py`的`probe_association()`输出`reachable:[]`，前端产物无写路径

## Phase 2: ms_update（用例与计划）

- [x] T005实现spec解析：`### User Story N - 标题 (Priority: Pn)`+`Acceptance Scenarios`编号项，提取Given/When/Then与US/AS号；验证：008=10、009=21、010=14、015=20，合计65
- [x] T006实现用例命名与前置条件：名字`<规格号>-US<n>-AS<m> <Then摘要>`、前置条件带`【来源】specs/<dir>/spec.md#USn-ASm`；验证：`--report`列出65条，前缀全部合规
- [x] T007实现写前查重（限本模块、按场景号前缀）+ `add`后补`update`落优先级 + full-update（先取detail、剥只读字段）；验证：首次写65条读回65/65
- [x] T008实现用例模块建/复用（`TF · tableflow v0.6.0`）；验证：模块id`1744872795197685760`，重跑复用不新建
- [x] T009实现计划模块与测试计划建/复用（`type=TEST_PLAN`）；验证：计划`tableflow v0.6.0 · 契约与技能验收`=`1744872984176246784`
- [x] T010验证幂等与漂移修复：重跑`新建0/更新0/跳过65`；人为改一条前置条件后重跑`更新1/跳过9`、再跑`更新0/跳过10`且改动被改回；验证：`.tmp-shots/ms-014/update-path.log`
- [x] T011实现只读体检`--report`：模块用例数、计划存在性与关联条数、关联端点探测；验证：输出项目用例260/本模块65/关联0/`reachable:[]`
- [x] T012实现写后读回核对（名称/模块/前置条件/步骤+预期四项，不符即failed）；验证：65/65通过，失败计数0

## Phase 3: ms_implement（执行结果回写）

- [x] T013实现`--list`：读计划内用例的关联行id与最近结果；0条时给界面挂载指引；验证：输出"关联用例 0 条"+指引
- [x] T014核实回写请求字段契约：`id(关联行id)/testPlanId/caseId/projectId/lastExecResult`五必填；验证：`POST /run {}`返回400，`messageDetail`逐个点名
- [x] T015实现结果枚举限缩与三态判定：只放行`SUCCESS/ERROR`（其余服务端静默空转），成功只认计划内`lastExecResult`读回；验证：枚举探测+caseId冒充探测（计划内仍0条）
- [x] T016实现证据账：`--evidence`文件必须存在，记`bytes`+`sha256前16位`写入`runlog.jsonl`；验证：`runlog.jsonl`两条记录与`runlog`路径输出
- [ ] T017**未验证**：有真实关联行时`/run`回写→读回一致（计划内关联0条、无关联写入API；按队长要求不直写DB，待人在界面挂载后补验）

## Phase 4: ms_summary（缺陷登记）

- [x] T018实现执行结果采集：用例级`lastExecuteResult`+计划级`lastExecResult`，每条带唯一记录id（`plan:<planId>:<linkId>:<lastExecTime>`/`case:<caseId>:<result>:<updateTime>`）；验证：扫描23条
- [x] T019实现归类口径：`ERROR`→候选、`BLOCKED`仅在有`--block-reason`时转候选、无原因→待判定、`SUCCESS/PENDING`→不登记；验证：7条BLOCKED全部待判定
- [x] T020实现轴1去重（消费账`.tmp-shots/ms-summary/consumed.json`）；验证：同记录重跑"跳过｜已消费→BUG-01"、新写0
- [x] T021实现轴2去重（标题归一化合并，追加MS用例号与`【复现】`计数，不新增字段）；验证：`defect-02-merge-demo`dry-run输出"合并到BUG-01（追加MS用例100338，复现+1）"
- [x] T022实现写`tf-bug`12字段并回读（单行+整表）；验证：`BUG-01`写入success、12字段回读一致
- [x] T023实现关闭需人确认（`--confirm-close`+可核验`--reason`，且要求SUCCESS晚于缺陷登记时刻）；验证：不加确认只提示；`008-US1-AS1`的SUCCESS早于登记未误报
- [x] T024实现`--defect-file`人工确认通道（证据用调用方原文、`【归类】`写"人工确认（无MS执行记录）"，不编造ERROR）；验证：`BUG-01`证据文本
- [x] T025验证`--dry-run`输出可逐条核对且不写平台；验证：`.tmp-shots/ms-summary/final-dryrun.log`（23条→ERROR0/BLOCKED待判定7/SUCCESS16）

## Phase 5: 登记与补录

- [x] T026更新看板`014-AR`阶段状态（`implement=done`、状态记三skill交付与BUG-01真写）；验证：读回`tf-i-implement=done`
- [x] T027补录本spec与tasks（V061-01），把"未验证范围"写进spec；验证：`specs/014-ms-skills/spec.md`的「未验证范围」5条与本清单T017对应
- [x] T028回填看板`014-AR`的`场景数`与`任务总数`，与spec场景数、本文件任务数一致；验证：读回两列分别等于22与28

> `acceptance=accepted`由需求方判定，不在本清单内；本需求状态为"有条件通过"（1项未验证见T017）。
