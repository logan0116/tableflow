---
name: tf-test-plan
description: "推进 tableflow board@5 版本第 2 节点「测试设计」（软件测试角色）：把 specs/<dir>/spec.md 的 Acceptance Scenario 按场景号幂等派生为 case 行，再为每条用例建 run 行（<版本号>--<用例号>，state=todo）并追加到 ver.runs，最后写 ver.测试设计=done 并回读。重复运行第二次新建 0 条；源场景消失只报告不静默删；不建测试计划。触发词：tf-test-plan、测试设计、派生用例、场景转用例、纳入版本、第2节点、用例幂等。"
---

# tf-test-plan：把规格场景变成版本可执行的用例

测试设计的唯一真源是 `specs/<dir>/spec.md` 的 Acceptance Scenario。本技能把真源**派生**成 `case` 行，再把用例**纳入**目标版本（建 `run` 行 + 追加 `ver.runs`），最后推进第 2 节点。

- 角色：软件测试
- 节点：`ver.stage.test_design`（字段名「测试设计」）
- 表作用域：读 `版本管理`/`独立规格需求`/`测试用例`/`用例执行情况`；写 `测试用例`/`用例执行情况`/`版本管理`
- 口径来源：`specs/019-test-contract/board@5.yaml` 的 `rules.case_projection`、`conventions.run_two_step_write`、`rules.run_one_per_version_case`
- **不建测试计划**：board@4 没有 `plan` 表；版本的执行范围就是 `ver.runs`

## 何时用

- 版本进入测试设计：把本版交付规格的场景落成用例并纳入本版。
- **复测历史能力（035）**：把不属本版交付的历史规格用例也纳入本版，只写 `ver.测试用例`，不改 `ver.独立需求管理`。
- 规格改了场景：重跑本技能，已有用例就地更新；删掉的场景进 `orphans`。
- 想先看会新建多少条、挂哪些执行记录：`--dry-run`。

## 何时不用

- 登记需求/开变更单 → `tf-register`。
- 执行用例、写通过与否 → `tf-test-implement`。
- MS 同步已下线（032 取消），本技能不再对接 MeterSphere。
- 建表/建字段/建计划 → 不在技能范围。

## 派生规则（与契约逐条对应）

| 契约 | 本技能实现 |
|---|---|
| 一条 Acceptance Scenario = 一条 `case` | 解析 `### User Story n` 块内的 `1. **Given** ... **When** ... **Then** ...` |
| 行 id = 场景号 | `<规格号>-US<n>-AS<m>`，如 `019-US1-AS1`；规格号取 `indep` 行 id 的前三位 |
| `case.indep` 指向来源规格 | 单值 relation `[spec_id]`；来源规格可以在本版交付范围外（035），但不能不存在 |
| `case.name` = Then 摘要 | Then 前 80 字；`前置条件`=Given、`操作步骤`=When、`预期结果`=Then |
| 优先级只记录意图 | 取 User Story 的 `(Priority: Pn)`，只接受 `P0/P1/P2`，其他回落 `P1` |
| 重复派生幂等 | 已存在则逐字段比对：不同才 PATCH 差异字段，相同计 `unchanged` |
| 源场景消失要报告 | 同前缀但不在本次派生集合的 `case` 行进 `orphans`，不删、不静默留 |
| 同版本同用例只有一条执行记录 | `run` 行 id = `<版本号>--<用例号>`，撞 id 即复用并校验 `用例号/用例` 一致 |
| 纳入是两步写入 | 先 POST `run` 行（`执行状态=todo`、`执行结果` 不写），再 PATCH `ver.测试用例` 追加；第二步失败要回读发现 |
| 空集语义 | 本版没纳入用例时 `用例总数=0`、`已完成=0`、`用例是否完成=真`，由计算字段承担 |
| 交付范围与测试范围分离（035） | 来源规格不在 `ver.独立需求管理` 时照常派生，报告列进 `out_of_scope_specs`；来源能力未验收时列进 `unaccepted_specs`，均不阻断 |
| 纯回归版本 | 本版交付范围为空、只用 `--spec` 指定来源时照常执行；但两者都为空则 `failed`（无处派生） |
| 修复版复用既有用例 | `--reuse-from <版本>`：把源版本收录的用例复制成本版的执行记录（`<本版>--<用例号>`），不重新派生 `case` |
| 精确复用 | `--reuse-from` 可配 `--case <用例号>`（可重复）只复用指定用例；指定的用例不在源版本时 `failed`，不静默跳过 |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role

# 只读：看会新建/更新多少条、会建哪些 run、会挂哪些清单
python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR --dry-run

# 真正派生 + 纳入版本 + 推进节点
python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR --apply   # 显式确认写入（等价于上一行）

# 版本内全部规格；只做用例不推进节点
python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --no-stage

# 修复版：复用上一版的用例，只挑与本版缺陷相关的几条
python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.8.5 \
  --reuse-from v0.8.3 --case 083-US2-AS1 --case 083-US3-AS1 --apply
```

> `--apply` 是写模式的显式别名（不传也写）；`--dry-run` 优先于 `--apply`。

`--spec` 可重复；不传则处理 `ver.独立需求管理` 的全部规格。传入的规格必须已挂在版本上，否则 `failed`（防止用例进错版本）。

`--reuse-from` 用于修复/回归版：本版没有新规格时，从源版本复制用例的执行记录。它与 `--spec` 互斥——给了 `--reuse-from` 就不再派生。

## 写与回读

1. **case**：新建时 POST 整行；更新时只 PATCH 差异字段。每次写后 GET 单行，比对 `用例号/用例名/来源规格/前置条件/操作步骤/预期结果/优先级`。
2. **run**：POST `<版本号>--<用例号>`，`用例号`与 `用例` 同步写入，`执行状态=todo`。回读比对四字段；已有行校验 `用例号`/`用例` 一致，不覆盖执行结果。
3. **ver.runs**：PATCH 版本行 `测试用例 = 已有 ∪ 本次 run ids`；回读版本行确认清单包含全部 run id。
4. **节点**：`ver.测试设计=done`，回读六节点快照。

三态按 012：`400`（含「已存在」「执行清单只能收录本版本」）不重试；`503`/超时/非 JSON 按 `unknown` 回读，回读确认才按成功（报告 `reconciled=true`）。

## 幂等的验收方式

对同一规格连续跑两次 `--apply`：

```bash
python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR > /tmp/plan1.json
python3 skills/tf-test-plan/scripts/tf_test_plan.py --version v0.7.0 --spec 019-AR > /tmp/plan2.json
python3 - <<'PY'
import json
second = json.load(open('/tmp/plan2.json'))
counts = second['counts']
assert counts['created_cases'] == 0, counts
assert counts['created_runs'] == 0, counts
print('第二次新建 0 条：', counts)
PY
```

## 报告

```jsonc
{
  "skill": "tf-test-plan",
  "mode": "apply",
  "result": "success",
  "counts": {
    "derived_cases": 15, "created_cases": 0, "updated_cases": 0, "unchanged_cases": 15,
    "created_runs": 0, "reused_runs": 15
  },
  "orphans": [{"case": "019-US5-AS9", "spec": "019-AR", "reason": "源场景已不存在"}],
  "readback": {
    "case/019-US1-AS1": {"ok": true, "fields": {"用例名": {"expect": "...", "actual": "...", "ok": true}}},
    "run/v0.7.0--019-US1-AS1": {"ok": true},
    "ver/v0.7.0": {"ok": true},
    "ver/v0.7.0#runs": {"v0.7.0--019-US1-AS1": {"state": "todo"}},
    "ver/v0.7.0#nodes": {"测试设计": "done"}
  }
}
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 手工在看板改用例步骤 | 用例是派生投影，下次派生会被覆盖；改真源 `spec.md` |
| 用 `ms_update` 替代 | MS 是历史台账，board@4 的 `case`/`run` 才是当前执行体系 |
| 建测试计划 | 明确不建；`ver.runs` 就是执行清单，多一层计划会造两个真相 |
| 同一版本重复纳入 | run id 固定，撞 id 复用；不要新建第二条 |
| 先写结果再写状态 | 020 会 400；本技能创建时只写 `state=todo`，执行由 `tf-test-implement` 写 |
| 删场景后直接删用例 | 技能只报 `orphans`，删不删由人决定；静默删除会丢执行历史 |
| 版本号不带 `v` | `run` 行 id 契约是 `v<主>.<次>.<修>--<用例号>`；技能要求版本行 id 为 `vX.Y.Z` |
| 打印请求头排障 | 严禁打印 `TF_API_KEY`/`X-API-Key` |

## 不做

- 不建表、不建字段、不建测试计划。
- 不执行用例、不写 `run.result`。
- 不直接连数据库；缺表/缺字段直接报「项目未迁到 board@5」。
- 不修改 `indep.验收状态` 或 `bug.status`。
