"""SQLite 连接与表结构。

只读连接优先用 URI `mode=ro`；WAL 模式下若 `-shm` 不存在导致只读打开失败，
退化为普通打开 + `PRAGMA query_only=ON`（SQLite 层面拒绝一切写语句）。

v0.3.0（002）表结构变化：
- `row_records` 主键改为 `(table_id, id)`：行 id 是业务编号，表内唯一、跨表可同名。
- 新增 `business_changes`：字段级业务变更记录（与 `write_audit` 技术审计分离）。
- `write_audit` 新增 `origin`：`agent` / `human-request` / `seed`。
- 兼容别名视图 `row_change_log`：暴露 agent_id/table_id/row_id/field_id/old_value/new_value/created_at。

v0.3.0（003）表结构变化：
- 新增 `computed_values`：计算字段的落库值（`override_*` 为人工覆盖），读侧只读不计算。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tables (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name       TEXT NOT NULL,
    "order"    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fields (
    id       TEXT PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES tables(id),
    name     TEXT NOT NULL,
    type     TEXT NOT NULL,
    options  TEXT,
    "order"  INTEGER NOT NULL,
    visible  INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1))
);

CREATE TABLE IF NOT EXISTS row_records (
    id       TEXT NOT NULL,
    table_id TEXT NOT NULL REFERENCES tables(id),
    data     TEXT NOT NULL,
    PRIMARY KEY (table_id, id)
);

CREATE TABLE IF NOT EXISTS write_audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   TEXT NOT NULL,
    origin     TEXT NOT NULL DEFAULT 'agent',
    action     TEXT NOT NULL,
    target     TEXT NOT NULL,
    payload    TEXT,
    result     TEXT NOT NULL,
    error      TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_changes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    actor       TEXT NOT NULL,
    origin      TEXT NOT NULL DEFAULT 'agent',
    table_id    TEXT NOT NULL,
    row_id      TEXT NOT NULL,
    field_id    TEXT NOT NULL,
    field_name  TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    change_kind TEXT NOT NULL,
    reason      TEXT
);

CREATE TABLE IF NOT EXISTS computed_values (
    table_id        TEXT NOT NULL,
    row_id          TEXT NOT NULL,
    field_id        TEXT NOT NULL,
    value           TEXT,
    computed_at     TEXT NOT NULL,
    override_value  TEXT,
    override_reason TEXT,
    override_by     TEXT,
    override_at     TEXT,
    PRIMARY KEY (table_id, row_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_tables_project ON tables (project_id, "order");
CREATE INDEX IF NOT EXISTS idx_fields_table ON fields (table_id, "order");
CREATE INDEX IF NOT EXISTS idx_row_records_table ON row_records (table_id, id);
CREATE INDEX IF NOT EXISTS idx_business_changes_row
    ON business_changes (table_id, row_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_computed_values_field ON computed_values (field_id);

CREATE VIEW IF NOT EXISTS row_change_log AS
SELECT
    id          AS id,
    actor       AS agent_id,
    table_id    AS table_id,
    row_id      AS row_id,
    field_id    AS field_id,
    old_value   AS old_value,
    new_value   AS new_value,
    occurred_at AS created_at
FROM business_changes;
"""


def connect_write(path: Path) -> sqlite3.Connection:
    """写连接：建库、WAL、外键。写接口与样例脚本使用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect_readonly(path: Path) -> sqlite3.Connection:
    """只读连接：人侧读接口唯一使用的连接方式。"""
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在：{path}")

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("SELECT count(*) FROM projects").fetchone()
    except sqlite3.OperationalError:
        # WAL 模式下 -shm 不存在时 mode=ro 打不开；退化为 query_only。
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if str(mode).lower() != "wal":
        conn.close()
        raise RuntimeError(f"数据库未启用 WAL（journal_mode={mode}）")
    return conn


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, ddl: str
) -> None:
    """给旧库补列（v0.2 → v0.3 的 write_audit.origin）。"""
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    # executescript 的 CREATE TABLE IF NOT EXISTS 不会给旧表补列，这里显式兜底。
    _ensure_column(conn, "write_audit", "origin", "origin TEXT NOT NULL DEFAULT 'agent'")
    conn.commit()
