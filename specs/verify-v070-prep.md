# board@4 评审准备清单（T9 前置，未下结论）

- 编写：reviewer（T9，attempt 1）；初稿 17:18；按队长多轮裁决更新（冲突裁决 → T4 口径 → 评审基准 → 低观察处置 → 影响面澄清）。时间：2026-11-22 17:37（Asia/Shanghai）
- 状态：**准备工作**。T1–T8 尚未完成，本文只做「27 条场景 → 证据清单」「board@4↔board@3 差异」「023 依赖」三件事，**不含任何通过/未通过结论**。
- 正式评审在队长通知「T1–T8 全部 completed」后执行，产出 `specs/verify-v070.md`。
- 基线：HEAD `fd4b841`；**裁决后** `specs/019-test-contract/spec.md` sha256 `f48bdf22…02b5`、`board@4.yaml` sha256 `2e499bdb…47da`、`board@3.yaml` sha256 `621e63c5…713c`（`env/env.json` 同时保留裁决前 hash）。
- 证据目录：`.tmp-shots/review-v070/`（`env/` 基线、`snapshot/` 数据库、`us1…us6/`、`ui/`、`skills/`、`scripts/`、`logs/`）。

## 0. 已捕获的环境基线（可复现，均为只读）

### 0.0 评审基准（队长裁定，正式结论按此出）

- **正式证据基准 = 本地当前源码（交付物）+ 迁移后线上库只读快照副本**。接口行为（020 拒绝路径、kind 暴露、写后回读、门禁）都在该组合上验，写操作只落副本，作为正式结论依据。
- **线上 0.6.5 不计缺陷**：旧镜像不承载本轮改动；其差异（API 不返回 kind、门禁每项目一条 kind 缺失）只记录，不判失败；最终报告单列「部署后需复验」一节。
- **T4 判据**：以「DB 中 48 张表 kind 已落库 + 本地新代码 API 返回 kind」为准，不拿线上旧 API 判 T4 失败。
- **部署后需复验清单（最终报告必列）**：①US1-AS3（run kind=detail、不进导航、按 id 可读）；②020 拒绝路径（state/result 一致 400、重复纳入、两步写入失败可见）；③门禁对线上实库差异 0（字段/表名/kind/关系列/闸门标记）；④`stage_done`/`gate` 在线上库的落库值与规则；⑤写后回读（no-store）仍返回新值。

| 项 | 值 | 证据 |
|---|---|---|
| 线上看板 | `http://localhost:8090`，8 个项目 / 32 张表 / 408 个字段实例 | `env/structure-before-migration.json`（`scripts/snapshot_board.py` 抓取） |
| 项目清单 | demo-bench, demo-cnc, demo, demo-im, demo-cloud, demo-edge, demo-screen, tableflow | `env/projects.json` |
| 迁移前结构 | 每项目 4 表（ver 15 / indep 16 / dep 9 / bug 11 字段）；`kind` 字段**不存在**（接口未暴露） | 同上 |
| 旧表行数（迁移比对基线） | tableflow 13/25/5/5、demo 4/1/3/9、demo-im 9/22/36/0、demo-cloud 12/18/9/0、demo-edge 8/12/1/0、demo-cnc 2/14/0/0、demo-bench 1/9/0/0、demo-screen 5/19/0/3（ver/indep/dep/bug） | `env/structure-before-migration.json` 的 `row_count` |
| board@3 门禁（现行） | `check_board.py` 默认契约 → **0 差异，exit 0**；模板产物同样 0 | `env/board3-gate.json`、`env/board3-gate-template.json` |
| board@4 门禁（迁移前） | `--contract specs/019-test-contract/board@4.yaml` → **exit 1，24 条差异**（每项目：ver 缺 13 字段/多 2 旧名；`独立需求是否完成`、`依赖需求是否完成` 线上仍打 gate:true） | `env/board4-gate-before.json` |
| board@4 门禁（模板产物，迁移前） | `--template --contract board@4` → **exit 1**，模板仍按 board@3 建表（字段名不符 + 闸门标记） | `env/board4-gate-template-before.json` |
| 裁决后的规格/契约 | 019 spec：US5-AS1「十一个字段」+ 两处「八个项目」；board@4：dep 名=`依赖变更需求`、`stage_done=and(六节点==done)`、`gate=and(ver.stage_done == true)`、删去「中间布尔字段」说法；`tables.kind` 已落库并返回 | `env/env.json.hashes`、本次复核输出 |
| T1 完成态（本次复核） | 8 项目 × 6 表（48 张表 / 624 个字段实例）；`tables.kind` 已落库（8 个 run=detail、8 个 case=board，48 张全有值）；ver **25** 字段（缺 `六节点是否全部完成`、Bug 两字段仍旧名、gate 仍旧规则——待 T4 A 方案补到 26）；四张老表行数不变、case/run 均为 0 行 | `env/structure-after-t1.json`、`env/us5-rowcount-after-t1.json`、远程 DB 查询 |
| 线上运行代码 | 容器镜像仍是 `tableflow:0.6.5`（旧代码）：`GET /api/projects/{pid}/tables` 的 `kind` 返回 null。按 0.0 基准，接口行为用**本地新代码 + 迁移后快照副本**验证；线上部署另列「部署后需复验」 | 实测 curl 输出（见第 0 节命令） |
| 评审基准冒烟（17:29） | 快照 sha256 `feac4fb1…9023`（线上与本地一致）；本地新代码 + 快照副本 `uvicorn :8010`：`GET /tableflow/tables` 的 kind 正常（case/ver/indep/dep/bug=board、run=detail），ver 25 字段（stage_done 未建，待 T4） | `snapshot/live-20261122-172920.db`、`env/smoke-tables.json`、`env/smoke-ver.json`、`logs/smoke-uvicorn.log` |
| 评审侧独立校验试跑（17:33） | 用本地新代码 + T1 快照副本抓结构（含行 id）并跑 `check_019_structure.py`：**kind 全部通过**；每项目仍余 3 条 = ver 缺 3 字段（stage_done+2 改名）+ 2 个旧 gate 标记（`上一版本Bug是否清空` 的旧标记被改名掩盖）；8 条关系边已齐、run 无反向字段 | `env/structure-t1-localcode.json`、`us1/check-t1-localcode.json` |
| 后端回归（HEAD 干净树） | `git archive HEAD` → `backend/.venv/bin/python -m pytest -q` → **146 passed, 1 warning in 5.26s** | `env/pytest-head.log`（运行后删除临时树） |
| 后端回归（工作树，**不稳定，不作证据**） | 17:13 `169 passed`；17:17 `3 failed, 172 passed`（T1 迁移测试仍在改） | `env/pytest-worktree.log` |
| 工具链 | Python 3.14.4（系统）/ 3.12（backend/.venv）；Node v24.19.0；npm 11.17.0 | 本文命令输出 |
| 本地 `data/tableflow.db` | **已过期**：仅 2 项目、ver 17 字段，与线上不一致 → **不得作为线上证据**，只能用于本地写入演练（用线上快照副本） | `env/env.json.local_db` |

复现基线命令（只读）：

```bash
cd /path/to/tableflow
python3 .tmp-shots/review-v070/scripts/snapshot_board.py \
  --base http://localhost:8090 --out .tmp-shots/review-v070/env/structure-before-migration.json
python3 backend/scripts/check_board.py --base http://localhost:8090 --json > env/board3-gate.json   # exit 0
python3 backend/scripts/check_board.py --contract specs/019-test-contract/board@4.yaml \
  --base http://localhost:8090 --json > env/board4-gate-before.json                                  # exit 1（迁移前预期）
```

> 注意：`check_board.py` 当前把 `ROLES` 写死为 ver/indep/dep/bug（`STATUS_FIELD_BY_ROLE` 也只有这三类），所以上面 24 条差异**没有覆盖 case/run 两表**——这正是 T4 的改造点，不能拿这 24 条当作 board@4 门禁的完整基线。

## 1. 019 六条用户故事 / 27 条 Acceptance Scenario 评审清单

证据方法编号（详细命令见第 4 节）：

- **E1** 结构快照：`snapshot_board.py` 抓项目/表/字段/options/kind/行数
- **E2** 门禁：`backend/scripts/check_board.py --contract board@4 --base <BASE> --json`（线上/本地副本/模板）
- **E3** 本地写入沙盒：线上库只读快照副本 + `uvicorn :8000`（写操作只落副本，绝不写线上）
- **E4** HTTP 黑盒用例脚本：`X-Agent-Id: reviewer`，按字段**名称**查 field_id，逐步 GET 回读并落日志
- **E5** 迁移证据：T1 的迁移前后 dump + 评审独立复算（旧表逐行逐字段 diff、幂等重跑、部分迁移重跑）
- **E6** 界面证据：`npm run build` 日志 + 本地 `npm run dev`（代理到 :8000）+ 浏览器截图/DOM 快照，存 `ui/`
- **E7** 技能证据：`skills/tf-test-plan` 等脚本的只读/演练运行日志 + 派生幂等两次运行 + 源码检查（无直连库、无凭据）

> 判定口径：每条必须落到「保存下来的产物路径」；唯一允许的非通过结论是「未验证（依赖未落地）」，不得用「看起来对」代替证据。

### US1 契约落到数据层（4 条）

| 场景 | Then 判据 | 证据 | 复现入口 | 依赖 |
|---|---|---|---|---|
| US1-AS1 | 六表齐备，每表字段数/名/类型/**顺序**与契约一致 | E1+E2 | 快照逐字段按契约 `tables.*.fields` 比对；`check_board` 差异 0 | T1,T4 |
| US1-AS2 | 8 条 relation 边（ver→indep/dep/bug/run、run→case、case→indep、dep→indep、bug→indep），任意两表间只有一条边 | E1 + 边集脚本 | 从快照 `type=relation` 的 `options.table_id` 枚举边，断言 8 条且 `(源,目标)` 去重后仍 8；断言 run 无指向 ver 的字段 | T1 |
| US1-AS3 | `run.kind=detail`、不进表导航、仍可按 id 读单行 | E1（`GET /api/projects/{pid}/tables` 的 kind）+ `GET /api/tables/{pid}-run/rows/{id}` + E6 | 接口读 kind；导航截图/`TableTabs` DOM 中无 run；单行 GET 200 | T1（表级 kind 落库+接口）、T5（导航过滤） |
| US1-AS4 | 每条 case 行 id 匹配 `<规格号>-US<n>-AS<m>`，且规格号能在 indep 找到 | E1 行 dump + 正则/归属脚本 | 逐行 `^\d{3}-US\d+-AS\d+$`；**适用范围：仅 tableflow 成立**（其 indep 为 `019-AR` 等）。case.id 前缀来自规格目录、`case.indep` 才指向 indep 行；其余 6 个项目的 indep id 形态不同（demo-bench `S1…`、demo-cnc `UD-01-AR`、demo `UD-04-AR`、demo-im `001-document-intake`、demo-cloud `C-501`、demo-edge `E-313`），无法用同一规则验，见第 7 节；校验脚本按「id==NNN 或 id 以 `NNN-` 开头」的项目约定，不硬编码 `-AR` | T1,T8 |

> **T1→T4 中间态**：T1 完成时 ver 是 **25** 字段（缺 `六节点是否全部完成`，Bug 两字段未改名，gate 仍旧规则）；T4 按队长批准的 A 方案补 `stage_done`+改名+gate 规则迁移后应为 **26**。US1-AS1/US6-AS1 按 T4 完成后判，25 只是中间态，不能拿它判失败。

> P-05 已裁决并落地：`tables.kind`（CHECK board/detail + `_ensure_column` 补列）、`TableSummaryOut.kind`、repository 读出与前端 `boardTables` 过滤均已具备。US1-AS3 按接口实际返回的 kind 验；迁移前快照里 kind 为 null 是历史状态，不是验收状态。

### US2 用例派生幂等（4 条）

| 场景 | Then 判据 | 证据 | 复现入口 | 依赖 |
|---|---|---|---|---|
| US2-AS1 | 一份含 N 条场景的 spec 派生 N 条用例，id=场景号，`case.indep` 指向来源规格 | E7 | 用 `.tmp-shots/review-v070/fixtures/` 下的夹具 spec（不动仓库真源）派生，读回 case 行 | T8,T3 |
| US2-AS2 | 二次派生新建 0；名称/步骤变化就地更新，其余不变 | E7 | 连续派生两次 + 改夹具场景名/步骤；比对 case 表全量快照与 write_audit 增量 | T8 |
| US2-AS3 | spec 删一条场景后重跑，报告「源场景已不存在」，不静默保留也不无提示删除 | E7 | 夹具删一条场景重跑；断言输出含该 case id 与提示、case 行未被静默删 | T8 |
| US2-AS4 | 用例被多版本纳入后更新步骤，各版本 run 记录不受影响 | E7+E4 | 两版本各纳入同一 case → 改步骤 → 读 run 行与 `ver.runs` 不变（只引用 id） | T8,T3 |

> 派生入口以 T8 `tf-test-plan` 实际交付为准；若脚本只能对真源 `specs/` 目录运行、无法在夹具上复现，按「不可复现」记缺陷，不降低验收。

### US3 执行记录与版本进度（6 条）

| 场景 | Then 判据 | 证据 | 复现入口 | 依赖 |
|---|---|---|---|---|
| US3-AS1 | 纳入=建 run 行（`state=todo`、result 空）+ 追加 `ver.runs`；回读版本行可见 | E3+E4 | 副本上 POST run → PATCH ver.runs → GET 版本行/执行行 | T1,T3 |
| US3-AS2 | 纳入 10、执行 4 → 用例总数 10、已完成 4、用例是否完成=false | E3+E4 | 建 10 case+10 run，4 条置 `state=done`，`POST .../recompute` 后 GET ver 行 | T1,T3 |
| US3-AS3 | 10 条全执行 → 已完成 10、完成=true；任一条 `result=fail` 不改这三字段 | E3+E4 | 全部 done（其中 1 条 fail），重算后读三字段 | T1,T3 |
| US3-AS4 | `state=todo` 时直接写 `result=pass` → 400，且两字段读回不变 | E3+E4 | PATCH → 断言 400；GET 行；查最近 `write_audit` 为 failed 且无业务变更 | T3 |
| US3-AS5 | 版本未纳入任何用例 → 0/0/true（空集） | E3+E4 | 新版本行重算后读三字段 | T1,T3 |
| US3-AS6 | 同版本同用例再次纳入 → 400 或就地复用，不产生第二条 | E3+E4 | 连续两次纳入；统计该 (版本,用例) 的 run 行数 =1，`ver.runs` 不重复 | T3 |

> P-06 裁决：019 只判「规则被定义且被拒绝」，拒绝路径与错误码归 020；不重复计分、不判越界。US3-AS4/AS6 的证据到「400 + 零写入/单行」即可。

### US4 六节点串行与闸门一致性（6 条）

| 场景 | Then 判据 | 证据 | 复现入口 | 依赖 |
|---|---|---|---|---|
| US4-AS1 | 六节点全 todo 时「开发」置 done → 400，错误指出前序未完成 | E3+E4 | PATCH dev=done；断言 400+错误文本；读回仍 todo；audit failed | T7 |
| US4-AS2 | 前五节点 done 且用例未全执行时「测试」置 done → 400 指出用例未执行完 | E3+E4 | 构造版本（空规格集合使 spec_done 真、case_done 假）→ PATCH test=done | T7 |
| US4-AS3 | 用例全执行但 Bug 未清零（且变更未回归通过）时「测试验收」置 done → 400 | E3+E4 | 挂 open 缺陷/未 passed 变更单 → PATCH test_accept=done | T7 |
| US4-AS4 | 本版规格尚有未验收时「开发验收」置 done → 400 | E3+E4 | 挂 pending 规格 → PATCH dev_accept=done | T7 |
| US4-AS5 | 某节点 failed 时推进后序 → 400；改回 doing 再 done 后才允许继续 | E3+E4 | test_design=failed → dev=done 400 → test_design=doing→done → dev=done 放行 | T7 |
| US4-AS6 | 六节点全 done 时 `stage_done` 与 `gate` 均为真；任一节点退回则转假 | E3+E4 | 满足各节点前置后逐个置 done → recompute → GET 行值；再退回一个节点重算 | T7 + **T2(023)** |

### US5 存量迁移（3 条）

| 场景 | Then 判据 | 证据 | 复现入口 | 依赖 |
|---|---|---|---|---|
| US5-AS1 | 新增 case/run 两表与版本表**十一个**字段（六个节点、六节点汇总、测试用例关联、用例总数、已完成用例数、用例是否完成）；四张老表行数与字段值完全不变 | E5 + E1 | 用 `env/structure-before-migration.json`（迁移前）对迁移后快照：旧表逐行逐字段 diff 必须为空；新表存在 | T1 |
| US5-AS2 | released 版本六节点均 done、gate 仍真；planned 版本六节点 todo | E1/E5 | 全量 ver 行按 release_status 断言 | T1（+T2 间接，见第 3 节） |
| US5-AS3 | 迁移中途失败后重跑：不重复建表、不覆盖已有行，最终与一次成功相同 | E5 | 在副本上制造部分状态（如只删 run 表或删一个新字段）后重跑；再连跑第二次；两次后结构+数据 dump 一致 | T1 |

> P-01 已裁决（规格笔误已改）：按 11 个字段判，字段清单以契约 `tables.ver.fields` 为准。P-02 已裁决：迁移范围=线上 8 个项目（含 demo-screen），US6-AS1 的“全部”指这 8 个。

### US6 一致性门禁（4 条）

| 场景 | Then 判据 | 证据 | 复现入口 | 依赖 |
|---|---|---|---|---|
| US6-AS1 | 全部已迁移项目（8 个）：六表字段名/类型/顺序、表名、relation 显示列与状态列、闸门标记、表级 kind 差异 0 | E2+E1 | `check_board --contract board@4` 差异 0；另需覆盖 run/case 的 `status_field`（run→执行状态、case 无）+ kind + dep 表名（P-03 要求 T4 加） | T4 |
| US6-AS2 | 缺 run 表的项目 → 门禁失败并指出缺失的表 | E2 | 副本项目删 `*-run` 表后跑门禁（本地副本服务），断言 exit 1 且信息含 run | T4 |
| US6-AS3 | 版本表仍是 board@3 的 15 字段 → 门禁失败并逐字段列出差异 | E2 | 用迁移前快照起本地服务（或副本项目）跑门禁，断言 exit 1 且列出缺失字段 | T4 |
| US6-AS4 | 模板脚本产物差异 0 | E2 | `check_board --template --contract board@4 --json` | T1,T4 |

> 覆盖提醒：`check_board` 目前按**字段名**定位比较类型/枚举/关系/闸门。字段改名后旧名字段不会进入比较（`actual.get(cf["name"]) is None → continue`），所以迁移前基线里 `上一版本Bug是否清空` 的 gate:true 漂移被“改名”掩盖（24 条里没有它）。T4 修好后评审必须确认：三个展示字段的 gate 标记**已移除**、`stage_done`/`gate` 已打标，且改名后旧名不再存在。

## 2. board@4 相对 board@3 的差异（评审重点）

### 2.1 表与字段

| 维度 | board@3（017） | board@4（019） | 评审落点 |
|---|---|---|---|
| 表 | 4 张：ver/indep/dep/bug | 6 张：+`case`（8 字段，board）、+`run`（9 字段，**detail**） | US1-AS1/AS3 |
| 字段总数 | 51 | 79（ver 15→26；indep 16、dep 9、bug 11 不变） | US1-AS1 |
| ver 新增 11 | — | 六节点 enum（版本需求设计/测试设计/开发/开发验收/测试/测试验收，todo/doing/done/failed，required）、`六节点是否全部完成`（computed, gate, rule=`and(六节点==done ×6)`）、`测试用例`（relation→run）、`用例总数`（count）、`已完成用例数`（count where state=done）、`用例是否完成`（rollup all state=done） | US1-AS1、US3-AS2/3/5、US4-AS6 |
| ver 改名 2 | `上一版本Bug已修复/总数`、`上一版本Bug是否清空` | `Bug已修复/总数`、`Bug是否清空`（只改名，语义键与口径不变） | US1-AS1、US6-AS1 |
| 字段顺序 | 发布条件在**第 3 位**（016 FR-006） | 发布条件在**第 10 位**（六节点 + stage_done 之后），发布状态顺延到第 11 位；其余字段整体后移 | US1-AS1（顺序比对）、T1 迁移需重排 order |
| 无 plan 表 | 无 | 明确不设测试计划表（版本直接持有执行记录） | US3-AS1、T1 |
| 表级 kind | 无（接口不返回） | `tables.kind`（board/detail；run=detail）；接口 `TableSummaryOut.kind` 返回 | US1-AS3、T4（门禁须比 kind） |
| dep 表显示名 | `依赖需求` | `依赖变更需求`（按裁决与线上/模板对齐；字段与判定不变） | US6-AS1（T4 须把表名纳入比对） |
| 行 id | ver/indep/dep/bug 各自格式 | +case=`<规格号>-US<n>-AS<m>`；+run=`<版本号>--<用例号>`（仅字母数字点横线下划线，禁 `/`、`#`） | US1-AS4、US3-AS1/AS6 |

### 2.2 发布条件与闸门标记

| 维度 | board@3 | board@4 |
|---|---|---|
| `ver.gate` 规则 | `and(ver.spec_done, ver.change_done, ver.bug_clear)` | `and(ver.stage_done == true)`（`stage_done=and(六节点==done ×6)`；023 只补配置期类型校验，不需要中间布尔字段） |
| gate:true 字段 | 4 个：发布条件、独立需求是否完成、依赖需求是否完成、上一版本Bug是否清空 | 2 个：发布条件、六节点是否全部完成；三个布尔降为**展示字段**，不再打闸门标记 |
| 节点闸门一致性 | 无（只靠三布尔） | 写入期校验：测试→要求 `case_done`；测试验收→要求 `bug_clear` 与 `change_done`；开发验收→要求 `spec_done`；不符 400 |

现状（迁移前实测）：线上 8 个项目 `独立需求是否完成`、`依赖需求是否完成` 仍打 gate:true，`上一版本Bug是否清空` 也打标（被改名掩盖，见第 1 节提醒）。迁移必须移除这 3 个标记并给 `六节点是否全部完成` 打标。**这也是 US6-AS1 的最容易漏项**。

### 2.3 关系与弹层列

| 维度 | board@3 | board@4 |
|---|---|---|
| 关系边 | 5 条：ver→indep/dep/bug、dep→indep、bug→indep | 8 条：+ver→run、run→case、case→indep；任何两表间仍只一条边；run 不得反向指 ver |
| 弹层第三列 `status_field` | indep→验收状态、dep→回归状态、bug→状态 | 同左，+run→执行状态（`run.state`）；**case 不给状态列**（用例是资产，无完成判据） |
| 执行清单弹层 | 无 | 第一列 run 行 id，第二列 `display_field=run.case_no`，第三列 `run.state`；通过与否点明细看 `run.result` |

### 2.4 状态域与规则

- 新增 3 个状态域：`version_stage`（todo/doing/done/failed，四态互斥、failed 非终态）、`run_state`（todo/done）、`run_result`（pass/fail/blocked/skip，与 state 强一致）。
- 新增规则 14 条：case_done、case_progress_only、run_state_result_consistency、bug_set_meaning、case_projection、case_needs_spec、run_owned_by_version、run_needs_case、run_one_per_version_case、version_stage_serial、version_stage_failure、version_stage_gate_consistency、version_stage_done、version_not_shipped；删除 3 条：bug_version_hookup、ver_bug_ready、bug_aggregate_impl；`release_gate` 改写。
- 新增 conventions：`table_kind`、`run_two_step_write`、`run_one_per_version_case`、`display_of_run`；`relation_status_column`/`relation_direction`/`row_id` 扩写。
- 新增 3 条迁移（均未执行）：`add-case-run`、`ver-add-stage-and-runs`、`rename-bug-fields`；存量版本行初始值：released→六节点 done，planned/dropped→todo；写入期校验对存量行放行一次。

## 3. 依赖 023 才能成立的场景

023（T2）状态：**队长裁决（P-04）后为终态**。`specs/023-cell-compute/spec.md` 按实际能力写：运行期 `and(字段==取值)` 严格相等比较是 010 既有能力；023 固化条件项取值的类型/取值域校验（配置期 400、不落库、不做隐式强转、禁止 relation 条件），并明确 **MUST NOT 依赖中间布尔字段**。契约已同步：`stage_done = and(六节点 == done)`、`gate = and(ver.stage_done == true)`，删去「中间布尔字段」说法。

| 场景 | 依赖强度 | 说明 |
|---|---|---|
| **US4-AS6** | **按 019 的声明仍依赖 023（T2 终态，评审时可关闭）** | 019 spec 把「条件表达式的汇总计算」划给 023、Non-Goals 明说只在 `stage_done` 处标注依赖；契约输出 `stage_done`/`gate` 必须能按该配置直接落地。评审时：①按 023 US1/US4/FR-009 验 6 条件 `and` 可建成、六节点全 done 为真、任一非 done/空值为假、且没有中间布尔字段；②再验 `gate=and(stage_done == true)` 联动。T2 已终态，此项不再是“未落地”。 |
| US5-AS2 | 不构成 023 依赖（相对初稿下调） | `released` 版本 `gate` 为真来自 `stage_done` 的运行时值；运行期 `and(枚举==取值)` 是 010 既有能力，023 只加配置期校验。直接读回 `gate`/`stage_done` 判定；023 校验通过只是“配置合法”的前置证据，不是该场景成立的必要条件。 |
| US6-AS1 | 部分依赖（口径核对） | 门禁比字段名/类型/顺序、表名、kind、gate、关系列，不比 rule 文本；但评审要读 `六节点是否全部完成` 的 `options.conditions` 与 `gate` 的规则，核对与契约一致（6 个枚举条件 + 1 个布尔条件），核对判据用 023 的表达式定义。 |
| US3-AS2/AS3/AS5 | 不依赖 023 | `用例总数=count(ver.runs)`、`已完成用例数=count(ver.runs, run.state==done)`、`用例是否完成=rollup(ver.runs, run.state, all==done)` 属 010 既有 count/rollup/where 能力。 |

P-04 裁决已生效：T2 任务描述「and 只接受布尔字段」是错的、不追改；评审按 023 spec 的实际范围判。023 的过时引用已由队长修正（改为「早期草案曾写…（已更正）」，文件内已无「第249行」字样，已复核），**评审不再就此计分**。

其余跨规格依赖（用于排评审顺序，不是 019 的验收豁免）：

| 019 场景组 | 主实现任务 | 说明 |
|---|---|---|
| US1、US5 | T1（建表/迁移）+ T4（门禁） | 数据层 |
| US2 | T8（tf-test-plan 派生） | 用例派生幂等/源场景消失报告 |
| US3-AS1/4/6 | T3（020 协议） | 两步写入、state/result 一致、重复纳入 |
| US3-AS2/3/5 | T1（字段配置） | count/rollup 既有能力 |
| US4-AS1…5 | T7（025 六节点） | 串行/闸门一致性，写入期 400 |
| US4-AS6 | T7 + T2（023） | 见上 |
| US1-AS3（导航） | T5（021） | 表导航过滤 detail 表 |

## 4. 六份规格（019–025）与证据方法

### 4.1 规格状态（本次复核；正式评审以 t4/t7/t10 completed 时的完成态为准）

| 规格 | 任务 | prep 时状态 | 评审要点（待其 Acceptance Scenario 定稿后逐条展开） |
|---|---|---|---|
| 019-test-contract | T1/T4 | T1 已交付（8 项目 × 6 表、kind 落库、ver 25 字段）；T4 claimed，按 17:25 口径继续（门禁+表名/kind+stage_done 迁移到 26 字段） | 六表/迁移/门禁 |
| 020-protocol-test | T3 | **已交付**（T3 completed；spec 17:15） | state/result 一致 400、两步写入失败可见、重复纳入二选一、请求信封不变 |
| 021-case-view | T5 | **已交付**（T5 completed；spec 17:18） | 用例表视图、版本行弹层三列（语义口径，见第 5 节展示偏差）、run 不进导航、复用 RelationListModal |
| 022-role-view | T6（+t10） | **已交付**（T6 completed；spec 最新 17:36；t10 修正测试角色映射中） | 顶部通栏四角色、高亮/常显、localStorage、CSS 变量、005 对比度阈值不下降；**角色可见表矩阵按 t10 完成后的映射判（软件测试角色 3→4 个页签）** |
| 023-cell-compute | T2 | **已终态**（T2 completed；spec 17:14） | and 条件项 `字段 == 取值` 的类型/取值域校验（配置期 400、不落库）、不引入中间布尔字段、既有 and/rollup/count/ratio 不回归 |
| 024-role-skills | T8 | **已交付**（T8 completed；spec 17:26） | 六个技能、只读写本角色表、写后回读、三态、tf-test-plan 幂等、无直连库/无凭据；**tf-test-plan 派生/幂等只验证了 tableflow 一个项目，报告须写明覆盖范围** |
| 025-version-stage | T7 | **进行中**（T7 protocol in_progress；spec 尚未出现） | 六节点四态落库、串行/闸门 400、stage_done 表达式、gate=and(stage_done == true) |

### 4.2 证据方法（正式评审要执行的命令模板）

**E0 线上库只读快照**（容器内 backup API，不 checkpoint 生产库；随后拷回本地）：

```bash
ssh -F /dev/null -o BatchMode=yes root@localhost \
  "docker exec tableflow python -c \"import sqlite3;s=sqlite3.connect('/data/tableflow.db');d=sqlite3.connect('/tmp/review-snapshot.db');s.backup(d);d.close();s.close();print('backup ok')\""
ssh -F /dev/null -o BatchMode=yes root@localhost \
  "docker cp tableflow:/tmp/review-snapshot.db /tmp/review-snapshot.db && sha256sum /tmp/review-snapshot.db"
ssh -F /dev/null -o BatchMode=yes root@localhost "cat /tmp/review-snapshot.db" \
  > .tmp-shots/review-v070/snapshot/live-$(date +%Y%m%d-%H%M%S).db
sha256sum .tmp-shots/review-v070/snapshot/*.db
```

**E1/E2 结构快照与门禁**：见第 0 节命令；迁移后重抓 `us1/structure-after.json` 与 `us6/gate-after.json`（记录 exit code）。

**评审侧独立校验脚本（已试跑）**：

```bash
# 结构+行 id 快照（本地新代码或线上均可；正式评审用本地）
python3 .tmp-shots/review-v070/scripts/snapshot_board.py   --base http://127.0.0.1:8010 --with-row-ids   --out .tmp-shots/review-v070/env/structure-<state>.json
# 按 board@4 独立比对：字段名/类型/顺序、表名、kind、枚举、关系边、gate 标记、computed kind、case 行 id
python3 .tmp-shots/review-v070/scripts/check_019_structure.py   --snapshot .tmp-shots/review-v070/env/structure-<state>.json   --out .tmp-shots/review-v070/us1/check-<state>.json
```

> 试跑口径说明：同一份 T1 快照，走线上旧 API 会因 kind 不返回报 9 条/项目（其中 6 条是旧镜像假缺失，按 0.0 基准不计缺陷）；走本地新代码只报 3 条/项目（ver 缺 3 字段 + 2 个旧 gate 标记），与 T4 待办完全对应。

**E3 本地写入沙盒**（所有写场景只在副本）：

```bash
cp .tmp-shots/review-v070/snapshot/live-<ts>.db .tmp-shots/review-v070/work.db
cd backend && TABLEFLOW_DB=../.tmp-shots/review-v070/work.db \
  .venv/bin/uvicorn tableflow.app:app --host 127.0.0.1 --port 8000
# 写请求头：X-Agent-Id: reviewer；脚本按字段“名称”查 field_id（不硬编码本地字段 id）
```

**E6 界面证据**：`cd frontend && npm run build`（日志）；`npm run dev`（vite :5173 代理 `/api` → localhost:8000，已核对 `vite.config.ts`）；浏览器截图/DOM 存 `ui/`；对照 005 的对比度阈值时记录取样方式。

**E7 技能证据**：读 `SKILL.md`；`grep -rn "sqlite3\|connect(" skills/<名>/scripts` 证明不直连库；每个技能只读跑一次（日志）；`tf-test-plan` 对同一夹具 spec 连跑两次（第二次新建 0）；输出不得含 key/token。

## 5. 冲突登记与裁决（队长裁决；prep 已据此更新）

| 编号 | 原问题 | 裁决 | 评审动作 |
|---|---|---|---|
| P-01 | 019 US5-AS1「版本表八个字段」vs 契约实际 +11 | 规格笔误，已改为「十一个字段」并列出清单 | 按契约 11 字段判；US5-AS1 证据里核对字段清单 |
| P-02 | 019「七个项目」vs 线上 8 个 | 按实际走：迁移 8 个（含 demo-screen），spec 两处已改「八个」 | US6-AS1/SC 的“全部项目”=8；少迁一个即不通过 |
| P-03 | 线上 dep 表名「依赖变更需求」vs 契约「依赖需求」；门禁不比表名 | 以实际为准：契约 dep 名已改为「依赖变更需求」；**T4 必须把表名纳入门禁比对** | 按 17:25 消息判（任务描述不再作为口径）；当前 `check_board.py` 仍只比字段，T4 claimed 中 |
| T4-17:25 | T4 任务描述仍写「7 个项目」且未提表名比对，且任务已 claimed、无法编辑 | 以队长 17:25 消息为准：8 个项目、比表名（dep=`依赖变更需求`）、比表级 kind，并允许补 stage_done/gate 数据层迁移；t1 的「7 个项目」也作废 | 评审按此口径判 T4；US1-AS1 按 T4 后 26 字段判（25 为中间态） |
| P-04 | T2 描述「and 只接受布尔字段」与代码不符 | 核实正确；T2 终态、任务描述不追改；023 spec 按实际能力写；契约 stage_done/gate 已改、不再提中间布尔字段 | 按 023 spec 实际范围判；023 过时引用已修正（已复核无「第249行」），不计分 |
| P-05 | 表级 kind 缺失（API/tables 无 kind） | 已解决：`tables.kind` CHECK + `_ensure_column`、`TableSummaryOut.kind`、仓库返回、前端按 kind 过滤 | US1-AS3 按接口返回 kind 验；缺失才是失败 |
| P-06 | 019 场景断言 400 与 020 边界重叠 | 不算冲突：019 判「规则被定义且被拒绝」，020 判「拒绝路径与错误码」 | 不重复计分、不判越界（已写入 US3 表注） |

**非冲突的展示偏差（记录，不判失败）**：frontend 报备的执行清单弹层列头取目标字段 `name`（编号/用例号/执行状态），契约的「执行编号/是否执行」是语义口径；评审按「第一列=run 行 id、第二列=用例号、第三列=执行状态」的语义判，不要求字面一致。

> **T4 验收口径（队长 17:25 裁定，优先于过时任务描述）**：T4 已 claimed、任务描述无法编辑，评审按 17:25 消息判：**8 个项目（含 demo-screen）**；门禁**必须比表名（dep=`依赖变更需求`）、必须比表级 `kind`**；允许 T4 一并补 `stage_done` 字段与 `gate` 规则的数据层迁移（A 方案），使 ver 由 25→26 字段。t1 任务描述里的「7 个项目」同样作废。

## 6. 下一步（等队长通知 t4/t7/t10 全部 completed 后执行）

0. 以裁决后 hash 重抓基线：契约/规格已改，先重跑 `check_board --contract board@4`（迁移未执行仍会 exit 1）并把新 hash 写进评审报告基线表；
1. 取线上只读快照 + 迁移证据（T1 保留的前后 dump），先做 E0/E1/E5；接口行为一律在「本地新代码 + 快照副本」上跑（0.0 基准）；
2. 结构类 US1/US5/US6 逐条（E1/E2/E5）；
3. 本地副本起服务，跑 US3/US4 的 HTTP 黑盒用例（E3/E4），每次写后回读 + 查 audit；
4. 前端 `npm run build` + 本地 dev 截图（E6），覆盖 021/022 的 AS；**022 的角色矩阵按 t10 完成后的映射判**（软件测试角色 3→4 个页签），报告里注明依赖 t10；
5. 技能只读/幂等演练（E7），覆盖 024 的 AS；
6. 收集 020/021/022/023/024（T2/T3/T5/T6/T8 已 completed）与 025（T7 定稿后）的 Acceptance Scenario，按本清单同格式逐条补表；022 的角色矩阵按 t10 后映射补；
7. 输出 `specs/verify-v070.md`：每条 AS 一行（通过/未通过/未验证+依赖），附证据路径；偏差按严重度分级；先报冲突再下结论；
8. 报告单列「部署后需复验」一节（至少 0.0 列的五项），明确上线 v0.7.0 后由谁重跑、用什么命令、期望结果。

## 7. 已知数据偏差（最终报告必列一节，队长两次裁定：低观察处置 + 影响面澄清）

以下为存量数据偏差，**不要求本轮修复**（属存量数据迁移，另立需求），评审不据此判 019 失败；但报告必须单列，写清对映射/派生能力的限制与适用范围。

| 偏差 | 实测范围 | 对评审的影响 |
|---|---|---|
| `indep` 行 id 不符合契约 `NNN-AR` | **6/8 项目**：demo-bench `S1…S9`、demo-cnc `UD-01-AR…`、demo `UD-04-AR`、demo-im `001-document-intake…`、demo-cloud `C-501…`、demo-edge `E-313…`；合规：tableflow `001-AR…025-AR`、demo-screen（NNN-AR） | **不影响 case.id 形态**：case.id 前缀来自**规格目录**（`specs/008-board-contract/` → `008-US1-AS1`），`case.indep` 才指向 indep 行。漂移影响的是「从 indep 行反推该派生哪些用例」：**跨项目派生必须项目级映射，不能从 `indep.id` 推导**。v0.7.0 只派生 tableflow 的 019–025，这 6 个项目本轮不派生，**不构成本轮缺陷**。报告按「US1-AS4 仅 tableflow 成立」标注，不算 019 失败，但结论须写明适用范围；校验脚本按「id==NNN 或 id 以 `NNN-` 开头」的项目约定，不硬编码 `-AR`。后续改进（不进本轮验收）：derive 的映射改项目级配置，或在 indep 表显式加「用例前缀」列 |
| 版本表 Bug 字段旧名 / 三布尔 gate 标记 | 迁移前 8 项目普遍存在；T4 按 A 方案处理 | 属 T4 待办，不算“已知偏差”；评审按 T4 后状态判 |

**验证覆盖范围（必须写进报告）**：024 的 `tf-test-plan` 派生/幂等只在 **tableflow 一个项目**上验证，不代表对 8 个项目都成立；报告按「已验证 tableflow，其余 7 个项目未覆盖」表述，且不得据此推断跨项目可用。
