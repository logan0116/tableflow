---
name: tableflow-board
description: "用 tableflow 多维表格看板管理项目：查项目/表格/数据，定义表与字段，写入需求、版本与状态。适用于 tableflow 实例（人只读、Agent 读写）。触发词：tableflow、多维表格、需求表、版本表、看板。"
---

# tableflow 多维表格：用 Agent 写接口管项目

tableflow 是一块只读看板 + 一套 Agent 写接口：**人只读，Agent 读写**。所有写操作必须带 `X-Agent-Id`，每次调用都会落一条审计。

## 何时用

- 要查某个项目的表格数据（需求、版本、任务、依赖）
- 要把一批需求/版本/字段定义写进看板
- 要把需求挂到版本、把依赖需求关联到独立需求
- 要新增一列、改字段顺序、隐藏字段

## 连接

```bash
export TF_BASE=http://127.0.0.1:8000          # 换成实际地址
export TF_AGENT=agent-my-task                  # 写操作必带，写入审计
```

## 读接口（全部 GET，无需鉴权）

| 路径 | 说明 |
|---|---|
| `/api/projects` | 项目列表 |
| `/api/projects/{project_id}/tables` | 项目下的表格（按 order 升序） |
| `/api/tables/{table_id}/table` | 字段（visible=1）+ 全部数据行 |
| `/api/tables/{table_id}/rows/{row_id}` | 单行明细（关联弹层用） |
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
| POST | `/api/agent/tables/{tid}/rows` | 写行 `{id?, values}` |
| PATCH/DELETE | `/api/agent/rows/{id}` | 改行（values 合并）· 删行 |

响应统一：`{"result":"success","id":"..."}` / `{"result":"failed","error":"..."}`（400）/ `{"result":"unknown","error":"..."}`（503，**不得当成功**）。

## 数据模型

```
项目 → 表格 → 字段 + 数据行
```

- 字段：`id`（全局唯一）、`table_id`、`name`、`type`、`options`、`order`、`visible`
- 类型：`text` / `number` / `datetime` / `enum` / `relation`
- `enum` 的 options：`[{"value":"doing","label":"进行中"}]`
- `relation` 的 options：`{"table_id":"目标表id"}`；**值必须是目标行 id 的字符串数组**（单值也写成 `["r-1"]`）
- 行值存在 `row_records.data`（JSON），键是字段 id

## 常用配方

### 1. 建项目 → 表 → 字段 → 行（顺序不能反）

```bash
H=(-H "X-Agent-Id: $TF_AGENT" -H 'Content-Type: application/json')

# 项目
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects -d '{"id":"proj-x","name":"新项目"}'

# 表格（relation 的目标表必须先建好）
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"t-a","name":"需求","order":1}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/projects/proj-x/tables -d '{"id":"t-b","name":"版本","order":2}'

# 字段
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/fields -d '{"id":"a-1","name":"编号","type":"text"}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/fields -d '{"id":"a-2","name":"所属版本","type":"relation","options":{"table_id":"t-b"}}'

# 行
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-b/rows -d '{"id":"v-1","values":{}}'
curl -s "${H[@]}" -X POST $TF_BASE/api/agent/tables/t-a/rows -d '{"id":"r-1","values":{"a-1":"REQ-01","a-2":["v-1"]}}'
```

### 2. 把一批需求挂到版本

```bash
# 版本行上维护关联（单向：版本表是唯一挂载点）
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/rows/v-1 \
  -d '{"values":{"v-req":["r-1","r-2"]}}'
```

### 3. 改状态

```bash
curl -s "${H[@]}" -X PATCH $TF_BASE/api/agent/rows/r-1 -d '{"values":{"a-status":"done"}}'
```

PATCH 是**合并**语义：只传要改的键，其余保持不变。

## 常见坑

| 坑 | 说明 |
|---|---|
| relation 目标表不存在 | 先建目标表再建 relation 字段，否则 400 |
| 字段 id 全局唯一 | 两个表不能复用同一个字段 id；建议 `<表前缀>-<字段名>` |
| 行 id 即关联标签 | 看板里 relation 显示的是目标行 id，起名要有可读性（如 `REQ-01`、`v0.3.0`） |
| 删除是硬删除 | 删表级联删字段与行；删行不级联，引用方显示“关联已失效” |
| seed 脚本全量替换 | `scripts/seed_data.py` 会清空业务四表，别在真实数据上重跑 |
| 未知字段键 | 行 values 的键必须是该表已有字段 id，否则 400 且不落库 |
| 写接口无鉴权 | 只靠 `X-Agent-Id` 留痕，不要把实例暴露到不可信网络 |

## 自检

```bash
curl -s $TF_BASE/api/projects | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST $TF_BASE/api/projects   # 人侧应为 405
```

## 附：命令行小工具

`assets/tf.py` 提供 `projects / tables / table / row / call` 五个子命令，见文件头注释。
