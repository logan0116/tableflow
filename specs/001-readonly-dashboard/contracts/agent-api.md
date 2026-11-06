# 接口契约：Agent 写接口

**Base URL**: `http://<host>:8000`

**通用约定**

- 全部写操作在 `/api/agent/*` 下，与人侧只读接口分离（宪法原则 I）。
- 必须带请求头 `X-Agent-Id`，值写入审计；缺失时返回 400 并记一条失败审计。
- 响应统一信封：

```json
{ "result": "success", "id": "t-eq" }
{ "result": "failed", "error": "字段校验失败：..." }
{ "result": "unknown", "error": "提交结果未知：..." }
```

- 三态语义：`success` 已提交；`failed` 未落库；`unknown` 表示提交结果无法确认（HTTP 503），调用方 MUST NOT 当作成功。
- 每次调用（成功或失败）都写一条 `write_audit`，字段见 data-model.md §6。

## 0. 项目

| 方法 | 路径 | 请求体 |
|---|---|---|
| POST | `/api/agent/projects` | `{ "id"?: string, "name": string }` |
| DELETE | `/api/agent/projects/{project_id}` | 无（级联删除其表格、字段、行） |

项目是写接口的第一层容器；建表前必须先有项目。

## 1. 表格

| 方法 | 路径 | 请求体 |
|---|---|---|
| POST | `/api/agent/projects/{project_id}/tables` | `{ "id"?: string, "name": string, "order"?: int }` |
| PATCH | `/api/agent/tables/{table_id}` | `{ "name"?: string, "order"?: int }` |
| DELETE | `/api/agent/tables/{table_id}` | 无 |

删除表格会级联删除其字段与数据行。

## 2. 字段

| 方法 | 路径 | 请求体 |
|---|---|---|
| POST | `/api/agent/tables/{table_id}/fields` | `{ "id"?: string, "name": string, "type": string, "options"?: any, "order"?: int, "visible"?: 0\|1 }` |
| PATCH | `/api/agent/fields/{field_id}` | 同上，字段均可选 |
| DELETE | `/api/agent/fields/{field_id}` | 无 |

`type` 取值：`text` / `number` / `datetime` / `enum` / `relation`。

- `enum` 的 `options`：`[{"value": "...", "label": "..."}]`
- `relation` 的 `options`：`{"table_id": "..."}`，目标表必须与当前表同属一个项目

## 3. 数据行

| 方法 | 路径 | 请求体 |
|---|---|---|
| POST | `/api/agent/tables/{table_id}/rows` | `{ "id"?: string, "values": object }` |
| PATCH | `/api/agent/rows/{row_id}` | `{ "values": object }`（与已有值合并） |
| DELETE | `/api/agent/rows/{row_id}` | 无 |

`values` 的键必须是该表的字段 id；relation 字段的值必须是字符串数组（目标行 id）。

## 4. 错误码

| 状态码 | 场景 | 响应 |
|---|---|---|
| 200 | 成功 | `{"result":"success","id":"..."}` |
| 400 | 校验失败 / 缺少 `X-Agent-Id` / 目标不存在 | `{"result":"failed","error":"..."}` |
| 503 | 数据存储不可用或提交结果未知 | `{"result":"unknown","error":"..."}` |

## 5. 审计记录

每次调用写入一条 `write_audit`：

```json
{
  "agent_id": "agent-cli",
  "action": "field.create",
  "target": "t-task",
  "payload": "{\"name\":\"负责人\",\"type\":\"relation\"}",
  "result": "success",
  "error": null,
  "created_at": "2026-11-06T12:40:00+08:00"
}
```

审计只增不改；`payload` 超过 4KB 时截断。
