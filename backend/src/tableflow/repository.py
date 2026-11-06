"""只读查询：项目、表格、字段、数据行、业务变更记录。

读侧只做 JSON 解析与透传，不做字段校验、不做格式化计算；
坏 options / 历史非法值一律降级，不阻断整表读取。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .schemas import (
    BusinessChangeOut,
    ComputedMetaOut,
    FieldOut,
    ProjectOut,
    RowDetailOut,
    RowOut,
    TableOut,
    TableSummaryOut,
)


def _parse_options(raw: Any) -> Any:
    """容错解析 fields.options：坏 JSON 回退 None，不抛异常。"""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _decode_value(raw: Any) -> Any:
    """容错解析业务变更记录的旧值/新值（JSON 编码；坏值原样返回）。"""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


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
            options=_parse_options(r["options"]),
            order=r["order"],
        )
        for r in rows
    ]


def _computed_rows(
    conn: sqlite3.Connection, table_id: str, field_ids: list[str]
) -> dict[tuple[str, str], sqlite3.Row]:
    """读取已落库的计算值；读侧只读，不做任何计算。"""
    if not field_ids:
        return {}
    placeholders = ",".join("?" for _ in field_ids)
    rows = conn.execute(
        "SELECT row_id, field_id, value, override_value, computed_at, override_reason"
        f" FROM computed_values WHERE table_id = ? AND field_id IN ({placeholders})",
        (table_id, *field_ids),
    ).fetchall()
    return {(row["row_id"], row["field_id"]): row for row in rows}


def _merge_computed(
    row_id: str,
    values: dict[str, Any],
    computed_fields: list[FieldOut],
    computed_rows: dict[tuple[str, str], sqlite3.Row],
) -> tuple[dict[str, Any], dict[str, ComputedMetaOut] | None]:
    """把计算字段的有效值（override 优先）合并进行值，并生成 computed_meta。"""
    if not computed_fields:
        return values, None
    meta: dict[str, ComputedMetaOut] = {}
    for field in computed_fields:
        stored = computed_rows.get((row_id, field.id))
        if stored is None:
            values[field.id] = None
            continue
        raw = stored["override_value"] if stored["override_value"] is not None else stored["value"]
        values[field.id] = _decode_value(raw)
        meta[field.id] = ComputedMetaOut(
            computed_at=stored["computed_at"],
            overridden=stored["override_value"] is not None,
            override_reason=stored["override_reason"],
        )
    return values, (meta or None)


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
    computed_fields = [field for field in fields if field.type == "computed"]
    computed_rows = _computed_rows(conn, table_id, [field.id for field in computed_fields])

    rows = conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id ASC",
        (table_id,),
    ).fetchall()

    output_rows = []
    for r in rows:
        values = {
            k: v
            for k, v in (json.loads(r["data"]) if r["data"] else {}).items()
            if k in visible_ids
        }
        values, meta = _merge_computed(r["id"], values, computed_fields, computed_rows)
        output_rows.append(RowOut(id=r["id"], values=values, computed_meta=meta))

    return TableOut(
        project=ProjectOut(id=row["project_id"], name=row["project_name"]),
        table=TableSummaryOut(id=row["id"], name=row["name"], order=row["order_"]),
        fields=fields,
        rows=output_rows,
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
    values = {
        k: v
        for k, v in (json.loads(row["data"]) if row["data"] else {}).items()
        if k in visible_ids
    }
    computed_fields = [field for field in fields if field.type == "computed"]
    computed_rows = _computed_rows(conn, table_id, [field.id for field in computed_fields])
    values, meta = _merge_computed(row["id"], values, computed_fields, computed_rows)

    return RowDetailOut(
        table=TableSummaryOut(id=table["id"], name=table["name"], order=table["order"]),
        fields=fields,
        row=RowOut(id=row["id"], values=values, computed_meta=meta),
    )


def list_changes(
    conn: sqlite3.Connection, table_id: str, row_id: str, limit: int = 50
) -> list[BusinessChangeOut] | None:
    """按 id 倒序返回一行的业务变更记录；行不存在返回 None。"""
    exists = conn.execute(
        "SELECT 1 FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id)
    ).fetchone()
    if exists is None:
        return None
    rows = conn.execute(
        """
        SELECT id, occurred_at, actor, origin, field_id, field_name,
               old_value, new_value, change_kind, reason
        FROM business_changes
        WHERE table_id = ? AND row_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (table_id, row_id, int(limit)),
    ).fetchall()
    return [
        BusinessChangeOut(
            id=r["id"],
            occurred_at=r["occurred_at"],
            actor=r["actor"],
            origin=r["origin"],
            field_id=r["field_id"],
            field_name=r["field_name"],
            old_value=_decode_value(r["old_value"]),
            new_value=_decode_value(r["new_value"]),
            change_kind=r["change_kind"],
            reason=r["reason"],
        )
        for r in rows
    ]
