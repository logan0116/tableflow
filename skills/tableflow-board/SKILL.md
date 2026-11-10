---
name: tableflow-board
description: "用 tableflow 多维表格看板管理项目：查项目/表格/数据与变更记录，定义表与字段，写入需求、版本与状态，配置计算字段。适用于 tableflow 实例（人只读、Agent 读写）。触发词：tableflow、多维表格、需求表、版本表、看板。"
---

# tableflow 多维表格：用 Agent 写接口管项目

tableflow 是一块只读看板 + 一套 Agent 写接口：**人只读，Agent 读写**。所有写操作必须带 `X-Agent-Id`，每次调用落一条 `write_audit`，字段值真实变化时另记一条 `business_changes`。

## 何时用

- 查某个项目的表格数据（需求、版本、依赖）
- 把一批需求/版本/字段定义写进看板
- 把需求挂到版本、把依赖需求关联到独立需求
- 加一列、改字段顺序、隐藏字段、配一个计算字段（进度/汇总/发布条件）

## 连接

```bash
export TF_BASE=http://<tableflow-host>:8090   # 线上实例；本地开发是 http://127.0.0.1:8000
export TF_AGENT=agent-my-task                 # 写操作必带，写入审计
```

## 读接口（全部 GET，无需鉴权）

| 路径 | 说明 |
|---|---|
| `/api/projects` | 项目列表 |
| `/api/projects/{project_id}/tables` | 项目下的表格（按 order 升序） |
| `/api/tables/{table_id}/table` | 字段（visible=1）+ 全部数据行（含计算字段值） |
| `/api/tables/{table_id}/rows/{row_id}` | 单行明细（关联弹层用） |
| `/api/tables/{table_id}/rows/{row_id}/changes` | 该行的业务变更记录 |
| `/api/health` | 探活 |

## 写接口（前缀 `/api/agent`，必带 `X-Agent-Id`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/projects` | 建项目 `{id?, name}` |
| DELETE | `/api/agent/projects/{id}` | 删项目（级联表/字段/行） |
| POST | `/api/agent/projects/{pid}/tables` | 建表 `{id?, name, order?}` |
| PATCH/DELETE | `/api/agent/tables/{id}` | 改名/改序 · 删表（级联） |
| POST | `/api/agent/tables/{tid}/fields` | 加字段 `{id?, name, type, options?, order?, visible?}` |
| PATCH/DELETE | `/api/agent/fields/{id}` | 改字段 · 删字段 |
| POST | `/api/agent/tables/{tid}/rows/{row_id}` | **写行**（行 id 在路径里） |
| PATCH | `/api/agent/tables/{tid}/rows/{row_id}` | 改行 `{values?, overrides?}`（合并） |
| DELETE | `/api/agent/tables/{tid}/rows/{row_id}` | 删行 |
| POST | `/api/agent/tables/{tid}/recompute` | 手动重算该表及其下游计算字段 |

响应统一：`{"result":"success","id":"..."}` / `{"result":"failed","error":"..."}`（400）/ `{"result":"unknown","error":"..."}`（503，**不得当成功**）。

可选请求头 `X-Origin: human-request` 标记"人发起、Agent 执行"的写入。

## 数据模型

```
项目 → 表格 → 字段 + 数据行
```

- 字段：`id`（全局唯一）、`table_id`、`name`、`type`、`options`、`order`、`visible`
- 行 id **就是业务编号**（如 `7.0.1`、`UD-01-BR`、`002-AR`），关联标签显示的就是它；行 id 创建后不可改
- 类型：`text` / `number` / `datetime` / `enum` / `relation` / `computed`

### options 形态

```jsonc
// enum：数组，每项带 tone（neutral/info/success/warning/danger）
[{"value":"done","label":"已完成","tone":"success"}]

// number
{"decimals":2,"percent":true,"unit":"台"}

// datetime
{"with_time":false}

// relation：目标表必须同项目
{"table_id":"t-staff"}

// computed：写侧算、读侧只读
{"kind":"percent","source":"<relation 字段 id>","where":{"field_id":"...","equals":"done"}}
{"kind":"count","source":"<relation 字段 id>"}
{"kind":"sum","source":"<relation 字段 id>","field_id":"...","decimals":0}
{"kind":"rollup","source":"<relation 字段 id>","field_id":"...","aggregate":"all_true"}
{"kind":"and","conditions":[{"field_id":"...","equals":100}]}
```

relation 的值是**目标行 id 的字符串数组**（单值也写 `["r-1"]`）。计算字段不可直接写；要人工覆盖用行 PATCH 的 `overrides`。

## 常用配方

### 1. 建项目 → 表 → 字段 → 行（顺序不能反）

```bash
H=(-H "X-Agent-Id: $TF_AGENT" -H 'Content-Type: application/json')

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects -d '{"id":"proj-x","name":"新项目"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"t-a","name":"需求","order":1}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"t-b","name":"版本","order":2}'

curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/fields -d '{"id":"a-1","name":"编号","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/fields \
  -d '{"id":"a-2","name":"所属版本","type":"relation","options":{"table_id":"t-b"}}'

# 行 id 在路径里；先写被关联的行
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-b/rows/v-1 -d '{"values":{}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/rows/REQ-01 \
  -d '{"values":{"a-1":"REQ-01","a-2":["v-1"]}}'
```

### 2. 加一个计算字段并重算

```bash
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/fields \
  -d '{"id":"a-dev","name":"完成比例","type":"computed",
       "options":{"kind":"percent","source":"a-2","where":{"field_id":"a-status","equals":"done"}}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/recompute
```

### 3. 改状态 / 人工覆盖

```bash
# 改状态：PATCH 是合并语义
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/t-a/rows/REQ-01 -d '{"values":{"a-status":"done"}}'

# 人工覆盖计算字段（原因必填；clear=true 清除后立即重算）
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/t-a/rows/v-1 \
  -d '{"overrides":[{"field_id":"v-cond","value":true,"reason":"客户特批","clear":false}]}'
```

### 4. 查变更记录

```bash
curl -s $TF_BASE/api/tables/t-a/rows/REQ-01/changes
```

## 常见坑

| 坑 | 说明 |
|---|---|
| relation 目标表不存在 | 先建目标表再建 relation 字段，否则 400 |
| 字段 id 全局唯一 | 两个表不能复用同一个字段 id；建议 `<表前缀>-<字段名>` |
| 行 id 即关联标签 | 用业务编号起名（`7.0.1`、`UD-01-BR`），创建后不可改 |
| 写行路径带 table_id | `POST /api/agent/tables/{tid}/rows/{row_id}`，旧的无 table_id 路径已移除 |
| 计算字段不可直写 | 只读 `computed_values`；要覆盖走 `overrides`，要刷新走 `recompute` |
| 删除是硬删除 | 删表级联删字段与行；删行不级联，引用方显示"关联已失效" |
| seed 脚本全量替换 | `scripts/seed_data.py` / `rebuild_v030.py` 会清空业务表，别在真实数据上重跑 |
| 未知字段键 | 行 values 的键必须是该表已有字段 id，否则 400 且不落库 |
| 写接口无鉴权 | 只靠 `X-Agent-Id` 留痕，不要把实例暴露到不可信网络 |

## 自检

```bash
curl -s $TF_BASE/api/projects | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST $TF_BASE/api/projects   # 人侧应为 405
```

## 附：命令行小工具

`assets/tf.py` 提供 `projects / tables / table / row / changes / call` 子命令，见文件头注释。
