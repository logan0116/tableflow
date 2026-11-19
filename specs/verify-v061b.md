# v0.6.1复验报告（t21，2026-11-19）

复验人：qa。窗口：12:58–13:05。范围：v0.6.1（011/014）与第二轮7条缺陷的回归确认；只读，不改源码、不写看板业务行、不执行git写操作。
证据目录：`.tmp-shots/qa-v061b/`（可逐条重跑；沿用`.tmp-shots/qa-v061/`、`.tmp-shots/ms-014/`、`.tmp-shots/ms-summary/`的既有日志）。

## 一、结论

**可发布。**

依据：
1. 第二轮7条缺陷**全部关闭**（V061-02按契约明示延后，不算缺陷；其余6条已修，逐条见第三节）。
2. `pytest -q` **133 passed**；`check_contracts.py` 两契约 `exit0`，`--pre-write`合法内容原子写入、重复键拒绝且目标不变。
3. 014按新spec复判：22个验收场景 ↔ 22行证据表**一一对应**（无缺失、无多余），「未验证范围」5条显式列出；看板`014-AR`两列为22/28，与spec/tasks一致。
4. 011：线上`tf-bug`12字段与`board@2`逐项一致（重新回读）；`closed`准入未实现与契约表述一致（契约明示“写入期校验，后续需求实现”）。

## 二、验证基线

| 项 | 值 |
|---|---|
| `backend/src/tableflow/calculation.py` | `e10b97aa94fd46ccd48b539244c464951fc37d57c01e4530da98e751d535f719`（与v0.6.0基线一致） |
| `backend/src/tableflow/contracts.py` | `17ef16dc3fe48134b1b30ac6866f847f0215835ce2aec9486dffacb306113aa7` |
| `specs/011-bug-table/board@2.yaml`（rev2） | `d45d159f149497e3269ee4d5445e11fef808ba3683c66b99b4688fa9b4b088a1` |
| `specs/008-board-contract/board@1.yaml`（rev3） | `142ccf067ab372858a2cb898e78506f7a6dcc8adeb86a1e16210d6d507930537` |
| `specs/014-ms-skills/spec.md` | `375b38680d21f8d8dc64a0b57a56dc37c491c2f701a7eed5b20b4b9230804ab2` |
| `specs/014-ms-skills/tasks.md` | `df96d647e92dccbeb4c56232344b2923ba26999590d7ad7a6187a18a91ab03de` |
| 后端回归 | `133 passed, 1 warning in 4.74s`（`pytest.log`） |
| 线上看板 | `http://192.168.1.155:8090`（只读GET） |

## 三、7条缺陷逐条结论（V061-01…07）

| 缺陷 | 结论 | 证据 |
|---|---|---|
| V061-01[高] 014无spec | **已关闭** | `specs/014-ms-skills/spec.md`存在：3 US/22 AS/17 FR/7 SC；`tasks.md` 28任务（T017 `/run` 故意留空）；看板`014-AR`场景数22、任务总数28 |
| V061-02[中] 011关闭准入未实现 | **已关闭（按契约延后，不算缺陷）** | `board@2.yaml`第85行`bug_closed_evidence`与`specs/011-bug-table/spec.md`FR-009均写“写入期校验，后续需求实现”，措辞一致；实现确未加校验，属契约明示范围 |
| V061-03[中] 契约编辑窗口不可解析 | **已关闭** | `contracts.py`+`check_contracts.py`存在；默认校验两契约`exit0`；`--pre-write`合法内容原子写入且内容一致；重复键`exit1`、目标未变、无残留临时文件（`check_contracts.log`） |
| V061-04[低] calculation.py基线漂移 | **已关闭** | sha256=`e10b97aa…`，与v0.6.0验证基线一致 |
| V061-05[低] ms skill未写解释器要求 | **已关闭** | `ms-update`/`ms-implement`/`ms-summary`三份SKILL.md均有“运行环境（脚本解释器）”节（3/3命中） |
| V061-06[低] 014-AR两列统计为空 | **已关闭** | 线上`014-AR`：场景数22、任务总数28（复读） |
| V061-07[低] BUG-01关闭清空剩余事项 | **已关闭（文档）** | `ms-summary/SKILL.md`新增“先把原剩余事项并入证据`【原剩余事项】`段，再清空rest”约定（命中2处） |

## 四、014按新spec复判

| 检查项 | 结论 | 证据 |
|---|---|---|
| 场景数与证据表一一对应 | 通过 | 22个场景（US1 8、US2 6、US3 8），证据表22行；集合比对：缺0、多0（`check_014_spec.log`） |
| 「未验证范围」显式 | 通过 | 5条：①计划↔用例无关联API；②`/run`回写未跑通；③MS项目归属（cnc_nexus v3.0，独立模块隔离）；④探测副作用已覆盖；⑤计划级`ERROR`样本0 |
| SC-001 用例65条、读回65/65 | 通过（只读核对） | `ms_sync --report`：项目260、模块65，用例名带场景号（`ms_report.log`） |
| SC-002 幂等与就地更新 | 通过（引用既有日志） | `.tmp-shots/ms-014/update-path.log`：`新建0/更新1/跳过9/读回10/10`→再跑`更新0/跳过10` |
| SC-003 计划存在、报告读出关联0并说明 | 通过 | `ms_report.log`：计划`1744872984176246784`、已关联0、`reachable:[]` |
| SC-004 无关联行拒绝回写、证据缺失拒绝、100200不算成功 | 部分（引用t10证据） | `ms_run --list`：关联0条并拒绝回写（`ms_list.log`）；证据缺失拒绝与100200反例已在t10/skill文档留证，本轮未复跑 |
| SC-005 dry-run可核对、真写12字段回读 | 通过 | `ms_dryrun.log`：23条→ERROR0/BLOCKED待判定7/SUCCESS16；线上`tf-bug/BUG-01`12字段单行 |
| SC-006 轴1不新增、轴2合并、关闭需确认 | 部分（引用t10证据） | 轴1`final-apply.log`“跳过｜已消费→BUG-01”；轴2合并与关闭确认在t10独立复现 |
| SC-007 看板两列与spec/tasks一致 | 通过 | 看板22/28 = spec 22 AS / tasks 28 |

## 五、011复核

| 检查项 | 结论 | 证据 |
|---|---|---|
| 线上`tf-bug`12字段与`board@2`逐项一致 | 通过 | `compare_bug.log`：契约12/线上12，名称/类型/枚举/关联/必填“核对问题：无”；线上1行（BUG-01） |
| `closed`准入未实现与契约表述一致 | 通过 | 契约`rules.bug_closed_evidence`与011 spec FR-009均写“写入期校验，后续需求实现”；US2-AS2因此不可判为当前行为（见V061b-02） |
| 看板`011-AR`统计与文件一致 | 通过 | 看板15/18 = spec 15 AS / tasks 18（实测计数） |
| 建表脚本幂等/冲突/三表不动 | 通过（沿用t10实测） | 线上`--dry-run`12跳过；临时实例建表/幂等/冲突三场景通过（`.tmp-shots/qa-v061/`） |

## 六、后端与契约

| 项 | 结果 |
|---|---|
| `cd backend && .venv/bin/python -m pytest -q` | `133 passed`（`pytest.log`） |
| `python backend/scripts/check_contracts.py` | 两契约`[OK]`，`exit0`（`check_contracts.log`） |
| `--pre-write`（合法/重复键） | 合法→原子写入且内容一致；重复键→`exit1`、目标未变、无残留 |
| 014 MS只读复核 | 260用例/模块65、计划关联0、dry-run 23条口径一致（`ms_*.log`） |

## 七、缺陷登记（V061b-01…03，均为低）

### V061b-01 [低] 014 spec 的 Status 行与「未验证范围」条数不一致

- 现象：`**Status**: Implemented（有条件通过：1项未验证，见「未验证范围」）`，但「未验证范围」列了**5条**。
- 复现：`grep -n "^\*\*Status\*\*" specs/014-ms-skills/spec.md`；`check_014_spec.log`显示“未验证范围条目: 5”。
- 影响：读Status的人会以为只有1项未验；验收记录引用时易少记。
- 建议：改为“5项未验证（见「未验证范围」）”，或明确“核心链路1项（/run）”。

### V061b-02 [低] 011 spec 的 US2-AS2 写成当下行为，与 FR-009/契约的“后续实现”不一致

- 现象：US2-AS2 写“**When** 走写入期校验，**Then** 必须满足其一…”，按字面是当前必须成立的行为；而 FR-009 与`board@2.rule bug_closed_evidence`都写“写入期校验，后续需求实现”，实现确实不存在。
- 复现：`sed -n '61p;115p' specs/011-bug-table/spec.md`；`grep -n bug_closed_evidence specs/011-bug-table/board@2.yaml`。
- 影响：按场景验收会得到1个“未验证”（t10已如此记录），与“按契约延后”的口径并存，容易被误读成实现缺口。
- 建议：在AS2标注“（契约规定；写入期校验待后续需求实现）”，或在场景表加“状态”列。

### V061b-03 [低] ms_sync 把关联端点不可达概括为“候选全 404”，实测为 500

- 现象：`skills/ms-update/assets/ms_sync.py`第460行打印“无（候选全 404）”；直探关联端点返回`status=500`、body`{"code":100500,"message":"No static resource …"}`。
- 复现：`probe_assoc_status.log`（两条候选均`500 No static resource`）；`.tmp-shots/ms-014/update-path.log`第11/19行输出“候选全 404”。
- 影响：状态码表述与实测不符（404=路由不存在，500=服务端无该资源映射），排障时可能误导。
- 建议：改为打印实际状态码，或统一写“全部不存在（No static resource）”。

## 八、验收建议

| 需求 | 建议 | 依据与备注 |
|---|---|---|
| 011 bug表 | **可置 `acceptance=accepted`** | 契约与线上12字段逐项一致；15场景中14通过；US2-AS2为契约明示“后续实现”，建议验收记录注明该场景状态（V061b-02） |
| 014 MS三技能 | **可置 `acceptance=accepted`** | spec 22场景↔证据表22行一一对应；5项未验证已在spec显式列出，建议验收记录直接引用「未验证范围」；`/run`端到端待MS关联可用后补验 |

## 九、未验证与风险（不影响“可发布”）

| 项 | 状态 | 说明 |
|---|---|---|
| `/run` 回写端到端 | 未验证 | MS无计划↔用例关联写入API（18候选实测500），计划内0条；已在spec「未验证范围」第2条 |
| 计划级`ERROR`→缺陷链路 | 未验证 | 现有执行结果ERROR为0；只在SUCCESS与历史BLOCKED上验证 |
| SC-004/SC-006 部分细节 | 未复跑 | 引用t10证据与既有日志；本轮只读复核了`ms_run --list`与`ms_report` |

## 十、证据清单（`.tmp-shots/qa-v061b/`）

| 文件 | 内容 |
|---|---|
| `pytest.log` | 133 passed |
| `check_contracts.log` | 两契约`[OK]`、exit0 |
| `check_014_spec.log` | 22场景↔22证据行、缺0多0、未验证5条、Status行原文 |
| `compare_bug.log` | `tf-bug`12字段与契约逐项一致 |
| `ms_report.log` / `ms_list.log` / `ms_dryrun.log` | 014只读复核（260/65、关联0、23条口径） |
| `probe_assoc_status.log` | 关联端点实测`500 No static resource`（V061b-03） |
