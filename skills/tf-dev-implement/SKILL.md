---
name: tf-dev-implement
description: "推进 tableflow board@4 版本第 3 节点「开发」（软件开发角色）：校验版本内每份规格的 tasks.md 已全部勾选、spec 有验收场景，然后写 indep.speckit-implement状态=done 与 ver.开发=done 并回读。支持 --dry-run、--spec、--no-stage。触发词：tf-dev-implement、开发完成、第3节点、实现状态、任务清单、开发节点。"
---

# tf-dev-implement：开发做完了吗？

第 3 节点「开发」的判据是**代码与单测完成**。本技能不写代码、不跑构建，而是校验交付证据（`tasks.md` 全部勾选）、把每份规格的 `speckit-implement状态` 置 `done`，再推进版本节点。

- 角色：软件开发
- 节点：`ver.stage.dev`（字段名「开发」）
- 表作用域：读/写 `版本管理`/`独立规格需求`；不碰 `dep`/`case`/`run`/`bug`
- 口径来源：board@4 `rules.version_stage_serial`、`tables.indep.fields` 的 `spec.stage.implement`

## 何时用

- 本版规格的 tasks 全部完成，要把「开发」节点推到 `done`。
- 想知道「开发节点还差哪份规格、哪几条任务」。

## 何时不用

- 写代码/改任务 → `speckit-implement`（本技能只做收尾判定）。
- 开发验收（需求方确认）→ `tf-dev-check`。
- 派生用例 → `tf-test-plan`；测试执行 → `tf-test-implement`。

## 前置条件与检查项

| 检查 | 通过条件 | 不通过 |
|---|---|---|
| 版本 | 存在且 `planned` | `failed`，零写入 |
| 前序节点 | `版本需求设计`、`测试设计` 均 `done` | `failed`，指出缺哪个 |
| 规格挂载 | `--spec` 指定的规格在 `ver.独立需求管理` 中 | `failed` |
| 规格真源 | `specs/<dir>/spec.md` 存在且有 Acceptance Scenario | `failed` |
| 任务清单 | `tasks.md` 存在；`- [ ]` 为零；`- [x]` 至少一条 | `failed`，列出未完成任务 |
| 实现状态 | 写后读回 `speckit-implement状态=done` | 按三态上报 |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role

# 只读预览
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.7.0 --spec 017-AR --dry-run

# 推进（写 indep 的 implement + ver 的 开发）
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.7.0 --spec 017-AR --apply   # 显式确认写入（等价于上一行）

# 只更新规格实现状态，不推进节点
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.7.0 --no-stage
```

> `--apply` 是写模式的显式别名（不传也写）；`--dry-run` 优先于 `--apply`。

`--spec` 可重复；不传则处理版本内全部规格。

## 写与回读

1. 对每份规格 PATCH `indep`：`speckit-implement状态=done`；GET 单行比对，已是 `done` 则跳过写入。
2. 表级读回：重新 GET `indep` 表，确认 `--spec` 覆盖的规格全部 `done`。
3. 推进 `ver.开发=done`；GET 版本行比对六节点快照。

三态按 012：`400` 不重试；`503`/超时按 `unknown` 回读，不能定案才退避重试 ≤3 次。

## 报告要点

```jsonc
{
  "skill": "tf-dev-implement",
  "role": "软件开发",
  "node": "开发",
  "result": "success",
  "checks": [
    {"name": "规格 017-AR 任务全部完成", "ok": true, "detail": "已勾选 6 条，未勾选 0 条"},
    {"name": "前序节点（2 个）", "ok": true, "detail": "全部 done"}
  ],
  "writes": [{"target": "indep/017-AR", "field": "speckit-implement状态", "value": "done", "state": "success"}],
  "readback": {"indep/017-AR": {"ok": true}, "ver/v0.7.0#nodes": {"开发": "done"}}
}
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 任务没勾完就推进 | 技能 `failed` 并列出 `- [ ]` 项；不要手工改看板绕过 |
| 把「测试设计」当已完成 | 第 2 节点不是 `done` 时第 3 节点不能推进（串行） |
| 空 tasks.md | `- [x]` 为零视为未完成；空清单不是「全部完成」 |
| 用看板字段替代 tasks.md | 任务完成判据在真源 `tasks.md`，看板只记录 implement 状态 |
| 直接连数据库 | 只走 HTTP；缺表/缺字段报「项目未迁到 board@4」 |
| 打印凭据 | 严禁打印 `TF_API_KEY`/请求头 |

## 不做

- 不写代码、不跑测试、不修改 `tasks.md`。
- 不写 `验收状态`（`tf-dev-check` 只读它）。
- 不推进第 4-6 节点。
