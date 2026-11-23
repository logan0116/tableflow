---
name: tableflow-board
description: "用tableflow多维表格看板管理项目：查项目/表格/数据与变更记录，定义表与字段，写入需求、版本与缺陷，配置计算字段。字段口径以specs/017-bug-relation/board@3.yaml（四表：版本/独立规格需求/依赖需求/缺陷）为准。触发词：tableflow、多维表格、需求表、版本表、缺陷表、看板、依赖变更需求。"
---

> **已弃用（2026-11-19，2026-11-23 更新）**：日常登记用 `tf-register`，发布就绪用 `tf-release-status`，生命周期动作用 `tf-lifecycle`；本文件仅作底层 API 参考，不再发布到 SkillHub，也不随契约升级维护。

# tableflow多维表格：用Agent写接口管项目

tableflow是一块只读看板+一套Agent写接口：**人只读，Agent读写**。所有写操作必须带`X-Agent-Id`，每次调用落一条`write_audit`，字段值真实变化时另记一条`business_changes`。

## 何时用

- 查某个项目的表格数据（版本、规格、变更单、缺陷）
- 把一个项目的规格拆成行写进看板，规划版本并把规格挂到版本
- 已完成规格被改动 → 开一张变更单，追踪影响面与回归
- 发现一个缺陷 → 在缺陷表建一行，登记发现版本与修复版本
- 加一列、改字段顺序、隐藏字段、配一个计算字段（进度/汇总/发布条件）

## 连接

```bash
export TF_BASE=http://<tableflow-host>:8090   # 线上实例；本地开发是 http://127.0.0.1:8000
export TF_AGENT=agent-my-task                 # 写操作必带，写入审计
```

## 读接口（全部GET，无需鉴权）

| 路径 | 说明 |
|---|---|
| `/api/projects` | 项目列表 |
| `/api/projects/{project_id}/tables` | 项目下的表格（按order升序） |
| `/api/tables/{table_id}/table` | 字段（visible=1）+全部数据行（含计算字段值） |
| `/api/tables/{table_id}/rows/{row_id}` | 单行明细（关联弹层用） |
| `/api/tables/{table_id}/rows/{row_id}/changes` | 该行的业务变更记录 |
| `/api/health` | 探活 |

## 写接口（前缀`/api/agent`，必带`X-Agent-Id`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/projects` | 建项目`{id?, name}` |
| DELETE | `/api/agent/projects/{id}` | 删项目（级联表/字段/行） |
| POST | `/api/agent/projects/{pid}/tables` | 建表`{id?, name, order?}` |
| PATCH/DELETE | `/api/agent/tables/{id}` | 改名/改序 · 删表（级联） |
| POST | `/api/agent/tables/{tid}/fields` | 加字段`{id?, name, type, options?, order?, visible?}` |
| PATCH/DELETE | `/api/agent/fields/{id}` | 改字段 · 删字段 |
| POST | `/api/agent/tables/{tid}/rows/{row_id}` | **写行**（行id在路径里） |
| PATCH | `/api/agent/tables/{tid}/rows/{row_id}` | 改行`{values?, overrides?}`（合并） |
| DELETE | `/api/agent/tables/{tid}/rows/{row_id}` | 删行 |
| POST | `/api/agent/tables/{tid}/recompute` | 手动重算该表及其下游计算字段 |

响应统一：`{"result":"success","id":"..."}` / `{"result":"failed","error":"..."}`（400）/ `{"result":"unknown","error":"..."}`（503，**不得当成功**）。

写行/改行后服务端自动重算受影响的下游计算字段（指向被改表的relation计算字段所在表），一般不需要手动`recompute`。

可选请求头`X-Origin: human-request`标记"人发起、Agent执行"的写入。

## 数据模型

```
项目 → 表格 → 字段 + 数据行
```

- 字段：`id`（全局唯一）、`table_id`、`name`、`type`、`options`、`order`、`visible`
- 行id**就是业务编号**（如`v1.0.0`、`008-AR`、`D01`、`BUG-01`），关联标签显示的就是它；行id创建后不可改
- 类型：`text`/`number`/`datetime`/`enum`/`relation`/`computed`
- 一个项目可以有任意多张表；但**项目看板用契约定义的四张表**，范式见下一节

### options形态

```jsonc
// enum：数组，每项带tone（neutral/info/success/warning/danger）
[{"value":"done","label":"已完成","tone":"success"}]

// number
{"decimals":2,"percent":true,"unit":"台"}

// datetime
{"with_time":false}

// text/number/relation 都可带 constraints：required / min / max / enum_strict / relation_must_exist
{"constraints":{"required":true}}

// relation：目标表必须同项目；display_field/status_field 决定关联弹层第二、三列（不配则只显示行id）
{"table_id":"tf-staff"}
{"table_id":"ab-indep","display_field":"ab-i-clause","status_field":"ab-i-acceptance",
 "constraints":{"relation_must_exist":true}}

// computed：写侧算、读侧只读；布尔值默认显示"是/否"，and可用true_label/false_label改字面
{"kind":"count","source":"<relation字段id>"}
{"kind":"percent","source":"<relation字段id>","where":{"field_id":"...","equals":"done"},"decimals":0}
{"kind":"sum","source":"<relation字段id>","field_id":"...","decimals":0}
{"kind":"rollup","source":"<relation字段id>","field_id":"...","aggregate":"all","equals":"passed"}
{"kind":"and","conditions":[{"field_id":"...","equals":true}]}
```

rollup的`aggregate`只认`all`/`any`/`none`/`min`/`max`/`count_distinct`；`all`/`any`/`none`必须同时给`equals`（写成`all_true`这类会400）。契约口径是**单字段判定**，不要给rollup配`require`（board@3明确不设行级前置）。

relation的值是**目标行id的字符串数组**（单值也写`["v0.6.0"]`）。计算字段不可直接写；要人工覆盖用行PATCH的`overrides`，闸门字段不得覆盖（见下文）。

## 看板四表契约（board@3）

字段口径的唯一来源是`specs/017-bug-relation/board@3.yaml`（它取代`board@2`与`board@1`，前两版留档）。本节只对齐口径；存量迁移与写入校验不在契约范围。

四张表记的是四类不同的东西：

| 表 | 表id | 一行代表什么 | 解决什么问题 | 被谁引用 |
|---|---|---|---|---|
| 版本管理 | `<前缀>-ver` | 一个发布版本（`v1.0.0`） | 发哪一版、发什么、够不够条件发 | 看板主视图；引用indep、dep、bug三类行 |
| 独立规格需求 | `<前缀>-indep` | **一份规格**（业务编号`008-AR`） | 做哪些规格、每份规格走到哪一步 | ver的`独立需求管理`、dep的`关联的独立规格需求`、bug的`关联规格` |
| 依赖需求 | `<前缀>-dep` | **一张变更单**（业务编号`D01`） | 已完成规格被改动时，改了哪些影响面、回归做完没有 | ver的`依赖需求管理` |
| 缺陷 | `<前缀>-bug` | **一个缺陷**（业务编号`BUG-01`） | 哪坏了、修没修、修在哪版 | ver的`Bug管理`（本版需清零的缺陷）；bug的`关联规格`指向indep |

三条引用关系：**ver→indep**（本版交付哪些规格）、**ver→dep**（本版待回归的变更单）、**ver→bug**（本版需清零的缺陷，通常来自上一版本）。缺陷的`发现版本号`是**文本**，只记来源；它不反向持有关联，避免与`ver→bug`构成双向。

一句话：indep回答"要做哪些规格"，dep回答"已做完的规格又被改了什么"，bug回答"哪里坏了、修没修"，ver回答"发哪一版、能不能发"。**需求不单独建表**，它以`条款`字段挂在规格行上。

### 字段id与行id

字段id用`<项目前缀>-<表前缀字母>-<字段短名>`：`-v-`（ver）、`-i-`（indep）、`-d-`（dep）、`-b-`（bug）。行id是业务编号：版本`v<主>.<次>.<修>`、规格`NNN-AR`、变更单`D01`、缺陷`BUG-01`。字段id全局唯一。

### 版本管理`<前缀>-ver`（15字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 版本号 | `<前缀>-v-version` | text | 行 id；格式 v<主>.<次>.<修> |
| 发布时间 | `<前缀>-v-release_date` | datetime | 精确到日 |
| 发布状态 | `<前缀>-v-release_status` | enum：planned/released/dropped |  |
| 独立需求管理 | `<前缀>-v-specs` | relation→indep | 本版新增的规格 |
| 独立需求已完成/总数 | `<前缀>-v-spec_ratio` | computed | ratio(ver.specs, spec.acceptance == accepted) |
| 独立需求是否完成 | `<前缀>-v-spec_done` | computed（闸门） | rollup(ver.specs, spec.acceptance, all == accepted) |
| 依赖需求管理 | `<前缀>-v-changes` | relation→dep | 本版待回归的变更单 |
| 依赖需求已完成/总数 | `<前缀>-v-change_ratio` | computed | ratio(ver.changes, change.regress == passed) |
| 依赖需求是否完成 | `<前缀>-v-change_done` | computed（闸门） | rollup(ver.changes, change.regress, all == passed) |
| Bug管理 | `<前缀>-v-bugs` | relation→bug | 本版需清零的缺陷（通常来自上一版本） |
| 上一版本Bug已修复/总数 | `<前缀>-v-bug_ratio` | computed | ratio(ver.bugs, bug.status == closed) |
| 上一版本Bug是否清空 | `<前缀>-v-bug_clear` | computed（闸门） | rollup(ver.bugs, bug.status, all == closed) |
| 发布条件 | `<前缀>-v-gate` | computed（闸门） | and(ver.spec_done, ver.change_done, ver.bug_clear) |
| 负责人 | `<前缀>-v-owner` | text |  |
| 变更说明 | `<前缀>-v-note` | text |  |

七个计算字段的options（照抄，只改id前缀）：

```jsonc
{"kind":"ratio","source":"px-v-indep","where":{"field_id":"px-i-acceptance","equals":"accepted"}}
{"kind":"ratio","source":"px-v-dep","where":{"field_id":"px-d-regress","equals":"passed"}}
{"kind":"ratio","source":"px-v-bug","where":{"field_id":"px-b-status","equals":"closed"}}
{"kind":"rollup","source":"px-v-indep","field_id":"px-i-acceptance","aggregate":"all","equals":"accepted","gate":true,"true_label":"是","false_label":"否"}
{"kind":"rollup","source":"px-v-dep","field_id":"px-d-regress","aggregate":"all","equals":"passed","gate":true,"true_label":"是","false_label":"否"}
{"kind":"rollup","source":"px-v-bug","field_id":"px-b-status","aggregate":"all","equals":"closed","gate":true,"true_label":"是","false_label":"否"}
{"kind":"and","conditions":[{"field_id":"px-v-spec-done","equals":true},{"field_id":"px-v-change-done","equals":true},{"field_id":"px-v-bug-clear","equals":true}],"gate":true,"true_label":"是","false_label":"否"}
```

**闸门字段**：`独立需求是否完成`、`依赖需求是否完成`、`上一版本Bug是否清空`、`发布条件`四个只由计算得出，不要人工写值、也不要开人工覆盖。

### 独立规格需求`<前缀>-indep`（16字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-i-id` | text | 行 id；NNN-AR |
| 条款 | `<前缀>-i-clause` | text |  |
| 规格目录 | `<前缀>-i-dir` | text | specs/<dir>/ |
| 场景数 | `<前缀>-i-scenes` | number | spec.md 场景条数 |
| 任务总数 | `<前缀>-i-tasks` | number | tasks.md 任务条数 |
| speckit-constitution状态 | `<前缀>-i-stage-constitution` | enum：todo/doing/done/na |  |
| speckit-specify状态 | `<前缀>-i-stage-specify` | enum：todo/doing/done/na |  |
| speckit-plan状态 | `<前缀>-i-stage-plan` | enum：todo/doing/done/na |  |
| speckit-task状态 | `<前缀>-i-stage-task` | enum：todo/doing/done/na |  |
| speckit-implement状态 | `<前缀>-i-stage-implement` | enum：todo/doing/done | 进度记录；是置 accepted 的前置条件，无 na |
| speckit-clarify状态 | `<前缀>-i-stage-clarify` | enum：todo/doing/done/na |  |
| speckit-analyze状态 | `<前缀>-i-stage-analyze` | enum：todo/doing/done/na |  |
| speckit-checklist状态 | `<前缀>-i-stage-checklist` | enum：todo/doing/done/na |  |
| 宪法版本 | `<前缀>-i-constitution_version` | text |  |
| 验收状态 | `<前缀>-i-acceptance` | enum：pending/accepted/rejected | 规格完成的唯一判据；implement=done 才允许置 accepted |
| 负责人 | `<前缀>-i-owner` | text |  |

八个speckit阶段状态**全部是enum**：`constitution`/`specify`/`plan`/`task`/`implement`/`clarify`/`analyze`/`checklist`；除`implement`外都可取`na`。不另设"状态"字段，也不设`优先级`。

### 依赖需求`<前缀>-dep`（9字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-d-id` | text | 行 id；D01 |
| 条款 | `<前缀>-d-clause` | text | 改动点；必须点到规格编号与场景号 |
| 关联的独立规格需求 | `<前缀>-d-spec` | relation→indep | 被改的规格，可多份（横切改动） |
| 影响面 | `<前缀>-d-impact` | text | 受影响的能力/接口/场景/用例/下游 |
| 回归状态 | `<前缀>-d-regress` | enum：todo/doing/passed/failed | 唯一判定字段；todo=未合入，doing=已合入待验 |
| 证据 | `<前缀>-d-evidence` | text | 提交号/构建/截图/用例号；置 passed 时必须有可核验证据 |
| 剩余事项 | `<前缀>-d-rest` | text | 未完成的部分与阻塞；空表示无 |
| 规格修订 | `<前缀>-d-spec_revision` | enum：not_needed/pending/done | 改动是否已写回 spec；不参与完成判定，只为防文档与代码脱节 |
| 负责人 | `<前缀>-d-owner` | text |  |

### 缺陷`<前缀>-bug`（11字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-b-id` | text | 行 id；BUG-01 |
| 标题 | `<前缀>-b-title` | text |  |
| 状态 | `<前缀>-b-status` | enum：open/fixing/verifying/closed | closed 为完成判据 |
| 严重度 | `<前缀>-b-severity` | enum：blocker/critical/major/minor |  |
| 来源 | `<前缀>-b-source` | enum：ms_case/manual/prod/review |  |
| 关联规格 | `<前缀>-b-indep` | relation→indep | 可多份、可暂未归因 |
| 发现版本号 | `<前缀>-b-found_version` | text | 017：由 relation 改文本，避免与版本表双向 |
| 证据 | `<前缀>-b-evidence` | text |  |
| 剩余事项 | `<前缀>-b-rest` | text |  |
| MS用例号 | `<前缀>-b-ms_case` | text |  |
| 负责人 | `<前缀>-b-owner` | text |  |

## dep的真实语义：变更单，不是"规格之间的依赖"

dep的一行=**一张变更单**：某份**已经完成**的规格，之后又被修改，于是开单记录改动与回归。它不是需求之间的依赖关系表。

### 什么时候才开一张变更单

两个条件同时成立才开：

1. 该规格在indep里`speckit-implement状态`已是`done`（或`验收状态`已`accepted`）——它已经是完成基线；
2. 现在又要改它的能力、字段或验收口径。

还没做完的规格要改，直接改indep行与规格文件，**不开变更单**。

### 一张变更单的生命周期

1. 开单：在dep建一行，行id`D01`、`D02`递增，`条款`写清改什么（指到规格编号与场景号）。
2. 关联被改规格：`关联的独立规格需求`填`["008-AR"]`（relation）。
3. 填影响面：哪些能力/字段/接口/验收用例/下游规格受影响。
4. 推进回归：`回归状态`按`todo → doing → passed`；失败填`failed`；确认不受影响也填`passed`，理由写进`证据`（契约没有`na`）。
5. 挂到版本：把变更单填进受影响版本的`依赖需求关联`。挂上`todo`的变更单后该版本`依赖需求是否完成`立即转"否"；回归推到`passed`后才恢复"是"，`发布条件`才可能成立。

### 空集语义：没挂变更单时"依赖需求是否完成"显示"是"

`依赖需求是否完成`= `rollup all`（本版dep行的`回归状态` `equals` `passed`）。**没挂任何变更单时`all`作用于空集，结果为true**，界面显示"是"。

它的意思是"本版没有待回归的变更项"，**不是**"已经做过回归验证"。同理，新建版本三项就绪都是真、`发布条件`也会显示"是"——那是**"无待办"**，不是"可交付"。要判断某版能不能发，用`ft-status`看逐行缺口，不要只看这一个格子。

### 这些都不是dep（反例清单）

| 容易被误写成dep的东西 | 正确去处 |
|---|---|
| 规格之间的开发依赖顺序（如`003-AR`依赖`002-AR`） | 设计文档/`spec.md`的依赖说明；看板不记"谁先做谁后做" |
| 一份规格内部的需求拆解、任务清单 | 规格的`spec.md`/`tasks.md`；看板只用`场景数`/`任务总数`两列汇总 |
| Bug、缺陷 | `bug`表（缺陷有独立表，见「bug的真实语义」） |
| 前置事项、待澄清问题 | 前置清单类文档；与版本的关联用`变更说明`写一句 |
| 新规格 | 在indep新建一行，不是变更单 |
| 版本之间的先后、并行关系 | 不记录在看板 |

判定标准一句话：**dep的一行必须能回答"哪份已完成规格被改了、改了什么、改后要回归什么"**。答不上来，就不是变更单。

## bug的真实语义：缺陷，不是需求

- **缺陷不走需求分类树**：发现即进`bug`表；由缺陷引发的规格改动，才按`classify`走（改已`accepted`规格→开`dep`）。
- **挂接键是`发现版本`**（必填单值）：版本vX的"上一版本"= 版本号按`v<主>.<次>.<修>`语义序严格小于vX的最大版本，不看发布时间、不看发布状态；上一版本Bug集合按`发现版本`取，不按`修复版本`取。
- **`closed`是唯一终态**：要么修复版本有值且证据可核验；要么证据写明"不修复"的结论与依据、`剩余事项`为空。不修复也记`closed`，不引入`na`/`wontfix`。
- **严重度不进闸门**：发布条件只数"上一版本Bug未解决数"，避免同一问题两个真相。
- **可暂未归因**：`关联规格`为空数组是允许的，归因不改变任何判定。
- **自动聚合未落地**：`上一版本Bug总数`/`未解决数`两个number字段在聚合实现前由脚本或人工按口径填报；契约只定口径与填报方式。

## 新项目落地检查单

建完立刻核对，六条都成立才算对：

1. 项目下**只有4张表**：`<前缀>-ver`、`<前缀>-indep`、`<前缀>-dep`、`<前缀>-bug`（顺序：版本在前，缺陷在最后）。
2. `<前缀>-dep`与`<前缀>-bug`初始**0行**。
3. 每个ver行初始：`独立需求已完成/总数=0/0`、`独立需求是否完成=是`、`依赖需求已完成/总数=0/0`、`依赖需求是否完成=是`、`上一版本Bug已修复/总数=0/0`、`上一版本Bug是否清空=是`、`发布条件=是`（空集语义：是"无待办"不是"可交付"）、两个relation为`[]`。
4. 命名：表id=`<项目短前缀>-ver/-indep/-dep/-bug`；字段id=`<项目短前缀>-<v|i|d|b>-<字段短名>`，**全局唯一**；行id=业务编号（`v1.0.0`/`008-AR`/`D01`/`BUG-01`）。
5. 建字段顺序：**先indep字段 → 再dep字段 → 再bug字段 → 最后ver的relation与计算字段**。ver的`独立需求是否完成`/`依赖需求是否完成`/`上一版本Bug是否清空`是rollup，创建时就要解析indep的`验收状态`、dep的`回归状态`与bug的`状态`，目标字段没建完会400（`rollup.field_id 必须是目标表字段`）；bug的relation要指向已存在的ver与indep表。
6. 建行顺序：先ver行，再indep行、dep行、bug行，最后PATCH挂relation（relation的目标行必须已存在，否则400）。

## 常用配方

### 1. 建项目 → 四张表 → 字段 → 行（顺序不能反）

```bash
H=(-H "X-Agent-Id: $TF_AGENT" -H 'Content-Type: application/json')
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects -d '{"id":"proj-x","name":"新项目"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-ver","name":"版本管理","order":1}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-indep","name":"独立规格需求","order":2}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-dep","name":"依赖需求","order":3}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-bug","name":"缺陷","order":4}'

# 字段顺序：indep → dep → bug → ver（ver的rollup要解析三张表的判定字段）。完整清单见四表契约。
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields \
  -d '{"id":"px-i-acceptance","name":"验收状态","type":"enum","options":[
       {"value":"pending","label":"待验收","tone":"warning"},{"value":"accepted","label":"已验收","tone":"success"},{"value":"rejected","label":"未通过","tone":"danger"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-id","name":"编号","type":"text","options":{"constraints":{"required":true}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-implement","name":"speckit-implement状态","type":"enum","options":[{"value":"todo","label":"未开始","tone":"neutral"},{"value":"doing","label":"进行中","tone":"info"},{"value":"done","label":"完成","tone":"success"}]}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/fields \
  -d '{"id":"px-d-regress","name":"回归状态","type":"enum","options":[
       {"value":"todo","label":"未开始","tone":"neutral"},{"value":"doing","label":"进行中","tone":"info"},{"value":"passed","label":"通过","tone":"success"},{"value":"failed","label":"失败","tone":"danger"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/fields \
  -d '{"id":"px-d-spec","name":"关联的独立规格需求","type":"relation","options":{"table_id":"px-indep","display_field":"px-i-clause","status_field":"px-i-acceptance"}}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/fields \
  -d '{"id":"px-b-status","name":"状态","type":"enum","options":[
       {"value":"open","label":"待处理","tone":"danger"},{"value":"fixing","label":"修复中","tone":"warning"},{"value":"verifying","label":"待验证","tone":"info"},{"value":"closed","label":"已关闭","tone":"success"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/fields -d '{"id":"px-b-found-ver","name":"发现版本号","type":"text"}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-indep","name":"独立需求管理","type":"relation","options":{"table_id":"px-indep","display_field":"px-i-clause","status_field":"px-i-acceptance"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-dep","name":"依赖需求管理","type":"relation","options":{"table_id":"px-dep","display_field":"px-d-clause","status_field":"px-d-regress"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-bug","name":"Bug管理","type":"relation","options":{"table_id":"px-bug","display_field":"px-b-title","status_field":"px-b-status"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-spec-ratio","name":"独立需求已完成/总数","type":"computed","options":{"kind":"ratio","source":"px-v-indep","where":{"field_id":"px-i-acceptance","equals":"accepted"}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-change-ratio","name":"依赖需求已完成/总数","type":"computed","options":{"kind":"ratio","source":"px-v-dep","where":{"field_id":"px-d-regress","equals":"passed"}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-bug-ratio","name":"上一版本Bug已修复/总数","type":"computed","options":{"kind":"ratio","source":"px-v-bug","where":{"field_id":"px-b-status","equals":"closed"}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-spec-done","name":"独立需求是否完成","type":"computed","options":{"kind":"rollup","source":"px-v-indep","field_id":"px-i-acceptance","aggregate":"all","equals":"accepted","gate":true,"true_label":"是","false_label":"否"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-change-done","name":"依赖需求是否完成","type":"computed","options":{"kind":"rollup","source":"px-v-dep","field_id":"px-d-regress","aggregate":"all","equals":"passed","gate":true,"true_label":"是","false_label":"否"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-bug-clear","name":"上一版本Bug是否清空","type":"computed","options":{"kind":"rollup","source":"px-v-bug","field_id":"px-b-status","aggregate":"all","equals":"closed","gate":true,"true_label":"是","false_label":"否"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-cond","name":"发布条件","type":"computed","options":{"kind":"and","gate":true,"conditions":[
       {"field_id":"px-v-spec-done","equals":true},{"field_id":"px-v-change-done","equals":true},{"field_id":"px-v-bug-clear","equals":true}],"true_label":"是","false_label":"否"}}'

# 行：先写被关联的行，再写引用方（relation目标必须已存在）
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 -d '{"values":{"px-v-ver":"v0.1.0","px-v-indep":[],"px-v-dep":[],"px-v-bug":[]}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/rows/008-AR \
  -d '{"values":{"px-i-id":"008-AR","px-i-implement":"todo","px-i-acceptance":"pending"}}'
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 -d '{"values":{"px-v-indep":["008-AR"]}}'
```

### 2. 加一个计算字段并重算

```bash
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-change-ratio2","name":"依赖需求已完成/总数(2)","type":"computed",
       "options":{"kind":"ratio","source":"px-v-dep","where":{"field_id":"px-d-regress","equals":"passed"}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/recompute
```

### 3. 改状态 / 人工覆盖

```bash
# 改验收状态：PATCH 是合并语义；写入后下游比率与是否完成同事务重算
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-indep/rows/008-AR -d '{"values":{"px-i-acceptance":"accepted"}}'

# 闸门字段（px-v-spec-done 等）禁止人工覆盖，会 400；非闸门计算字段可覆盖，须给原因
```

### 4. 开一张变更单（建行 + 关联规格 + 推进回归）

```bash
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/rows/D01 -d '{
  "values":{"px-d-clause":"S05指标权重改为按类别绑定默认方案","px-d-spec":["S05"],
            "px-d-impact":"指标树、权重方案接口、S07/S08下游取数","px-d-regress":"todo"}}'
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.2.0 -d '{"values":{"px-v-dep":["D01"]}}'
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-dep/rows/D01 -d '{"values":{"px-d-regress":"passed","px-d-evidence":"提交 abc123；回归 21/21"}}'
```

### 5. 记一个缺陷

```bash
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/rows/BUG-01 -d '{
  "values":{"px-b-title":"设置页在窄屏下溢出","px-b-status":"open","px-b-severity":"major",
            "px-b-source":"manual","px-b-found-ver":"v0.6.4","px-b-evidence":"截图 attached"}}'
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.6.4 -d '{"values":{"px-v-bug":["BUG-01"]}}'
```

### 6. 查变更记录

```bash
curl -s $TF_BASE/api/tables/px-indep/rows/008-AR/changes
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 把规格间依赖写进dep | dep只收"已完成规格又被改"的变更单，见上文反例清单 |
| 缺陷当需求登记 | 缺陷不进需求分类树，直接进`bug`表 |
| 空版本发布条件显示"是" | 三项布尔在空集时都为真，`发布条件`随之显示"是"；含义是"无待办"，不是"可交付" |
| 回归状态写`na` | 契约没有`na`；确认不受影响记`passed`，理由写`证据` |
| 缺陷反挂版本 | 缺陷表只有文本`发现版本号`；关联由版本表的`Bug管理`正向持有，禁止再建双向relation |
| 不修复就不关单 | 不修复也置`closed`，证据写明"不修复"的依据，剩余事项留空 |
| 严重度进闸门 | 严重度只是记录字段，发布条件只数未解决数 |
| dep初始就有行 | 新项目dep与bug必须0行 |
| relation目标表不存在 | 先建目标表再建relation字段，否则400 |
| 字段id全局唯一 | 四张表不能复用同一字段id；用`<前缀>-<表字母>-<短名>` |
| 行id即关联标签 | 用业务编号起名（`v1.0.0`/`008-AR`/`D01`/`BUG-01`），创建后不可改 |
| 写行路径带table_id | `POST /api/agent/tables/{tid}/rows/{row_id}`，旧的无table_id路径已移除 |
| rollup写`all_true` | 只认`all`/`any`/`none`/`min`/`max`/`count_distinct`，且`all`必须配`equals` |
| 给rollup配`require` | 契约是单字段判定，不设行级前置；配了`require`会与契约口径冲突 |
| rollup建在目标字段之前 | 建ver计算字段前，indep的`验收状态`与dep的`回归状态`必须已存在，否则400；顺序indep→dep→bug→ver |
| 计算字段不可直写 | 只读`computed_values`；闸门字段不得`overrides`，非闸门要覆盖走`overrides` |
| 忘了挂`Bug管理` | 空集判"是"（无缺陷要清）；挂了`open`的缺陷才转"否" |
| 删除是硬删除 | 删表级联删字段与行；删行不级联，引用方显示"关联已失效"（010起悬空关联会让`就绪`判否） |
| 存量项目字段照抄 | 7个项目已于v0.6.4统一到board@3；新建项目一律按四表契约 |
| seed脚本全量替换 | `scripts/seed_data.py`/`rebuild_v030.py`会清空业务表，别在真实数据上重跑 |
| 未知字段键 | 行values的键必须是该表已有字段id，否则400且不落库 |
| 写接口无鉴权 | 只靠`X-Agent-Id`留痕，不要把实例暴露到不可信网络 |

## 自检

```bash
curl -s $TF_BASE/api/projects | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST $TF_BASE/api/projects   # 人侧应为405
```

建完看板按「新项目落地检查单」核对；最快的核对方式是读一次`/api/tables/<前缀>-dep/table`与`/api/tables/<前缀>-bug/table`，`rows`都应为空数组。

## 附：命令行小工具

`assets/tf.py`提供`projects`/`tables`/`table`/`row`/`changes`/`call`子命令，见文件头注释。
