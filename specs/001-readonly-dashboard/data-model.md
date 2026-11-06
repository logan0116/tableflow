# 数据模型

**Feature**: 001-readonly-dashboard | **Constitution**: v5.0.0（原则 I 规定数据模型为项目 → 表格 → 字段/行）

五张表：项目、表格、字段、数据行、写入审计。前四张由读接口查询，全部由 Agent 写接口或样例脚本写入。

## 1. `projects` — 项目

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 项目标识 |
| `name` | TEXT | NOT NULL | 项目显示名 |

## 2. `tables` — 表格

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 表格标识 |
| `project_id` | TEXT | NOT NULL, REFERENCES `projects(id)` | 所属项目 |
| `name` | TEXT | NOT NULL | 表格显示名 |
| `order` | INTEGER | NOT NULL DEFAULT 0 | 同项目内的显示顺序 |

索引：`idx_tables_project (project_id, "order")`。

## 3. `fields` — 字段定义（列）

列名与宪法原则 III 一致。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 字段标识；`row_records.data` 的键 |
| `table_id` | TEXT | NOT NULL, REFERENCES `tables(id)` | 所属表格 |
| `name` | TEXT | NOT NULL | 列标题 |
| `type` | TEXT | NOT NULL | 取值见 §5；不加 CHECK，未知类型前端回退纯文本 |
| `options` | TEXT | NULL | JSON；`enum` 存取值表，`relation` 存目标表 |
| `order` | INTEGER | NOT NULL | 显示顺序，升序 |
| `visible` | INTEGER | NOT NULL DEFAULT 1, CHECK(`visible` IN (0,1)) | 0 = 不显示（数据保留） |

索引：`idx_fields_table (table_id, "order")`。

`options` 的两种形态：

```json
[{ "value": "todo", "label": "待办" }]
```

```json
{ "table_id": "t-staff" }
```

（第一段为 `enum` 的取值表；第二段为 `relation` 的目标表，必须与当前表同属一个项目。）

## 4. `row_records` — 数据行

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 行标识 |
| `table_id` | TEXT | NOT NULL, REFERENCES `tables(id)` | 所属表格 |
| `data` | TEXT | NOT NULL | JSON 对象，键 = `fields.id`，值 = 该行在该列的值 |

索引：`idx_row_records_table (table_id, id)`。

`data` 示例：

```json
{ "f-1": "采购电机", "f-2": "doing", "f-3": "2026-11-05T09:30:00+08:00", "f-4": ["r-101"] }
```

## 5. 类型与渲染映射

| `type` | JSON 值形态 | 前端渲染 | 值缺失或非法 |
|---|---|---|---|
| `text` | string | 原样 | 空单元格 |
| `number` | number | 按原值 | 空单元格 |
| `datetime` | ISO 8601 字符串 | 本地时区；含时间 `YYYY-MM-DD HH:mm`，不含时间 `YYYY-MM-DD` | 原样文本 |
| `enum` | string | 查 `options` 得 label；查不到显示原值 | 原值 |
| `relation` | string[]（目标行 id） | 逐个显示目标行 id，顿号分隔；点击打开只读明细 | 目标行不存在时该标签显示"关联已失效" |
| 其他 | 任意 | 按 `text` 渲染 | 空单元格 |

关联标签统一用目标行 id（用户 2026-11-06 决定），不取目标表字段值。

## 6. `write_audit` — 写入审计

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增 |
| `agent_id` | TEXT | NOT NULL | 请求头 `X-Agent-Id` |
| `action` | TEXT | NOT NULL | 如 `table.create` / `field.update` / `row.delete` |
| `target` | TEXT | NOT NULL | 目标标识（表 id / 字段 id / 行 id） |
| `payload` | TEXT | NULL | 请求体 JSON（截断到 4KB） |
| `result` | TEXT | NOT NULL | `success` / `failed` / `unknown` |
| `error` | TEXT | NULL | 失败原因 |
| `created_at` | TEXT | NOT NULL | ISO 8601 带时区 |

只增不改。每次写接口调用（成功或失败）都必须写一条。

## 7. 不变量

1. `fields.table_id`、`row_records.table_id` MUST 指向已存在的表格。
2. `relation` 字段的 `options.table_id` MUST 指向同一项目内的另一张表格（允许自关联）。
3. `relation` 值 MUST 是字符串数组；读取时逐个解析，目标行缺失按"关联已失效"显示，不报错。
4. `enum` 值不在 options 内时显示原值，不报错。
5. `visible = 0` 的字段：读接口不返回该字段，且行的值中也不返回对应键。
6. 删除表格：级联删除其 `fields` 与 `row_records`；删除字段：删除 `fields` 行，`data` 中的键成为孤儿键、读取时忽略；删除行：不级联，引用方显示"关联已失效"。
7. 样例脚本为全量替换（清空业务四张表，审计表保留）。
8. 排序：`tables` 按 `order` 升序（`id` 兜底）；`fields` 按 `order` 升序（`id` 兜底）；`rows` 按 `id` 升序。

## 8. 关系

```text
projects 1 ── N tables
tables   1 ── N fields
tables   1 ── N row_records
fields.id ──(JSON 键)── row_records.data
fields(relation).options.table_id ──> tables.id
row_records.data[relation] ──> 目标表的 row_records.id
write_audit 独立，只记录写入
```

字段与行之间没有外键（JSON 内嵌），关系由写接口与样例脚本校验保证。

## 9. 样例数据格式

```json
{
  "projects": [
    {
      "id": "proj-001",
      "name": "产线改造",
      "tables": [
        {
          "id": "t-task",
          "name": "任务",
          "order": 1,
          "fields": [
            { "id": "f-1", "name": "任务", "type": "text", "options": null, "order": 1, "visible": 1 },
            { "id": "f-2", "name": "负责人", "type": "relation", "options": { "table_id": "t-staff" }, "order": 2, "visible": 1 }
          ],
          "rows": [
            { "id": "r-1", "values": { "f-1": "采购电机", "f-2": ["s-1"] } }
          ]
        }
      ]
    }
  ]
}
```
