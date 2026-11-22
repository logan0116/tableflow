# Feature Specification: 版本表六节点四态与串行/闸门校验（025）

**Feature Branch**: `025-version-stage`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 `025-AR`。board@4 给版本表加了六个四态节点（`ver.stage.plan/test_design/dev/dev_accept/test/test_accept`），发布条件自 board@4 起只由「六节点是否全部完成」决定。字段存在不等于闸门存在：节点是普通 enum，任何客户端都能一行 PATCH 把它们改成六个 `done`，于是「发布条件」可以在一条用例都没跑、一个缺陷都没关的情况下变绿。本规格把契约 `rules.version_stage_serial` / `rules.version_stage_gate_consistency` 落到写侧，并明确「人工能记录进度，但不能绕过判定」。

**实现落点**:

| 落点 | 内容 |
|---|---|
| `backend/src/tableflow/version_stage.py` | 六节点识别、串行推进校验、节点闸门一致性校验（直读源数据） |
| `backend/src/tableflow/write_service.py` | `create_row` / `update_row` 统一入口接线（沿用 020 的 `run_protocol` 模式） |
| `backend/tests/test_version_stage_025.py` | 15 条用例，覆盖跳级 400、三处闸门 400、六节点全 done 时 `gate` 为真、回退转假、空集放行、不自动回退、识别口径 |

**边界**: `stage_done` 字段、`gate` 规则与三布尔 gate 标记的**数据层迁移**归 019/023 的实施链（T4 的门禁与迁移脚本）；本规格只定义并实现**写侧校验**，不新建、不改名任何字段，不改计算引擎。测试夹具按 board@4 契约临时定义 `stage_done`/`gate` 只是为了验证「六节点全 done → gate 为真」这条行为，不代表数据层已迁移。

## 结论速览

1. **六个节点是一个状态机，不是一个多选字段组**：节点只有按 `plan → test_design → dev → dev_accept → test → test_accept` 的顺序到达 `done`；到达 `done` 时它左边的节点必须全部 `done`。跳级（例如第 4 个节点直接 `done`）返回 400，零写入。
2. **`failed` 不是终态，但会挡住下游**：任一前序节点为 `failed` 时，后序节点不得向前推进（`doing`/`done` 都拦）；把失败节点返工改回 `doing` 后，后序节点才能继续。反向移动（把后序节点改回 `todo`）不拦，**也不自动回退下游节点**。
3. **三个关键节点有数据闸门**：`开发验收` 要求本版规格全部 `accepted`；`测试` 要求本版用例全部 `state=done`；`测试验收` 要求本版缺陷全部 `closed` 且变更单全部 `regress=passed`。空集为真（沿用 `empty_set`），任一不满足 400，零写入。
4. **闸门只在「到达 done」的那一刻把关**：同一节点重放 `done`、或改与该节点无关的字段，不再重新验闸门（否则历史数据一旦恶化，整张版本行都无法编辑）。代价是 gate 不是持续审计——节点全 `done` 之后证据再恶化，gate 不会自动转假，这由评审/缺陷流程发现（见「已知边界」）。
5. **校验直读源数据，不读 `case_done`/`bug_clear`/`change_done`/`spec_done` 计算值**：`update_row` 里校验发生在重算之前，同一请求既追加 `ver.runs` 又置 `stage.test=done` 时计算值还是旧的。这里按与 010 相同的口径自行判定（空集为真、目标行缺失按未就绪），与计算字段等价且不受重算时机影响。

## 背景与问题证据

| 现状 | 证据 | 后果 |
|---|---|---|
| 六节点是普通 enum，无写入期约束 | `board@4.yaml` 的 `rules.version_stage_serial` / `version_stage_gate_consistency` 标着"写入期校验"；020 之前 `write_service._validate_values` 只校验枚举值域 | 一条 PATCH 就能把六节点改成全 `done`；用例一条没跑、缺陷一个没关，发布条件照样变绿 |
| 发布条件只看节点，节点又能人工改 | `board@4.yaml` 的 `rules.release_gate`：`ver.gate = and(ver.stage_done)`；`version_stage_done = 六节点全部 done 之与` | 闸门被"人工填表"绕过；board@3 时代至少还有三个计算布尔挡着 |
| 计算值在写事务末尾才重算 | `write_service.update_row` 的顺序是：校验 → 落库 → `calculation.recompute_for_write` | 若校验读 `case_done` 等计算值，同一请求内追加用例 + 置节点 done 会拿旧值判定，出现"刚补的用例不算数"的假 400 |
| 019 的迁移脚本只补结构 | `backend/scripts/migrate_board4.py` 建六个 enum、按发布状态初始化存量行，不做写接口校验（归 020/025） | 存量 `released` 行的六节点由脚本直接写库；新的人工推进没有任何闸门 |
| 020 已建立写侧校验入口 | `write_service.create_row` / `update_row` 调 `run_protocol.validate_row_write`（落库前，失败 400 零写入） | 025 沿用同一模式接入，不需要新路由、不改信封 |

## Clarifications

### Session 2026-11-22

- Q: 校验放在哪一层？ → A: 写服务层，`create_row` / `update_row` 各一处调用（与 020 的 `run_protocol` 完全同构）。理由：脚本、测试直连写服务时受同一口径约束；接口层只是薄路由，散在路由里必然漏。校验在任何落库语句之前，失败由 `run_write` 回滚并记失败审计。
- Q: 怎么认定"这是版本表的六节点"？ → A: 表内**恰好六个**值域为 `{todo,doing,done,failed}` 的 enum 字段。不看表 id、字段 id 或表级 `kind`。board@4 里只有 `ver.stage.*` 是这个值域：`spec.stage.*` 含 `na`、`change.regress` 含 `passed`、`bug.status` 是另一组四值、`run.state` 只有两值。因此迁移脚本怎么给字段起 id 都识别得到。
- Q: 六个节点的顺序怎么定？ → A: 先按语义键解析（字段 id 里的 `stage-*` 段 → `plan/test_design/dev/dev_accept/test/test_accept`；退一步按契约名称「版本需求设计/测试设计/开发/开发验收/测试/测试验收」），再按契约顺序排。解析不全时退回字段 `order`（019 门禁保证六节点按契约顺序落库），此时只跳过无法定位的闸门项，不猜节点身份。
- Q: 为什么前序 `failed` 时后序连 `doing` 也不让置？ → A: 契约 `version_stage_serial` 原文是"前一节点处于 failed 时，后一节点不得推进"，"推进"含 `doing`。若只拦 `done`，界面上仍会出现"开发失败、测试进行中"的假进度。反向移动（改回 `todo`）不拦，因为那是撤票不是推进。
- Q: 不自动回退下游节点怎么理解？ → A: 把某个已完成节点改回 `doing`/`failed` 时，服务端**不动**它右边的节点（契约 `version_stage_failure`：失败影响哪个下游节点由人判断）。规格不提供"级联回退"，也不提供"跳过"取值（节点只有 `todo/doing/done/failed`）。
- Q: 闸门判定为什么不用 `ver.case_done` 等计算字段？ → A: 重算时机（见结论速览 5）。写侧校验按同样口径直接从 `ver.runs` / `ver.bugs` / `ver.changes` / `ver.specs` 关联行读判据字段；这是"同一事实的同一算法"，不是第二套口径。对应计算字段仍由 023/019 维护，供展示与 `gate` 使用。
- Q: 空集怎么算？ → A: 沿用 board@4 `empty_set`：本版没纳入用例/缺陷/变更/规格时，该项闸门为真（含义是"本版无此类工作"）。目标行缺失（悬空引用）按未就绪处理，与 010 一致。
- Q: 六节点全 done 之后证据恶化怎么办？ → A: 校验不是持续审计。节点全 `done` 后 gate 保持为真，直到有人显式把某个节点改回非 `done`；此时不自动回退其它节点，gate 由重算转为假。证据恶化由评审与缺陷流程发现，不由写入期闸门兜底——这是契约 `version_stage_failure`"由人判断"的直接代价，写进「已知边界」。
- Q: 存量 `released` 行的六节点怎么初始化？ → A: 迁移脚本直接写库（`migrate_board4.py` 的 `_init_stage_nodes`，T4/019 范围），不走写接口，因此不触发本规格的校验。若某个项目改走写接口批量补数据，六节点全 `done` 的行会逐条经过闸门；空关联时三项均真，能通过；有未满足证据时会被 400，需要先补证据（或用迁移脚本）。
- Q: 依赖的 relation 认不出时怎么办？ → A: 该项闸门不启用（不猜）。依赖来源按目标表值域识别：`run` = 含 `{todo,done}` + `{pass,fail,blocked,skip}` 子集；`bug` = `{open,fixing,verifying,closed}`；`dep` = `{todo,doing,passed,failed}`；`indep` = `{pending,accepted,rejected}`。同一角色有多个 relation 时同样不启用。字段缺失由 019 门禁（FR-015）负责暴露，不由写侧猜。
- Q: 新建版本行时要不要校验？ → A: 要，但只对"提交值本身就是 `done` 的节点"校验。新建 `planned` 版本（六个 `todo`）不受影响；新建一个六节点全 `done` 的历史版本（空关联）也能通过（空集为真），与迁移口径一致。
- Q: 与 020 的 `run_protocol` 校验谁先谁后？ → A: 同一写请求里先 `run_protocol`（先保证执行记录本身自洽、清单不重复不跨版本），再 `version_stage`（再判节点闸门），最后才是必填/枚举/关联存在性约束。错误优先级由此固定：先结构性错误，再进度闸门错误。

## 使用者与验收场景

### User Story 1 - 串行推进不可跳级 (Priority: P1)

填版本进度的人只能从左往右推进；跳级、或在前序失败时推进后序，都得到 400 且整行不变。

**Why this priority**: 六节点是发布条件的唯一输入，"能跳级"等于没有阶段判定。

**Independent Test**: 六个 `todo` 的版本行，直接 PATCH 第 4 个节点 `done` → 400；按顺序推进 → 200；把第 3 个节点置 `failed` 后第 4 个节点置 `doing` → 400，返工后 → 200。

**Acceptance Scenarios**:

1. **Given** 六节点全 `todo`，**When** 把「测试设计」（第 2 节点）置 `done`，**Then** 400（错误指出必须串行推进并列出未完成前序），六节点与 `business_changes` 均不变。
2. **Given** 六节点全 `todo`，**When** 把「开发验收」（第 4 节点）置 `done`，**Then** 400，错误列出「版本需求设计/测试设计/开发」三项未完成。
3. **Given** 证据齐备（规格 accepted、用例 done、缺陷 closed、变更 passed），**When** 从第 1 到第 6 节点逐个置 `done`，**Then** 六次都 200。
4. **Given** 前三个节点 `done`、第 3 个节点为 `failed`，**When** 把第 4 个节点置 `doing` 或 `done`，**Then** 400，错误指出前序节点 failed；**When** 把第 4 个节点改回 `todo`，**Then** 200（不算推进）。
5. **Given** 前序 `failed` 的节点被返工改回 `doing`，**When** 再推进后序节点，**Then** 200。
6. **Given** 六节点全 `done`，**When** 把第 3 节点改回 `failed`，**Then** 200，且第 4–6 节点仍为 `done`（不自动回退下游）。

### User Story 2 - 节点闸门不可绕过 (Priority: P1)

三个关键节点到达 `done` 时必须有数据支撑，人工改不出"全绿"。

**Why this priority**: 这三处正是 board@4 用来自动判定「用例跑完没有、缺陷清完没有、规格验收没有」的地方。

**Independent Test**: 规格仍 `pending` 时置「开发验收」`done` → 400；有用例未执行时置「测试」`done` → 400；缺陷未关闭或变更未回归时置「测试验收」`done` → 400。

**Acceptance Scenarios**:

1. **Given** 前三个节点 `done`、本版规格 `acceptance=pending`，**When** 把「开发验收」置 `done`，**Then** 400（错误指名未 accepted 的规格行），节点保持 `todo`。
2. **Given** 规格已 accepted、前四个节点 `done`、本版有一条 `run.state=todo`，**When** 把「测试」置 `done`，**Then** 400（错误指名未执行的执行记录）；把该记录改为 `state=done` 后重试，**Then** 200。
3. **Given** 前五个节点 `done`、本版缺陷仍 `fixing`，**When** 把「测试验收」置 `done`，**Then** 400（错误指名未关闭缺陷）。
4. **Given** 缺陷已清零、但本版变更单仍 `doing`，**When** 把「测试验收」置 `done`，**Then** 400（错误指名未回归通过的变更单）；置为 `passed` 后重试，**Then** 200。
5. **Given** 本版未关联任何用例/缺陷/变更/规格，**When** 逐节点推进到 `done`，**Then** 相应闸门按空集为真放行（200）。

### User Story 3 - 六节点全 done 与 gate (Priority: P1)

六节点全部 `done` 后，`stage_done` 与 `gate` 随重算转真；节点回退后转假。

**Why this priority**: 这是 019 的发布条件口径，也是 025 校验的最终目的。

**Independent Test**: 证据齐备后逐节点推进到全 `done`，读表得到 `stage_done=true`、`gate=true`；把一个节点改回 `doing`，两者转假。

**Acceptance Scenarios**:

1. **Given** 证据齐备、六节点全部推进到 `done`，**When** 读版本表，**Then** `六节点是否全部完成=true`、`发布条件=true`（夹具按 board@4 规则定义，真实迁移归 T4）。
2. **Given** 六节点已全 `done` 且 gate 为真，**When** 只改版本行的说明字段（不碰节点），**Then** 200，gate 仍为真（不重复验闸门）。
3. **Given** 六节点全 `done` 后把某节点改回 `doing`，**When** 读版本表，**Then** `stage_done=false`、`gate=false`。

### User Story 4 - 识别不误伤 (Priority: P2)

只有版本表的六节点结构受这套校验约束；字段 id 不规范时按契约名称解析，仍生效；其它表不受影响。

**Why this priority**: 校验写死了识别口径才有意义；误伤普通表会让所有既有项目不可用。

**Independent Test**: 只有 1 个四态 enum 的普通表写 `done` → 200；字段 id 非 `stage-*` 但名称是契约名称的版本表，跳级 → 400。

**Acceptance Scenarios**:

1. **Given** 一张普通表只有 1 个值域 `{todo,doing,done,failed}` 的 enum，**When** 写 `done`，**Then** 200（不是六节点结构，不套用校验）。
2. **Given** 版本表的六个节点字段 id 是 `s1…s6`、名称仍是契约名称，**When** 跳级置第 4 节点 `done`，**Then** 400；按顺序推进，**Then** 200（按名称解析顺序）。
3. **Given** 版本表恰好六个四态 enum，**When** 写入第一个节点 `done`，**Then** 200（首节点无前序）。

### Edge Cases

- 同一 PATCH 里既改节点又改证据来源：闸门按合并后的 `ver.runs` 等数组判定，同一请求内补的关联算数（不读重算前的计算值）。
- 目标行缺失（悬空引用）：按未就绪处理（400），与 010 的悬空口径一致；不静默当空集。
- 前序节点值缺失（历史行未填）：按"未完成"处理（不等于 `done`），错误里显示"未填"。
- 迁移脚本直接写库初始化存量行：不经过本校验（T4/019 范围）；之后的人工推进照常受约束。
- 六节点全 `done` 之后重放任一节点 `done`：无变化即无校验（幂等）；不算"再次推进"。
- 把节点从 `done` 改成 `done` 并顺手改证据：证据不满足也放行——闸门只在"到达 done 的那一刻"生效，见「已知边界」。
- `recompute` 接口不触发本校验：它不写节点值。
- `gate` 字段本身仍受 010 的闸门字段保护（只能清除覆盖，不能设值），本规格不重复。

## Requirements *(mandatory)*

- **FR-001**: 六节点 MUST 按 `plan → test_design → dev → dev_accept → test → test_accept` 串行推进；某节点置 `done` 时其全部前序 MUST 为 `done`，否则 400 且零写入。
- **FR-002**: 任一前序节点为 `failed` 时，后序节点 MUST NOT 被置为 `doing` 或 `done`（400）；反向移动（改回 `todo`/`failed` 之前的值）MUST NOT 被拦截。
- **FR-003**: 「开发验收」置 `done` MUST 要求本版 `ver.specs` 关联的规格全部 `spec.acceptance=accepted`。
- **FR-004**: 「测试」置 `done` MUST 要求本版 `ver.runs` 关联的执行记录全部 `run.state=done`。
- **FR-005**: 「测试验收」置 `done` MUST 要求本版 `ver.bugs` 关联缺陷全部 `bug.status=closed`，且 `ver.changes` 关联变更单全部 `change.regress=passed`。
- **FR-006**: 上述闸门 MUST 按合并后的关联数组判定（同一请求内新增的关联算数），空集 MUST 为真，悬空目标行 MUST 按未就绪处理。
- **FR-007**: 校验 MUST 只在节点值发生变化时生效；重放同一值、或改无关字段 MUST NOT 触发闸门复验。
- **FR-008**: 校验 MUST 在 `create_row` 与 `update_row` 的统一入口执行（落库前），失败 MUST 400、MUST NOT 改动行数据、MUST NOT 新增 `business_changes`；失败审计 MUST 照 P-043 记录。
- **FR-009**: 六节点识别 MUST 以"恰好六个值域为 `{todo,doing,done,failed}` 的 enum 字段"为准，MUST NOT 依赖表 id、字段 id 或表级 `kind`；顺序解析 MUST 先语义键、再字段 `order`。
- **FR-010**: 不自动回退下游节点；MUST NOT 引入"跳过"取值（节点取值域固定四态）。
- **FR-011**: 本规格 MUST NOT 新建/改名 `stage_done`、`gate` 或三布尔字段；MUST NOT 改计算引擎与既有计算口径。
- **FR-012**: 请求/响应信封 MUST 不变（protocol@2 的 400 `{"result":"failed","error":"..."}`），MUST NOT 新增路由。

## 校验规则表

**图例**：`已实现（025）` = 本次落地的写侧校验；`满足` = 既有行为已符合；`边界` = 有意不做。

| 编号 | 规则 | 现状 | 判定方式 |
|---|---|---|---|
| VS-01 | 六节点识别：恰好六个值域 `{todo,doing,done,failed}` 的 enum 字段；不依赖表 id/字段 id/`kind` | 已实现（025） | 普通表只有 1 个四态 enum 写 `done` → 200；版本表照样校验 |
| VS-02 | 顺序解析：字段 id 的 `stage-*` 段 → 语义键；退一步按契约名称；都不成时退回字段 `order` | 已实现（025） | 字段 id 为 `s1…s6`、名称为契约名称的版本表，跳级仍 400 |
| VS-03 | 串行：节点置 `done` 时前序必须全部 `done` | 已实现（025） | 第 2/4 节点跳级 → 400，错误列出未完成前序；顺序推进 → 200 |
| VS-04 | 失败阻断：前序有 `failed` 时后序不得置 `doing`/`done` | 已实现（025） | 第 3 节点 failed 后第 4 节点 `doing` → 400；失败节点改回 `doing` 后 → 200 |
| VS-05 | 反向不拦、不级联：把节点改回 `todo`/`failed` 不拦，也不动下游 | 已实现（025） | 六节点全 done 后第 3 节点 `failed` → 200，第 4–6 仍 done |
| VS-06 | 开发验收闸门：本版规格全部 accepted | 已实现（025） | 规格 `pending` → 400（指名规格行）；accepted 后 → 200 |
| VS-07 | 测试闸门：本版用例全部 `state=done` | 已实现（025） | 有 `todo` 执行记录 → 400（指名记录）；执行后 → 200 |
| VS-08 | 测试验收闸门：缺陷全部 closed 且变更全部 passed | 已实现（025） | 缺陷 `fixing` → 400；缺陷 closed 但变更 `doing` → 400；都满足 → 200 |
| VS-09 | 闸门在"到达 done"时校验一次：重放 done、改无关字段不重验 | 已实现（025） | 六节点 done、gate 真 → 缺陷回退 + 改说明 → 200，gate 仍真 |
| VS-10 | 零写入与审计：校验在落库前，失败 400、行不变、`business_changes` 不增、失败审计照记 | 已实现（025） | 失败后 `row_records` 六节点不变；`business_changes` 计数不变；`write_audit` 末条 `failed` |
| VS-11 | 依赖来源按目标表值域识别（run/bug/dep/indep）；缺来源或多义时不猜、该项不启用 | 已实现（025） | 去掉 `ver.specs` relation 的副本上推进「开发验收」不被拦（记录为已知降级，由 019 门禁暴露字段缺失） |
| VS-12 | 信封不变：仍走 protocol@2 的 400 失败信封，不新增路由 | 满足 | 失败响应体只含 `result`/`error`；`/api/agent` 路径清单不变 |

## 状态机

```
            ┌──────────────────────────────────────────────────────────────┐
            │  plan ─▶ test_design ─▶ dev ─▶ dev_accept ─▶ test ─▶ test_accept │
            └──────────────────────────────────────────────────────────────┘
到达 done 的前置条件（按节点）：
  plan           前序：无
  test_design    前序：plan done
  dev            前序：plan, test_design done
  dev_accept     前序：plan…dev done          ＋ 本版规格全部 accepted
  test           前序：plan…dev_accept done   ＋ 本版用例全部 state=done
  test_accept    前序：plan…test done         ＋ 缺陷全部 closed 且变更全部 passed

任意前序为 failed  ⇒ 该节点不得置 doing/done（返工：failed → doing 后可继续）
反向移动          ⇒ 允许；服务端不自动回退其它节点；无"跳过"取值
```

## 客户端实现清单（人工推进版本进度）

1. 读版本行，确认要推进的节点与其前序节点的当前值（读改写自检，012 P-037）。
2. 若前序里有 `failed`：先返工该节点（`failed → doing`），再谈推进。
3. 推进前先确认该节点自己的闸门：`开发验收` 查本版规格 `acceptance`、`测试` 查 `ver.runs` 的 `state`、`测试验收` 查缺陷与变更单；不满足先补证据，不要先试后改。
4. `PATCH` 只提交要变的那一个节点字段（`{"values":{"<节点字段>":"done"}}`）；不要在同一请求里顺手改别的节点。
5. 400 时按错误文本定位（人读）：错误里会点名未完成前序、未 accepted 的规格、未执行的执行记录、未关闭缺陷/未通过变更单；机器判定只用状态码与 `result`（P-026）。
6. 跨节点动作（一次要改两个节点）分两次请求；第一次失败即停，不要"补一个成功"。
7. 失败后回读版本行确认零写入，再决定补证据还是返工。
8. 不尝试把节点设成 `skipped` 之类的值：取值域只有 `todo/doing/done/failed`，写别的值由枚举校验 400。

## 示例会话（临时库）

```bash
H=(-H 'X-Agent-Id: agent-demo' -H 'Content-Type: application/json')

# 1 跳级：第 2 节点直接 done
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-stage-test-design":"done"}}'
# → 400 {"result":"failed","error":"版本进度必须串行推进：「测试设计」置 done 前，前序节点必须全部 done；未完成：「版本需求设计」=todo"}

# 2 顺序推进第一节点
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-stage-plan":"done"}}'
# → {"result":"success","id":"v0.7.0"}

# 3 开发验收闸门：规格仍 pending
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-stage-dev-accept":"done"}}'
# → 400 {"result":"failed","error":"「开发验收」置 done 前，本版规格必须全部 accepted：025-AR=pending（字段「独立需求管理」）"}

# 4 测试闸门：仍有用例未执行
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-stage-test":"done"}}'
# → 400 {"result":"failed","error":"「测试」置 done 前，本版用例必须全部执行：v0.7.0--025-US1-AS1=todo（字段「测试用例」）"}

# 5 测试验收闸门：缺陷未清零
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/<ver>/rows/v0.7.0 \
  -d '{"values":{"tf-v-stage-test-accept":"done"}}'
# → 400 {"result":"failed","error":"「测试验收」置 done 前，本版缺陷必须全部 closed：BUG-01=fixing（字段「Bug管理」）"}

# 6 六节点全部 done 后：stage_done / gate 随重算转真
curl -s $TF_BASE/api/tables/<ver>/table | python3 -m json.tool | grep -A1 '六节点是否全部完成'
```

## 已知边界与缺口

| 编号 | 事项 | 影响 | 归属 |
|---|---|---|---|
| N1 | 闸门不是持续审计：节点全 done 后证据恶化，gate 不自动转假 | 需要评审/缺陷流程发现；写入期校验不做定时复核 | 设计取舍（契约 `version_stage_failure` 由人判断） |
| N2 | 依赖来源 relation 认不出时该项闸门不启用 | 字段被删/改名的项目可能失去该项保护 | 019 门禁（FR-015）负责暴露；写侧不猜 |
| N3 | 迁移/批量补数据没有"放行一次"的接口 | 存量 `released` 行只能由迁移脚本直接写库，或先补证据再走接口 | T4/019 迁移脚本 |
| N4 | 无跨节点批量推进接口 | 六节点要六次请求；中途失败即停 | 协议@2 P-019（一次只写一个资源） |

## 非目标

- 不新建/改名 `stage_done`、`gate` 或三布尔字段；不改三布尔的 gate 标记（T4/019 数据层迁移）。
- 不改计算引擎（and/rollup/count 口径沿用 010/023）。
- 不实现界面（六节点在版本行如何展示、角色视图属 021/022）。
- 不实现"节点失败后自动回退下游"或"跳过"取值。
- 不做证据的定时复核、不做发布流程编排。
- 不迁移 MeterSphere 数据，不改 `case`/`run` 的写入协议（020 已定义）。

## Success Criteria

- **SC-001**: 六节点全 `todo` 的版本行，跳级置第 2 或第 4 节点 `done` 返回 400，六节点与 `business_changes` 不变。
- **SC-002**: 前序 `failed` 时后序 `doing`/`done` 返回 400；失败节点改回 `doing` 后可继续推进。
- **SC-003**: 规格 pending 时「开发验收」、有用例 todo 时「测试」、缺陷未清零或变更未通过时「测试验收」，各自 400 且零写入；证据补齐后各自 200。
- **SC-004**: 证据齐备后六节点全部 `done`，`stage_done` 与 `gate` 读回为真；节点回退后转假。
- **SC-005**: 只有 1 个四态 enum 的普通表不受影响；字段 id 不规范但名称为契约名称的版本表仍受校验。
- **SC-006**: `cd backend && .venv/bin/python -m pytest -q`：本规格新增 15 条用例全绿，既有用例无回退。

## 验收判定（场景 → 测试）

| 场景 | 测试（`backend/tests/test_version_stage_025.py`） |
|---|---|
| US1-AS1 / AS2（跳级 400 零写入） | `test_skip_node_rejected_zero_write` / `test_skip_to_later_node_rejected` |
| US1-AS3（顺序推进 200） | `test_serial_forward_allowed_in_order` |
| US1-AS4 / AS5（failed 阻断与返工） | `test_failed_predecessor_blocks_forward_and_rework_unblocks` |
| US1-AS6（不自动回退下游） | `test_no_auto_rollback_of_downstream` |
| US2-AS1（开发验收需规格 accepted） | `test_dev_accept_requires_specs_accepted` |
| US2-AS2（测试需用例全执行） | `test_test_requires_all_runs_done` |
| US2-AS3 / AS4（测试验收需缺陷清零 + 变更回归） | `test_test_accept_requires_bug_clear` / `test_test_accept_requires_change_regressed` |
| US2-AS5（空集放行、create 路径同受校验） | `test_empty_set_gates_pass_on_new_version` |
| US3-AS1 / AS2 / AS3（gate 真、重放不重验、回退转假） | `test_gate_computed_true_when_all_six_done` / `test_replay_same_done_does_not_revalidate_gate` / `test_gate_turns_false_after_node_rollback` |
| US4-AS1 / AS2（不误伤与命名鲁棒） | `test_non_version_table_with_one_stage_enum_untouched` / `test_stage_nodes_resolved_by_name_when_ids_unconventional` |

## Key Entities

- **六节点（version stage nodes）**：版本行的六个四态 enum，串行推进；到达 `done` 是发布条件的唯一输入。
- **串行键（node key）**：`plan/test_design/dev/dev_accept/test/test_accept`，由字段 id 的 `stage-*` 段或契约名称解析。
- **节点闸门（node gate）**：`开发验收`↔规格 accepted、`测试`↔用例全执行、`测试验收`↔缺陷清零且变更回归通过。
- **证据来源（evidence source）**：版本表指向 `indep/dep/run/bug` 的 relation 字段，按目标表值域识别。
- **到达时刻（transition moment）**：节点值从非 `done` 变为 `done` 的那一次写入，是闸门校验的唯一触发点。
