# 接口契约：只读看板 API

**Base URL**: `http://<host>:8000`

**通用约定**

- 只允许 `GET`。其他方法一律 `405 Method Not Allowed`（宪法原则 I：v0 无写路径）。
- 所有响应带 `Content-Type: application/json; charset=utf-8` 与 `Cache-Control: no-store`（宪法原则 II）。
- 字段与行的排序由服务端固定：`fields` 按 `order` 升序、`rows` 按 `id` 升序，前端不再排序。
- `fields` 只返回 `visible = 1` 的字段；`visible = 0` 的字段及其数据不出现。

---

## 1. `GET /api/projects`

返回全部项目，用于项目切换。

**200 响应**

```json
{ "projects": [ { "id": "proj-001", "name": "产线改造" } ] }
```

- 没有项目时：`{ "projects": [] }`
- 不返回项目内的字段与行（避免首屏请求体过大）。

---

## 2. `GET /api/projects/{project_id}/table`

返回一个项目的字段定义与全部数据行。

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | string | 项目标识 |

**200 响应**

```json
{
  "project": { "id": "proj-001", "name": "产线改造" },
  "fields": [
    { "id": "f-1", "name": "任务", "type": "text", "options": null, "order": 1 },
    { "id": "f-2", "name": "状态", "type": "enum", "options": [ { "value": "todo", "label": "待办" } ], "order": 2 }
  ],
  "rows": [
    { "id": "r-1", "values": { "f-1": "采购电机", "f-2": "todo" } }
  ]
}
```

**字段说明**

| 字段 | 说明 |
|---|---|
| `project` | 项目标识与名称 |
| `fields[].id` | 字段标识，也是 `rows[].values` 的键 |
| `fields[].type` | `text` / `number` / `datetime` / `enum`；未识别类型原样返回，前端回退纯文本 |
| `fields[].options` | `type = enum` 时的取值表，否则为 `null` |
| `fields[].order` | 显示顺序（已升序） |
| `rows[].values` | 键为字段 id；值缺失表示该行该列为空 |

**错误响应**

| 状态码 | 场景 | 响应体 |
|---|---|---|
| 404 | `project_id` 不存在 | `{ "detail": "项目不存在" }` |
| 503 | 数据存储打不开或查询失败 | `{ "detail": "数据存储不可用" }` |

空项目不是错误：返回 `"rows": []`，`fields` 照常返回。

---

## 3. `GET /api/health`

用于启动探活与 quickstart 检查，不涉及业务数据。

**200 响应**

```json
{ "status": "ok" }
```

数据存储不可用时返回 `503`，响应体同 §2。

---

## 4. 明确不存在的东西

- 任何 `POST` / `PUT` / `PATCH` / `DELETE` 路由
- 写接口的空实现、开关或占位路由（宪法原则 VII）
- 分页、筛选、排序参数（属非目标）
- 认证与鉴权头（v0 局域网内无登录）
