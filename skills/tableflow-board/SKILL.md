---
name: tableflow-board
description: "用tableflow多维表格看板管理项目：查项目/表格/数据与变更记录，定义表与字段，写入需求、版本与状态，配置计算字段。适用于tableflow实例（人只读、Agent读写）。触发词：tableflow、多维表格、需求表、版本表、看板、依赖变更需求。"
---

# tableflow多维表格：用Agent写接口管项目

tableflow是一块只读看板+一套Agent写接口：**人只读，Agent读写**。所有写操作必须带`X-Agent-Id`，每次调用落一条`write_audit`，字段值真实变化时另记一条`business_changes`。

## 何时用

- 查某个项目的表格数据（版本、规格、变更单）
- 把一个项目的规格拆成行写进看板，规划版本并把规格挂到版本
- 已完成规格被改动 → 开一张变更单，追踪影响面与回归
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
- 行id**就是业务编号**（如`7.0.1`、`UD-01-BR`、`S01`），关联标签显示的就是它；行id创建后不可改
- 类型：`text`/`number`/`datetime`/`enum`/`relation`/`computed`
- 一个项目可以有任意多张表；但**项目看板只用三张表**，范式见下一节

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
{"table_id":"t-staff"}
{"table_id":"ab-indep","display_field":"ab-i-clause","status_field":"ab-i-implement",
 "constraints":{"relation_must_exist":true}}

// computed：写侧算、读侧只读；布尔值默认显示"是/否"，and可用true_label/false_label改字面
{"kind":"count","source":"<relation字段id>"}
{"kind":"percent","source":"<relation字段id>","where":{"field_id":"...","equals":"done"},"decimals":0}
{"kind":"sum","source":"<relation字段id>","field_id":"...","decimals":0}
{"kind":"rollup","source":"<relation字段id>","field_id":"...","aggregate":"all","equals":"passed"}
{"kind":"and","conditions":[{"field_id":"...","equals":100}]}
```

rollup的`aggregate`只认`all`/`any`/`none`/`min`/`max`/`count_distinct`；`all`/`any`/`none`必须同时给`equals`（写成`all_true`这类会400）。可选`require:[{field_id,equals}]`给行级前置条件。

relation的值是**目标行id的字符串数组**（单值也写`["r-1"]`）。计算字段不可直接写；要人工覆盖用行PATCH的`overrides`。

## 看板三表规范（建表前先读这一节）

三张表是固定范式。它们的区别不在"层级"，而在**各自记的是不同的东西**：

| 表 | 表id | 一行代表什么 | 解决什么问题 | 被谁引用 |
|---|---|---|---|---|
| 版本管理 | `<前缀>-ver` | 一个发布版本（`v1.0.0`） | 发哪一版、发什么、够不够条件发 | 看板主视图；`需求关联（独立）`引用indep行，`需求关联（依赖）`引用dep行 |
| 独立规格需求 | `<前缀>-indep` | **一份规格**（业务编号`S01`） | 做哪些规格、每份规格走到哪一步 | ver的`需求关联（独立）`、dep的`关联的独立规格需求` |
| 依赖变更需求 | `<前缀>-dep` | **一张变更单**（业务编号`D01`） | 已完成规格被改动时，改了哪些影响面、回归做完没有 | ver的`需求关联（依赖）` |

两种引用关系：**ver→indep**（这一版交付哪些规格）、**ver→dep**（这一版里有哪些变更单待回归）。dep那一侧的indep引用只是登记"改的是哪份规格"。

一句话：indep回答"要做哪些规格"，dep回答"已做完的规格又被改了什么"，ver回答"发哪一版、能不能发"。**没有第四张表**：需求不单独建表，它以`条款`字段挂在规格行上；任务与Bug不进看板（只汇总成数）。

### 三表字段

字段id用`<项目前缀>-<表前缀字母>-<字段短名>`：`ab-v-`（ver）、`ab-i-`（indep）、`ab-d-`（dep）。

#### 版本管理`<前缀>-ver`

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 版本号 | `<前缀>-v-ver` | text | `v1.0.0`；也是行id |
| 发布时间 | `<前缀>-v-date` | datetime | 计划或实际发布日期 |
| 发布状态 | `<前缀>-v-status` | enum | `planned`/`released`/`dropped` |
| 需求关联（独立） | `<前缀>-v-indep` | relation→indep | 本版交付的规格 |
| 需求关联（依赖） | `<前缀>-v-dep` | relation→dep | 本版的变更单；**新版本为空**，规格被改后才挂 |
| 开发进度 | `<前缀>-v-dev` | computed | 本版规格里`implement=done`的占比 |
| 测试进度 | `<前缀>-v-test` | text | 人填（如`4/13`） |
| 未清Bug数 | `<前缀>-v-bug-open` | number | ≥0 |
| Bug已清空 | `<前缀>-v-bug-clear` | computed | 未清Bug数=0 |
| 回归通过 | `<前缀>-v-regress` | computed | 本版变更单的回归状态全为`passed` |
| 发布条件 | `<前缀>-v-cond` | computed | 进度=100 且 Bug已清空 且 回归通过 |
| 场景总数 | `<前缀>-v-scenes` | computed | 本版规格的场景数之和 |
| 任务总数 | `<前缀>-v-tasks` | computed | 本版规格的任务总数之和 |
| 负责人 | `<前缀>-v-owner` | text | |
| 变更说明 | `<前缀>-v-note` | text | 本版范围/口径变化 |

六个计算字段的options（照抄，只改id前缀）：

```jsonc
{"kind":"percent","source":"ab-v-indep","where":{"field_id":"ab-i-implement","equals":"done"},"decimals":0}
{"kind":"and","conditions":[{"field_id":"ab-v-bug-open","equals":0}],"true_label":"是","false_label":"否","allow_override":true}
{"kind":"rollup","source":"ab-v-dep","field_id":"ab-d-regress","aggregate":"all","equals":"passed"}
{"kind":"and","conditions":[{"field_id":"ab-v-dev","equals":100},{"field_id":"ab-v-regress","equals":true},{"field_id":"ab-v-bug-clear","equals":true}],"true_label":"是","false_label":"否"}
{"kind":"sum","source":"ab-v-indep","field_id":"ab-i-scenes","decimals":0}
{"kind":"sum","source":"ab-v-indep","field_id":"ab-i-tasks","decimals":0}
```

#### 独立规格需求`<前缀>-indep`

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-i-id` | text | 业务编号`S01`；也是行id |
| 条款 | `<前缀>-i-clause` | text | 这份规格要满足的需求条款原文或摘要 |
| 规格目录 | `<前缀>-i-dir` | text | speckit产物目录，如`specs/002-evaluation/` |
| 场景数 | `<前缀>-i-scenes` | number | `spec.md`场景条数 |
| 任务总数 | `<前缀>-i-tasks` | number | `tasks.md`任务条数 |
| 状态 | `<前缀>-i-status` | text | 一句话现状 |
| speckit各阶段状态 | `<前缀>-i-constitution`/`-specify`/`-plan`/`-task`/`-implement`/`-clarify`/`-analyze`/`-checklist` | text或enum | 逐阶段状态，见下 |
| 验收状态 | `<前缀>-i-acceptance` | enum | `pending`/`accepted`/`rejected` |
| 优先级 | `<前缀>-i-priority` | enum | `P0`/`P1`/`P2`/`P3` |
| 负责人 | `<前缀>-i-owner` | text | |

speckit阶段状态列：`constitution`、`specify`、`plan`、`task`、`implement`、`clarify`、`analyze`、`checklist`。其中**`speckit-implement状态`是版本开发进度的分子分母**，必须是enum `todo`/`doing`/`done`；其余阶段用text或enum均可。

#### 依赖变更需求`<前缀>-dep`

| 字段 | 字段id | 类型 | 说明 |
|---|---|---|---|
| 编号 | `<前缀>-d-id` | text | `D01`；也是行id |
| 条款（变更内容） | `<前缀>-d-clause` | text | 这次改什么 |
| 依赖规格 | `<前缀>-d-spec` | text | 被改规格的业务编号（如`S05`）；字段名沿用"依赖规格"，**指"变更所依赖的已完成规格"，不是规格之间的依赖** |
| 关联的独立规格需求 | `<前缀>-d-indep` | relation→indep | 指向被改的那份规格行 |
| 影响面 | `<前缀>-d-impact` | text | 受影响的能力/字段/接口/验收用例/下游规格 |
| 回归状态 | `<前缀>-d-regress` | enum | `todo`/`doing`/`passed`/`failed`/`na` |
| 状态 | `<前缀>-d-status` | text | 变更单自身状态（如`待评审`/`已合入`） |

## dep的真实语义：变更单，不是"规格之间的依赖"

dep的一行=**一张变更单**：某份**已经完成**的规格，之后又被修改，于是开单记录改动与回归。它不是需求之间的依赖关系表。

### 什么时候才开一张变更单

两个条件同时成立才开：

1. 该规格在indep里`speckit-implement状态`已是`done`（或`验收状态`已`accepted`）——它已经是完成基线；
2. 现在又要改它的能力、字段或验收口径。

还没做完的规格要改，直接改indep行与规格文件，**不开变更单**。

### 一张变更单的生命周期

1. 开单：在dep建一行，行id`D01`、`D02`递增，`条款`写清改什么。
2. 关联被改规格：`关联的独立规格需求`填`["S05"]`，`依赖规格`填`S05`（文本，给人看）。
3. 填影响面：哪些能力/字段/接口/验收用例/下游规格受影响。
4. 推进回归：`回归状态`按`todo → doing → passed`；失败填`failed`，确认不受影响填`na`。
5. 挂到版本：把变更单填进受影响版本的`需求关联（依赖）`。挂上后该版本`回归通过`立即转"否"；回归推到`passed`后才恢复"是"，`发布条件`才可能成立。

### 空集语义：dep为空时"回归通过"显示"是"

`回归通过`= `rollup all`（本版dep行的`回归状态` `equals` `passed`）。**没挂任何变更单时`all`作用于空集，结果为true**，界面显示"是"。

它的意思是"本版没有待回归的变更项"，**不是**"已经做过回归验证"。新建版本`需求关联（依赖）`为空、`回归通过`显示"是"，属正常初始态：不要为了让它"看起来正确"而补变更单，也不要据此认为发布前提已满足（还差`开发进度=100`与`Bug已清空`）。

### 这些都不是dep（反例清单）

| 容易被误写成dep的东西 | 正确去处 |
|---|---|
| 规格之间的开发依赖顺序（如`S03`依赖`S05`） | 设计文档/`spec.md`的依赖说明；看板不记"谁先做谁后做" |
| 一份规格内部的需求拆解、任务清单 | 规格的`spec.md`/`tasks.md`；看板只用`场景数`/`任务总数`两列汇总 |
| Bug、缺陷 | 缺陷跟踪；看板只汇总`未清Bug数` |
| 前置事项、待澄清问题 | 前置清单类文档；与版本的关联用`变更说明`写一句 |
| 新规格 | 在indep新建一行，不是变更单 |
| 版本之间的先后、并行关系 | 不进看板 |

判定标准一句话：**dep的一行必须能回答"哪份已完成规格被改了、改了什么、改后要回归什么"**。答不上来，就不是变更单。

## 新项目落地检查单

建完立刻核对，六条都成立才算对：

1. 项目下**只有3张表**：`<前缀>-ver`、`<前缀>-indep`、`<前缀>-dep`（顺序：版本在前）。
2. `<前缀>-dep`初始**0行**。
3. 每个ver行初始：`开发进度`=0（未关联规格时该格为空，关联后从0起算）、`回归通过`=是、`发布条件`=否、`需求关联（依赖）`=空数组；建行时把`未清Bug数`写成`0`，否则`Bug已清空`恒为"否"，`发布条件`永远不成立。
4. 命名：表id=`<项目短前缀>-ver/-indep/-dep`；字段id=`<项目短前缀>-<v|i|d>-<字段短名>`，**全局唯一**，两张表不能复用同一字段id；行id=业务编号（ver用`v1.0.0`，indep用`S01`，dep用`D01`）。
5. 建字段顺序：**先indep字段 → 再dep字段 → 最后ver的relation与计算字段**。ver的`回归通过`是rollup，创建时就要解析dep的`回归状态`字段，dep字段没建完会400（`rollup.field_id 必须是目标表字段`）。
6. 建行顺序：先ver行，再indep行、dep行，最后PATCH挂relation（relation的目标行必须已存在，否则400）。

## 常用配方

### 1. 建项目 → 三张表 → 字段 → 行（顺序不能反）

```bash
H=(-H "X-Agent-Id: $TF_AGENT" -H 'Content-Type: application/json')

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects -d '{"id":"proj-x","name":"新项目"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-ver","name":"版本管理","order":1}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-indep","name":"独立规格需求","order":2}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"px-dep","name":"依赖变更需求","order":3}'

# 字段：顺序 indep → dep → ver（ver的rollup要解析dep的回归状态字段，dep字段没建完会400）。
# 完整字段清单见「三表字段」，这里只示意顺序。
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields \
  -d '{"id":"px-i-implement","name":"speckit-implement状态","type":"enum",
       "options":[{"value":"todo","label":"未开始","tone":"neutral"},{"value":"doing","label":"进行中","tone":"info"},{"value":"done","label":"完成","tone":"success"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-id","name":"编号","type":"text","options":{"constraints":{"required":true}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-clause","name":"条款","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-scenes","name":"场景数","type":"number","options":{"decimals":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/fields -d '{"id":"px-i-tasks","name":"任务总数","type":"number","options":{"decimals":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/fields \
  -d '{"id":"px-d-regress","name":"回归状态","type":"enum",
       "options":[{"value":"todo","label":"未开始","tone":"neutral"},{"value":"doing","label":"进行中","tone":"info"},{"value":"passed","label":"通过","tone":"success"},{"value":"failed","label":"失败","tone":"danger"},{"value":"na","label":"不适用","tone":"neutral"}]}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-indep","name":"需求关联（独立）","type":"relation",
       "options":{"table_id":"px-indep","display_field":"px-i-clause","status_field":"px-i-implement"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-dep","name":"需求关联（依赖）","type":"relation",
       "options":{"table_id":"px-dep","display_field":"px-d-clause","status_field":"px-d-regress"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-regress","name":"回归通过","type":"computed",
       "options":{"kind":"rollup","source":"px-v-dep","field_id":"px-d-regress","aggregate":"all","equals":"passed"}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields -d '{"id":"px-v-ver","name":"版本号","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields -d '{"id":"px-v-bug-open","name":"未清Bug数","type":"number","options":{"decimals":0}}'

# 行：先写被关联的行，再写引用方。ver行的未清Bug数写0，否则Bug已清空恒为否
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 \
  -d '{"values":{"px-v-ver":"v0.1.0","px-v-indep":[],"px-v-bug-open":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-indep/rows/S01 \
  -d '{"values":{"px-i-id":"S01","px-i-clause":"…","px-i-scenes":6,"px-i-tasks":18}}'
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 -d '{"values":{"px-v-indep":["S01"]}}'
```

### 2. 加一个计算字段并重算

```bash
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/fields \
  -d '{"id":"px-v-dev","name":"开发进度","type":"computed",
       "options":{"kind":"percent","source":"px-v-indep","where":{"field_id":"px-i-implement","equals":"done"},"decimals":0}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-ver/recompute
```

### 3. 改状态 / 人工覆盖

```bash
# 改状态：PATCH是合并语义；写入后下游计算字段自动重算
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-indep/rows/S01 -d '{"values":{"px-i-implement":"done"}}'

# 人工覆盖计算字段（原因必填；clear=true清除后立即重算）。px-v-cond的建法见「三表字段」
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.1.0 \
  -d '{"overrides":[{"field_id":"px-v-cond","value":true,"reason":"客户特批","clear":false}]}'
```

### 4. 开一张变更单（建行 + 关联规格 + 推进回归）

```bash
# ① 开单：dep建行，登记被改规格与影响面
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/px-dep/rows/D01 -d '{
  "values":{"px-d-id":"D01","px-d-clause":"S05指标权重改为按类别绑定默认方案",
            "px-d-spec":"S05","px-d-indep":["S05"],
            "px-d-impact":"指标树、权重方案接口、S07/S08下游取数",
            "px-d-regress":"todo","px-d-status":"待评审"}}'

# ② 挂到受影响版本（假设v0.2.0已存在）：该版本"回归通过"立刻转"否"，"发布条件"转"否"
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-ver/rows/v0.2.0 -d '{"values":{"px-v-dep":["D01"]}}'

# ③ 回归完成后推进状态：回归通过恢复"是"
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/px-dep/rows/D01 \
  -d '{"values":{"px-d-regress":"passed","px-d-status":"已合入"}}'
```

### 5. 查变更记录

```bash
curl -s $TF_BASE/api/tables/px-indep/rows/S01/changes
```

## 常见坑

| 坑 | 说明 |
|---|---|
| 把规格间依赖写进dep | dep只收"已完成规格又被改"的变更单，见上文反例清单 |
| dep初始就有行 | 新项目dep必须0行；`回归通过`显示"是"不等于"已回归" |
| relation目标表不存在 | 先建目标表再建relation字段，否则400 |
| 字段id全局唯一 | 两个表不能复用同一个字段id；用`<前缀>-<表字母>-<短名>` |
| 行id即关联标签 | 用业务编号起名（`v1.0.0`、`S01`、`D01`），创建后不可改 |
| 写行路径带table_id | `POST /api/agent/tables/{tid}/rows/{row_id}`，旧的无table_id路径已移除 |
| rollup写`all_true` | 只认`all`/`any`/`none`/`min`/`max`/`count_distinct`，且`all`必须配`equals` |
| rollup建在目标字段之前 | 建ver计算字段前，dep的`回归状态`字段必须已存在，否则400；顺序indep→dep→ver |
| 计算字段不可直写 | 只读`computed_values`；要覆盖走`overrides`，要刷新走`recompute` |
| 未清Bug数留空 | 空≠0，`Bug已清空`恒为"否"，`发布条件`永远不成立；建ver行时就写`0` |
| 删除是硬删除 | 删表级联删字段与行；删行不级联，引用方显示"关联已失效" |
| seed脚本全量替换 | `scripts/seed_data.py`/`rebuild_v030.py`会清空业务表，别在真实数据上重跑 |
| 未知字段键 | 行values的键必须是该表已有字段id，否则400且不落库 |
| 写接口无鉴权 | 只靠`X-Agent-Id`留痕，不要把实例暴露到不可信网络 |

## 自检

```bash
curl -s $TF_BASE/api/projects | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST $TF_BASE/api/projects   # 人侧应为405
```

建完看板按「新项目落地检查单」核对；最快的核对方式是读一次`/api/tables/<前缀>-dep/table`，`rows`应为空数组。

## 附：命令行小工具

`assets/tf.py`提供`projects`/`tables`/`table`/`row`/`changes`/`call`子命令，见文件头注释。
