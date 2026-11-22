# Feature Specification: 三角色六节点技能包（board@4）

**Feature Branch**: `024-role-skills`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 024-AR。board@4 把版本进度拆成六个节点（`ver.stage.plan` → `test_design` → `dev` → `dev_accept` → `test` → `test_accept`），并新增 `case`/`run` 两表承载用例与执行记录。但节点由谁推进、每个角色能碰哪些表、写失败怎么判定，仍只写在人类文档里：任何一个 Agent 都能绕过节点直接写 `ver`，也能一边执行测试一边改验收状态。本规格把「角色 × 节点 → 技能 → 表作用域」固化成六个可执行技能，使六节点推进既有唯一入口，又能被三态协议与回读证据约束。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 节点推进没有唯一入口 | board@4 只定义 `ver.stage.*` 四态与写入期校验；谁在什么条件下推进，无技能承载 | 同一个节点可能由「人改一下」「脚本跑一下」「Agent 顺手改」三种方式推进，证据不可追溯 |
| 角色表作用域只在前端 | 022 的角色切换只影响可见表清单；写接口不区分角色 | 测试角色可以改 `indep.验收状态`，开发角色可以改 `run.result`，越权写入无从发现 |
| 测试设计没有落点技能 | 019 定义 `case` 是 spec 场景的派生投影；`tf-update` 只登记需求，`ms-update` 走 MS，均不写 `case`/`run` | 用例表空着，六节点的「测试设计」无法完成，进度永远卡在第 2 节点 |
| 派生幂等无强制 | 019 FR-004 要求重复派生新建 0 条，但没有可执行载体 | 每次同步都造重复用例，执行记录错位 |
| 写成功判定靠 HTTP 码 | 012 实测：`503 {"detail":...}` 是锁冲突唯一形态，`400` 是确定性失败；只看 200 会把未落库当成功 | 节点显示 `done`、数据实际没写，发布资格被虚报 |
| 凭据易被顺手打印 | 写接口支持 `X-API-Key`；脚本排障时常把整个请求/环境打印出来 | key 泄漏到日志与对话记录 |

## Clarifications

### Session 2026-11-22

- Q: 为什么是六个技能而不是三个？ → A: 一个节点一个技能：节点是写入期校验的最小单位，也是「谁推进」的唯一归属；一个技能推进多个节点会让「做到一半」无法表达。三角色按 022 的定义分配，系统工程拿 1 个、软件开发 2 个、软件测试 3 个。
- Q: 为什么 `tf-dev-plan` 归系统工程？ → A: 它推进的是版本第 1 节点「版本需求设计」（范围确定、需求已挂载），不是写代码。技能名沿用任务给定的 `tf-dev-plan`；「dev」指研发计划，不是软件开发角色。
- Q: 测试角色能不能改 `indep.验收状态`？ → A: 不能。验收是需求方判定；测试技能只读 `indep`/`dep`/`bug`，写 `case`/`run`/`ver.stage.*`。
- Q: 节点闸门由客户端还是服务端判？ → A: 两边都判，职责不同：服务端（025）是最终闸门，防绕过；技能客户端先判一遍，为了在写之前给出可读的阻塞清单，并且**不把服务端的 400 翻译成成功**。技能不重复实现服务端没有的放行条件。
- Q: 为什么每个技能都要 `--dry-run`？ → A: 技能要在不改变看板的前提下回答「现在推进这个节点会发生什么、缺什么」。只读是验证与排障的默认姿势，也是「角色只能看本角色的表」的最小验证面。
- Q: `tf-test-plan` 为什么不建测试计划？ → A: board@4 明确不设 `plan` 表：版本直接持有执行记录（`ver.runs`），一个版本的执行范围就是「本版纳入的用例集合」。关联用例的动作即建 `run` 行，第二个「计划」层不承载额外信息。
- Q: 一个用例在版本里重复纳入怎么办？ → A: `run` 行 id 固定为 `<版本号>--<用例号>`，同版本同用例天然只有一行；重复派生复用该行，不新建。这比「400 或就地复用」二选一更硬：id 即幂等键。
- Q: 技能能不能直接连 SQLite？ → A: 不能。全部经 HTTP 读接口与 `/api/agent` 写接口；这样审计（`write_audit`）与业务留痕（`business_changes`）不会被绕过，也保证技能在远端实例上可用。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 六个技能各管一个节点且只碰本角色的表 (Priority: P1)

任意一个 board@4 项目上，六个技能各自只解析自己声明允许的表；越出作用域的读写被技能自身拒绝，而不是靠调用者自觉。

**Why this priority**: 这是「角色隔离」从界面约定变成可执行约束的地基；没有它，其余五条都只是建议。

**Independent Test**: 对 `tf-dev-implement` 传入 `--spec` 后运行，检查其请求路径只出现 `ver`/`indep` 两张表；对 `tf-test-check` 检查只出现 `ver`/`run`/`bug`/`dep`。

**Acceptance Scenarios**:

1. **Given** 一个 board@4 项目与六个技能，**When** 逐个运行 `--dry-run`，**Then** 每个技能的 `writes` 数组每项 `state` 均为 `skipped`，且 `write_audit` 不新增任何记录。
2. **Given** `tf-dev-plan` 的运行环境，**When** 它解析表，**Then** 只解析 `版本管理`/`独立规格需求`/`依赖需求` 三张表；解析到其他表按 `failed` 中止。
3. **Given** `tf-test-check` 的运行环境，**When** 它解析表，**Then** 只解析 `版本管理`/`用例执行情况`/`缺陷`/`依赖需求` 四张表，且只写 `版本管理` 的节点字段。
4. **Given** 六个技能的仓库目录，**When** 检视文件，**Then** 每个技能目录都含 `SKILL.md` 与 `scripts/` 下的可执行入口，且入口不 import 任何数据库驱动。

### User Story 2 - 写后必须回读，三态按 012 协议判定 (Priority: P1)

技能发出的每一次写，都要用读接口回读目标行并逐字段比对；`success`/`failed`/`unknown` 的判定与 012 的判定树一致，`unknown` 不当成功。

**Why this priority**: 节点状态被虚报比节点没推进更危险——发布资格会直接建立在假数据上。

**Independent Test**: 对一个不存在的版本号跑 `tf-dev-plan`：技能在写之前 `failed`，`ver` 表零变更；对同一写请求故意指向错误字段：`400` 后不重试、不报成功。

**Acceptance Scenarios**:

1. **Given** 一次成功的写，**When** 技能完成，**Then** 报告中含 `readback` 字段，逐项列出「期望值 = 读回值」，且只有全部一致才报 `success`。
2. **Given** 写接口返回 `503 {"detail":"数据存储不可用"}`，**When** 技能处理，**Then** 终态为 `unknown` 并立即 GET 回读；回读一致才按成功（注明由回读确认），否则保留 `unknown`。
3. **Given** 写接口返回 `400 {"result":"failed"}`，**When** 技能处理，**Then** 终态为 `failed`，不自动重试，报告附原始 `error`。
4. **Given** 写接口返回 `200` 但响应体不是 JSON，**When** 技能处理，**Then** 按 `unknown` 回读定案，不报成功。
5. **Given** 一次 `unknown` 且回读不一致，**When** 技能退避重试（100ms 起、最多 3 次），**Then** 仍无法定案时终态保持 `unknown`，退出码非 0。

### User Story 3 - 测试设计从规格场景派生用例并纳入版本 (Priority: P1)

`tf-test-plan` 读取 spec 的 Acceptance Scenario，按场景号幂等派生 `case` 行，再为每条用例在目标版本建 `run` 行并追加到 `ver.runs`；重复运行第二次新建 0 条。

**Why this priority**: 这是第 2 节点唯一的可执行载体，也是测试角色所有后续动作的锚点。

**Independent Test**: 对 `specs/019-test-contract/spec.md` 连续跑两次 `--apply`，第二次 `created_cases=0`、`created_runs=0`。

**Acceptance Scenarios**:

1. **Given** 一份含 N 条 Acceptance Scenario 的 spec，**When** 运行 `tf-test-plan --apply`，**Then** `case` 表新增 N 行，行 id 为 `<规格号>-US<n>-AS<m>`，且每行 `来源规格` 指向该 spec 的 `indep` 行。
2. **Given** 已派生过一次，**When** 再次运行 `--apply`，**Then** `created_cases` 与 `created_runs` 均为 0，名称/步骤有变化的用例就地更新。
3. **Given** 某 spec 删掉一条场景，**When** 再次运行，**Then** 报告 `orphans` 列出该用例「源场景已不存在」，不静默删除也不静默保留。
4. **Given** 目标版本，**When** 派生完成，**Then** 每条用例都有 `run` 行 `<版本号>--<用例号>`（`执行状态=todo`、`执行结果` 为空），且其 id 出现在 `ver.runs` 中；**不创建任何测试计划表或计划行**。
5. **Given** 第 1 节点的 `版本需求设计` 尚未 `done`，**When** 运行 `tf-test-plan --apply`，**Then** 返回 `failed` 并指出前序节点，零写入。

### User Story 4 - 开发与开发验收只推进本角色节点 (Priority: P1)

`tf-dev-implement` 在任务全部完成后把 `indep` 的 implement 状态与本版「开发」节点置 `done`；`tf-dev-check` 只在版本内规格全部 `accepted` 时推进「开发验收」。

**Why this priority**: 这两个节点决定代码是否可进入测试；跳过任何一个都会让测试跑在半成品上。

**Independent Test**: 对一个仍有未勾选任务的 spec 跑 `tf-dev-implement`：`failed` 且节点不变；把任务勾完再跑：`indep` 与 `ver` 读回均为 `done`。

**Acceptance Scenarios**:

1. **Given** 版本内某 spec 的 `tasks.md` 仍含未勾选任务，**When** 运行 `tf-dev-implement --apply`，**Then** 返回 `failed` 并列出未完成任务，`indep` 与 `ver` 零变更。
2. **Given** 任务全部完成，**When** 运行 `tf-dev-implement --apply`，**Then** 该 spec 的 `speckit-implement状态` 与 `ver.stage.dev` 读回均为 `done`。
3. **Given** 版本内任一规格的 `验收状态` 不是 `accepted`，**When** 运行 `tf-dev-check --apply`，**Then** 返回 `failed` 并逐条列出未验收规格，`开发验收` 节点不变。
4. **Given** 版本内规格全部 `accepted` 且「开发」节点为 `done`，**When** 运行 `tf-dev-check --apply`，**Then** `ver.stage.dev_accept` 读回为 `done`。
5. **Given** 前序节点未 `done`，**When** 运行任一推进技能，**Then** 技能在写之前 `failed` 并指出缺哪个节点。

### User Story 5 - 测试执行与测试验收 (Priority: P1)

`tf-test-implement` 只写目标版本的 `run` 行（`执行状态`/`执行结果`/证据/时间/执行人），全部执行完后推进「测试」；`tf-test-check` 在用例全执行、缺陷清零、变更回归通过三条同时成立时推进「测试验收」。

**Why this priority**: 第 5、6 节点直接决定发布条件；任何一条被跳过，`gate` 都会说谎。

**Independent Test**: 对版本内两条待执行用例跑 `tf-test-implement --all-pending --result pass`：两条 `run` 读回 `done/pass`，「测试」节点为 `done`；有未关闭缺陷时 `tf-test-check` 返回 `failed`。

**Acceptance Scenarios**:

1. **Given** 一条 `执行状态=todo` 的 `run` 行，**When** 运行 `tf-test-implement --case <用例号> --result pass --evidence <路径>`，**Then** 该行 `执行状态=done`、`执行结果=pass`、证据与执行人非空，且读回一致。
2. **Given** `运行结果` 给了值但 `执行状态` 仍是 `todo`，**When** 技能构造写入，**Then** 客户端先拒绝（`state/result` 一致性），零写入；若服务端返回 400，按 `failed` 上报。
3. **Given** 版本内所有 `run` 均已 `done`，**When** 运行 `tf-test-implement`，**Then** `ver.stage.test` 读回为 `done`；仍有 `todo` 时不推进。
4. **Given** 本版 `Bug管理` 中有未 `closed` 的缺陷，**When** 运行 `tf-test-check --apply`，**Then** 返回 `failed` 并列出缺陷，`测试验收` 节点不变。
5. **Given** 用例全执行、缺陷全关闭、变更全 `passed`，**When** 运行 `tf-test-check --apply`，**Then** `ver.stage.test_accept` 读回为 `done`，客户端重算的「六节点全部完成」为真。
6. **Given** 任一技能运行，**When** 检视输出与进程环境，**Then** 输出不含 `X-API-Key`/`TF_API_KEY` 的值；错误信息只引用字段名与行 id。

### User Story 6 - 技能可独立只读验证 (Priority: P2)

每个技能都有 `--dry-run`，能单独回答「这个节点现在能不能推进、缺什么、将写哪些字段」，不需要先写一次。

**Why this priority**: 评审与排障需要在不改变看板的前提下复现判定；写路径的验证不能依赖「先破坏再修复」。

**Independent Test**: 在验证夹具上按节点顺序对六个技能各跑一次 `--dry-run`，全部退出 0 且 `write_audit` 增量为 0。

**Acceptance Scenarios**:

1. **Given** 一个满足前置条件的节点，**When** 运行对应技能 `--dry-run`，**Then** 输出 `plan`（将写的字段与值）与全部检查项，退出码 0，零写入。
2. **Given** 一个不满足前置条件的节点，**When** 运行对应技能 `--dry-run`，**Then** `failed`，输出阻塞项清单，仍零写入。
3. **Given** 本地没有 `TF_BASE`，**When** 运行任一技能，**Then** 立即 `failed` 并提示设置 `TF_BASE`，不尝试读数据库文件。

## Requirements *(mandatory)*

- **FR-001**: 六个技能 MUST 一一对应 board@4 的六个版本节点：`tf-dev-plan`→`ver.stage.plan`、`tf-test-plan`→`ver.stage.test_design`、`tf-dev-implement`→`ver.stage.dev`、`tf-dev-check`→`ver.stage.dev_accept`、`tf-test-implement`→`ver.stage.test`、`tf-test-check`→`ver.stage.test_accept`。
- **FR-002**: 每个技能 MUST 声明并强制自己的表作用域（读/写），作用域外的表 MUST 在解析阶段拒绝；写操作 MUST 只指向本技能声明可写的表。
- **FR-003**: 所有数据访问 MUST 经 HTTP API；技能 MUST NOT 连接 SQLite、MUST NOT 读写 `data/` 下的数据库文件。
- **FR-004**: 写入 MUST 按 012 协议判定三态：200+`result=success`→`success`；400/401/404/405/422→`failed`；503（含 `detail` 信封）、其他 5xx、超时、非 JSON→`unknown`。`failed` MUST NOT 自动重试；`unknown` MUST 先回读，回读不能定案才按 100ms 起退避重试，最多 3 次。
- **FR-005**: 每次写 MUST 回读目标行，并逐字段比对意图值；只有全部一致才允许报 `success`；`unknown` 经回读确认时 MUST 在报告中注明。
- **FR-006**: `tf-test-plan` MUST 以 `specs/<dir>/spec.md` 的 Acceptance Scenario 为唯一真源派生 `case` 行，行 id MUST 为 `<规格号>-US<n>-AS<m>`，`case.indep` MUST 指向来源规格。
- **FR-007**: `tf-test-plan` MUST 幂等：同一规格连续派生两次，第二次新建 `case` 与 `run` 均为 0；名称/步骤变化就地更新；源场景消失 MUST 在 `orphans` 中报告，MUST NOT 静默删除。
- **FR-008**: `tf-test-plan` MUST 把用例纳入目标版本：为每条用例建 `run` 行（id=`<版本号>--<用例号>`，`执行状态=todo`，`执行结果` 为空），再把 id 追加到 `ver.runs`；MUST NOT 创建测试计划表、计划行或任何 `plan` 资源。
- **FR-009**: `tf-test-implement` MUST 在写 `run` 前校验 `执行状态/执行结果` 一致性（`todo`→结果空，`done`→结果非空）；重跑 MUST 就地更新同一 `run` 行，不新建。
- **FR-010**: 各技能 MUST 在写前校验本节点前序节点均为 `done` 且无 `failed`；服务端返回的 400 MUST 原样作为 `failed` 上报，不得翻译为成功。
- **FR-011**: 节点推进 MUST 使用 board@4 的字段名经字段名解析，MUST NOT 硬编码字段 id；缺表或字段 MUST 给出「项目未迁到 board@4」的可读错误。
- **FR-012**: 技能 MUST 默认只处理 `release_status=planned` 的版本；非 `planned` MUST `failed`。
- **FR-013**: 技能输出 MUST 为 JSON 报告，至少含 `skill`、`mode`、`result`、`checks`、`writes`、`readback`；退出码 MUST 为 0 当且仅当 `result=success`（`--dry-run` 且检查通过同样为 0）。
- **FR-014**: 技能 MUST NOT 打印或记录任何凭据（`TF_API_KEY`/`X-API-Key`）；错误信息只引用字段名、行 id、HTTP 状态与 `error` 文本。
- **FR-015**: 每个技能目录 MUST 含 `SKILL.md` 与 `scripts/` 入口；`--dry-run` MUST 覆盖该技能的全部读路径与检查，且零写入。

## 技能契约

| 技能 | 角色 | 节点 | 读 | 写 | 关键产物 |
|---|---|---|---|---|---|
| `tf-dev-plan` | 系统工程 | `ver.stage.plan` | ver, indep, dep | ver | 范围校验报告 + 节点置 `done` |
| `tf-test-plan` | 软件测试 | `ver.stage.test_design` | ver, indep, case, run | case, run, ver | 派生/更新用例 + 每版本 `run` 行 + `ver.runs` + 节点置 `done` |
| `tf-dev-implement` | 软件开发 | `ver.stage.dev` | ver, indep | indep, ver | `speckit-implement状态=done` + 节点置 `done` |
| `tf-dev-check` | 软件开发 | `ver.stage.dev_accept` | ver, indep | ver | 规格验收清单 + 节点置 `done` |
| `tf-test-implement` | 软件测试 | `ver.stage.test` | ver, case, run | run, ver | 执行结论 + 节点置 `done` |
| `tf-test-check` | 软件测试 | `ver.stage.test_accept` | ver, run, dep, bug | ver | 三闸门复算 + 节点置 `done` |

统一环境变量：`TF_BASE`（必填）、`TF_PROJECT`（默认 `tableflow`）、`TF_AGENT`（写审计身份）、`TF_API_KEY`（可选，只发送不打印）、`TF_ORIGIN`（默认 `human-request`）、`TF_REPO_ROOT`（默认按脚本位置推导仓库根）。

统一 CLI：六个入口都接受 `--version`/`--dry-run`/`--apply`/`--no-stage`。`--apply` 显式确认执行写入，与默认写模式等价（不传也写）；`--dry-run` 优先于 `--apply`，两者同时给出时按只读执行。

统一报告：

```jsonc
{
  "skill": "tf-test-plan",
  "project": "tableflow",
  "version": "v0.7.0",
  "mode": "dry-run",              // dry-run | apply
  "result": "success",            // success | failed | unknown
  "checks": [{"name": "前序节点", "ok": true, "detail": "版本需求设计=done"}],
  "writes": [{"target": "ver/v0.7.0", "field": "版本需求设计", "value": "done", "state": "skipped"}],
  "readback": {"ver/v0.7.0": {"版本需求设计": {"expect": "done", "actual": "done", "ok": true}}},
  "counts": {"created_cases": 0, "updated_cases": 0, "created_runs": 0},
  "orphans": [],
  "errors": []
}
```

## Verification

```bash
# 1) 本地 board@4 夹具（临时库 + HTTP 建表，不碰任何真实库）
bash specs/024-role-skills/verify/run_verify.sh

# 2) 对真实实例逐技能只读运行（board@4 已迁移后）
TF_BASE=http://localhost:8090 TF_PROJECT=tableflow TF_AGENT=agent-tf-role \
  python3 skills/tf-dev-plan/scripts/tf_dev_plan.py --version v0.7.0 --dry-run
```

验证脚本给出：六个技能 `--dry-run` 各退出 0 且所有写入为 `skipped`；`tf-test-plan` 对同一规格连续 `--apply` 两次，第二次 `created_cases=0`、`created_runs=0`；六节点按顺序全部推进后客户端重算「六节点全部完成」为真。

已执行记录（2026-11-22）：`bash specs/024-role-skills/verify/run_verify.sh` 退出 0，证据在 `specs/024-role-skills/verify/evidence/`：

| 证据 | 结论 |
|---|---|
| `summary.json` | `six_skills_readonly_ok=true`、`second_derive_zero=true`、`six_nodes_done=true` |
| `01-dev-plan-dryrun.json` … `06-test-check-dryrun.json` | 六个技能只读运行 `success`，`writes` 全部 `skipped` |
| `02-test-plan-apply-1.json` | 019-AR 派生 27 条用例、建 27 条 `run`、挂入 `ver.runs` |
| `02-test-plan-apply-2.json` | 第二次 `created_cases=0`、`created_runs=0`、`unchanged_cases=27`、`reused_runs=27` |
| `06-test-check-apply.json` | 六节点全 `done`，客户端 `stage_done=true` |

D-01（`--apply` 参数）修复回放（2026-11-22）：`bash specs/024-role-skills/verify/run_d01_apply.sh` 退出 0，证据在 `specs/024-role-skills/verify/evidence-d01/results.json`——024 US3-AS1..AS5 / US4-AS1..AS4 共 9 条 AS 均按字面 `--apply` 命令复跑通过；六个技能均接受 `--apply`；无 `unrecognized arguments`；`--apply --dry-run` 同时给出时按只读执行、零写审计。

## Non-Goals

- 不实现服务端的节点串行校验与闸门一致性校验（025 的范围）；技能只做写前提示，不替服务端放行。
- 不实现角色切换界面与配色（022 的范围）；技能只固化「角色能碰哪些表」。
- 不实现计算字段表达式与重算（023 的范围）；技能在客户端复算判定值，与看板计算字段值对照但不依赖。
- 不迁移存量项目、不建表、不改字段（019 实现/T1 的范围）；技能对缺表/缺字段只报错。
- 不代替人给 `spec.acceptance` 或 `bug.status`；验收与缺陷关闭仍由人/缺陷流程写入。
- 不把执行结果回写 MeterSphere（MS 只保留历史台账身份）。

## Success Criteria

- 六个技能在验证夹具上各只读运行一次，全部 `success` 且零写入。
- `tf-test-plan` 对同一规格派生两次，第二次新建 `case` 与 `run` 均为 0。
- 每个技能的写路径都有回读证据；`failed` 不重试、`unknown` 不被当成功。
- 六节点按 1→6 顺序推进后，`ver` 读回六节点全 `done`，客户端复算 `stage_done=true`，`gate` 与看板计算字段一致（若存在）。
- 技能输出中不出现任何 key/token；`grep -r "TF_API_KEY" skills/tf-*/scripts` 只出现在读取环境变量处，不出现在日志语句。

## 依赖与验收边界

- 依赖 T1 的六表与版本表字段、T3 的写协议（`run.state/result` 一致性、两步写入语义）、T7 的六节点串行与闸门校验。三者未落地前，本规格的验证在本地 board@4 夹具上完成（HTTP 建表 + 种子，`verify/` 可复现）；三者落地后，同一组命令对真实项目重跑即为集成验收。
- 技能不复制服务端的闸门实现：服务端返回 400 时，技能报 `failed` 并附服务端错误；技能自己的写前检查只用于提前给出阻塞清单。
