---
name: tableflow-board
description: "用tableflow多维表格看板管理项目：查项目/表格/数据与变更记录，定义表与字段，写入需求、版本与缺陷，配置计算字段。字段口径以specs/011-bug-table/board@2.yaml（四表：版本/独立规格需求/依赖需求/缺陷）为准。触发词：tableflow、多维表格、需求表、版本表、缺陷表、看板、依赖变更需求。"
---

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

rollup的`aggregate`只认`all`/`any`/`none`/`min`/`max`/`count_distinct`；`all`/`any`/`none`必须同时给`equals`（写成`all_true`这类会400）。契约口径是**单字段判定**，不要给rollup配`require`（board@2明确不设行级前置）。

relation的值是**目标行id的字符串数组**（单值也写`["v0.6.0"]`）。计算字段不可直接写；要人工覆盖用行PATCH的`overrides`，闸门字段不得覆盖（见下文）。

## 看板四表契约（board@2）

字段口径的唯一来源是`specs/011-bug-table/board@2.yaml`（它取代`board@1.yaml`，board@1留档）。本节只对齐口径；计算落地、写入校验、存量迁移不在契约范围。

四张表记的是四类不同的东西：

| 表 | 表id | 一行代表什么 | 解决什么问题 | 被谁引用 |
|---|---|---|---|---|
| 版本管理 | `<前缀>-ver` | 一个发布版本（`v1.0.0`） | 发哪一版、发什么、够不够条件发 | 看板主视图；引用indep与dep行；被bug的发现版本/修复版本引用 |
| 独立规格需求 | `<前缀>-indep` | **一份规格**（业务编号`008-AR`） | 做哪些规格、每份规格走到哪一步 | ver的`独立需求关联`、dep的`关联的独立规格需求`、bug的`关联规格` |
| 依赖需求 | `<前缀>-dep` | **一张变更单**（业务编号`D01`） | 已完成规格被改动时，改了哪些影响面、回归做完没有 | ver的`依赖需求关联` |
| 缺陷 | `<前缀>-bug` | **一个缺陷**（业务编号`BUG-01`） | 发现/修复到哪一步，修在哪个版本 | ver的`上一版本Bug`按缺陷的`发现版本`汇总；bug的`关联规格`指向indep |

引用关系四条：**ver→indep**（本版交付哪些规格）、**ver→dep**（本版有哪些变更单待回归）、**bug→ver**（`发现版本`必填单值，是版本表"上一版本Bug"的唯一挂接键；`修复版本`只作记录）、**bug→indep**（多对多，可暂未归因）。

一句话：indep回答"要做哪些规格"，dep回答"已做完的规格又被改了什么"，bug回答"哪里坏了、修没修、修在哪版"，ver回答"发哪一版、能不能发"。**需求不单独建表**，它以`条款`字段挂在规格行上；任务与场景不进表，只在规格行上汇总成数。

### 字段id与行id

字段id用`<项目前缀>-<表前缀字母>-<字段短名>`：`-v-`（ver）、`-i-`（indep）、`-d-`（dep）、`-b-`（bug）。行id是业务编号：版本`v<主>.<次>.<修>`、规格`NNN-AR`、变更单`D01`、缺陷`BUG-01`。字段id全局唯一，四张表不能复用同一id。

### 版本管理`<前缀>-ver`（16字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 版本号 | `<前缀>-v-ver` | text | 行id；`v1.0.0` |
| 发布时间 | `<前缀>-v-date` | datetime | 精确到日；上一版本判定不看它 |
| 发布状态 | `<前缀>-v-status` | enum | `planned`/`released`/`dropped` |
| 独立需求关联 | `<前缀>-v-specs` | relation→indep | 本版交付的规格 |
| 独立需求总数 | `<前缀>-v-spec-total` | computed | `count(独立需求关联)` |
| 独立需求就绪 | `<前缀>-v-spec-ready` | computed（闸门） | 关联规格`验收状态`全为`accepted` |
| 依赖需求关联 | `<前缀>-v-changes` | relation→dep | 本版待回归的变更单 |
| 依赖需求总数 | `<前缀>-v-change-total` | computed | `count(依赖需求关联)` |
| 依赖需求就绪 | `<前缀>-v-change-ready` | computed（闸门） | 关联变更单`回归状态`全为`passed` |
| 上一版本Bug总数 | `<前缀>-v-bug-total` | number | 口径见bug的`发现版本`；自动聚合落地前由脚本或人工填 |
| 上一版本Bug未解决数 | `<前缀>-v-bug-open` | number | 已解决数 = 总数 − 未解决数，不单独存 |
| 上一版本Bug就绪 | `<前缀>-v-bug-ready` | computed（闸门） | `上一版本Bug未解决数=0` |
| 发布条件 | `<前缀>-v-gate` | computed（闸门） | 三项就绪同时为真 |
| 场景总数 | `<前缀>-v-scenes` | computed | 本版规格的场景数之和 |
| 负责人 | `<前缀>-v-owner` | text | |
| 变更说明 | `<前缀>-v-note` | text | 本版范围/口径变化 |

七个计算字段的options（照抄，只改id前缀）：

```jsonc
{"kind":"count","source":"px-v-specs"}
{"kind":"rollup","source":"px-v-specs","field_id":"px-i-acceptance","aggregate":"all","equals":"accepted"}
{"kind":"count","source":"px-v-changes"}
{"kind":"rollup","source":"px-v-changes","field_id":"px-d-regress","aggregate":"all","equals":"passed"}
{"kind":"and","conditions":[{"field_id":"px-v-bug-open","equals":0}],"true_label":"是","false_label":"否"}
{"kind":"and","conditions":[{"field_id":"px-v-spec-ready","equals":true},{"field_id":"px-v-change-ready","equals":true},{"field_id":"px-v-bug-ready","equals":true}],"true_label":"是","false_label":"否"}
{"kind":"sum","source":"px-v-specs","field_id":"px-i-scenes","decimals":0}
```

**闸门字段**：`独立需求就绪`、`依赖需求就绪`、`上一版本Bug就绪`、`发布条件`四个只由计算得出，不要人工写值、也不要开人工覆盖。

### 独立规格需求`<前缀>-indep`（16字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-i-id` | text | 行id；`008-AR` |
| 条款 | `<前缀>-i-clause` | text | 这份规格要满足的需求条款原文或摘要 |
| 规格目录 | `<前缀>-i-dir` | text | speckit产物目录，如`specs/008-board-contract/` |
| 场景数 | `<前缀>-i-scenes` | number | `spec.md`场景条数 |
| 任务总数 | `<前缀>-i-tasks` | number | `tasks.md`任务条数 |
| speckit-constitution状态 | `<前缀>-i-constitution` | enum | `todo`/`doing`/`done`/`na` |
| speckit-specify状态 | `<前缀>-i-specify` | enum | 同上 |
| speckit-plan状态 | `<前缀>-i-plan` | enum | 同上 |
| speckit-task状态 | `<前缀>-i-task` | enum | 同上 |
| speckit-implement状态 | `<前缀>-i-implement` | enum | **`todo`/`doing`/`done`，没有`na`**；是置`accepted`的前置条件 |
| speckit-clarify状态 | `<前缀>-i-clarify` | enum | `todo`/`doing`/`done`/`na` |
| speckit-analyze状态 | `<前缀>-i-analyze` | enum | 同上 |
| speckit-checklist状态 | `<前缀>-i-checklist` | enum | 同上 |
| 宪法版本 | `<前缀>-i-constitution-version` | text | |
| 验收状态 | `<前缀>-i-acceptance` | enum | `pending`/`accepted`/`rejected`；**规格完成的唯一判据** |
| 负责人 | `<前缀>-i-owner` | text | |

八个speckit阶段状态**全部是enum**：`constitution`/`specify`/`plan`/`task`/`implement`/`clarify`/`analyze`/`checklist`；除`implement`外都可取`na`。不另设"状态"字段（同一问题两个真相），也不设`优先级`。

### 依赖需求`<前缀>-dep`（9字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-d-id` | text | 行id；`D01` |
| 条款 | `<前缀>-d-clause` | text | 改动点；必须点到规格编号与场景号 |
| 关联的独立规格需求 | `<前缀>-d-spec` | relation→indep | 被改的规格，可多份（横切改动） |
| 影响面 | `<前缀>-d-impact` | text | 受影响的能力/接口/场景/用例/下游 |
| 回归状态 | `<前缀>-d-regress` | enum | `todo`/`doing`/`passed`/`failed`；**唯一判据，没有`na`** |
| 证据 | `<前缀>-d-evidence` | text | 提交号/构建/截图/用例号；置`passed`时必须有 |
| 剩余事项 | `<前缀>-d-rest` | text | 未完成部分与阻塞；空表示无 |
| 规格修订 | `<前缀>-d-spec-revision` | enum | `not_needed`/`pending`/`done`；不参与判定 |
| 负责人 | `<前缀>-d-owner` | text | |

### 缺陷`<前缀>-bug`（12字段）

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-b-id` | text | 行id；`BUG-01`，全局递增不复用 |
| 标题 | `<前缀>-b-title` | text | 一句话说清现象与位置，不写修复方案 |
| 状态 | `<前缀>-b-status` | enum | `open`/`fixing`/`verifying`/`closed`；**唯一判据，`closed`是唯一终态，没有`na`** |
| 严重度 | `<前缀>-b-severity` | enum | `blocker`/`critical`/`major`/`minor`；记录字段，不进任何闸门 |
| 来源 | `<前缀>-b-source` | enum | `test`/`prod`/`review`/`user`；不参与判定 |
| 关联规格 | `<前缀>-b-specs` | relation→indep | 多对多；空数组=暂未归因，不阻塞流转 |
| 发现版本 | `<前缀>-b-found` | relation→ver | **必填单值**；版本表"上一版本Bug"的唯一挂接键 |
| 修复版本 | `<前缀>-b-fix` | relation→ver | 单值；修在哪版，不参与判定；不修复留空 |
| 证据 | `<前缀>-b-evidence` | text | 复现步骤/提交号/构建/用例号；置`closed`时必须有 |
| 剩余事项 | `<前缀>-b-rest` | text | 置`closed`时必须为空 |
| MS用例号 | `<前缀>-b-ms-case` | text | 多个用逗号分隔，可空 |
| 负责人 | `<前缀>-b-owner` | text | |

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
5. 挂到版本：把变更单填进受影响版本的`依赖需求关联`。挂上`todo`的变更单后该版本`依赖需求就绪`立即转"否"；回归推到`passed`后才恢复"是"，`发布条件`才可能成立。

### 空集语义：没挂变更单时"依赖需求就绪"显示"是"

`依赖需求就绪`= `rollup all`（本版dep行的`回归状态` `equals` `passed`）。**没挂任何变更单时`all`作用于空集，结果为true**，界面显示"是"。

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
3. 每个ver行初始：`独立需求总数=0`、`独立需求就绪=是`、`依赖需求总数=0`、`依赖需求就绪=是`、`上一版本Bug总数=0`、`上一版本Bug未解决数=0`、`上一版本Bug就绪=是`、`发布条件=是`（空集语义：是"无待办"不是"可交付"）、两个relation为`[]`。
4. 命名：表id=`<项目短前缀>-ver/-indep/-dep/-bug`；字段id=`<项目短前缀>-<v|i|d|b>-<字段短名>`，**全局唯一**；行id=业务编号（`v1.0.0`/`008-AR`/`D01`/`BUG-01`）。
5. 建字段顺序：**先indep字段 → 再dep字段 → 再bug字段 → 最后ver的relation与计算字段**。ver的`独立需求就绪`/`依赖需求就绪`是rollup，创建时就要解析indep的`验收状态`与dep的`回归状态`，目标字段没建完会400（`rollup.field_id 必须是目标表字段`）；bug的relation要指向已存在的ver与indep表。
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

# 字段：顺序 indep → dep → bug → ver（ver的rollup要解析indep/dep的判定字段）。
# 完整字段清单见「四表契约」，这里只示意顺序。
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields \
  -d '{"id":"px-i-implement","name":"speckit-implement状态","type":"enum",
       "options":[{"value":"todo","label":"未开始","tone":"neutral"},{"value":"doing","label":"进行中","tone":"info"},{"value":"done","label":"完成","tone":"success"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-id","name":"编号","type":"text","options":{"constraints":{"required":true}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-clause","name":"条款","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-scenes","name":"场景数","type":"number","options":{"decimals":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-tasks","name":"任务总数","type":"number","options":{"decimals":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields \
  -d '{"id":"px-i-acceptance","name":"验收状态","type":"enum",
       "options":[{"value":"pending","label":"未验收","tone":"neutral"},{"value":"accepted","label":"已验收","tone":"success"},{"value":"rejected","label":"不通过","tone":"danger"}]}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/fields -d '{"id":"px-d-id","name":"编号","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/fields \
  -d '{"id":"px-d-spec","name":"关联的独立规格需求","type":"relation","options":{"table_id":"px-indep","display_field":"px-i-clause","status_field":"px-i-acceptance"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/fields \
  -d '{"id":"px-d-regress","name":"回归状态","type":"enum",
       "options":[{"value":"todo","label":"未开始","tone":"neutral"},{"value":"doing","label":"进行中","tone":"info"},{"value":"passed","label":"通过","tone":"success"},{"value":"failed","label":"失败","tone":"danger"}]}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/fields -d '{"id":"px-b-id","name":"编号","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/fields \
  -d '{"id":"px-b-status","name":"状态","type":"enum",
       "options":[{"value":"open","label":"待修","tone":"danger"},{"value":"fixing","label":"修复中","tone":"warning"},{"value":"verifying","label":"已修待验","tone":"info"},{"value":"closed","label":"已关闭","tone":"success"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/fields \
  -d '{"id":"px-b-found","name":"发现版本","type":"relation","options":{"table_id":"px-ver","constraints":{"relation_must_exist":true}}}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-specs","name":"独立需求关联","type":"relation","options":{"table_id":"px-indep","display_field":"px-i-clause","status_field":"px-i-acceptance"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-changes","name":"依赖需求关联","type":"relation","options":{"table_id":"px-dep","display_field":"px-d-clause","status_field":"px-d-regress"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields -d '{"id":"px-v-ver","name":"版本号","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields -d '{"id":"px-v-bug-open","name":"上一版本Bug未解决数","type":"number","options":{"decimals":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-spec-ready","name":"独立需求就绪","type":"computed",
       "options":{"kind":"rollup","source":"px-v-specs","field_id":"px-i-acceptance","aggregate":"all","equals":"accepted"}}'

# 行：先写被关联的行，再写引用方。上一版本Bug未解决数写0，否则上一版本Bug就绪恒为否
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 \
  -d '{"values":{"px-v-ver":"v0.1.0","px-v-specs":[],"px-v-changes":[],"px-v-bug-open":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/rows/008-AR \
  -d '{"values":{"px-i-id":"008-AR","px-i-clause":"…","px-i-scenes":10,"px-i-tasks":10,"px-i-acceptance":"pending","px-i-implement":"todo"}}'
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 -d '{"values":{"px-v-specs":["008-AR"]}}'
```

### 2. 加一个计算字段并重算

```bash
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-spec-total","name":"独立需求总数","type":"computed",
       "options":{"kind":"count","source":"px-v-specs"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/recompute
```

### 3. 改状态 / 人工覆盖

```bash
# 改状态：PATCH是合并语义；写入后下游计算字段自动重算
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-indep/rows/008-AR -d '{"values":{"px-i-implement":"done"}}'

# 人工覆盖只对非闸门的计算字段有意义（原因必填；clear=true清除后立即重算）
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 \
  -d '{"overrides":[{"field_id":"px-v-scenes","value":12,"reason":"口径说明","clear":false}]}'

# 闸门字段（spec-ready/change-ready/bug-ready/gate）不得覆盖：要实现"例外"，改行数据或走变更单
```

### 4. 开一张变更单（建行 + 关联规格 + 推进回归）

```bash
# ① 开单：dep建行，登记被改规格与影响面
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/rows/D01 -d '{
  "values":{"px-d-id":"D01","px-d-clause":"008-AR#US1-AS2 指标权重改为按类别绑定默认方案",
            "px-d-spec":["008-AR"],"px-d-impact":"指标树、权重方案接口、下游取数",
            "px-d-regress":"todo"}}'

# ② 挂到受影响版本（假设v0.2.0已存在）：该版本"依赖需求就绪"立刻转"否"，"发布条件"转"否"
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.2.0 -d '{"values":{"px-v-changes":["D01"]}}'

# ③ 回归完成后推进状态：依赖需求就绪恢复"是"
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-dep/rows/D01 \
  -d '{"values":{"px-d-regress":"passed","px-d-evidence":"pytest 108 passed / 构建 2026-11-19"}}'
```

### 5. 记一个缺陷

```bash
# 发现版本必填单值；状态closed的准入见「bug的真实语义」
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-bug/rows/BUG-01 -d '{
  "values":{"px-b-id":"BUG-01","px-b-title":"看板刷新后筛选词丢失","px-b-status":"open",
            "px-b-severity":"major","px-b-source":"test","px-b-found":["v0.6.0"],
            "px-b-specs":["008-AR"],"px-b-evidence":"复现：输入筛选→点刷新→筛选清空"}}'

# 修复并关闭：修复版本 + 证据，剩余事项必须为空
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-bug/rows/BUG-01 \
  -d '{"values":{"px-b-status":"closed","px-b-fix":["v0.6.1"],"px-b-evidence":"fix 提交 a1b2c3d；用例 test_refresh_keeps_filter 通过"}}'
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
| 空版本发布条件显示"是" | 三项就绪在空集时都为真，`发布条件`随之显示"是"；含义是"无待办"，不是"可交付" |
| 回归状态写`na` | 契约没有`na`；确认不受影响记`passed`，理由写`证据` |
| `修复版本`当挂接键 | 版本表"上一版本Bug"按`发现版本`取；修复版本只记录 |
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
| 上一版本Bug未解决数留空 | 空≠0，`上一版本Bug就绪`恒为"否"，`发布条件`永远不成立；建ver行时就写`0` |
| 删除是硬删除 | 删表级联删字段与行；删行不级联，引用方显示"关联已失效"（010起悬空关联会让`就绪`判否） |
| 存量项目字段照抄 | 存量项目按board@1/v0.5.x建的字段未迁移（迁移不在board@2范围）；新建项目一律按四表契约 |
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
