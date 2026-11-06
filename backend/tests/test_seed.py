"""样例脚本测试：计数、未知键拒绝、幂等、WAL。"""

from __future__ import annotations

import sqlite3

import pytest

from tableflow.db import connect_readonly
from tableflow.seed import SeedError, build_generated, write_seed


def _seed_data():
    return {
        "projects": [
            {
                "id": "p1",
                "name": "项目一",
                "fields": [
                    {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                    {"id": "f2", "name": "状态", "type": "enum",
                     "options": [{"value": "todo", "label": "待办"}], "order": 2, "visible": 1},
                ],
                "rows": [
                    {"id": "r1", "values": {"f1": "甲", "f2": "todo"}},
                    {"id": "r2", "values": {"f1": "乙"}},
                ],
            }
        ]
    }


def test_seed_counts(tmp_path):
    db = tmp_path / "t.db"
    counts = write_seed(db, _seed_data())
    assert counts == {"projects": 1, "fields": 2, "rows": 2}


def test_unknown_key_rejected_and_db_untouched(tmp_path):
    db = tmp_path / "t.db"
    write_seed(db, _seed_data())

    bad = _seed_data()
    bad["projects"][0]["rows"][0]["values"]["nope"] = "x"
    with pytest.raises(SeedError):
        write_seed(db, bad)

    conn = connect_readonly(db)
    try:
        assert conn.execute("SELECT count(*) FROM row_records").fetchone()[0] == 2
    finally:
        conn.close()


def test_rerun_replaces_not_appends(tmp_path):
    db = tmp_path / "t.db"
    write_seed(db, _seed_data())
    counts = write_seed(db, _seed_data())
    assert counts == {"projects": 1, "fields": 2, "rows": 2}

    conn = connect_readonly(db)
    try:
        assert conn.execute("SELECT count(*) FROM projects").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM row_records").fetchone()[0] == 2
    finally:
        conn.close()


def test_journal_mode_is_wal(tmp_path):
    db = tmp_path / "t.db"
    write_seed(db, _seed_data())
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_generated_scale(tmp_path):
    db = tmp_path / "t.db"
    counts = write_seed(db, build_generated(3, 5))
    assert counts == {"projects": 3, "fields": 12, "rows": 15}
