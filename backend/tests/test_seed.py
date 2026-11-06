"""样例脚本测试：计数、未知键拒绝、关联校验、幂等、WAL。"""

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
                "tables": [
                    {
                        "id": "t-staff",
                        "name": "人员",
                        "order": 1,
                        "fields": [
                            {"id": "s1", "name": "姓名", "type": "text", "options": None, "order": 1, "visible": 1},
                        ],
                        "rows": [{"id": "sr1", "values": {"s1": "张工"}}],
                    },
                    {
                        "id": "t-task",
                        "name": "任务",
                        "order": 2,
                        "fields": [
                            {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                            {"id": "f2", "name": "负责人", "type": "relation",
                             "options": {"table_id": "t-staff"}, "order": 2, "visible": 1},
                        ],
                        "rows": [{"id": "r1", "values": {"f1": "甲", "f2": ["sr1"]}}],
                    },
                ],
            }
        ]
    }


def test_seed_counts(tmp_path):
    db = tmp_path / "t.db"
    counts = write_seed(db, _seed_data())
    assert counts == {"projects": 1, "tables": 2, "fields": 3, "rows": 2}


def test_unknown_key_rejected(tmp_path):
    db = tmp_path / "t.db"
    write_seed(db, _seed_data())
    bad = _seed_data()
    bad["projects"][0]["tables"][1]["rows"][0]["values"]["nope"] = "x"
    with pytest.raises(SeedError):
        write_seed(db, bad)
    conn = connect_readonly(db)
    try:
        assert conn.execute("SELECT count(*) FROM row_records").fetchone()[0] == 2
    finally:
        conn.close()


def test_relation_target_must_be_same_project(tmp_path):
    data = _seed_data()
    data["projects"][0]["tables"][1]["fields"][1]["options"] = {"table_id": "missing"}
    with pytest.raises(SeedError):
        write_seed(tmp_path / "t.db", data)


def test_relation_value_must_be_array(tmp_path):
    data = _seed_data()
    data["projects"][0]["tables"][1]["rows"][0]["values"]["f2"] = "sr1"
    with pytest.raises(SeedError):
        write_seed(tmp_path / "t.db", data)


def test_rerun_replaces(tmp_path):
    db = tmp_path / "t.db"
    write_seed(db, _seed_data())
    counts = write_seed(db, _seed_data())
    assert counts == {"projects": 1, "tables": 2, "fields": 3, "rows": 2}
    conn = connect_readonly(db)
    try:
        assert conn.execute("SELECT count(*) FROM tables").fetchone()[0] == 2
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
    counts = write_seed(db, build_generated(2, 3, 5))
    assert counts == {"projects": 2, "tables": 6, "fields": 24, "rows": 30}
