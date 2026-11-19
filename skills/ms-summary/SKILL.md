---
name: ms-summary
description: "把MeterSphere执行结果里失败与产品缺陷导致的阻塞总结成缺陷，按两轴去重后登记到tableflow看板tf-bug表，并在后续复测通过时提示关闭。触发词：缺陷登记、bug表、ms_summary、执行结果汇总、复现计数、关闭缺陷。"
---

# ms-summary：执行结果 → tf-bug缺陷行

**一句话**：从MS读执行结果，`ERROR`（以及**由产品缺陷导致的**`BLOCKED`）转成缺陷候选；
按**执行记录id**与**缺陷实体**两轴去重后写进`tf-bug`；写后回读；`closed`只在后续`SUCCESS`
存在且**人确认**时写。字段口径唯一来源：`specs/011-bug-table/board@2.yaml`。

## 运行环境（脚本解释器）

脚本依赖`cryptography`，用**系统`python3`**运行（如`/usr/bin/python3`）；
`backend/.venv/bin/python`没有该依赖，会报`ModuleNotFoundError: No module named 'cryptography'`。
下文所有`python3 ...`命令均指系统解释器。

## 何时用

- 一轮执行跑完，要把失败结果整理成缺陷登记进看板
- 同一缺陷被多条用例命中，要合并成一行并记复现次数
- 缺陷修复后复测通过，要关掉对应行（需人确认）

**不做什么**：不判定"是不是产品缺陷"（那是人的结论，脚本按原因标注归类）；
不自动关闭任何缺陷；不改用例、不改执行结果；不直写MS数据库。

## 数据源（三选一，可叠加）

| 来源 | 取法 | 适用 |
|---|---|---|
| 用例级结果 | `POST /functional/case/page` 每行的`lastExecuteResult` | 计划↔用例尚未关联时（本版本就是这样，绕开计划） |
| 计划级结果 | `POST /test-plan/functional/case/page` 每行的`lastExecResult`/`lastExecTime` | 计划里已有真实关联行时最准 |
| 人工确认缺陷 | `--defect-file <json>` | 已核实但无执行记录（如环境缺陷），证据仍须指到MS用例号 |

实测：本MS版本**没有**用例级结果登记端点（`/functional/case/run|exec|execute|result`、
`/functional/case/exec/history`全部`500 No static resource`）；用例库的`lastExecuteResult`只有
真实执行（计划内`/run`）或历史数据才会变，脚本只读它，不替它写。

## 归类口径

| 执行结果 | 处理 | 理由 |
|---|---|---|
| `ERROR` | 缺陷候选 | 明确的失败结论 |
| `BLOCKED` + 显式产品缺陷原因（`--block-reason <caseId>=<原因>`） | 缺陷候选 | 阻塞是产品缺陷引起才算缺陷 |
| `BLOCKED` 无原因 | **待判定**，不登记 | 环境/设备/数据阻塞不是产品缺陷，登记会污染缺陷口径 |
| `SUCCESS` | 不登记；命中未关闭缺陷时输出**可关闭建议** | 关闭需人确认，见下文 |
| `PENDING` | 不登记 | 没人跑过，不是结论 |

## 两轴去重（核心，缺一轴就会重复）

**轴1执行记录唯一id**：`plan:<planId>:<linkId>:<lastExecTime>`或
`case:<caseId>:<result>:<updateTime>`；已消费的记在`.tmp-shots/ms-summary/consumed.json`，
同一次执行重跑只会落到`skip`，不会新增行。

**轴2缺陷实体**：标题归一化（去空格、小写）后相同 → 视为同一缺陷，**合并**到已有行：
把新MS用例号追加进`MS用例号`（逗号分隔去重）、在`证据`里追加"【复现】再次出现…"，
刷新的复现次数由`证据`里`【复现】`出现次数推得（**表里没有count字段**，board@2只定
`证据/剩余事项`两个记录字段，不另加字段）。

实测演示：
```
# 轴1：同一执行记录重跑
= 跳过｜MS用例落在…（执行记录已消费→BUG-01）
# 轴2：同一缺陷、另一条用例（演练，dry-run）
~ 合并到 BUG-01｜MS用例落在…（追加MS用例100338，复现+1）
```

## 写接口与三态

```bash
curl -X POST "http://localhost:8090/api/agent/tables/tf-bug/rows/BUG-01" \
  -H 'Content-Type: application/json' -H 'X-Agent-Id: agent-tf-ms' -H 'X-Origin: human-request' \
  -d '{"values":{...}}'
```

- 三态只认响应体：`success`/`failed`(400)/`unknown`(503)；`unknown`必须回读判定，**不得当成功**；
- 写后回读**单行**`GET /api/tables/tf-bug/rows/{id}`并比对每个字段，再对整表查一次该id在不在；
- 字段值格式：枚举用英文`value`（`open/fixing/verifying/closed`、`blocker/critical/major/minor`、
  `test/prod/review/user`）；关系字段是**行id数组**（`["v0.6.0"]`、`["014-AR"]`），不存在的行会被
  `relation_must_exist`拒绝。

## 字段映射（tf-bug，12字段）

| 契约键 | 本地字段 | 取值 |
|---|---|---|
| `bug.id` | `tf-b-id` | `BUG-NN`，全局递增不复用 |
| `bug.title` | `tf-b-title` | 一句话说清现象与位置，不写修复方案 |
| `bug.status` | `tf-b-status` | 新建固定`open`；`closed`只经人确认 |
| `bug.severity` | `tf-b-severity` | 记录用，不进闸门；默认`major` |
| `bug.source` | `tf-b-source` | 执行结果来的记`test`；人工确认可给`review` |
| `bug.specs` | `tf-b-indep` | 行id数组，空数组=暂未归因 |
| `bug.found` | `tf-b-found` | **挂接键**，单值`["v0.6.0"]`，不从规格反查 |
| `bug.fix` | `tf-b-fix` | 修复发布时填，不修复留空 |
| `bug.evidence` | `tf-b-evidence` | 必须能指到MS用例号：`【MS】<num>…【归类】…【复现】N次【现象】…` |
| `bug.rest` | `tf-b-rest` | 未完成部分与阻塞；`closed`时必须为空 |
| `bug.ms_case` | `tf-b-ms` | MS用例号（num），多条逗号分隔 |
| `bug.owner` | `tf-b-owner` | 执行者身份，默认`agent-tf-ms` |

## 关闭（必须人确认）

```bash
# 只提示，不写
python3 skills/ms-summary/assets/ms_summary.py --close BUG-01 --reason "复测通过：MS 100337 重跑 SUCCESS（2026-11-19）"
# 确认后写 closed
python3 skills/ms-summary/assets/ms_summary.py --close BUG-01 --confirm-close --reason "同上"
```

三条硬约束：①该用例在**缺陷登记之后**出现`SUCCESS`执行记录才给关闭建议（脚本按消费账里的登记
时刻与该用例最新执行时刻比较）；②`--reason`必须可核验（MS用例号+执行时间+结论）；
③`--confirm-close`只能由人给——脚本永远不会自己关。
关闭写入`status=closed`、`rest=""`、`证据`追加`【关闭】<理由>`，读回核对后才算完成。

**剩余事项自动保留（脚本行为）**：`closed`要求`rest`为空，但原待办不能凭空消失。`--close`的脚本
顺序是：①取原`剩余事项`原文；②非空时把它写成`证据`的固定段`【原剩余事项】<原文>`；③追加
`【关闭】<理由>`；④清空`rest`。读回校验除`status=closed`与`rest`为空外，还要求证据里出现
`【原剩余事项】`（原`rest`非空时）与`【关闭】`，缺任一即判不一致、退出码非0——避免"写了但没核"。
演练证据：`.tmp-shots/ms-014/close-merge.log`（临时行`BUG-02`：写入→关闭→证据顺序87<120→删除，`BUG-01`未动）。


## 命令

```bash
# 只看：扫描执行结果，打印将写入/合并/跳过的行
python3 skills/ms-summary/assets/ms_summary.py --dry-run
# 真写（执行结果来源）
python3 skills/ms-summary/assets/ms_summary.py --apply --found v0.6.0 --specs 014-AR
# 真写（人工确认的缺陷）
python3 skills/ms-summary/assets/ms_summary.py --apply --defect-file .tmp-shots/ms-summary/defect-01.json
# 指定产品缺陷原因的BLOCKED
python3 skills/ms-summary/assets/ms_summary.py --dry-run --block-reason 100337=接口500导致无法执行
```

## 本轮实测（2026-11-19，155:8081 + 155:8090）

- 扫描执行记录23条：`ERROR`0、`BLOCKED`7（无产品缺陷原因→全部待判定）、`SUCCESS`16；
- 真写`BUG-01`一行（`status=open`、`severity=major`、`source=test`、`found=["v0.6.0"]`、
  `specs=["014-AR"]`、`ms=100337`），单行+整表回读一致；重跑→`skip`（轴1生效）；
- 关闭提示未误报：`008-US1-AS1`的SUCCESS早于缺陷登记时刻，故不给关闭建议（时间比较生效）。

**未验证范围**：①计划级链路——本版本计划内关联用例为0（关联无写入API），`ERROR`样本为0，
只有用例级`SUCCESS`与历史计划的`BLOCKED`可扫；②`BLOCKED`的产品缺陷原因在MS里没有字段可读，
必须由执行者用`--block-reason`补，否则一律待判定；③合并轴的"多用例同一缺陷"依赖标题归一化或
显式`--signature`，跨用例的自动归并只做到"标题一致"这一层。

## 自检清单

- [ ] dry-run输出里每条候选都能指到具体执行记录id与MS用例号
- [ ] 重跑后没有新增行（轴1）；同标题缺陷落到`合并`而不是新建（轴2）
- [ ] `BUG-NN`未复用、`found`是单个版本行id、`specs`为空或都是存在的行
- [ ] 写后单行回读12字段一致，且整表能查到该id
- [ ] `closed`行`rest`为空、`证据`里有可核验的复测依据
- [ ] 报告里写了未验证范围（计划级链路、BLOCKED原因来源）
