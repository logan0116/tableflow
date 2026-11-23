---
name: tf-dev-implement
description: "推进 tableflow board@4 版本第 3 节点「开发」（软件开发角色）：驱动 speckit 实现侧全流程 plan → tasks → implement——按 spec.md 场景生成并校验 plan.md 与 tasks.md，要求任务全部勾选且单测通过，然后写 indep 的 speckit-plan/task/implement 状态与 ver.开发=done 并回读。支持 --plan-only、--force-plan、--force-tasks、--test-cmd、--dry-run、--spec、--no-stage。触发词：tf-dev-implement、开发完成、第3节点、实现状态、任务清单、开发节点、生成计划、生成任务。"
---

# tf-dev-implement：开发做完了吗？

第 3 节点「开发」的判据是**实现侧三个阶段都留下产物与证据**。本技能一次执行依次处理 plan → tasks → implement：缺产物就按 `spec.md` 生成骨架，产物不全就拒绝推进，单测不过就不算实现完成。

- 角色：软件开发
- 节点：`ver.stage.dev`（字段名「开发」）
- 表作用域：读/写 `版本管理`/`独立规格需求`；不碰 `dep`/`case`/`run`/`bug`
- 本地作用域：读 `specs/<dir>/spec.md`；写 `specs/<dir>/plan.md`、`specs/<dir>/tasks.md`
- 口径来源：需求 042-AR、board@4 `rules.version_stage_serial`

## 三个阶段

| 阶段 | 产物 | 置 done 的条件 | 写入字段 |
|---|---|---|---|
| plan | `plan.md` | 每个 User Story 一节，每条实现项回链全部场景号 | `speckit-plan状态` |
| tasks | `tasks.md` | 每条任务回链场景号，覆盖全部场景 | `speckit-task状态` |
| implement | 代码 + 单测 | `tasks.md` 无 `- [ ]` 剩余，且单测命令返回 0 | `speckit-implement状态` |

`plan.md`/`tasks.md` 是**生成物**：不存在就生成骨架（`（待补）` 占位），已存在则沿用并只做校验——人工补充内容不会被覆盖。要重生成必须显式 `--force-plan`/`--force-tasks`。

生成后的骨架必须由开发填写实现要点并逐条勾选，本技能不代填、不代勾。

## 何时用

- 规格刚进开发，还没有 `plan.md`/`tasks.md`：跑 `--plan-only` 生成两份骨架并写好两阶段状态。
- 开发完成、任务已勾选：默认模式跑一遍，跑单测并收口 implement。
- 想知道「开发节点还差哪份规格、缺哪份产物、哪条任务没勾」。

## 何时不用

- 写业务代码 → 按生成出来的 `plan.md`/`tasks.md` 落地，本技能只做产物生成、校验与证据采集。
- 开发验收（需求方确认）→ `tf-dev-check`。
- 派生用例 → `tf-test-plan`；测试执行 → `tf-test-implement`。

## 前置条件与检查项

| 检查 | 通过条件 | 不通过 |
|---|---|---|
| 版本 | 存在且 `planned` | `failed`，零写入 |
| 前序节点 | `版本需求设计`、`测试设计` 均 `done` | `failed`，指出缺哪个 |
| 规格挂载 | `--spec` 指定的规格在 `ver.独立需求管理` 中 | `failed` |
| 规格真源 | `specs/<dir>/spec.md` 存在且有 Acceptance Scenario | `failed` |
| plan 回链 | `plan.md` 含该规格全部场景号 | `failed`，列出缺失场景号 |
| tasks 回链 | `tasks.md` 含该规格全部场景号 | `failed` |
| 任务完成 | `- [ ]` 为零且 `- [x]` 至少一条 | `failed`，列出未完成任务 |
| 单测 | `--test-cmd` 返回 0 | `failed`，附输出末尾 800 字 |
| 版本节点 | 仅当本次覆盖版本内**全部**规格才推进 | 子集模式只写规格状态 |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role

# 1. 生成 plan.md 与 tasks.md 骨架，写两个阶段状态，不推进节点
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.8.0 --spec 042-AR --plan-only

# 2. 只读预览：看会生成什么、还差什么
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.8.0 --spec 042-AR --dry-run

# 3. 收口：任务已勾选，跑单测，写 implement 并推进节点
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.8.0

# 只用指定命令跑单测 / 延长超时
python3 skills/tf-dev-implement/scripts/tf_dev_implement.py --version v0.8.0 \
  --test-cmd ".venv/bin/python -m pytest -q" --test-timeout 1800
```

> `--apply` 是写模式的显式别名（不传也写）；`--dry-run` 优先于 `--apply`。
> `--spec` 可重复；不传则处理版本内全部规格。传子集时按 FR-010 **不推进版本节点**。

单测命令缺省自动探测：有 `backend/.venv` 用它在该目录跑 pytest，否则在仓库根跑 `python3 -m pytest -q`。

## 生成物骨架

`plan.md`：

```markdown
# 实现计划：<规格标题>

- **需求**：042-AR
- **规格**：`specs/042-xxx/spec.md`
- **基线修订**：首次

## 实现项

### US1 <User Story 标题>（P1）

- 覆盖场景：042-US1-AS1、042-US1-AS2
- 实现要点：（待补）
- 影响面：（待补）
- 验证方式：（待补）
```

`tasks.md`：

```markdown
- [ ] T001 实现 US1 <标题>（覆盖场景：042-US1-AS1、042-US1-AS2）
- [ ] T00N 补齐单元测试（覆盖上述全部实现项）
- [ ] T00N+1 更新文档与契约引用（如涉及）
- [ ] T00N+2 跑通全量测试并记录结果
```

## 写与回读

1. 本地写 `plan.md`/`tasks.md`（`--dry-run` 时只报字数不落盘）。
2. PATCH `indep` 的阶段字段；GET 单行比对，已是目标值则跳过写入。
3. 单测通过后 PATCH `speckit-implement状态=done`，表级读回确认覆盖到的规格全部 `done`。
4. 覆盖全量规格时推进 `ver.开发=done`；GET 版本行比对六节点快照。

三态按 012：`400` 不重试；`503`/超时按 `unknown` 回读，不能定案才退避重试 ≤3 次。

## 报告要点

```jsonc
{
  "skill": "tf-dev-implement",
  "mode": "apply",
  "result": "success",
  "counts": {"plans_created": 1, "tasks_created": 1},
  "checks": [
    {"name": "规格 042-AR plan 回链场景", "ok": true, "detail": "13 条场景全覆盖"},
    {"name": "规格 042-AR 任务全部完成", "ok": true, "detail": "已勾选 7 条，未勾选 0 条"},
    {"name": "单测通过", "ok": true, "detail": "`.venv/bin/python -m pytest -q` -> 通过"}
  ],
  "writes": [
    {"target": "file/specs/042-xxx/plan.md", "field": "<create>", "state": "success"},
    {"target": "indep/042-AR", "field": "speckit-plan状态", "value": "done", "state": "success"}
  ],
  "readback": {"indep#implement/v0.8.0": {"042-AR": "done"}, "ver/v0.8.0#nodes": {"开发": "done"}}
}
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 生成的骨架直接勾选 | `tasks.md` 是给你填的，未实现就勾等于伪造证据；单测会兜住一部分但不是全部 |
| 任务没勾完就推进 | `failed` 并列出 `- [ ]` 项；不要手工改看板绕过 |
| 手工改 `plan.md` 后又被覆盖 | 只有显式 `--force-plan` 才覆盖；默认沿用并只校验回链 |
| 空 `tasks.md` | `- [x]` 为零视为未完成；空清单不是「全部完成」 |
| 用单测以外的证据 | 单测是 implement 的唯一机器可验证证据；文档类豁免要写在 `plan.md` 的验证方式里 |
| 只跑一份规格就推进版本 | 子集模式按 FR-010 不推进节点；版本完成要求全部规格 |
| 直接连数据库 | 只走 HTTP；缺表/缺字段报「项目未迁到 board@4」 |
| 打印凭据 | 严禁打印 `TF_API_KEY`/请求头 |

## 不做

- 不写业务代码、不改 `spec.md`、不代勾任务。
- 不写 `验收状态`（`tf-dev-check` 只读它）。
- 不推进第 4-6 节点；不处理依赖需求（需求 037 另行承担）。
