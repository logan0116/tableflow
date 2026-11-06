"""v0.3.0 重建脚本测试：重建可重复、数据一致、单向关联、tone、业务编号。"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

import rebuild_v030  # noqa: E402

from tableflow.app import app  # noqa: E402
from tableflow.write_service import TONES  # noqa: E402

BUSINESS_TABLES = ("projects", "tables", "fields", "row_records")


def _dump(db: Path) -> dict[str, list[tuple]]:
    conn = sqlite3.connect(db)
    try:
        result = {}
        for table in BUSINESS_TABLES:
            result[table] = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        return result
    finally:
        conn.close()


def _query(db: Path, sql: str, params=()):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


@pytest.fixture()
def rebuilt(tmp_path, monkeypatch):
    db = tmp_path / "rebuild.db"
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        counts = rebuild_v030.rebuild(db, client, backup=False)
        yield db, counts, client


def test_rebuild_row_counts(rebuilt):
    _, counts, _ = rebuilt
    assert counts["fd_system"] == {"fd-ver": 4, "fd-indep": 1, "fd-dep": 3}
    assert counts["tableflow"] == {"tf-ver": 3, "tf-indep": 4, "tf-dep": 1}


def test_rebuild_is_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "rebuild-twice.db"
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        first_counts = rebuild_v030.rebuild(db, client, backup=False)
        first_dump = _dump(db)
        second_counts = rebuild_v030.rebuild(db, client, backup=False)
        second_dump = _dump(db)
    assert first_counts == second_counts
    assert first_dump == second_dump


def test_no_reverse_relation_field(rebuilt):
    db, _, _ = rebuilt
    for table_id, field_id, version_table in (
        ("fd-dep", "d-version", "fd-ver"),
        ("tf-dep", "tf-d-version", "tf-ver"),
    ):
        assert _query(db, "SELECT 1 FROM fields WHERE id = ?", (field_id,)) == []
        field_names = [
            row["name"]
            for row in _query(db, "SELECT name FROM fields WHERE table_id = ?", (table_id,))
        ]
        assert "所属版本" not in field_names
        # 依赖变更需求表不得再有指向版本管理表的 relation
        relations = _query(
            db, "SELECT id, options FROM fields WHERE table_id = ? AND type = 'relation'", (table_id,)
        )
        for relation in relations:
            assert json.loads(relation["options"])["table_id"] != version_table


def test_all_enum_options_have_tone(rebuilt):
    db, _, _ = rebuilt
    rows = _query(db, "SELECT id, options FROM fields WHERE type = 'enum'")
    assert rows
    for row in rows:
        options = json.loads(row["options"])
        items = options["items"] if isinstance(options, dict) else options
        assert items, row["id"]
        for item in items:
            assert item["tone"] in TONES, (row["id"], item)


def test_business_number_row_ids(rebuilt):
    db, _, _ = rebuilt
    ids = {
        table_id: {row["id"] for row in _query(db, "SELECT id FROM row_records WHERE table_id = ?", (table_id,))}
        for table_id in ("fd-ver", "fd-indep", "fd-dep", "tf-ver", "tf-indep", "tf-dep")
    }
    assert "7.0.1" in ids["fd-ver"]
    assert "UD-01-BR" in ids["fd-dep"]
    assert "002-AR" in ids["tf-indep"]
    assert "v0.3.0" in ids["tf-ver"]
    assert "DEP-01-BR" in ids["tf-dep"]


def test_relation_values_point_to_existing_business_ids(rebuilt):
    db, _, _ = rebuilt
    fields = {
        row["id"]: json.loads(row["options"])
        for row in _query(db, "SELECT id, options FROM fields WHERE type = 'relation'")
    }
    rows = _query(db, "SELECT table_id, id, data FROM row_records")
    for row in rows:
        values = json.loads(row["data"])
        for field_id, target in values.items():
            if field_id not in fields:
                continue
            target_table = fields[field_id]["table_id"]
            for target_id in target or []:
                exists = _query(
                    db,
                    "SELECT 1 FROM row_records WHERE table_id = ? AND id = ?",
                    (target_table, target_id),
                )
                assert exists, f"{row['table_id']}/{row['id']} → {target_table}/{target_id} 不存在"


def test_rebuild_records_business_changes(rebuilt):
    db, _, _ = rebuilt
    changes = _query(db, "SELECT count(*) AS c FROM business_changes")[0]["c"]
    assert changes > 0
    view = _query(db, "SELECT count(*) AS c FROM row_change_log")[0]["c"]
    assert view == changes


def test_rebuild_backup_keeps_first_copy(tmp_path, monkeypatch):
    db = tmp_path / "rebuild-backup.db"
    backup = tmp_path / "rebuild-backup.db.bak-20261106"
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        rebuild_v030.rebuild(db, client, backup=False)
        rebuild_v030.rebuild(db, client, backup=True, backup_file=backup)
        first_bytes = backup.read_bytes()
        rebuild_v030.rebuild(db, client, backup=True, backup_file=backup)
    assert backup.exists()
    assert backup.read_bytes() == first_bytes
