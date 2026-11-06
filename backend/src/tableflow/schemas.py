"""接口响应模型（与 contracts/api.md 对齐）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProjectOut(BaseModel):
    id: str
    name: str


class FieldOut(BaseModel):
    id: str
    name: str
    type: str
    options: list[dict[str, Any]] | None = None
    order: int


class RowOut(BaseModel):
    id: str
    values: dict[str, Any]


class ProjectsOut(BaseModel):
    projects: list[ProjectOut]


class TableOut(BaseModel):
    project: ProjectOut
    fields: list[FieldOut]
    rows: list[RowOut]
