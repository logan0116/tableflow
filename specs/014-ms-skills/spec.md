# Feature Specification: MS三技能（ms_update / ms_implement / ms_summary）（v0.6.0）

**Feature Branch**: `014-ms-skills`

**Created**: 2026-11-19

**Status**: Implemented（有条件通过：5项未验证/受限，见「未验证范围」；其中核心未验证1项=计划↔用例关联与`/run`端到端，另有4项环境/证据限制）

**Input**: 需求014-AR：`ms_update`按版本创建用例与测试计划；`ms_implement`执行测试并回写结果与证据；`ms_summary`从执行结果总结缺陷并登记到看板bug表（去重、复现计数、关闭）。依赖008（契约口径）与011（bug表口径）。

**补录说明**：本spec按V061-01在交付**之后**补写——三个skill与脚本已实现并实测，spec从「已实现的行为+实测证据」反推，
只写做过的事；没跑通的部分单列在「未验证范围」，不写成验收场景。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 用例靠手点 | v0.6.0的008/009/010/015共65个验收场景，此前MS里一条对应用例都没有 | 版本验收无平台记录，回归无载体 |
| 用例与spec脱节 | 手建用例改名/改步骤后无法追溯到`spec.md`的哪一条 | 改了spec不知道哪条用例要跟着改 |
| 计划挂不上用例 | MS v3.6.9-lts无「计划↔用例」关联写入端点（18个候选路径实测全部`500 No static resource`） | 计划只有壳，`/run`没有关联行id可用 |
| 执行结果写不进平台 | 用例级无结果登记端点（`/functional/case/run|exec|execute|result`、`/functional/case/exec/history`全404） | 结果只能留在Agent日志里 |
| 缺陷靠人肉搬 | 执行失败的用例要人读日志再手写bug行，重复缺陷各记一行 | 复现次数丢失，重复行污染缺陷口径 |
| 014无spec（V061-01） | `specs/`下没有`014-ms-skills/`，看板`014-AR`的`场景数`/`任务总数`为空 | 无法按spec流程验收，`场景总数=sum`偏小 |

## Clarifications

### Session 2026-11-19（补录时确认）

- Q: 三个skill的边界怎么切？ → A: `ms-update`只写用例与计划；`ms-implement`只回写执行结果与证据；`ms-summary`只写缺陷。三者都不改`specs/`、不改看板需求行（除本需求自身登记）。
- Q: 计划↔用例关联怎么办？ → A: 该版本没有写端点，**不直写数据库**（共享测试实例，绕过平台校验会留下不可复现的后遗症）。关联由人在界面完成；skill负责把缺口说清，不假装成功。
- Q: 没有关联行时`ms_summary`读什么？ → A: 读用例库的`lastExecuteResult`（用例级，绕开计划）+ 历史计划的`lastExecResult`（计划级）。两条都支持，读到的每条记录带唯一id。
- Q: 复现次数存哪个字段？ → A: 不新增字段。`board@2`的`bug`表只有`证据`与`剩余事项`两个记录字段，复现次数写进`证据`的`【复现】N次`，由文本推得（表结构以011契约为准，不由014改）。
- Q: 关闭谁能做？ → A: 只有人。脚本给建议（该用例在缺陷登记**之后**出现`SUCCESS`）并要求`--confirm-close`，永不自动关。
- Q: 人工确认的缺陷会不会被写成"执行失败"？ → A: 不会。`--defect-file`通道登记的行，证据用调用方给的原文，`【归类】`写"人工确认（无MS执行记录）"，分类字段`source`可为`review`，不伪造`ERROR`。
- Q: 运行环境有什么硬约束？ → A: 必须用系统`python3`（`ms_env→ms_client`依赖`cryptography`）；`backend/.venv/bin/python`里没有该包，直接`ModuleNotFoundError`（V061-05）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 把spec场景同步成MS用例与计划 (Priority: P1)

给定一组spec，`ms_update`把每个验收场景变成一条MS功能用例（名字保留场景号、前置条件指回spec原文），
并建/复用本版本的测试计划；重复执行不产生重复用例。

**Why this priority**: 没有用例就没有版本验收的载体，后面的执行与缺陷登记都无从谈起。

**Independent Test**: 对008/009/010/015执行`--dry-run`再`--apply`，MS模块里得到65条用例，
名字全部以`NNN-USn-ASm`开头；重跑时`新建0/更新0/跳过65`。

**Acceptance Scenarios**:

1. **Given** specs 008/009/010/015，**When** 解析，**Then** 每个验收场景生成一条用例（008=10、009=21、010=14、015=20，合计65），用例名以`<规格号>-US<故事号>-AS<场景号>`开头。
2. **Given** 首次执行`--apply`，**When** 写入平台，**Then** 建出用例模块并逐条`GET /functional/case/detail/{id}`读回，名称/模块/前置条件/步骤+预期四项全部一致（实测65/65）。
3. **Given** 用例已同步，**When** 再次执行`--apply`，**Then** 输出`新建0/更新0/跳过65`且读回仍65/65（幂等）。
4. **Given** 某条用例在平台上被改动（前置条件与spec不一致），**When** 重新同步，**Then** 该条走full-update就地改写、其余跳过（实测`更新1/跳过9`，再跑`更新0/跳过10`，改动被覆盖回spec口径）。
5. **Given** 本版本还没有测试计划，**When** 执行`--apply`，**Then** 建计划模块与计划并写回id，计划`type=TEST_PLAN`（实测`1744872984176246784`）。
6. **Given** 计划已存在，**When** 再执行，**Then** 复用同名计划、不重复创建；执行结束输出「已关联用例数」。
7. **Given** 只想知道平台现状，**When** 执行`--report`，**Then** 只读输出模块用例数、计划存在性与关联条数、关联端点探测结果，不产生任何写请求。
8. **Given** 计划↔用例需要关联，**When** 尝试写入关联，**Then** skill如实报告"该版本无关联写入端点（18个候选全404）、需界面操作或人工决定直写DB"，不把0条关联说成已挂载。

---

### User Story 2 - 执行结果按计划回写（含证据） (Priority: P1)

`ms_implement`从计划里读用例（拿关联行id），把真实执行结果`SUCCESS/ERROR`与证据文件回写，
读完回核对才认账；没有关联行时拒绝回写并说明下一步。

**Why this priority**: 结果写不进平台，"跑过"就只是口头结论；证据与结果必须能对上。

**Independent Test**: 对空计划执行`--list`得到"关联用例0条"并提示界面关联；对不存在的证据文件执行回写被拒；
对`FAIL/BLOCKED`取值脚本直接拒绝（服务端会静默空转）。

**Acceptance Scenarios**:

1. **Given** 指定计划，**When** 执行`--list`，**Then** 打印计划内每条用例的关联行id与最近结果；0条时明确写"尚未关联用例"并给出界面挂载指引。
2. **Given** 计划内没有目标用例的关联行，**When** 回写结果，**Then** 脚本拒绝并说明"先关联再回写"，不向平台发任何请求。
3. **Given** 要回写的结果不是`SUCCESS`/`ERROR`（如`FAIL`/`BLOCKED`/`SKIP`/`PENDING`），**When** 调用脚本，**Then** 直接拒绝——实测这些取值服务端返回`100200`但什么都不写，属静默空转。
4. **Given** 服务端返回`200/100200`，**When** 判定是否写入成功，**Then** 只认`/test-plan/functional/case/page`读回的计划内`lastExecResult`是否变化；实测把`caseId`当关联行id传时计划内仍`total=0`，不能当成功。
5. **Given** 回写时给了证据文件，**When** 记账，**Then** 每个文件记`bytes`与`sha256前16位`并追加到`runlog.jsonl`；证据文件不存在则拒绝回写。
6. **Given** 回写请求体，**When** 漏字段，**Then** 服务端`400`的`messageDetail`逐个点名`id/testPlanId/caseId/projectId/lastExecResult`五个必填项，字段契约以该报错文本为准。

---

### User Story 3 - 从执行结果总结缺陷并登记到bug表 (Priority: P1)

`ms_summary`扫描执行结果，把`ERROR`与"由产品缺陷导致的阻塞"转成缺陷候选，
按执行记录与缺陷实体两轴去重后写进`tf-bug`，并在后续复测通过时提示关闭（人确认）。

**Why this priority**: 缺陷不去重就是噪音；没有复现计数就分不清普遍问题与个例。

**Independent Test**: 对真实执行结果`--dry-run`，输出可逐条核对且不写平台；真写一行后单行与整表回读一致，
证据里能读到MS用例号；同一记录重跑不新增行。

**Acceptance Scenarios**:

1. **Given** 平台现有执行结果，**When** `--dry-run`，**Then** 汇总`ERROR`/`BLOCKED待判定`/`SUCCESS`三类计数（实测23条：ERROR 0、BLOCKED 7、SUCCESS 16），并逐条列出待判定记录id。
2. **Given** 一条`BLOCKED`没有给出产品缺陷原因，**When** 归类，**Then** 进"待判定"不登记；只有`--block-reason`显式给出原因才转缺陷候选（环境/设备/数据阻塞不是产品缺陷）。
3. **Given** 某次执行记录已经被消费，**When** 重跑，**Then** 输出"跳过｜已消费→BUG-01"、不新增行（轴1：执行记录唯一id）。
4. **Given** 同一缺陷被另一条用例命中（标题归一化相同），**When** 登记，**Then** 合并到已有行：追加MS用例号、证据里`【复现】`次数+1，不新建行（轴2：缺陷实体）。
5. **Given** 一条已核实的缺陷，**When** `--apply`，**Then** 在`tf-bug`写出12个字段（编号/标题/状态/严重度/来源/关联规格/发现版本/修复版本/证据/剩余事项/MS用例号/负责人）并单行+整表回读一致（实测`BUG-01`）。
6. **Given** 缺陷来自某条MS用例，**When** 看`证据`与`MS用例号`，**Then** 能直接指到MS用例号（实测`ms=100337`，`证据`首段含该号与用例名）。
7. **Given** 某缺陷的用例后来出现`SUCCESS`（且晚于缺陷登记时刻），**When** 请求关闭，**Then** 未加`--confirm-close`只输出"关闭需人确认"不写入；加确认后才写`closed`并清空`剩余事项`、证据追加`【关闭】`；SUCCESS早于登记时不误报。
8. **Given** 一条已核实但无`ERROR`执行记录的缺陷（如环境缺陷），**When** 用`--defect-file`登记，**Then** 行的证据用调用方原文、`【归类】`写"人工确认（无MS执行记录）"，不编造`ERROR`结果。

---

## 未验证范围（mandatory，如实列出）

1. **计划↔用例关联**：MS v3.6.9-lts无关联写入端点（`batch/add`、`batch/relate`、`relate`、`association/{id}/case`
   等18个候选路径实测全部`500 No static resource`；前端产物也搜不到写路径）。本轮**没有**通过任何通道建立关联，
   计划`tableflow v0.6.0 · 契约与技能验收`内关联用例数恒为0；按队长要求不直写MS数据库。
2. **`/run`回写端到端**：`POST /test-plan/functional/case/run`存在、五个必填字段已由400报错逐个核实，
   但"有真实关联行→回写成功→读回一致"这条链**未跑通**（无关联行id），故不声称通过。
   已知反例：把`caseId`当关联行id传，服务端回`100200`、计划内仍0条，用例库该用例`lastExecuteResult`却被改写。
3. **MS项目归属**：`MS_PROJECT_ID`指向`demo-cnc v3.0`（`1695095876583694336`），tableflow没有独立MS项目，
   65条用例与另一产品共库，只能以独立模块`TF · tableflow v0.6.0`隔离。该环境缺陷已登记`BUG-01`并按"独立模块隔离"关闭
   （队长2026-11-19决定）。
4. **探测副作用**：`/run`字段探测时把`008-US1-AS1`的`lastExecuteResult`写成`SUCCESS`；
   已用对该用例的真实执行（解析`board@1.yaml`：ver16/indep16/dep9、闸门4个）覆盖，证据`.tmp-shots/ms-evidence/008-US1-AS1/`
   与`runlog.jsonl`，skill与记录均保留。
5. **计划级`ERROR`样本为0**：现有计划里`ERROR`为0条，缺陷归类链路只在`SUCCESS`与历史`BLOCKED`上验证过。

## Requirements *(mandatory)*

- **FR-001**: `ms_update`MUST按`specs/<feature>/spec.md`的`**Acceptance Scenarios**`逐场景生成用例，一条场景一条用例。
- **FR-002**: 用例名MUST以`<规格号>-US<故事号>-AS<场景号>`开头；前置条件MUST含`【来源】specs/<dir>/spec.md#USn-ASm`。
- **FR-003**: 写前MUST查重——按场景号前缀、**限定在本模块内**匹配（场景号跨spec会撞）；写后MUST`GET /functional/case/detail`读回四项。
- **FR-004**: `ms_update`MUST支持建/复用测试计划；计划`type`MUST为`TEST_PLAN`（写`ALL`会导致计划打不开）。
- **FR-005**: `ms_update`MUST NOT直写数据库、MUST NOT修改`specs/`；无关联端点时MUST如实报告缺口。
- **FR-006**: `ms_implement`MUST以`/test-plan/functional/case/page`的关联行`id`为回写键，`caseId`不能代替。
- **FR-007**: `ms_implement`MUST只放行`SUCCESS`/`ERROR`，其它结果取值MUST拒绝（服务端静默空转）。
- **FR-008**: 回写成功MUST以计划内`lastExecResult`读回为准，MUST NOT以HTTP码或`code:100200`为准。
- **FR-009**: 没有证据文件MUST NOT回写；证据MUST记`bytes`+`sha256`并落`runlog.jsonl`。
- **FR-010**: `ms_summary`MUST支持两类输入（用例级`lastExecuteResult`、计划级`lastExecResult`），每条记录带唯一id。
- **FR-011**: 归类MUST区分`ERROR`、`BLOCKED（有产品缺陷原因）`、`BLOCKED（无原因→待判定）`、`SUCCESS`、`PENDING`。
- **FR-012**: 去重MUST两轴：执行记录id（消费账`.tmp-shots/ms-summary/consumed.json`）与缺陷实体（标题归一化合并）。
- **FR-013**: 写`tf-bug`MUST遵守`specs/011-bug-table/board@2.yaml`：12字段、枚举用英文value、关系字段为行id数组、`found`单值。
- **FR-014**: 复现次数MUST写在`证据`的`【复现】N次`，MUST NOT为此新增表字段。
- **FR-015**: `closed`MUST由人确认（`--confirm-close`+可核验`--reason`），且要求该用例在缺陷登记后出现`SUCCESS`；脚本MUST NOT自动关闭。
- **FR-016**: 人工确认的缺陷MUST NOT被描述成`ERROR`执行结果；证据MUST由调用方提供且指到MS用例号。
- **FR-017**: 三个skill MUST用系统`python3`运行（依赖`cryptography`）；凭据只从`ms_env`读，MUST NOT打印AK/SK。

## Success Criteria *(mandatory)*

- **SC-001**: 对008/009/010/015执行后，MS模块内用例数=65，且每条名字保留场景号、`detail`读回四项齐备（实测65/65）。
- **SC-002**: 连续执行两次，第二次`新建0/更新0/跳过65`；平台内容被人改动后重跑能就地改回（实测`更新1/跳过9`→`更新0/跳过10`）。
- **SC-003**: 计划存在且`type=TEST_PLAN`；`--report`能读出模块用例数与计划关联条数（0条时明确说明原因）。
- **SC-004**: 无关联行时`ms_implement`拒绝回写；证据缺失时同样拒绝；`100200`不被当作成功。
- **SC-005**: `ms_summary --dry-run`输出可逐条核对（23条→ERROR0/BLOCKED待判定7/SUCCESS16）；真写一行后12字段回读一致、证据指到MS用例号。
- **SC-006**: 同一执行记录重跑0新增；同标题缺陷落到合并而非新建；关闭未确认时不写。
- **SC-007**: 看板`014-AR`的`场景数`/`任务总数`与本spec场景数、`tasks.md`任务数一致。

## Non-Goals

- 不建MS独立项目（属环境治理，另立事项）；不直写MS数据库补关联。
- 不改`specs/008`/`specs/011`的契约口径，不改`backend/`代码。
- 不做用例评审流转、不做缺陷严重度定级规则、不自动关闭缺陷、不自动判定"是不是产品缺陷"。
- 不覆盖接口用例/场景用例的同步（只做功能用例）。

## Key Entities

- **用例同步（Sync）**：spec场景→MS功能用例；键=场景号前缀+模块；幂等靠"读回比对"。
- **计划（Plan）**：`TEST_PLAN`类型，挂计划模块；与用例的关联在该版本只能人做。
- **执行记录（ExecutionRecord）**：`plan:<planId>:<linkId>:<lastExecTime>`或`case:<caseId>:<result>:<updateTime>`，消费后进账。
- **缺陷实体（DefectEntity）**：标题归一化后的同一缺陷；承载复现次数与多条MS用例号。
- **证据账（EvidenceLedger）**：`runlog.jsonl`，每条含文件路径/字节数/sha256前16位。

## 场景 ↔ 证据对应表（验收用）

| 场景 | 证据 |
|---|---|
| US1-AS1 | `ms_sync.py`解析输出：008=10/009=21/010=14/015=20；`--report`列65条，名字前缀齐 |
| US1-AS2 | `ms_sync.py --apply`：新建65｜失败0｜读回核对通过65/65 |
| US1-AS3 | 同命令二次：新建0/更新0/跳过65/读回65/65 |
| US1-AS4 | `.tmp-shots/ms-014/update-path.log`：注入漂移→`更新1/跳过9`→再跑`跳过10`→探针被清 |
| US1-AS5 | 建计划模块`1744872966996377600`、计划`1744872984176246784`（type=TEST_PLAN） |
| US1-AS6 | 第二次`--apply`输出"（复用）"；`--report`/`ms_run --list`读到同一计划id |
| US1-AS7 | `ms_sync.py --report`：项目用例260、本模块65、关联0条、关联端点探测`reachable:[]` |
| US1-AS8 | 18候选路径探测日志：全部`500 No static resource`；SKILL.md第7节与报告均写明缺口 |
| US2-AS1 | `ms_run.py --list`："关联用例 0 条"+界面挂载指引 |
| US2-AS2 | `ms_run.py --case 008-US1-AS1 …`：拒绝"计划里没有…" |
| US2-AS3 | `lastExecResult`取值探测：`FAIL/BLOCKED/SKIP/PENDING`→`100200`无动作；`SUCCESS/ERROR`才进回写分支 |
| US2-AS4 | caseId冒充探测：计划内`total=0`而用例库`lastExecuteResult=SUCCESS` |
| US2-AS5 | `ms_run.py`证据校验（不存在即退出）；`runlog.jsonl`含bytes+sha256 |
| US2-AS6 | `POST /run {}`的400文本：`testPlanId/lastExecResult/caseId/id/projectId` |
| US3-AS1 | `ms_summary.py --dry-run`：23条→ERROR0/BLOCKED待判定7/SUCCESS16（`.tmp-shots/ms-summary/final-dryrun.log`） |
| US3-AS2 | 同上：7条BLOCKED逐条"未给出产品缺陷原因"；`--block-reason`才转候选 |
| US3-AS3 | `final-apply.log`重跑："跳过｜已消费→BUG-01"、新写0 |
| US3-AS4 | `defect-02-merge-demo.json --dry-run`："合并到BUG-01（追加MS用例100338，复现+1）" |
| US3-AS5 | `tf-bug/BUG-01`：12字段、单行+整表回读一致 |
| US3-AS6 | `BUG-01`：`ms=100337`、证据首段含`num=100337`与用例名 |
| US3-AS7 | `--close BUG-01 --reason …`：输出"关闭需人确认"未写入；关闭建议按时间比较不误报 |
| US3-AS8 | `--defect-file`写入：`【归类】人工确认（无MS执行记录）`，证据为调用方原文 |
