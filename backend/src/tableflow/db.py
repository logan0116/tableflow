"""SQLite 连接与表结构。

只读连接优先用 URI `mode=ro`；WAL 模式下若 `-shm` 不存在导致只读打开失败，
退化为普通打开 + `PRAGMA query_only=ON`（SQLite 层面拒绝一切写语句）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fields (
    id       TEXT PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES projects(id),
    name     TEXT NOT NULL,
    type     TEXT NOT NULL,
    options  TEXT,
    "order"  INTEGER NOT NULL,
    visible  INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1))
);

CREATE TABLE IF NOT EXISTS row_records (
    id       TEXT PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES projects(id),
    data     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fields_table ON fields (table_id, "order");
CREATE INDEX IF NOT EXISTS idx_row_records_table ON row_records (table_id, id);
"""


def connect_write(path: Path) -> sqlite3.Connection:
    """写连接：建库、WAL、外键。仅导入脚本使用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect_readonly(path: Path) -> sqlite3.Connection:
    """只读连接：服务端唯一使用的连接方式。"""
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在：{path}")

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("SELECT count(*) FROM projects").fetchone()
    except sqlite3.OperationalError:
        # WAL 模式下 -shm 不存在时 mode=ro 打不开；退化为 query_only。
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if str(mode).lower() != "wal":
        conn.close()
        raise RuntimeError(f"数据库未启用 WAL（journal_mode={mode}）")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
