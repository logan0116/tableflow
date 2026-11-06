"""只读查询：项目、字段、数据行。"""

from __future__ import annotations

import json
import sqlite3

from .schemas import FieldOut, ProjectOut, RowOut, TableOut


def list_projects(conn: sqlite3.Connection) -> list[ProjectOut]:
    rows = conn.execute("SELECT id, name FROM projects ORDER BY id").fetchall()
    return [ProjectOut(id=r["id"], name=r["name"]) for r in rows]


def get_table(conn: sqlite3.Connection, project_id: str) -> TableOut | None:
    project = conn.execute(
        "SELECT id, name FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if project is None:
        return None

    field_rows = conn.execute(
        """
        SELECT id, name, type, options, "order"
        FROM fields
        WHERE table_id = ? AND visible = 1
        ORDER BY "order" ASC, id ASC
        """,
        (project_id,),
    ).fetchall()

    fields = [
        FieldOut(
            id=r["id"],
            name=r["name"],
            type=r["type"],
            options=json.loads(r["options"]) if r["options"] else None,
            order=r["order"],
        )
        for r in field_rows
    ]

    row_rows = conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id ASC",
        (project_id,),
    ).fetchall()

    visible_ids = {field.id for field in fields}
    rows = [
        RowOut(
            id=r["id"],
            values={k: v for k, v in json.loads(r["data"]).items() if k in visible_ids},
        )
        for r in row_rows
    ]

    return TableOut(
        project=ProjectOut(id=project["id"], name=project["name"]),
        fields=fields,
        rows=rows,
    )
