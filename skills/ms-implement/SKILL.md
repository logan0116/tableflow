---
name: ms-implement
description: "按MeterSphere测试计划执行功能用例、截图存证，并把执行结果与证据回写到计划（POST /test-plan/functional/case/run）。触发词：MS执行、回写结果、跑用例、ms_implement、执行测试计划、截图存证。"
---

# ms-implement：按计划执行、截图存证、回写结果

**一句话**：先从计划里读用例（拿**关联行id**），真正执行一次、留下证据文件，再回写
`SUCCESS/ERROR`；回写是否成立只认`/test-plan/functional/case/page`读回的`lastExecResult`，
**200和`100200`都不算**。

## 运行环境（脚本解释器）

脚本依赖`cryptography`，用**系统`python3`**运行（如`/usr/bin/python3`）；
`backend/.venv/bin/python`没有该依赖，会报`ModuleNotFoundError: No module named 'cryptography'`。
下文所有`python3 ...`命令均指系统解释器。

## 何时用

- `ms-update`已把本版本用例与计划建好，要按计划逐条跑
- 某条用例需要重新执行（改了代码/规格），要把新结果与证据更新进MS
- 要统计"这个计划到底跑了多少条、通过多少条"

**不做什么**：不替人执行（脚本只回写，执行是跑界面/命令+截图）；不编造结果；
没有证据文件**拒绝回写**；不改用例内容（那是`ms-update`）。

## 第零步：先确认计划里真的有用例

```bash
export MS_TOOLS_DIR=~/PycharmProjects/cnc_nexus/tools/metersphere
python3 skills/ms-implement/assets/ms_run.py --list
```

- 输出`关联用例 0 条`就**停**：本版本没有关联写入API（见`skills/ms-update/SKILL.md`第7节），
  必须先在MS界面「计划详情 → 功能用例 → 关联用例」把用例挂进计划，脚本才有可回写的行；
- 有行时每行给出`[最近结果] 用例名 关联行id`，回写要用的就是**关联行id**（不是用例id）。

## 执行一条用例的六步

1. **读用例**：按计划与场景号定位，`--list`里找到`008-US1-AS1`那条；
2. **执行**：按用例的`前置条件`与`操作步骤`真做——界面类用浏览器点并按需截图，接口/契约类跑命令；
3. **取证**：证据落到`<仓库>/.tmp-shots/ms-evidence/<场景号>/`（截图png、命令输出log、对比json）；
   UI类至少一张**全页截图**，必要时补一张元素区域截图；
4. **回写**：

```bash
python3 skills/ms-implement/assets/ms_run.py \
  --case 008-US1-AS1 --result SUCCESS \
  --evidence .tmp-shots/ms-evidence/008-US1-AS1/check.log \
  --note "解析board@1.yaml：ver16/indep16/dep9，语义键无重复"
```

```
# 失败/阻塞一律记 ERROR，原因写 --note（本地脚本已拒绝FAIL/BLOCKED/SKIP，见第4节）
python3 skills/ms-implement/assets/ms_run.py --case 008-US2-AS1 --result ERROR \
  --evidence .tmp-shots/ms-evidence/008-US2-AS1/shot.png --note "看板缺字段导致无法比对，阻塞在010落地"
```

5. **读回**：脚本打印`读回：{lastExecResult, lastExecTime, executeUserName}`；与目标值一致才算写成，
   不一致退出码非0，按"未验证"处理；
6. **记账**：证据文件+sha256+note自动追加到`.tmp-shots/ms-evidence/runlog.jsonl`，
   报告里引用这条账，不引用"我跑过了"的口头结论。

## 回写端点契约（实测，v3.6.9-lts / 155:8081）

`POST /test-plan/functional/case/run`，**必填五字段**：

| 字段 | 取值 | 说明 |
|---|---|---|
| `id` | 计划内用例的**关联行id** | 从`/test-plan/functional/case/page`取；拿用例id冒充会静默空转 |
| `testPlanId` | 计划id | |
| `caseId` | 用例id | 关联行里的`caseId` |
| `projectId` | 项目id | 来自`ms_env.ids()` |
| `lastExecResult` | `SUCCESS`/`ERROR` | 其它值见第4节 |

缺任一字段→`400 parameter validate failure`，`messageDetail`会逐字段点名，可直接照抄修请求体。
响应`{"code":100200}`**不代表写入成功**：实测把`caseId`当`id`传时返回`100200`，
计划内用例仍是`total 0`（结果没落到计划里），但**用例库该用例的`lastExecuteResult`被改写了**——
这就是拿用例id冒充关联行id的代价：计划里查不到，用例库里多了一条无计划依据的结果。
**唯一判据是读回计划内用例的`lastExecResult`变化**。

## 结果枚举：只放行SUCCESS/ERROR

实测同一请求体换`lastExecResult`的四个取值：

| 取值 | 服务端行为 |
|---|---|
| `SUCCESS` / `ERROR` | 进入回写分支（有真实关联行时才写） |
| `FAIL` / `BLOCKED` / `SKIP` / `PENDING` | 返回`100200`但**什么都不做**（静默空转） |

所以脚本只接受`SUCCESS`/`ERROR`：失败、阻塞、跳过、部分通过统一记`ERROR`，
把真实原因写进`--note`，避免"报了FAIL却什么都没写"的假记录。
`SUCCESS`必须带`--note`（说清执行了什么、依据是什么），否则脚本拒绝执行。

## 证据纪律

- **没有证据不得回写**：`--evidence`指向不存在的文件时脚本直接退出；
- 每个证据文件记`bytes`与`sha256前16位`，同一场景多次执行追加多行，历史不覆盖；
- 证据目录默认`.tmp-shots/ms-evidence/`（已在`.gitignore`），随仓库走但不入库；
- 截图要能看出"被测系统+当前状态"：全页截图默认，细节用元素裁剪；
- 报告里写"已执行"必须同时给出证据路径与读回结果，缺一个都按未执行处理。

## 已知缺口与未验证范围（本轮实测，必须如实报）

- **端点与字段契约已验证**：`/run`存在，必填五字段由400报错文本逐个确认；
- **写入路径未端到端验证**：计划与用例的关联无API可用（18候选全`No static resource`），
  当前环境也没有SSH/MySQL通道可以补关联行，所以"有真实关联行→回写成功→读回一致"这条链
  **本轮跑不到**。上面的命令与判据是按字段契约与读回语义写的，**不得声称已验证通过**；
- 一旦有人把用例关联进计划，`--list`能列出关联行id，即可按第3节六步直接回写。

## 报告格式（六字段）

1. 计划名与id、关联用例数；2. 本次执行了哪些场景号；3. 每条的结果（SUCCESS/ERROR）与依据；
4. 证据路径与sha256；5. 读回结果（`lastExecResult/lastExecTime`）；6. 未执行/未验证项与原因。

## 自检清单

- [ ] `--list`关联条数>0（0条说明还没关联，不能开跑）
- [ ] 每条`SUCCESS`都有`--note`与实际证据文件
- [ ] 读回的`lastExecResult`与目标一致，`lastExecTime`有更新
- [ ] `runlog.jsonl`里有本次记录（文件+sha256）
- [ ] 报告写了未验证范围（如关联未完成、端到端未跑通）
