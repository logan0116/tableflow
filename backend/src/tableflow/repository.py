"""只读查询：项目、表格、字段、数据行。"""

from __future__ import annotations

import json
import sqlite3

from .schemas import (
    FieldOut,
    ProjectOut,
    RowDetailOut,
    RowOut,
    TableOut,
    TableSummaryOut,
)


def list_projects(conn: sqlite3.Connection) -> list[ProjectOut]:
    rows = conn.execute("SELECT id, name FROM projects ORDER BY id").fetchall()
    return [ProjectOut(id=r["id"], name=r["name"]) for r in rows]


def list_tables(conn: sqlite3.Connection, project_id: str) -> list[TableSummaryOut] | None:
    project = conn.execute(
        "SELECT id, name FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if project is None:
        return None
    rows = conn.execute(
        'SELECT id, name, "order" FROM tables WHERE project_id = ? ORDER BY "order" ASC, id ASC',
        (project_id,),
    ).fetchall()
    return [TableSummaryOut(id=r["id"], name=r["name"], order=r["order"]) for r in rows]


def _visible_fields(conn: sqlite3.Connection, table_id: str) -> list[FieldOut]:
    rows = conn.execute(
        """
        SELECT id, name, type, options, "order"
        FROM fields
        WHERE table_id = ? AND visible = 1
        ORDER BY "order" ASC, id ASC
        """,
        (table_id,),
    ).fetchall()
    return [
        FieldOut(
            id=r["id"],
            name=r["name"],
            type=r["type"],
            options=json.loads(r["options"]) if r["options"] else None,
            order=r["order"],
        )
        for r in rows
    ]


def get_table(conn: sqlite3.Connection, table_id: str) -> TableOut | None:
    row = conn.execute(
        """
        SELECT t.id, t.name, t."order" AS order_, t.project_id, p.name AS project_name
        FROM tables t JOIN projects p ON p.id = t.project_id
        WHERE t.id = ?
        """,
        (table_id,),
    ).fetchone()
    if row is None:
        return None

    fields = _visible_fields(conn, table_id)
    visible_ids = {field.id for field in fields}

    rows = conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id ASC",
        (table_id,),
    ).fetchall()

    return TableOut(
        project=ProjectOut(id=row["project_id"], name=row["project_name"]),
        table=TableSummaryOut(id=row["id"], name=row["name"], order=row["order_"]),
        fields=fields,
        rows=[
            RowOut(
                id=r["id"],
                values={k: v for k, v in json.loads(r["data"]).items() if k in visible_ids},
            )
            for r in rows
        ],
    )


def get_row_detail(
    conn: sqlite3.Connection, table_id: str, row_id: str
) -> RowDetailOut | None:
    table = conn.execute(
        'SELECT id, name, "order" FROM tables WHERE id = ?', (table_id,)
    ).fetchone()
    if table is None:
        return None

    row = conn.execute(
        "SELECT id, data FROM row_records WHERE id = ? AND table_id = ?",
        (row_id, table_id),
    ).fetchone()
    if row is None:
        return None

    fields = _visible_fields(conn, table_id)
    visible_ids = {field.id for field in fields}
    values = {k: v for k, v in json.loads(row["data"]).items() if k in visible_ids}

    return RowDetailOut(
        table=TableSummaryOut(id=table["id"], name=table["name"], order=table["order"]),
        fields=fields,
        row=RowOut(id=row["id"], values=values),
    )
