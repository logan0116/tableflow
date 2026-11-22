"""T4：一致性门禁认 board@4 六表，且不放宽契约。

覆盖：
- 六表字段名/类型/顺序、表名、表级 kind、relation 显示列/状态列、闸门标记、计算规则；
- 仍四表的项目被明确报缺 case/run，不被跳过；
- 缺 run 表的副本失败并指名缺表；
- 模板产物差异 0；
- 表名 / kind / 闸门标记 / 发布条件规则漂移都能被抓出来。
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
for path in (REPO_ROOT / "data", SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import migrate_board4  # noqa: E402
import migrate_board4_gate  # noqa: E402

from tableflow import calculation  # noqa: E402
from tableflow.db import connect_write  # noqa: E402
from tableflow.seed import write_seed  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GATE = _load(SCRIPTS_DIR / "check_board.py", "check_board_board4")
CONTRACT = GATE.load_contract(REPO_ROOT / "specs/019-test-contract/board@4.yaml")


def _board3_template():
    return _load(REPO_ROOT / "backend/tests/fixtures/board3_template.py", "board3_template_t4")


def _fid(prefix: str, role: str, short: str) -> str:
    return f"{prefix}-{role}-{short}" if prefix else f"{role}-{short}"


def _seed_data(table_prefix: str = "tf", field_prefix: str = "tf") -> dict:
    def fid(role: str, short: str) -> str:
        return _fid(field_prefix, role, short)

    # board@3 输入不含六节点；T1 迁移会按发布状态初始化（released→done，其余 todo）。
    stage_values: dict = {}
    todo_stages: dict = {}
    rows = {
        f"{table_prefix}-ver": [
            {
                "id": "v0.7.0",
                "values": {
                    fid("v", "ver"): "v0.7.0",
                    fid("v", "date"): "2026-11-01",
                    fid("v", "status"): "released",
                    fid("v", "indep"): ["008-AR"],
                    fid("v", "dep"): ["D01"],
                    fid("v", "bug"): ["BUG-01"],
                    **stage_values,
                },
            },
            {
                "id": "v0.8.0",
                "values": {
                    fid("v", "ver"): "v0.8.0",
                    fid("v", "status"): "planned",
                    **todo_stages,
                },
            },
            {
                "id": "v0.6.0",
                "values": {
                    fid("v", "ver"): "v0.6.0",
                    fid("v", "status"): "dropped",
                    **todo_stages,
                },
            },
        ],
        f"{table_prefix}-indep": [
            {
                "id": "008-AR",
                "values": {
                    fid("i", "id"): "008-AR",
                    fid("i", "clause"): "看板契约",
                    fid("i", "implement"): "done",
                    fid("i", "acceptance"): "accepted",
                },
            },
        ],
        f"{table_prefix}-dep": [
            {
                "id": "D01",
                "values": {
                    fid("d", "id"): "D01",
                    fid("d", "clause"): "变更单",
                    fid("d", "indep"): ["008-AR"],
                    fid("d", "impact"): "版本表字段",
                    fid("d", "regress"): "passed",
                },
            },
        ],
        f"{table_prefix}-bug": [
            {
                "id": "BUG-01",
                "values": {
                    fid("b", "id"): "BUG-01",
                    fid("b", "title"): "已关闭缺陷",
                    fid("b", "status"): "closed",
                    fid("b", "severity"): "major",
                    fid("b", "source"): "manual",
                    fid("b", "indep"): ["008-AR"],
                },
            },
        ],
    }
    tables = []
    for table in _board3_template().build_tables(table_prefix, field_prefix):
        fields = [
            {
                "id": field_id,
                "name": name,
                "type": ftype,
                "options": options,
                "order": index + 1,
                "visible": 1,
            }
            for index, (field_id, name, ftype, options) in enumerate(table["fields"])
        ]
        tables.append(
            {
                "id": table["id"],
                "name": table["name"],
                "order": table["order"],
                "kind": table.get("kind", "board"),
                "fields": fields,
                "rows": rows.get(table["id"], []),
            }
        )
    return {"projects": [{"id": "demo", "name": "演示项目", "tables": tables}]}


def _build_board3_db(db: Path) -> None:
    write_seed(db, _seed_data())
    conn = connect_write(db)
    try:
        calculation.recompute_table(conn, "tf-ver", actor="test", origin="seed")
        conn.commit()
    finally:
        conn.close()


def _migrate_full(db: Path, tmp_path: Path) -> tuple[dict, dict]:
    board4 = migrate_board4.migrate(db, artifact=tmp_path / "board4.json", backup=False)
    gate = migrate_board4_gate.migrate(db, artifact=tmp_path / "gate.json", backup=False)
    return board4, gate


def _structure(db: Path, project_id: str = "demo") -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        tables = []
        for table in conn.execute(
            'SELECT id, name, "order", kind FROM tables WHERE project_id = ? ORDER BY "order"',
            (project_id,),
        ):
            fields = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "type": row["type"],
                    "options": json.loads(row["options"]) if row["options"] else None,
                    "order": row["order"],
                    "visible": row["visible"],
                }
                for row in conn.execute(
                    'SELECT id, name, type, options, "order", visible FROM fields'
                    ' WHERE table_id = ? ORDER BY "order", id',
                    (table["id"],),
                )
            ]
            tables.append(
                {
                    "id": table["id"],
                    "name": table["name"],
                    "kind": table["kind"],
                    "fields": fields,
                }
            )
        return tables
    finally:
        conn.close()


def _computed(db: Path, table_id: str) -> dict[tuple[str, str], object]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {
            (row["row_id"], row["field_id"]): json.loads(row["value"])
            for row in conn.execute(
                "SELECT row_id, field_id, value FROM computed_values WHERE table_id = ?",
                (table_id,),
            )
        }
    finally:
        conn.close()


def _rows(db: Path, table_id: str) -> dict[str, dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {
            row["id"]: json.loads(row["data"] or "{}")
            for row in conn.execute(
                "SELECT id, data FROM row_records WHERE table_id = ?", (table_id,)
            )
        }
    finally:
        conn.close()


def _fields(db: Path, table_id: str) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                'SELECT id, name, type, options, "order" FROM fields'
                ' WHERE table_id = ? ORDER BY "order", id',
                (table_id,),
            )
        ]
    finally:
        conn.close()


# ---------- 门禁：六表 ----------

def test_fully_migrated_project_passes_board4_gate(tmp_path: Path) -> None:
    db = tmp_path / "full.db"
    _build_board3_db(db)
    _migrate_full(db, tmp_path)
    issues = GATE.check_tables("demo", _structure(db), CONTRACT)
    assert issues == [], "\n".join(issues)


def test_template_artifact_passes_same_gate() -> None:
    issues = GATE.check_tables("template", GATE.template_tables(), CONTRACT)
    assert issues == [], "\n".join(issues)


def test_four_table_project_is_reported_not_skipped(tmp_path: Path) -> None:
    db = tmp_path / "board3.db"
    _build_board3_db(db)
    issues = GATE.check_tables("demo", _structure(db), CONTRACT)
    assert any("缺表 case" in issue for issue in issues)
    assert any("缺表 run" in issue for issue in issues)
    # 版本表仍 15 字段：必须逐字段报出，而不是只报缺表就放过。
    assert any("字段名不符" in issue for issue in issues)


def test_missing_run_table_fails_and_names_it(tmp_path: Path) -> None:
    db = tmp_path / "no-run.db"
    _build_board3_db(db)
    _migrate_full(db, tmp_path)
    tables = [table for table in _structure(db) if not table["id"].endswith("-run")]
    issues = GATE.check_tables("demo", tables, CONTRACT)
    assert any("缺表 run" in issue for issue in issues), issues


def test_check_live_does_not_skip_project_without_role_tables(monkeypatch) -> None:
    tables = {"p1": [{"id": "p1-notes", "name": "随手记", "kind": "board", "fields": [
        {"id": "n-id", "name": "编号", "type": "text", "options": None}
    ]}]}

    def fake_api_get(base: str, path: str):
        if path == "/api/projects":
            return {"projects": [{"id": "p1", "name": "P1"}]}
        if path == "/api/projects/p1/tables":
            return {"tables": [{"id": "p1-notes", "name": "随手记", "order": 1, "kind": "board"}]}
        if path == "/api/tables/p1-notes/table":
            return {"table": {"id": "p1-notes", "name": "随手记", "order": 1, "kind": "board"},
                    "fields": tables["p1"][0]["fields"]}
        raise AssertionError(path)

    monkeypatch.setattr(GATE, "api_get", fake_api_get)
    issues = GATE.check_live("http://example.invalid", CONTRACT)
    for role in ("ver", "indep", "dep", "case", "run", "bug"):
        assert any(f"缺表 {role}" in issue for issue in issues), issues


# ---------- 门禁：漂移抓取 ----------

def _mutated(tmp_path: Path, mutate) -> list[str]:
    db = tmp_path / "mutate.db"
    _build_board3_db(db)
    _migrate_full(db, tmp_path)
    tables = _structure(db)
    mutate(tables)
    return GATE.check_tables("demo", tables, CONTRACT)


def test_table_name_drift_is_caught(tmp_path: Path) -> None:
    def mutate(tables):
        for table in tables:
            if table["id"].endswith("-dep"):
                table["name"] = "依赖需求"

    issues = _mutated(tmp_path, mutate)
    assert any("表名" in issue and "依赖变更需求" in issue for issue in issues), issues


def test_table_kind_drift_is_caught(tmp_path: Path) -> None:
    def mutate(tables):
        for table in tables:
            if table["id"].endswith("-run"):
                table["kind"] = "board"

    issues = _mutated(tmp_path, mutate)
    assert any("表级 kind" in issue for issue in issues), issues


def test_gate_mark_drift_is_caught(tmp_path: Path) -> None:
    def mutate(tables):
        for table in tables:
            if not table["id"].endswith("-ver"):
                continue
            for field in table["fields"]:
                if field["name"] == "独立需求是否完成":
                    field["options"]["gate"] = True

    issues = _mutated(tmp_path, mutate)
    assert any("gate:true，契约未标闸门" in issue for issue in issues), issues


def test_gate_rule_drift_is_caught(tmp_path: Path) -> None:
    def mutate(tables):
        for table in tables:
            if not table["id"].endswith("-ver"):
                continue
            spec_done = next(f for f in table["fields"] if f["name"] == "独立需求是否完成")
            change_done = next(f for f in table["fields"] if f["name"] == "依赖需求是否完成")
            bug_clear = next(f for f in table["fields"] if f["name"] == "Bug是否清空")
            for field in table["fields"]:
                if field["name"] == "发布条件":
                    field["options"]["conditions"] = [
                        {"field_id": spec_done["id"], "equals": True},
                        {"field_id": change_done["id"], "equals": True},
                        {"field_id": bug_clear["id"], "equals": True},
                    ]

    issues = _mutated(tmp_path, mutate)
    assert any("and 条件与契约规则不一致" in issue for issue in issues), issues


# ---------- 数据层：改名 / stage_done / gate / 摘闸门 ----------

def test_gate_migration_renames_and_recomputes(tmp_path: Path) -> None:
    db = tmp_path / "phase2.db"
    _build_board3_db(db)
    migrate_board4.migrate(db, artifact=tmp_path / "phase1.json", backup=False)
    before_rows = _rows(db, "tf-ver")
    first = migrate_board4_gate.migrate(db, artifact=tmp_path / "g1.json", backup=False)
    assert first["ok"] is True and first["row_diff_total"] == 0

    ver_fields = _fields(db, "tf-ver")
    names = [field["name"] for field in ver_fields]
    assert "Bug已修复/总数" in names and "上一版本Bug已修复/总数" not in names
    assert "Bug是否清空" in names and "上一版本Bug是否清空" not in names
    assert names == migrate_board4_gate.VER_ORDER
    by_name = {field["name"]: field for field in ver_fields}
    assert by_name["六节点是否全部完成"]["order"] == 9
    assert by_name["发布条件"]["order"] == 10

    gated = {
        field["name"]
        for field in ver_fields
        if (json.loads(field["options"]) if field["options"] else {}).get("gate")
    }
    assert gated == {"六节点是否全部完成", "发布条件"}

    gate_id = by_name["发布条件"]["id"]
    stage_done_id = by_name["六节点是否全部完成"]["id"]
    computed = _computed(db, "tf-ver")
    for row_id, expected in (("v0.7.0", True), ("v0.8.0", False), ("v0.6.0", False)):
        assert computed[(row_id, gate_id)] is expected, row_id
        assert computed[(row_id, stage_done_id)] is expected, row_id
    assert _rows(db, "tf-ver") == before_rows

    # 第二次：结构/规则/行数据都不再变化。
    dump_before = _dump(db)
    second = migrate_board4_gate.migrate(db, artifact=tmp_path / "g2.json", backup=False)
    action = second["projects"][0]
    assert second["ok"] is True
    assert action["renamed_fields"] == []
    assert action["fields_added"] == []
    assert action["gate_marks_removed"] == []
    assert action["gate_options_updated"] == []
    assert action["order_updates"] == []
    assert _dump(db) == dump_before


def _dump(db: Path) -> dict:
    conn = sqlite3.connect(db)
    try:
        return {
            "tables": conn.execute("SELECT * FROM tables ORDER BY id").fetchall(),
            "fields": conn.execute("SELECT * FROM fields ORDER BY id").fetchall(),
            "rows": conn.execute(
                "SELECT table_id, id, data FROM row_records ORDER BY table_id, id"
            ).fetchall(),
            "computed": conn.execute(
                "SELECT table_id, row_id, field_id, value, override_value, override_reason"
                " FROM computed_values ORDER BY table_id, row_id, field_id"
            ).fetchall(),
        }
    finally:
        conn.close()
