"""Agent 写接口测试：建表 → 加字段 → 写行 → 读回；审计；三态；校验。"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

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
                    ],
                    "rows": [{"id": "sr1", "values": {"s1": "张工"}}],
                }
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "agent.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


def _audit_rows(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT agent_id, action, target, result, error FROM write_audit ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_full_write_flow(env):
    client, _ = env

    created = client.post("/api/agent/projects/p/tables", json={"id": "t-eq", "name": "设备"}, headers=HEADERS)
    assert created.status_code == 200
    assert created.json() == {"result": "success", "id": "t-eq"}

    field = client.post(
        "/api/agent/tables/t-eq/fields",
        json={"id": "f-name", "name": "设备名", "type": "text"},
        headers=HEADERS,
    )
    assert field.json()["result"] == "success"

    row = client.post(
        "/api/agent/tables/t-eq/rows",
        json={"id": "r-1", "values": {"f-name": "CNC-01"}},
        headers=HEADERS,
    )
    assert row.json()["result"] == "success"

    table = client.get("/api/tables/t-eq/table").json()
    assert [f["id"] for f in table["fields"]] == ["f-name"]
    assert table["rows"][0]["values"]["f-name"] == "CNC-01"


def test_relation_field_requires_same_project(env):
    client, _ = env
    client.post("/api/agent/projects/p/tables", json={"id": "t-eq", "name": "设备"}, headers=HEADERS)
    bad = client.post(
        "/api/agent/tables/t-eq/fields",
        json={"id": "f-x", "name": "关联", "type": "relation", "options": {"table_id": "nope"}},
        headers=HEADERS,
    )
    assert bad.status_code == 400
    assert bad.json()["result"] == "failed"


def test_validation_failure_does_not_write(env):
    client, _ = env
    bad = client.post(
        "/api/agent/tables/t-staff/rows",
        json={"id": "r-x", "values": {"unknown": "x"}},
        headers=HEADERS,
    )
    assert bad.status_code == 400
    table = client.get("/api/tables/t-staff/table").json()
    assert [r["id"] for r in table["rows"]] == ["sr1"]


def test_missing_agent_header_rejected(env):
    client, _ = env
    response = client.post("/api/agent/projects/p/tables", json={"id": "t-x", "name": "X"})
    assert response.status_code == 400
    assert "X-Agent-Id" in response.json()["error"]


def test_audit_records_every_write(env):
    client, db = env
    client.post("/api/agent/projects/p/tables", json={"id": "t-eq", "name": "设备"}, headers=HEADERS)
    client.post("/api/agent/tables/t-eq/rows", json={"values": {"unknown": 1}}, headers=HEADERS)
    rows = _audit_rows(db)
    assert len(rows) == 2
    assert rows[0][0] == "agent-test"
    assert rows[0][1] == "table.create"
    assert rows[0][3] == "success"
    assert rows[1][3] == "failed"
    assert rows[1][4]


def test_delete_table_cascades(env):
    client, db = env
    client.post("/api/agent/projects/p/tables", json={"id": "t-eq", "name": "设备"}, headers=HEADERS)
    client.post(
        "/api/agent/tables/t-eq/fields",
        json={"id": "f1", "name": "设备名", "type": "text"},
        headers=HEADERS,
    )
    client.post("/api/agent/tables/t-eq/rows", json={"id": "r1", "values": {"f1": "x"}}, headers=HEADERS)
    deleted = client.delete("/api/agent/tables/t-eq", headers=HEADERS)
    assert deleted.json()["result"] == "success"
    assert client.get("/api/tables/t-eq/table").status_code == 404

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT count(*) FROM fields WHERE table_id='t-eq'").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM row_records WHERE table_id='t-eq'").fetchone()[0] == 0
    finally:
        conn.close()


def test_update_row_merges_values(env):
    client, _ = env
    client.post(
        "/api/agent/tables/t-staff/rows",
        json={"id": "r-9", "values": {"s1": "旧"}},
        headers=HEADERS,
    )
    client.patch("/api/agent/rows/r-9", json={"values": {"s1": "新"}}, headers=HEADERS)
    table = client.get("/api/tables/t-staff/table").json()
    values = {row["id"]: row["values"] for row in table["rows"]}
    assert values["r-9"]["s1"] == "新"
