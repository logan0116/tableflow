"""board@4 模板脚本：产物必须与六表契约一致，且能真的建库。

原来 data/template_board5.py 还是 board@2（开发进度/未清Bug数/需求关联（独立）），
从它起新项目就会造出旧口径的表——一致性门禁把模板产物也纳入校验后，这里固化断言。
board@4（019）起模板升级为六表：ver 26 字段、case 8、run 9（kind=detail），
闸门只剩「六节点是否全部完成」「发布条件」，展示布尔不再打 gate。
"""

from __future__ import annotations

import importlib.util
import json
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
    return _load(ROOT / "data/template_board5.py", "template_board5_under_test")


@pytest.fixture(scope="module")
def gate():
    return _load(ROOT / "backend/scripts/check_board.py", "check_board_under_test")


def _template_tables(template, table_prefix: str = "tf", field_prefix: str = "tf") -> list[dict]:
    tables = []
    for table in template.build_tables(table_prefix, field_prefix):
        tables.append(
            {
                "id": table["id"],
                "name": table["name"],
                "order": table["order"],
                "kind": table.get("kind", "board"),
                "fields": [
                    {"id": fid, "name": name, "type": ftype, "options": options}
                    for fid, name, ftype, options in table["fields"]
                ],
            }
        )
    return tables


def test_template_matches_board4(template, gate):
    contract = gate.load_contract(ROOT / "specs/019-test-contract/board@4.yaml")
    assert gate.check_tables("template", _template_tables(template), contract) == []


def test_template_seeds_a_working_board(template, tmp_path):
    """模板产物能真的建库：六表、字段数、kind、闸门标记都按 board@4。"""
    tables = []
    for table in template.build_tables("t", "t"):
        fields = [
            {"id": fid, "name": name, "type": ftype, "options": options, "order": i + 1, "visible": 1}
            for i, (fid, name, ftype, options) in enumerate(table["fields"])
        ]
        tables.append(
            {
                "id": table["id"],
                "name": table["name"],
                "order": table["order"],
                "kind": table.get("kind", "board"),
                "fields": fields,
                "rows": [],
            }
        )
    db = tmp_path / "template.db"
    write_seed(db, {"projects": [{"id": "p", "name": "模板项目", "tables": tables}]})

    conn = sqlite3.connect(db)
    try:
        ids = {row[0] for row in conn.execute("SELECT id FROM tables")}
        assert ids == {"t-ver", "t-indep", "t-dep", "t-case", "t-run", "t-bug"}
        assert not any(table_id.endswith("-plan") for table_id in ids)
        kinds = {row[0]: row[1] for row in conn.execute("SELECT id, kind FROM tables")}
        assert kinds["t-run"] == "detail"
        assert all(kinds[table_id] == "board" for table_id in ids - {"t-run"})
        fields = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT id, name, type FROM fields")}
        assert len([f for f in fields if f.startswith("t-v-")]) == 26
        assert len([f for f in fields if f.startswith("t-i-")]) == 16
        assert len([f for f in fields if f.startswith("t-d-")]) == 9
        assert len([f for f in fields if f.startswith("t-c-")]) == 8
        assert len([f for f in fields if f.startswith("t-r-")]) == 9
        assert len([f for f in fields if f.startswith("t-b-")]) == 11
        assert fields["t-v-cond"] == ("发布条件", "computed")
        assert fields["t-v-stage-done"] == ("六节点是否全部完成", "computed")
        # 旧 board@2 字段不得复活
        for gone in ("t-v-dev", "t-v-test", "t-v-bug-open", "t-v-doc", "t-i-status", "t-i-priority"):
            assert gone not in fields
    finally:
        conn.close()

    # 闸门只剩两个；三个展示布尔不再打 gate。
    gate_rows = {
        row["name"]: json.loads(row["options"])
        for row in _dict_rows(db, "SELECT name, options FROM fields WHERE table_id = 't-ver'")
        if row["options"]
    }
    gated = {name for name, options in gate_rows.items() if options.get("gate")}
    assert gated == {"六节点是否全部完成", "发布条件"}
    assert gate_rows["六节点是否全部完成"]["conditions"]
    assert gate_rows["六节点是否全部完成"]["conditions"][0]["equals"] == "done"
    assert gate_rows["发布条件"]["conditions"][0]["equals"] is True


def _dict_rows(db: Path, sql: str):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql)]
    finally:
        conn.close()
