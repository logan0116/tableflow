"""DEP-05-BR：模板脚本产物必须与 board@3 一致，且能真的建库。

原来 data/template_fd_system.py 还是 board@2（开发进度/未清Bug数/需求关联（独立）），
从它起新项目就会造出旧口径的表——一致性门禁把模板产物也纳入校验后，这里固化断言。
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from tableflow.seed import write_seed

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def template():
    return _load(ROOT / "data/template_fd_system.py", "template_fd_system_under_test")


@pytest.fixture(scope="module")
def gate():
    return _load(ROOT / "backend/scripts/check_board.py", "check_board_under_test")


def test_template_matches_board3(template, gate):
    contract = gate.load_contract(ROOT / "specs/017-bug-relation/board@3.yaml")
    tables = []
    for table in template.build_tables("tf", "tf"):
        fields = [
            {"id": fid, "name": name, "type": ftype, "options": options}
            for fid, name, ftype, options in table["fields"]
        ]
        tables.append({"id": table["id"], "name": table["name"], "fields": fields})
    assert gate.check_tables("template", tables, contract) == []


def test_template_seeds_a_working_board(template, tmp_path):
    """模板产物能真的建库，且四个表与 发布条件 都在。"""
    tables = []
    for table in template.build_tables("t", "t"):
        fields = [
            {"id": fid, "name": name, "type": ftype, "options": options, "order": i + 1, "visible": 1}
            for i, (fid, name, ftype, options) in enumerate(table["fields"])
        ]
        tables.append({"id": table["id"], "name": table["name"], "order": table["order"], "fields": fields, "rows": []})
    db = tmp_path / "template.db"
    write_seed(db, {"projects": [{"id": "p", "name": "模板项目", "tables": tables}]})

    conn = sqlite3.connect(db)
    try:
        ids = {row[0] for row in conn.execute("SELECT id FROM tables")}
        assert ids == {"t-ver", "t-indep", "t-dep", "t-bug"}
        fields = {row[0]: row[1] for row in conn.execute("SELECT id, type FROM fields")}
        # 版本表 15 字段、独立需求 16、依赖 9、缺陷 11
        assert len([f for f in fields if f.startswith("t-v-")]) == 15
        assert len([f for f in fields if f.startswith("t-i-")]) == 16
        assert len([f for f in fields if f.startswith("t-d-")]) == 9
        assert len([f for f in fields if f.startswith("t-b-")]) == 11
        assert fields["t-v-cond"] == "computed"
        # 旧 board@2 字段不得复活
        for gone in ("t-v-dev", "t-v-test", "t-v-bug-open", "t-v-doc", "t-i-status", "t-i-priority"):
            assert gone not in fields
    finally:
        conn.close()
