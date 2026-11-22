"""019（board@4）数据层迁移：六表落地、幂等、存量行不变、节点初始化。

覆盖 task T1 的四条交付：
1. 为 board@3 项目建 case/run 两表（run kind=detail），版本表加六节点、runs 与三个
   用例字段，不建 plan 表；
2. 重跑不重复建表建字段、不覆盖已有行；
3. released 版本六节点 done，planned/dropped 为 todo；
4. 迁移前后四张老表按「迁移前已存在的字段」逐行比对差异 0，并落比对产物。
"""

from __future__ import annotations

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

import importlib.util  # noqa: E402

import migrate_board4  # noqa: E402


def _load_board3_template():
    """冻结的 board@3 模板：T1 迁移测试的输入基线，不随 data/template 升级而漂移。"""
    path = REPO_ROOT / "backend" / "tests" / "fixtures" / "board3_template.py"
    spec = importlib.util.spec_from_file_location("board3_template", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

from tableflow import calculation  # noqa: E402
from tableflow.db import connect_write  # noqa: E402
from tableflow.seed import write_seed  # noqa: E402

EXPECTED_VER_NAMES = [
    "版本号",
    "发布时间",
    "版本需求设计",
    "测试设计",
    "开发",
    "开发验收",
    "测试",
    "测试验收",
    "发布条件",
    "发布状态",
    "独立需求管理",
    "独立需求已完成/总数",
    "独立需求是否完成",
    "依赖需求管理",
    "依赖需求已完成/总数",
    "依赖需求是否完成",
    "测试用例",
    "用例总数",
    "已完成用例数",
    "用例是否完成",
    "Bug管理",
    "上一版本Bug已修复/总数",
    "上一版本Bug是否清空",
    "负责人",
    "变更说明",
]
EXPECTED_CASE_NAMES = ["用例号", "用例名", "来源规格", "前置条件", "操作步骤", "预期结果", "优先级", "负责人"]
EXPECTED_RUN_NAMES = [
    "执行编号",
    "用例号",
    "用例",
    "执行状态",
    "执行结果",
    "证据",
    "执行时间",
    "执行人",
    "备注",
]


def _field_id(field_prefix: str, role: str, short: str) -> str:
    prefix = f"{field_prefix}-" if field_prefix else ""
    return f"{prefix}{role}-{short}"


def _seed_data(table_prefix: str, field_prefix: str) -> dict:
    """用 board@3 模板造一个项目：三条版本行覆盖 released / planned / dropped。"""

    def fid(role: str, short: str) -> str:
        return _field_id(field_prefix, role, short)

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
                    fid("v", "note"): "已发布版本，迁移前既有备注",
                },
            },
            {
                "id": "v0.8.0",
                "values": {
                    fid("v", "ver"): "v0.8.0",
                    fid("v", "status"): "planned",
                    fid("v", "note"): "计划中版本",
                },
            },
            {
                "id": "v0.6.0",
                "values": {
                    fid("v", "ver"): "v0.6.0",
                    fid("v", "status"): "dropped",
                    fid("v", "note"): "已废弃版本",
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
    for table in _load_board3_template().build_tables(table_prefix, field_prefix):
        fields = [
            {"id": field_id, "name": name, "type": ftype, "options": options,
             "order": index + 1, "visible": 1}
            for index, (field_id, name, ftype, options) in enumerate(table["fields"])
        ]
        tables.append(
            {
                "id": table["id"],
                "name": table["name"],
                "order": table["order"],
                "fields": fields,
                "rows": rows.get(table["id"], []),
            }
        )
    return {"projects": [{"id": "demo", "name": "演示项目", "tables": tables}]}


def _build_db(db: Path, *, table_prefix: str = "tf", field_prefix: str = "tf") -> None:
    write_seed(db, _seed_data(table_prefix, field_prefix))
    # 先让 board@3 的计算字段有落库值，才能验证迁移前后旧计算值不变（尤其 gate）。
    conn = connect_write(db)
    try:
        calculation.recompute_table(conn, f"{table_prefix}-ver", actor="test", origin="seed")
        conn.commit()
    finally:
        conn.close()


def _rows(db: Path, table_id: str) -> dict[str, dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {
            row["id"]: json.loads(row["data"] or "{}")
            for row in conn.execute(
                "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id", (table_id,)
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
                'SELECT id, name, type, options, "order", visible FROM fields'
                ' WHERE table_id = ? ORDER BY "order", id',
                (table_id,),
            )
        ]
    finally:
        conn.close()


def _tables(db: Path) -> dict[str, dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {
            row["id"]: dict(row)
            for row in conn.execute('SELECT id, name, "order", kind FROM tables')
        }
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


def _dump(db: Path) -> dict:
    conn = sqlite3.connect(db)
    try:
        return {
            "projects": conn.execute("SELECT * FROM projects ORDER BY id").fetchall(),
            "tables": conn.execute('SELECT * FROM tables ORDER BY id').fetchall(),
            "fields": conn.execute('SELECT * FROM fields ORDER BY id').fetchall(),
            "rows": conn.execute(
                "SELECT table_id, id, data FROM row_records ORDER BY table_id, id"
            ).fetchall(),
            "computed": conn.execute(
                "SELECT table_id, row_id, field_id, value, computed_at, override_value,"
                " override_reason, override_by, override_at"
                " FROM computed_values ORDER BY table_id, row_id, field_id"
            ).fetchall(),
        }
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("table_prefix", "field_prefix"),
    [("tf", "tf"), ("fd", "")],
)
def test_migration_creates_six_tables_and_preserves_rows(
    tmp_path: Path, table_prefix: str, field_prefix: str
) -> None:
    db = tmp_path / f"{table_prefix}.db"
    artifact = tmp_path / f"{table_prefix}-artifact.json"
    _build_db(db, table_prefix=table_prefix, field_prefix=field_prefix)
    gate_before = _computed(db, f"{table_prefix}-ver")[("v0.7.0", _field_id(field_prefix, "v", "cond"))]

    result = migrate_board4.migrate(db, artifact=artifact, backup=False)

    assert result["ok"] is True, result
    assert result["diff_total"] == 0
    assert artifact.exists()
    saved = json.loads(artifact.read_text(encoding="utf-8"))
    assert saved["ok"] is True and saved["diff_total"] == 0

    tables = _tables(db)
    ver_id = f"{table_prefix}-ver"
    case_id = f"{table_prefix}-case"
    run_id = f"{table_prefix}-run"
    assert set(tables) == {
        ver_id,
        f"{table_prefix}-indep",
        f"{table_prefix}-dep",
        f"{table_prefix}-bug",
        case_id,
        run_id,
    }
    assert not any(table_id.endswith("-plan") for table_id in tables)
    assert tables[run_id]["name"] == "用例执行情况"
    assert tables[run_id]["kind"] == "detail"
    assert tables[case_id]["kind"] == "board"
    assert tables[ver_id]["kind"] == "board"

    # 版本表：六节点 + runs + 三个用例字段，位置与 board@4 一致（stage_done 归 023/025）。
    ver_names = [field["name"] for field in _fields(db, ver_id)]
    assert ver_names == EXPECTED_VER_NAMES
    case_names = [field["name"] for field in _fields(db, case_id)]
    run_names = [field["name"] for field in _fields(db, run_id)]
    assert case_names == EXPECTED_CASE_NAMES
    assert run_names == EXPECTED_RUN_NAMES

    # 写侧协议（020）按字段 id 形状识别执行记录表，case_no/state/result 必须保住后缀。
    run_ids = {field["name"]: field["id"] for field in _fields(db, run_id)}
    assert run_ids["用例号"].endswith("-case_no")
    assert run_ids["执行状态"].endswith("-state")
    assert run_ids["执行结果"].endswith("-result")

    # 关系：ver→run、run→case、case→indep；run 表不允许有指回版本的字段。
    ver_fields = {field["name"]: field for field in _fields(db, ver_id)}
    case_fields = {field["name"]: field for field in _fields(db, case_id)}
    run_fields = {field["name"]: field for field in _fields(db, run_id)}
    runs_options = json.loads(ver_fields["测试用例"]["options"])
    assert runs_options["table_id"] == run_id
    assert runs_options["display_field"] == run_ids["用例号"]
    assert runs_options["status_field"] == run_ids["执行状态"]
    indep_options = json.loads(case_fields["来源规格"]["options"])
    assert indep_options["table_id"] == f"{table_prefix}-indep"
    case_options = json.loads(run_fields["用例"]["options"])
    assert case_options["table_id"] == case_id
    assert "status_field" not in case_options
    for field in run_fields.values():
        if field["type"] != "relation":
            continue
        assert json.loads(field["options"])["table_id"] != ver_id

    # 存量行：行数不变，旧字段值不变；六节点按发布状态初始化。
    ver_rows = _rows(db, ver_id)
    assert len(ver_rows) == 3
    assert len(_rows(db, f"{table_prefix}-indep")) == 1
    assert len(_rows(db, f"{table_prefix}-dep")) == 1
    assert len(_rows(db, f"{table_prefix}-bug")) == 1
    assert ver_rows["v0.7.0"][_field_id(field_prefix, "v", "note")] == "已发布版本，迁移前既有备注"
    stage_ids = [
        ver_fields[name]["id"] for name in migrate_board4.STAGE_FIELD_NAMES
    ]
    assert all(ver_rows["v0.7.0"][field_id] == "done" for field_id in stage_ids)
    assert all(ver_rows["v0.8.0"][field_id] == "todo" for field_id in stage_ids)
    assert all(ver_rows["v0.6.0"][field_id] == "todo" for field_id in stage_ids)

    # 旧计算值（gate）不下降；三个用例字段按空集语义初始化。
    computed = _computed(db, ver_id)
    assert computed[("v0.7.0", _field_id(field_prefix, "v", "cond"))] == gate_before is True
    assert computed[("v0.7.0", ver_fields["用例总数"]["id"])] == 0
    assert computed[("v0.7.0", ver_fields["已完成用例数"]["id"])] == 0
    assert computed[("v0.7.0", ver_fields["用例是否完成"]["id"])] is True
    assert result["comparison"]["demo"]["ver"]["row_value_diffs"] == []
    assert result["comparison"]["demo"]["ver"]["computed_value_diffs"] == []
    for role in ("indep", "dep", "bug"):
        assert result["comparison"]["demo"][role]["diff"] == 0


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "twice.db"
    artifact1 = tmp_path / "first.json"
    artifact2 = tmp_path / "second.json"
    _build_db(db)

    first = migrate_board4.migrate(db, artifact=artifact1, backup=False)
    dump1 = _dump(db)
    second = migrate_board4.migrate(db, artifact=artifact2, backup=False)
    dump2 = _dump(db)

    assert first["ok"] is True and second["ok"] is True
    assert second["diff_total"] == 0
    assert dump1 == dump2

    action1 = first["projects"][0]
    action2 = second["projects"][0]
    assert action1["tables_created"] == ["tf-case", "tf-run"]
    assert action1["fields_created"]
    assert action1["nodes_initialized"]
    assert action2["tables_created"] == []
    assert action2["fields_created"] == []
    assert action2["order_updates"] == []
    assert action2["nodes_initialized"] == []
    assert action2["computed_initialized"] == []
    assert len(_tables(db)) == 6


def test_read_api_exposes_table_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """表级 kind 要能被读接口看到：前端导航靠它把 detail 表挡在外面。"""
    from fastapi.testclient import TestClient

    from tableflow.app import app

    db = tmp_path / "api.db"
    _build_db(db)
    migrate_board4.migrate(db, artifact=tmp_path / "api.json", backup=False)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        payload = client.get("/api/projects/demo/tables").json()
        by_id = {table["id"]: table for table in payload["tables"]}
        assert by_id["tf-run"]["kind"] == "detail"
        assert by_id["tf-case"]["kind"] == "board"
        assert by_id["tf-ver"]["kind"] == "board"
        detail = client.get("/api/tables/tf-run/table").json()
        assert detail["table"]["kind"] == "detail"
