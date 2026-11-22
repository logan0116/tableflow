---
name: tf-test-implement
description: "推进 tableflow board@4 版本第 5 节点「测试」（软件测试角色）：把指定用例在目标版本的 run 行写成执行状态=done、执行结果 pass/fail/blocked/skip、证据/时间/执行人，全部执行后写 ver.测试=done 并回读。重跑就地更新，不新建；pass 必须带证据。触发词：tf-test-implement、测试执行、第5节点、跑用例、执行结果、run.state、测试节点。"
---

# tf-test-implement：用例跑完了吗？

第 5 节点「测试」只关心**跑没跑**：`run.state` 全部 `done` 才推进；通过与否留在 `run.result`，不进入版本闸门。本技能写执行记录，不判断质量、不建缺陷。

- 角色：软件测试
- 节点：`ver.stage.test`（字段名「测试」）
- 表作用域：读 `版本管理`/`用例执行情况`/`测试用例`；写 `用例执行情况`/`版本管理`
- 口径来源：board@4 `rules.case_done`、`rules.run_state_result_consistency`、`rules.run_one_per_version_case`

## 何时用

- 执行完一条或一批用例，要回写执行状态与结论。
- 想知道「测试节点还差哪几条执行记录」。

## 何时不用

- 派生用例/纳入版本 → `tf-test-plan`。
- 测试验收（缺陷清零/回归通过）→ `tf-test-check`。
- 登记缺陷 → `ms-summary`/缺陷流程；技能不写 `bug`。

## 前置条件与检查项

| 检查 | 通过条件 | 不通过 |
|---|---|---|
| 版本 | 存在且 `planned`；行 id 形如 `vX.Y.Z` | `failed`，零写入 |
| 前序节点 | 前 4 个节点均 `done` | `failed`，指出缺哪个 |
| 执行范围 | `--case` 或 `--all-pending` 二选一；目标必须在 `ver.测试用例` 清单里 | `failed` |
| 用例关系 | `run.用例号` 与 `run.用例` 指向同一条 `case` | `failed` |
| 状态/结果一致 | `done` 必须有 `result`；`todo` 时 `result` 为空 | 客户端先拒绝，服务端 400 也按 `failed` |
| 证据 | `--result pass` 必须给 `--evidence` | `failed` |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role

# 执行一条
python3 skills/tf-test-implement/scripts/tf_test_implement.py \
  --version v0.7.0 --case 019-US1-AS1 --result pass \
  --evidence .tmp-shots/019/us1-as1.png --executor agent-tf-role --apply

# 执行本版所有待执行用例（证据目录统一给）
python3 skills/tf-test-implement/scripts/tf_test_implement.py \
  --version v0.7.0 --all-pending --result pass --evidence .tmp-shots/019/

# 只读预览：列出待执行记录，不写
python3 skills/tf-test-implement/scripts/tf_test_implement.py \
  --version v0.7.0 --all-pending --result pass --evidence .tmp-shots/019/ --dry-run

# 只写执行记录，不推进节点
python3 skills/tf-test-implement/scripts/tf_test_implement.py \
  --version v0.7.0 --case 019-US1-AS1 --result pass --evidence ... --no-stage
```

`--case` 可传用例号（自动补 `<版本号>--`）或完整执行记录 id，可重复。`--note` 用于 `fail/blocked/skip` 的原因说明。

> 六个技能统一接受 `--apply`（显式确认写入，与默认行为等价）；`--dry-run` 优先于 `--apply`。

## 写与回读

每条目标 `run` 行 PATCH：

```json
{
  "执行状态": "done",
  "执行结果": "pass",
  "证据": ".tmp-shots/019/us1-as1.png",
  "执行时间": "2026-11-22T17:20:00+08:00",
  "执行人": "agent-tf-role"
}
```

写后 GET 单行比对上述字段；全部写完重新 GET `run` 表，逐条确认 `执行状态`。全部 `done` 后写 `ver.测试=done` 并回读六节点。三态按 012：`400`（状态/结果不一致、记录不在清单）不重试；`503`/超时按 `unknown` 回读。

## 报告要点

```jsonc
{
  "skill": "tf-test-implement",
  "result": "success",
  "counts": {"executed": 15, "pending": 0, "runs": 15},
  "checks": [{"name": "全部用例已执行", "ok": true, "detail": "15 条全部 done"}],
  "readback": {
    "run/v0.7.0--019-US1-AS1": {"ok": true, "fields": {"执行状态": {"expect": "done", "actual": "done", "ok": true}}},
    "ver/v0.7.0#nodes": {"测试": "done"}
  }
}
```

仍有待执行记录时：报告 `result=success`（本次指定范围已写成功）、`stage_advanced=false`，并给出 `blocker`；不把「测试」节点置 done。

## 常见坑

| 坑 | 说明 |
|---|---|
| 先写 `result` 再写 `state` | 020 会 400；一次 PATCH 同时写两者 |
| `todo` 却带结果 | 客户端先拒绝；不要试图绕过 |
| 同一版本重复建执行记录 | 行 id 固定；重跑就地更新 |
| 把 `fail` 当节点不推进 | 节点只看 `state`；`fail` 不阻止「测试」节点，但会进缺陷流程 |
| `pass` 不带证据 | 技能拒绝；证据是后续复核的唯一凭据 |
| 直接连数据库 | 只走 HTTP；缺表/缺字段报「项目未迁到 board@4」 |
| 打印凭据 | 严禁打印 `TF_API_KEY`/请求头 |

## 不做

- 不派生用例、不建 `run` 行（`tf-test-plan` 的事）。
- 不写 `bug` 表、不写 `indep`/`dep`。
- 不推进第 6 节点。
