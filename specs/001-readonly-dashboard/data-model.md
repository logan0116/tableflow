# 数据模型

**Feature**: 001-readonly-dashboard | **Constitution**: v3.0.0（原则 III 规定 `fields` 的列名）

v0 只有三张表，全部由导入脚本写入、由后端只读查询。没有状态机、没有软删除、没有审计表（审计属 v1 写侧）。

## 1. `projects` — 项目

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 稳定标识，不用名称做键 |
| `name` | TEXT | NOT NULL | 项目显示名 |

## 2. `fields` — 字段定义（列）

列名与宪法原则 III 完全一致，不额外增加列。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 字段标识；`row_records.data` 的键 |
| `table_id` | TEXT | NOT NULL, REFERENCES `projects(id)` | 所属项目 |
| `name` | TEXT | NOT NULL | 列标题（界面显示） |
| `type` | TEXT | NOT NULL | 取值见 §4；**不加 CHECK 约束**，未知类型由前端回退纯文本 |
| `options` | TEXT | NULL | 枚举类字段的取值表，JSON 字符串 |
| `order` | INTEGER | NOT NULL | 显示顺序，升序 |
| `visible` | INTEGER | NOT NULL DEFAULT 1, CHECK(`visible` IN (0,1)) | 0 = 不显示（数据保留） |

索引：`idx_fields_table (table_id, "order")`。

`options` 的 JSON 形态（仅 `type = enum` 使用）：

```json
[{ "value": "todo", "label": "待办" }, { "value": "done", "label": "已完成" }]
```

v0 只渲染 `label`，不渲染颜色；`tone` 之类字段不预埋。

## 3. `row_records` — 数据行

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | 行标识 |
| `table_id` | TEXT | NOT NULL, REFERENCES `projects(id)` | 所属项目 |
| `data` | TEXT | NOT NULL | JSON 对象，键 = `fields.id`，值 = 该行在该列的值 |

索引：`idx_row_records_table (table_id, id)`。

`data` 示例：

```json
{ "f-1": "采购电机", "f-2": 3, "f-3": "2026-11-05T09:30:00+08:00", "f-4": "todo" }
```

## 4. 类型与渲染映射

| `type` | JSON 值形态 | 前端渲染 | 值缺失或非法 |
|---|---|---|---|
| `text` | string | 原样显示 | 显示空单元格 |
| `number` | number | 按原值显示（不做千分位与单位换算） | 显示空单元格 |
| `datetime` | ISO 8601 字符串 | 浏览器本地时区；含时间显示 `YYYY-MM-DD HH:mm`，不含时间显示 `YYYY-MM-DD` | 原样显示为文本 |
| `enum` | string | 在 `options` 中查 `value` 并显示对应 `label`；查不到则显示原值 | 显示原值 |
| 其他（未识别） | 任意 | 按 `text` 渲染 | 显示空单元格 |

`type` 的枚举集合为 `text / number / datetime / enum`，记录在此文档；数据库不做约束，新增类型不必迁移。

## 5. 不变量与导入校验

1. `row_records.data` 的键 MUST 属于同一项目的 `fields.id`；出现未知键，导入脚本报错退出，不写入。
2. `fields` 与 `row_records` 的 `table_id` MUST 指向已存在的项目。
3. `visible = 0` 的字段：接口不返回该字段，`data` 中的值保留不删。
4. 删除一列 = 删除 `fields` 行；`data` 中对应键成为孤儿键，读取时忽略，不做数据迁移。
5. 导入为**全量替换**：清空三张表后写入新快照（v0 只有初始化场景，不做增量合并）。
6. 行与字段的排序：`fields` 按 `order` 升序（`id` 兜底）；`rows` 按 `id` 升序。

## 6. 关系

```text
projects 1 ── N fields
projects 1 ── N row_records
fields.id  ──(JSON 键)──  row_records.data
```

字段与行之间没有外键（JSON 内嵌），关系由导入脚本校验保证。
