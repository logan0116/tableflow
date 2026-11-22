---
name: tf-dev-check
description: "推进 tableflow board@4 版本第 4 节点「开发验收」（软件开发角色）：只读校验本版全部规格 indep.验收状态=accepted 且 speckit-implement状态=done，再写 ver.开发验收=done 并回读六节点。验收状态由需求方给，技能不代写。触发词：tf-dev-check、开发验收、第4节点、规格验收、accepted、验收清单。"
---

# tf-dev-check：需求方确认了吗？

第 4 节点「开发验收」的明细口径是每份规格的 `验收状态`。本技能只读验收状态、列出未验收项，全部 `accepted` 后才把 `ver.开发验收` 置 `done`。

- 角色：软件开发
- 节点：`ver.stage.dev_accept`（字段名「开发验收」）
- 表作用域：读 `版本管理`/`独立规格需求`；**只写** `版本管理`
- 口径来源：board@4 `rules.version_stage_gate_consistency`（dev_accept 要求 `ver.spec_done`）、`rules.spec_done`

## 何时用

- 本版规格都已验收，要推进「开发验收」节点。
- 想知道「开发验收卡在哪份规格」。

## 何时不用

- 给规格打 `accepted` → 需求方判定，Agent 不代写。
- 推进开发节点 → `tf-dev-implement`。
- 测试执行/测试验收 → `tf-test-implement`/`tf-test-check`。

## 前置条件与检查项

| 检查 | 通过条件 | 不通过 |
|---|---|---|
| 版本 | 存在且 `planned` | `failed`，零写入 |
| 前序节点 | `版本需求设计`/`测试设计`/`开发` 均 `done` | `failed`，指出缺哪个 |
| 规格存在 | `ver.独立需求管理` 的每行在 `indep` 表中存在 | `failed` |
| 验收状态 | 每份规格 `验收状态=accepted` | `failed`，逐条列出 `pending/rejected` |
| 实现状态 | 每份规格 `speckit-implement状态=done` | `failed` |
| 空集 | 本版无规格时按空集语义通过（`spec_done=真`） | — |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role

# 只读预览
python3 skills/tf-dev-check/scripts/tf_dev_check.py --version v0.7.0 --dry-run

# 推进节点
python3 skills/tf-dev-check/scripts/tf_dev_check.py --version v0.7.0 --apply   # 显式确认写入（等价于上一行）
```

> `--apply` 是写模式的显式别名（不传也写）；`--dry-run` 优先于 `--apply`。

## 写与回读

只写 `ver.开发验收=done`；GET 版本行回读该字段，并输出六节点快照与 `stage_done`。三态按 012：`400` 不重试；`503`/超时按 `unknown` 回读。

## 报告要点

```jsonc
{
  "skill": "tf-dev-check",
  "result": "failed",
  "checks": [
    {"name": "规格 019-AR 已验收", "ok": false, "detail": "验收状态=pending"}
  ],
  "readback": {"indep#acceptance/v0.7.0": {"017-AR": {"验收状态": "accepted", "speckit-implement状态": "done"}}},
  "errors": ["开发验收未满足：019-AR 验收状态=pending"]
}
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 为了让节点过而写 `accepted` | 验收是需求方判定；技能拒绝代写，也不会自动改 |
| 把 `rejected` 当未开始 | `pending`/`rejected` 都算未完成，报告要原样展示 |
| 忽略前序 `failed` | 前序节点 `failed` 时后序不能推进；先返工改回 `doing` |
| 空版本直接拒绝 | 本版无规格是空集语义（`spec_done=真`），不是错误 |
| 打印凭据 | 严禁打印 `TF_API_KEY`/请求头 |

## 不做

- 不写 `indep.验收状态`、不写 `dep.回归状态`、不写 `bug.status`。
- 不推进第 5-6 节点。
- 不直接连数据库。
