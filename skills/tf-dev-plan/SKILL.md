---
name: tf-dev-plan
description: "推进 tableflow board@5 版本第 1 节点「版本需求设计」（系统工程角色）：校验版本范围与需求挂载（规格目录/spec.md/验收场景/变更单条款）、按需求 039 校验规格结构下限，驱动 spec 侧五个阶段字段（constitution/specify/clarify/analyze/checklist），再写 ver.版本需求设计=done 并回读。支持 --dry-run 零写入预览。触发词：tf-dev-plan、版本需求设计、版本范围、需求挂载、推进第1节点、研发计划、规格结构、specify 状态。"
---

# tf-dev-plan：版本范围确定了吗？

一个版本要开始动工，先回答两件事：**这一版到底包含什么**，以及**每份规格是否已经具备可开工的结构**。本技能推进第 1 节点「版本需求设计」，并为 spec 侧五个阶段状态写入取值；不写代码、不改验收、不撰写规格内容。

- 角色：系统工程
- 节点：`ver.stage.plan`（字段名「版本需求设计」，四态 `todo/doing/done/failed`）
- 表作用域：读 `版本管理`/`独立规格需求`/`依赖需求`；写 `版本管理` 的节点，以及 `独立规格需求` 的 5 个 spec 侧阶段字段
- 口径来源：`specs/019-test-contract/board@5.yaml`（`tables.ver.fields` 第 3 项、`rules.version_stage_serial`）

## 何时用

- 版本刚建、需求已登记，要确认「范围定了」并推进第 1 节点。
- 发布前怀疑某版本范围是空的或挂错规格，要只读出报告。
- 想知道「推进第 1 节点还缺什么」。

## 何时不用

- 登记需求、开变更单 → `tf-register`。
- 改验收状态、推进回归 → 人工/缺陷流程。
- 派生用例、测试执行 → `tf-test-plan`/`tf-test-implement`。
- 建表、改字段 → 019 实现/T1，不在技能范围。

## 前置条件与检查项

| 检查 | 通过条件 | 不通过 |
|---|---|---|
| 版本存在 | `版本号` 行 id 命中 | `failed`，零写入 |
| 发布状态 | `planned` | `failed`（不动 released/dropped 版本） |
| 前序节点 | 第 1 节点无前序 | — |
| 版本范围 | `独立需求管理` / `依赖需求管理` / `Bug管理` / `测试用例` 至少一项非空 | `failed`，零写入 |
| 修复/回归版 | 无新规格时，本版缺陷必须都有复现证据 | `failed`，列出缺证据的缺陷 |
| 规格就绪 | 每条规格的 `规格目录` 非空、`specs/<dir>/spec.md` 存在且有 Acceptance Scenario | `failed` |
| 变更单就绪 | 每条变更单 `条款` 非空、`关联的独立规格需求` 非空且目标存在 | `failed` |
| 场景数漂移 | 看板 `场景数` 与实测不一致时写入 `scene_drift`（提示，不阻断） | — |
| 结构下限（039） | 每份规格 US≥2、场景≥5、FR≥6、边界≥3 | `failed`，报出低于下限的维度 |

## 命令

```bash
export TF_BASE=http://localhost:8090
export TF_PROJECT=tableflow
export TF_AGENT=agent-tf-role
export TF_ORIGIN=human-request        # 可选：agent/human-request/seed
# export TF_API_KEY=...               # 可选；只发送，任何输出都不打印

# 只读预览（零写入，验证/排障默认用这个）
python3 skills/tf-dev-plan/scripts/tf_dev_plan.py --version v0.7.0 --dry-run

# 真正推进节点（写后回读）
python3 skills/tf-dev-plan/scripts/tf_dev_plan.py --version v0.7.0 --apply   # 显式确认写入（等价于上一行）

# 只校验不推进
python3 skills/tf-dev-plan/scripts/tf_dev_plan.py --version v0.7.0 --no-stage
```

> `--apply` 是写模式的显式别名（不传也写）；`--dry-run` 优先于 `--apply`。

退出码：`0` = `result=success`；`1` = `failed`；`2` = `unknown`。

## 修复版与回归版

没有新规格交付的版本（修复版、纯回归版）不再被拒：范围由 `Bug管理` 或已收录的 `测试用例` 界定。
有缺陷时先校验每条缺陷都有复现证据（`证据` 字段非空），缺证据直接 `failed`——没有复现就不能算「范围已确定」。

## 写什么、怎么回读

先写 spec 侧五个阶段字段（需求 042-AR），再推进版本节点：

| 字段 | 取值规则 |
|---|---|
| `speckit-specify状态` | 结构下限通过即 `done`（不通过则整体 `failed`） |
| `speckit-constitution状态` | 有宪法版本或 `.specify/memory/constitution.md` → `done`，否则 `na` |
| `speckit-clarify状态` | 有 `## Clarifications` 且无「待定/TODO/未决/TBD」→ `done`；无该章节 → `na`；否则 `doing` |
| `speckit-analyze状态` | `na`（本项目未启用跨文档一致性分析），理由写入报告 `stage_na_reasons` |
| `speckit-checklist状态` | `na`（本项目未启用检查清单），理由同上 |

然后写版本节点：

```json
{"target": "ver/v0.7.0", "field": "版本需求设计", "value": "done"}
```

写接口返回 `success` 不算完成：随后 GET `/api/tables/<ver>/rows/v0.7.0`，比对「版本需求设计=done」，并把六节点快照写进 `readback["ver/v0.7.0#nodes"]`。三态按 012 协议：`400` 不重试，`503`/超时按 `unknown` 回读，回读不一致保持 `unknown`。

## 报告

```jsonc
{
  "skill": "tf-dev-plan",
  "role": "系统工程",
  "node": "版本需求设计",
  "mode": "dry-run",
  "result": "success",
  "checks": [{"name": "版本范围已确定", "ok": true, "detail": "规格 2 条 / 变更单 0 条"}],
  "writes": [{"target": "ver/v0.7.0", "field": "版本需求设计", "value": "done", "state": "skipped"}],
  "readback": {"ver/v0.7.0#nodes": {"版本需求设计": "todo"}},
  "counts": {"specs": 2, "changes": 0},
  "scene_drift": {"019-AR": {"recorded": 14, "actual": 15}}
}
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 版本没挂需求就推进 | 范围没确定，`failed`；不要用空版本「先点 done 再补」 |
| 用 `场景数` 字段当场景真源 | 真源是 `specs/<dir>/spec.md`；字段不一致只提示，不阻断 |
| 直接改 `发布状态` 绕过 | 技能只推进 `planned` 版本；released/dropped 一律拒绝 |
| 把 `success` 当写成功 | 必须看 `readback`；写后回读不一致按 `failed` |
| 打印环境变量排障 | 严禁打印 `TF_API_KEY`/请求头；错误只引用字段名、行 id、HTTP 状态 |

## 不做

- 不撰写或修改 `spec.md` 内容；规格由需求方写，本技能只校验与登记。
- 不直接连 SQLite（`data/tableflow.db` 只属于服务端）。
- 不建表/不建字段/不改契约；缺表缺字段直接报「项目未迁到 board@5」。
- 不写 `indep.验收状态`，不写 `dep.回归状态`。
- 不推进第 2-6 节点（各有对应技能）。
