---
name: tf-release-status
description: "只读报告 tableflow board@5 某版本能不能发：按发布条件 = and(六节点全部 done) 复算，区分可发布/不可发布/已终止，给出逐条判定、复算口径与数据来源。取代已废弃的 tf-status。触发词：tf-release-status、能不能发、发布就绪、发布条件、版本状态、差什么、gate。"
---

# tf-release-status：这个版本能不能发？

只读。不发任何写请求。

- 角色：系统工程
- 判定字段：`ver.stage.*`（六节点）、`ver.发布条件`
- 口径来源：board@5 `rules.release_gate`

## 口径

`发布条件 = and(六节点全部 done)`。

三个布尔（独立需求是否完成 / 依赖需求是否完成 / Bug 是否清空）自 board@4 起**降为展示字段**，只列出来对照，不参与判定——这是本技能取代 `tf-status` 的根本原因：旧技能按三布尔算，会给出错误结论。

## 用法

```bash
export TF_BASE=http://localhost:8090 TF_PROJECT=tableflow TF_AGENT=agent-tf-role
python3 skills/tf-release-status/scripts/tf_release_status.py --version v0.8.0
```

`released` / `dropped` 也能报——`dropped` 会直接给「已终止」并说明红灯与证据保留。

## 输出

```jsonc
{
  "result": "success",
  "verdict": "不可发布",
  "reason": "六节点未齐：开发=todo、开发验收=todo、测试=todo、测试验收=todo",
  "facts": {"交付范围": "独立需求 10 条、依赖需求 0 条",
            "测试范围": "用例 121 条，其中结果 pass 0 条"},
  "checks": [{"name": "六节点全部完成", "ok": false, "detail": "..."},
             {"name": "看板发布条件与复算一致", "ok": true,
              "detail": "看板=False，复算=False（口径：发布条件 = and(六节点全部 done)）"}]
}
```

每条判定都带复算口径与数据来源。

## 不做

- 不写任何字段，不推进节点，不改发布状态。
- 不判断某条用例该不该失败——那是 `tf-test-check` 的事。
