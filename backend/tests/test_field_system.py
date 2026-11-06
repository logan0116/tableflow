"""002 字段体系契约测试：enum tone、字段约束、行 id、单向关联、业务变更记录。"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

STATUS_ITEMS = [
    {"value": "todo", "label": "待办", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "已完成", "tone": "success"},
]

BASE = {
    "projects": [
        {
            "id": "p",
            "name": "项目",
            "tables": [
                {
                    "id": "t-staff",
                    "name": "人员",
                    "order": 1,
                    "fields": [
                        {"id": "s1", "name": "姓名", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "s2", "name": "状态", "type": "enum", "options": STATUS_ITEMS, "order": 2, "visible": 1},
                        {"id": "s3", "name": "工时", "type": "number",
                         "options": {"decimals": 1, "constraints": {"min": 0, "max": 100}}, "order": 3, "visible": 1},
                        {"id": "s4", "name": "任务", "type": "relation",
                         "options": {"table_id": "t-task"}, "order": 4, "visible": 1},
                    ],
                    "rows": [
                        {"id": "sr1", "values": {"s1": "张工", "s2": "todo", "s3": 10}},
                    ],
                },
                {
                    "id": "t-task",
                    "name": "任务",
                    "order": 2,
                    "fields": [
                        {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                    ],
                    "rows": [{"id": "r1", "values": {"f1": "甲"}}],
                },
            ],
        },
        {
            "id": "p2",
            "name": "别的项目",
            "tables": [
                {
                    "id": "t-other",
                    "name": "外部表",
                    "order": 1,
                    "fields": [
                        {"id": "o1", "name": "名称", "type": "text", "options": None, "order": 1, "visible": 1},
                    ],
                    "rows": [],
                }
            ],
        },
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "field.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


def _query(db, sql, params=()):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _field_count(db, table_id="t-staff"):
    return _query(db, "SELECT count(*) AS c FROM fields WHERE table_id = ?", (table_id,))[0]["c"]


def _row_ids(client, table_id="t-staff"):
    return [row["id"] for row in client.get(f"/api/tables/{table_id}/table").json()["rows"]]


def _changes(db, table_id="t-staff", row_id=None):
    sql = "SELECT * FROM business_changes WHERE table_id = ?"
    params = [table_id]
    if row_id is not None:
        sql += " AND row_id = ?"
        params.append(row_id)
    sql += " ORDER BY id"
    return _query(db, sql, tuple(params))


def _audit(db):
    return _query(db, "SELECT * FROM write_audit ORDER BY id")


def _create_field(client, table_id, body):
    return client.post(f"/api/agent/tables/{table_id}/fields", json=body, headers=HEADERS)


def _create_row(client, table_id, row_id, values):
    return client.post(
        f"/api/agent/tables/{table_id}/rows/{row_id}", json={"values": values}, headers=HEADERS
    )


# ---------- enum tone ----------

def test_enum_option_requires_tone(env):
    client, db = env
    before = _field_count(db)
    response = _create_field(client, "t-staff", {
        "id": "bad", "name": "无 tone", "type": "enum",
        "options": [{"value": "x", "label": "X"}],
    })
    assert response.status_code == 400
    assert response.json()["result"] == "failed"
    assert _field_count(db) == before


def test_enum_rejects_unknown_tone(env):
    client, db = env
    response = _create_field(client, "t-staff", {
        "id": "bad", "name": "坏 tone", "type": "enum",
        "options": [{"value": "x", "label": "X", "tone": "purple"}],
    })
    assert response.status_code == 400
    assert "tone" in response.json()["error"]
    assert _field_count(db) == 4


def test_enum_option_value_must_be_nonempty_and_unique(env):
    client, _ = env
    empty = _create_field(client, "t-staff", {
        "id": "bad", "name": "空值", "type": "enum",
        "options": [{"value": "", "label": "X", "tone": "info"}],
    })
    assert empty.status_code == 400
    dup = _create_field(client, "t-staff", {
        "id": "bad", "name": "重复", "type": "enum",
        "options": [
            {"value": "x", "label": "X", "tone": "info"},
            {"value": "x", "label": "X2", "tone": "success"},
        ],
    })
    assert dup.status_code == 400


def test_enum_valid_options_are_stored_and_read_back(env):
    client, _ = env
    response = _create_field(client, "t-staff", {
        "id": "s5", "name": "优先级", "type": "enum",
        "options": [{"value": "p0", "label": "P0", "tone": "danger"}],
    })
    assert response.json()["result"] == "success"
    fields = client.get("/api/tables/t-staff/table").json()["fields"]
    field = next(f for f in fields if f["id"] == "s5")
    assert field["options"][0]["tone"] == "danger"


def test_visible_and_order_ranges(env):
    client, db = env
    assert _create_field(client, "t-staff", {"id": "a", "name": "A", "type": "text", "visible": 2}).status_code == 400
    assert _create_field(client, "t-staff", {"id": "b", "name": "B", "type": "text", "order": -1}).status_code == 400
    assert _field_count(db) == 4


def test_name_and_type_required(env):
    client, db = env
    assert _create_field(client, "t-staff", {"id": "a", "type": "text"}).status_code == 400
    assert _create_field(client, "t-staff", {"id": "b", "name": "B"}).status_code == 400
    assert _field_count(db) == 4


# ---------- 字段级约束 ----------

def test_relation_target_must_exist_and_same_project(env):
    client, db = env
    missing = _create_field(client, "t-staff", {
        "id": "x", "name": "X", "type": "relation", "options": {"table_id": "nope"},
    })
    assert missing.status_code == 400
    other_project = _create_field(client, "t-staff", {
        "id": "y", "name": "Y", "type": "relation", "options": {"table_id": "t-other"},
    })
    assert other_project.status_code == 400
    assert _field_count(db) == 4


def test_relation_is_single_direction(env):
    client, db = env
    reverse = _create_field(client, "t-task", {
        "id": "f-rev", "name": "反向", "type": "relation", "options": {"table_id": "t-staff"},
    })
    assert reverse.status_code == 400
    assert "双向" in reverse.json()["error"]
    assert _field_count(db, "t-task") == 1
    failed = [row for row in _audit(db) if row["result"] == "failed"]
    assert failed and failed[-1]["action"] == "field.create"


def test_row_unknown_key_does_not_write(env):
    client, db = env
    response = _create_row(client, "t-staff", "r-x", {"unknown": "x"})
    assert response.status_code == 400
    assert "r-x" not in _row_ids(client)
    assert _changes(db) == []


def test_relation_value_must_be_string_array(env):
    client, db = env
    response = _create_row(client, "t-staff", "r-x", {"s4": "r1"})
    assert response.status_code == 400
    assert "r-x" not in _row_ids(client)
    ok = _create_row(client, "t-staff", "r-y", {"s4": ["r1"]})
    assert ok.json()["result"] == "success"


def test_required_constraint(env):
    client, db = env
    _create_field(client, "t-staff", {
        "id": "req", "name": "必填", "type": "text",
        "options": {"constraints": {"required": True}},
    })
    assert _create_row(client, "t-staff", "r-x", {"s1": "甲"}).status_code == 400
    assert _create_row(client, "t-staff", "r-x", {"req": ""}).status_code == 400
    assert _create_row(client, "t-staff", "r-x", {"req": "值"}).json()["result"] == "success"
    assert _row_ids(client).count("r-x") == 1


def test_min_max_constraint(env):
    client, _ = env
    assert _create_row(client, "t-staff", "r-low", {"s3": -1}).status_code == 400
    assert _create_row(client, "t-staff", "r-high", {"s3": 101}).status_code == 400
    assert _create_row(client, "t-staff", "r-ok", {"s3": 50}).json()["result"] == "success"


def test_enum_strict_constraint(env):
    client, db = env
    _create_field(client, "t-staff", {
        "id": "strict", "name": "严格枚举", "type": "enum",
        "options": {"items": STATUS_ITEMS, "constraints": {"enum_strict": True}},
    })
    bad = _create_row(client, "t-staff", "r-x", {"strict": "unknown"})
    assert bad.status_code == 400
    assert "r-x" not in _row_ids(client)
    good = _create_row(client, "t-staff", "r-y", {"strict": "doing"})
    assert good.json()["result"] == "success"


def test_relation_must_exist_constraint(env):
    client, _ = env
    _create_field(client, "t-staff", {
        "id": "rel", "name": "强关联", "type": "relation",
        "options": {"table_id": "t-task", "constraints": {"relation_must_exist": True}},
    })
    bad = _create_row(client, "t-staff", "r-x", {"rel": ["missing"]})
    assert bad.status_code == 400
    good = _create_row(client, "t-staff", "r-y", {"rel": ["r1"]})
    assert good.json()["result"] == "success"


def test_update_uses_merged_values(env):
    client, _ = env
    _create_field(client, "t-staff", {
        "id": "req", "name": "必填", "type": "text",
        "options": {"constraints": {"required": True}},
    })
    assert _create_row(client, "t-staff", "r-x", {"req": "值"}).json()["result"] == "success"
    # 只改其它字段：required 由旧值满足
    assert client.patch(
        "/api/agent/tables/t-staff/rows/r-x", json={"values": {"s1": "新人"}}, headers=HEADERS
    ).json()["result"] == "success"
    # 把必填字段清空：合并后校验失败
    assert client.patch(
        "/api/agent/tables/t-staff/rows/r-x", json={"values": {"req": ""}}, headers=HEADERS
    ).status_code == 400


# ---------- 行 id ----------

def test_row_id_format(env):
    client, _ = env
    for bad_id in ("bad id", "中文", "a:b"):
        response = client.post(
            f"/api/agent/tables/t-staff/rows/{bad_id}", json={"values": {"s1": "x"}}, headers=HEADERS
        )
        assert response.status_code in (400, 404), bad_id


def test_row_id_unique_within_table(env):
    client, _ = env
    assert _create_row(client, "t-staff", "r-x", {"s1": "一"}).json()["result"] == "success"
    duplicate = _create_row(client, "t-staff", "r-x", {"s1": "二"})
    assert duplicate.status_code == 400
    assert duplicate.json()["result"] == "failed"


def test_row_id_same_across_tables(env):
    client, _ = env
    assert _create_row(client, "t-staff", "7.0.1", {"s1": "甲"}).json()["result"] == "success"
    assert _create_row(client, "t-task", "7.0.1", {"f1": "乙"}).json()["result"] == "success"
    staff = {row["id"]: row["values"] for row in client.get("/api/tables/t-staff/table").json()["rows"]}
    task = {row["id"]: row["values"] for row in client.get("/api/tables/t-task/table").json()["rows"]}
    assert staff["7.0.1"]["s1"] == "甲"
    assert task["7.0.1"]["f1"] == "乙"


def test_row_id_immutable(env):
    client, _ = env
    response = client.patch(
        "/api/agent/tables/t-staff/rows/sr1",
        json={"id": "sr2", "values": {"s1": "改"}},
        headers=HEADERS,
    )
    assert response.status_code == 400
    assert "不可变" in response.json()["error"]


# ---------- 业务变更记录 ----------

def test_changes_on_create(env):
    client, db = env
    _create_row(client, "t-staff", "r-new", {"s1": "新人", "s2": "doing"})
    changes = _changes(db, row_id="r-new")
    assert len(changes) == 2
    by_field = {row["field_id"]: row for row in changes}
    assert by_field["s1"]["old_value"] is None
    assert json.loads(by_field["s1"]["new_value"]) == "新人"
    assert json.loads(by_field["s2"]["new_value"]) == "doing"
    assert by_field["s1"]["change_kind"] == "create"
    assert by_field["s1"]["actor"] == "agent-test"
    assert by_field["s1"]["origin"] == "agent"
    assert by_field["s1"]["field_name"] == "姓名"
    assert by_field["s1"]["occurred_at"]


def test_changes_on_update_only_changed_fields(env):
    client, db = env
    response = client.patch(
        "/api/agent/tables/t-staff/rows/sr1",
        json={"values": {"s1": "张工", "s2": "done"}},
        headers=HEADERS,
    )
    assert response.json()["result"] == "success"
    changes = _changes(db, row_id="sr1")
    assert len(changes) == 1
    change = changes[0]
    assert change["field_id"] == "s2"
    assert json.loads(change["old_value"]) == "todo"
    assert json.loads(change["new_value"]) == "done"
    assert change["change_kind"] == "update"


def test_changes_on_delete(env):
    client, db = env
    response = client.delete("/api/agent/tables/t-staff/rows/sr1", headers=HEADERS)
    assert response.json()["result"] == "success"
    changes = _changes(db, row_id="sr1")
    assert len(changes) == 3
    assert all(row["change_kind"] == "delete" for row in changes)
    assert all(row["new_value"] is None for row in changes)
    assert {row["field_id"] for row in changes} == {"s1", "s2", "s3"}


def test_failed_write_keeps_no_changes_but_failed_audit(env):
    client, db = env
    before = len(_changes(db))
    response = client.patch(
        "/api/agent/tables/t-staff/rows/sr1", json={"values": {"s3": 999}}, headers=HEADERS
    )
    assert response.status_code == 400
    assert len(_changes(db)) == before
    audit = _audit(db)
    assert audit[-1]["result"] == "failed"
    assert audit[-1]["action"] == "row.update"


def test_changes_are_separate_from_write_audit(env):
    client, db = env
    _create_row(client, "t-staff", "r-new", {"s1": "新人", "s2": "doing"})
    changes = _query(db, "SELECT count(*) AS c FROM business_changes")[0]["c"]
    audits = _query(db, "SELECT count(*) AS c FROM write_audit")[0]["c"]
    assert changes == 2
    assert audits == 1
    names = {
        row["name"]
        for row in _query(
            db,
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('business_changes', 'write_audit')",
        )
    }
    assert names == {"business_changes", "write_audit"}


def test_changes_api_order_and_limit(env):
    client, db = env
    for i in range(3):
        client.patch(
            "/api/agent/tables/t-staff/rows/sr1",
            json={"values": {"s1": f"名字{i}"}},
            headers=HEADERS,
        )
    payload = client.get("/api/tables/t-staff/rows/sr1/changes?limit=2")
    assert payload.status_code == 200
    changes = payload.json()["changes"]
    assert len(changes) == 2
    assert changes[0]["new_value"] == "名字2"
    assert changes[1]["new_value"] == "名字1"
    assert payload.headers["Cache-Control"] == "no-store"
    assert client.get("/api/tables/t-staff/rows/nope/changes").status_code == 404


def test_changes_origin_human_request(env):
    client, db = env
    response = client.patch(
        "/api/agent/tables/t-staff/rows/sr1",
        json={"values": {"s2": "done"}},
        headers={**HEADERS, "X-Origin": "human-request"},
    )
    assert response.json()["result"] == "success"
    change = _changes(db, row_id="sr1")[-1]
    assert change["origin"] == "human-request"
    audit = _audit(db)[-1]
    assert audit["origin"] == "human-request"


def test_invalid_origin_rejected(env):
    client, _ = env
    response = client.patch(
        "/api/agent/tables/t-staff/rows/sr1",
        json={"values": {"s2": "done"}},
        headers={**HEADERS, "X-Origin": "robot"},
    )
    assert response.status_code == 400
    assert "X-Origin" in response.json()["error"]


def test_row_change_log_view(env):
    client, db = env
    _create_row(client, "t-staff", "r-new", {"s1": "新人"})
    view_rows = _query(db, "SELECT agent_id, table_id, row_id, field_id, old_value, new_value, created_at FROM row_change_log")
    table_rows = _query(db, "SELECT actor, table_id, row_id, field_id, old_value, new_value, occurred_at FROM business_changes")
    assert len(view_rows) == len(table_rows)
    assert view_rows[0]["agent_id"] == table_rows[0]["actor"]
    assert view_rows[0]["created_at"] == table_rows[0]["occurred_at"]


# ---------- 读侧容错 ----------

def test_read_side_tolerates_bad_options(env):
    client, db = env
    conn = sqlite3.connect(db)
    try:
        conn.execute("UPDATE fields SET options = '{bad json' WHERE id = 's2'")
        conn.commit()
    finally:
        conn.close()
    response = client.get("/api/tables/t-staff/table")
    assert response.status_code == 200
    field = next(f for f in response.json()["fields"] if f["id"] == "s2")
    assert field["options"] is None
