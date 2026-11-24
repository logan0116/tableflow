---
name: tf-test-check
description: "推进 tableflow board@5 版本第 6 节点「测试验收」（软件测试角色）：客户端复算本版用例是否全部执行、Bug 管理是否全部 closed、变更单回归是否全部 passed，三条同时成立才写 ver.测试验收=done 并回读六节点与 stage_done。只读缺陷/变更状态，不代写通过。触发词：tf-test-check、测试验收、第6节点、缺陷清零、回归通过、发布闸门、gate。"
---

# tf-test-check：这版能验收了吗？

第 6 节点「测试验收」同时要求三件事：本版用例全执行、本版 Bug 管理全 `closed`、本版变更单全 `passed`。本技能只在客户端按 board@5 规则**复算**这三条，全真才推进节点；看板计算字段只作对照。

- 角色：软件测试
- 节点：`ver.stage.test_accept`（字段名「测试验收」）
- 表作用域：读 `版本管理`/`用例执行情况`/`依赖需求`/`缺陷`；**只写** `版本管理`
- 口径来源：board@5 `rules.case_done`、`rules.bug_done`、`rules.change_done`、`rules.version_stage_gate_consistency`、`rules.empty_set`

## 何时用

- 用例已执行完，要判断「测试验收」能不能过。
- 发布前想知道「还差几条缺陷/几张变更单」。
- 需要给出六节点全 `done`、`stage_done=true` 的可核验证据。

## 何时不用

- 关闭缺陷、写回归结果 → 缺陷/变更流程；技能只读。
- 推进测试（执行）节点 → `tf-test-implement`。
- 改发布状态/发布 → 人工发布流程。

## 前置条件与检查项

| 检查 | 通过条件 | 不通过 |
|---|---|---|
| 版本 | 存在且 `planned` | `failed`，零写入 |
| 前序节点 | 前 5 个节点均 `done` | `failed`，指出缺哪个 |
| 用例完成 | `ver.测试用例` 中全部 `run.state=done` | `failed`，列出未执行记录 |
| 执行结果通过（036） | 每条 `run.result=pass`，或带有效放行标记 | `failed`，分别列出未通过项与已放行项 |
| 放行标记有效（036） | `放行标记=waived` 且 `放行批准人`、`放行理由` 都非空 | 该条按未放行处理 |
| 缺陷清零 | `ver.Bug管理` 中全部 `bug.status=closed` | `failed`，列出未关闭缺陷 |
| 变更回归 | `ver.依赖需求管理` 中全部 `dep.回归状态=passed` | `failed`，列出未通过变更单 |
| 空集 | 未关联时按空集为真（本版无此类工作） | 不阻断 |
| 计算字段对照 | 看板 `用例是否完成`/`Bug是否清空`/`依赖需求是否完成` 与复算一致 | 不一致写入 `checks`（提示偏差） |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role

# 只读预览
python3 skills/tf-test-check/scripts/tf_test_check.py --version v0.7.0 --dry-run

# 推进节点
python3 skills/tf-test-check/scripts/tf_test_check.py --version v0.7.0 --apply   # 显式确认写入（等价于上一行）
```

> `--apply` 是写模式的显式别名（不传也写）；`--dry-run` 优先于 `--apply`。

## 判定不通过时写什么

四项闸门（用例全部执行、缺陷全部 closed、变更回归全部 passed、执行结果 pass 或有效放行）任一不满足，
先把 `测试验收` 写成 `failed`，再以 `failed` 退出——`todo` 表示「还没验收」，`failed` 才是「验收没过」，
两者必须能区分。`--dry-run` 不写。

## 写与回读

只写 `ver.测试验收=done`；GET 版本行回读该字段，输出六节点快照、`stage_done`（客户端复算）与看板 `六节点是否全部完成`/`发布条件` 的对照值。三态按 012：`400`（服务端闸门一致性校验拒绝）按 `failed` 原样上报；`503`/超时按 `unknown` 回读。

## 报告要点

```jsonc
{
  "skill": "tf-test-check",
  "result": "failed",
  "checks": [
    {"name": "用例全部执行", "ok": true, "detail": "15 条全部 done"},
    {"name": "变更回归全部通过", "ok": true, "detail": "0 条全部 passed（空集为真）"},
    {"name": "本版 Bug 全部关闭", "ok": false, "detail": "未关闭 ['BUG-03']"}
  ],
  "readback": {
    "bug#status/v0.7.0": {"BUG-03": "fixing"},
    "ver/v0.7.0#nodes": {"测试验收": "todo"}
  },
  "errors": ["测试验收未满足：缺陷未关闭：['BUG-03']"]
}
```

全通过时 `gate` 字段给出 `{"stage_done": true, "board_stage_done": true, "board_gate": true}`（看板计算字段存在才对照）。

## 常见坑

| 坑 | 说明 |
|---|---|
| 有未关闭缺陷就置 done | 服务端 025 会 400；本技能也会在写前 `failed` |
| 把 `fail` 当缺陷已清零 | `fail` 是执行结论，缺陷是否解决只看 `bug.status=closed` |
| 变更单 `todo/doing/failed` 都算未通过 | 只有 `passed` 放行；「确认不受影响」也要显式写 `passed` |
| 空集合当未验证 | 空集为真：本版无缺陷/无变更单，不阻断 |
| 只信看板计算字段 | 判定以客户端复算为准；计算字段值只对照，防止重算未触发 |
| 打印凭据 | 严禁打印 `TF_API_KEY`/请求头 |

## 不做

- 不写 `bug.status`、不写 `dep.回归状态`、不写 `run.result`。
- 不改 `发布状态`、不发布。
- 不直接连数据库。
