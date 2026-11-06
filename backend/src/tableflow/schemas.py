"""接口响应模型（与 contracts/ 对齐）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProjectOut(BaseModel):
    id: str
    name: str


class ProjectsOut(BaseModel):
    projects: list[ProjectOut]


class TableSummaryOut(BaseModel):
    id: str
    name: str
    order: int


class FieldOut(BaseModel):
    id: str
    name: str
    type: str
    # 结构化 options：enum 为 [{value,label,tone,color?}]（或 {items:[...]}），
    # number 为 {decimals,percent,unit}，datetime 为 {with_time}，
    # relation 为 {table_id}，任意类型可带 {constraints}。
    options: Any | None = None
    order: int


class RowOut(BaseModel):
    # 行 id 为业务编号（如 UD-01、7.0.1），表内唯一、跨表可同名。
    id: str
    values: dict[str, Any]


class TableOut(BaseModel):
    project: ProjectOut
    table: TableSummaryOut
    fields: list[FieldOut]
    rows: list[RowOut]


class RowDetailOut(BaseModel):
    table: TableSummaryOut
    fields: list[FieldOut]
    row: RowOut


class BusinessChangeOut(BaseModel):
    id: int
    occurred_at: str
    actor: str
    origin: str
    field_id: str
    field_name: str
    old_value: Any | None = None
    new_value: Any | None = None
    change_kind: str
    reason: str | None = None


class ChangesOut(BaseModel):
    changes: list[BusinessChangeOut]
