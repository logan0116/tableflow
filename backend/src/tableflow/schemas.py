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
    options: Any | None = None
    order: int


class RowOut(BaseModel):
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
