"""Agent 写服务：表 / 字段 / 行的 CRUD + 审计 + 三态。

每次写入（成功、失败、未知）都在同一或后续事务里落一条 `write_audit`。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

TZ = timezone(timedelta(hours=8))
FIELD_TYPES = {"text", "number", "datetime", "enum", "relation"}


class WriteError(Exception):
    """业务校验或数据库错误；`unknown=True` 表示提交结果未知。"""

    def __init__(self, message: str, *, unknown: bool = False) -> None:
        super().__init__(message)
        self.unknown = unknown


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _audit_row(
    conn: sqlite3.Connection,
    agent_id: str,
    action: str,
    target: str,
    payload: str | None,
    result: str,
    error: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO write_audit (agent_id, action, target, payload, result, error, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (agent_id, action, target, payload[:4000] if payload else None, result, error, _now()),
    )


def run_write(
    conn: sqlite3.Connection,
    *,
    agent_id: str,
    action: str,
    target: str,
    payload: str | None,
    operation: Callable[[], Any],
) -> Any:
    """执行一次写入并保证留下审计记录。"""
    if not agent_id:
        _audit_row(conn, "-", action, target, payload, "failed", "缺少 X-Agent-Id")
        conn.commit()
        raise WriteError("缺少 X-Agent-Id")

    try:
        result = operation()
        _audit_row(conn, agent_id, action, target, payload, "success")
        conn.commit()
        return result
    except WriteError as exc:
        conn.rollback()
        _audit_row(conn, agent_id, action, target, payload, "failed", str(exc))
        conn.commit()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        _audit_row(conn, agent_id, action, target, payload, "failed", f"数据库错误：{exc}")
        conn.commit()
        raise WriteError(f"数据库错误：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 - 兜底，保证审计
        conn.rollback()
        _audit_row(conn, agent_id, action, target, payload, "failed", f"未预期错误：{exc}")
        conn.commit()
        raise WriteError(f"未预期错误：{exc}") from exc


def _payload_text(body: dict[str, Any] | None) -> str | None:
    return json.dumps(body, ensure_ascii=False) if body is not None else None


def _require_name(body: dict[str, Any]) -> str:
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WriteError("name 必须是非空字符串")
    return name.strip()


def _next_order(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) + 1


# ---------- 项目 ----------

def create_project(conn: sqlite3.Connection, body: dict[str, Any]) -> str:
    name = _require_name(body)
    project_id = body.get("id") or f"p-{uuid.uuid4().hex[:8]}"
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise WriteError(f"项目 id 已存在：{project_id}")
    conn.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (project_id, name))
    return project_id


# ---------- 表格 ----------

def create_table(conn: sqlite3.Connection, project_id: str, body: dict[str, Any]) -> str:
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        raise WriteError("项目不存在")
    name = _require_name(body)
    table_id = body.get("id") or f"t-{uuid.uuid4().hex[:8]}"
    order = body.get("order")
    if order is None:
        order = _next_order(
            conn, 'SELECT max("order") FROM tables WHERE project_id = ?', (project_id,)
        )
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone():
        raise WriteError(f"表格 id 已存在：{table_id}")
    conn.execute(
        'INSERT INTO tables (id, project_id, name, "order") VALUES (?, ?, ?, ?)',
        (table_id, project_id, name, int(order)),
    )
    return table_id


def update_table(conn: sqlite3.Connection, table_id: str, body: dict[str, Any]) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    if "name" in body:
        conn.execute("UPDATE tables SET name = ? WHERE id = ?", (_require_name(body), table_id))
    if "order" in body:
        conn.execute('UPDATE tables SET "order" = ? WHERE id = ?', (int(body["order"]), table_id))
    return table_id


def delete_table(conn: sqlite3.Connection, table_id: str) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    conn.execute("DELETE FROM row_records WHERE table_id = ?", (table_id,))
    conn.execute("DELETE FROM fields WHERE table_id = ?", (table_id,))
    conn.execute("DELETE FROM tables WHERE id = ?", (table_id,))
    return table_id


# ---------- 字段 ----------

def _validate_options(
    conn: sqlite3.Connection, table_id: str, field_type: str, options: Any
) -> Any:
    if field_type == "enum":
        if options is None:
            return None
        if not isinstance(options, list):
            raise WriteError("enum 的 options 必须是数组")
        for option in options:
            if not isinstance(option, dict) or "value" not in option or "label" not in option:
                raise WriteError("enum 的 options 项必须含 value 与 label")
        return options
    if field_type == "relation":
        if not isinstance(options, dict) or not isinstance(options.get("table_id"), str):
            raise WriteError("relation 的 options 必须形如 {\"table_id\": \"...\"}")
        target = options["table_id"]
        row = conn.execute(
            "SELECT project_id FROM tables WHERE id = ?", (target,)
        ).fetchone()
        if row is None:
            raise WriteError(f"relation 的目标表不存在：{target}")
        current = conn.execute(
            "SELECT project_id FROM tables WHERE id = ?", (table_id,)
        ).fetchone()
        if current is None or row["project_id"] != current["project_id"]:
            raise WriteError("relation 的目标表必须与当前表同属一个项目")
        return options
    return None


def create_field(conn: sqlite3.Connection, table_id: str, body: dict[str, Any]) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    name = _require_name(body)
    field_type = body.get("type")
    if field_type not in FIELD_TYPES:
        raise WriteError(f"type 必须是 {sorted(FIELD_TYPES)} 之一")
    options = _validate_options(conn, table_id, field_type, body.get("options"))
    field_id = body.get("id") or f"f-{uuid.uuid4().hex[:8]}"
    order = body.get("order")
    if order is None:
        order = _next_order(
            conn, 'SELECT max("order") FROM fields WHERE table_id = ?', (table_id,)
        )
    visible = int(body.get("visible", 1))
    if visible not in (0, 1):
        raise WriteError("visible 只能是 0 或 1")
    if conn.execute("SELECT 1 FROM fields WHERE id = ?", (field_id,)).fetchone():
        raise WriteError(f"字段 id 已存在：{field_id}")
    conn.execute(
        'INSERT INTO fields (id, table_id, name, type, options, "order", visible)'
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            field_id,
            table_id,
            name,
            field_type,
            json.dumps(options, ensure_ascii=False) if options is not None else None,
            int(order),
            visible,
        ),
    )
    return field_id


def update_field(conn: sqlite3.Connection, field_id: str, body: dict[str, Any]) -> str:
    field = conn.execute(
        "SELECT table_id, type, options FROM fields WHERE id = ?", (field_id,)
    ).fetchone()
    if field is None:
        raise WriteError("字段不存在")

    field_type = body.get("type", field["type"])
    if field_type not in FIELD_TYPES:
        raise WriteError(f"type 必须是 {sorted(FIELD_TYPES)} 之一")
    options = body["options"] if "options" in body else (
        json.loads(field["options"]) if field["options"] else None
    )
    options = _validate_options(conn, field["table_id"], field_type, options)

    if "name" in body:
        conn.execute("UPDATE fields SET name = ? WHERE id = ?", (_require_name(body), field_id))
    conn.execute(
        'UPDATE fields SET type = ?, options = ? WHERE id = ?',
        (
            field_type,
            json.dumps(options, ensure_ascii=False) if options is not None else None,
            field_id,
        ),
    )
    if "order" in body:
        conn.execute('UPDATE fields SET "order" = ? WHERE id = ?', (int(body["order"]), field_id))
    if "visible" in body:
        visible = int(body["visible"])
        if visible not in (0, 1):
            raise WriteError("visible 只能是 0 或 1")
        conn.execute("UPDATE fields SET visible = ? WHERE id = ?", (visible, field_id))
    return field_id


def delete_field(conn: sqlite3.Connection, field_id: str) -> str:
    if conn.execute("SELECT 1 FROM fields WHERE id = ?", (field_id,)).fetchone() is None:
        raise WriteError("字段不存在")
    conn.execute("DELETE FROM fields WHERE id = ?", (field_id,))
    return field_id


# ---------- 数据行 ----------

def _relation_field_ids(conn: sqlite3.Connection, table_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT id FROM fields WHERE table_id = ? AND type = 'relation'", (table_id,)
    ).fetchall()
    return {r["id"] for r in rows}


def _validate_values(conn: sqlite3.Connection, table_id: str, values: dict[str, Any]) -> None:
    known = {
        r["id"]
        for r in conn.execute("SELECT id FROM fields WHERE table_id = ?", (table_id,)).fetchall()
    }
    unknown = set(values) - known
    if unknown:
        raise WriteError(f"未知字段键：{sorted(unknown)}")
    relation_ids = _relation_field_ids(conn, table_id)
    for key in relation_ids & set(values):
        value = values[key]
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise WriteError(f"relation 字段 {key} 的值必须是字符串数组")


def create_row(conn: sqlite3.Connection, table_id: str, body: dict[str, Any]) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    values = body.get("values") or {}
    if not isinstance(values, dict):
        raise WriteError("values 必须是对象")
    _validate_values(conn, table_id, values)
    row_id = body.get("id") or f"r-{uuid.uuid4().hex[:8]}"
    if conn.execute("SELECT 1 FROM row_records WHERE id = ?", (row_id,)).fetchone():
        raise WriteError(f"行 id 已存在：{row_id}")
    conn.execute(
        "INSERT INTO row_records (id, table_id, data) VALUES (?, ?, ?)",
        (row_id, table_id, json.dumps(values, ensure_ascii=False)),
    )
    return row_id


def update_row(conn: sqlite3.Connection, row_id: str, body: dict[str, Any]) -> str:
    row = conn.execute(
        "SELECT table_id, data FROM row_records WHERE id = ?", (row_id,)
    ).fetchone()
    if row is None:
        raise WriteError("行不存在")
    values = body.get("values")
    if not isinstance(values, dict):
        raise WriteError("values 必须是对象")
    _validate_values(conn, row["table_id"], values)
    merged = {**json.loads(row["data"]), **values}
    conn.execute(
        "UPDATE row_records SET data = ? WHERE id = ?",
        (json.dumps(merged, ensure_ascii=False), row_id),
    )
    return row_id


def delete_row(conn: sqlite3.Connection, row_id: str) -> str:
    if conn.execute("SELECT 1 FROM row_records WHERE id = ?", (row_id,)).fetchone() is None:
        raise WriteError("行不存在")
    conn.execute("DELETE FROM row_records WHERE id = ?", (row_id,))
    return row_id
