---
name: tf-dev-check
description: "推进 tableflow 版本第 4 节点「开发验收」（软件开发角色）：按客观判据——本版每份规格「实现完成 + 单测通过」——写 indep.验收状态=accepted，再写 ver.开发验收=done 并回读六节点。不需要人工判断，也不重跑单测。触发词：tf-dev-check、开发验收、第4节点、规格验收、accepted、验收清单。"
---

# tf-dev-check：开发说的「做完了」成立吗？

判据是客观的，**不含人的判断**：本版每份规格的实现完成且单测通过。本技能据此把 `验收状态` 写成 `accepted`，再推进节点。

## 两层分工（不叠加）

| 节点 | 判据 | 谁写 |
|---|---|---|
| 开发 | 代码完成 + 单测通过 | `tf-dev-implement` 跑单测、校验 `plan.md`/`tasks.md` 回链，成立才写 `speckit-implement状态=done` |
| 开发验收 | 本版规格全部「实现+单测」成立 | **本技能**按判据写 `验收状态=accepted`，再推进节点 |

开发节点是「实现+单测成立」的唯一证据点；验收节点把这个结论翻译成「验收通过」。

**所以本技能不重跑单测**——重跑等于给同一件事加第二套判据。

- 角色：软件开发
- 节点：`ver.stage.dev_accept`（字段名「开发验收」）
- 表作用域：读/写 `版本管理`/`独立规格需求`
- 口径来源：board@5 `rules.spec_done`、`rules.spec_done_precondition`

## 命令

```bash
export TF_BASE=http://localhost:8090 TF_PROJECT=tableflow TF_AGENT=agent-tf-role

# 只读预览：会写哪几份 accepted
python3 skills/tf-dev-check/scripts/tf_dev_check.py --version v0.8.0 --dry-run

# 写入并推进节点
python3 skills/tf-dev-check/scripts/tf_dev_check.py --version v0.8.0
```

## 写与回读

1. 逐份 PATCH `indep`：`验收状态=accepted`（已是 accepted 的跳过）
2. 表级读回：确认本版全部规格 `accepted`
3. 推进 `ver.开发验收=done`；GET 版本行比对六节点快照

## 常见坑

| 坑 | 说明 |
|---|---|
| 有规格 implement 未 done | `failed` 并列出是哪份；先回去把开发节点做完 |
| 手动填 accepted 再跑技能 | 不必——accepted 由本技能按判据写，人填等于绕过 |
| 想让技能重跑单测 | 不做：单测是开发节点的证据，重跑会造两套判据 |
| 已验收但想推翻 | 把 `验收状态` 改回 `pending` 再跑开发节点返工，不改历史结论 |

## 不做

- 不写 `speckit-implement状态`（开发节点的事）。
- 不跑单测、不改代码。
- 不推进第 5-6 节点。
