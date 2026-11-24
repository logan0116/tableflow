"""090-13 强制鉴权：`TABLEFLOW_AUTH_MODE=enforced` 时写接口必须带有效 X-API-Key。

覆盖：默认 legacy 仍接受 X-Agent-Id；enforced 下无 key/无效 key 均 401 且零写入；
有效 key 正常写入并落 key_id；enforced 且无有效 key 时健康检查降级为 503。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow import auth
from tableflow.app import app
from tableflow.db import connect_write, init_schema
from tableflow.seed import write_seed

BASE = {
    "projects": [
        {
            "id": "p90",
            "name": "090 强制鉴权",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本",
                    "order": 1,
                    "fields": [
                        {"id": "v-name", "name": "版本", "type": "text", "options": None, "order": 1, "visible": 1}
                    ],
                    "rows": [],
                }
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "auth-enforce.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    monkeypatch.delenv("TABLEFLOW_AUTH_MODE", raising=False)
    with TestClient(app) as client:
        yield client, db


def _issue(db: Path, label: str):
    conn = connect_write(db)
    try:
        init_schema(conn)
        return auth.issue_key(conn, label)
    finally:
        conn.close()


def _query(db: Path, sql: str, params: tuple = ()):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _create(client: TestClient, row_id: str = "v2", headers: dict | None = None):
    return client.post(
        f"/api/agent/tables/t-ver/rows/{row_id}",
        json={"values": {"v-name": "2.0"}},
        headers=headers or {},
    )


def test_legacy_default_still_accepts_agent_id(env):
    client, _ = env
    response = _create(client, headers={"X-Agent-Id": "agent-legacy"})
    assert response.status_code == 200
    assert response.json()["result"] == "success"


def test_enforced_rejects_missing_key_and_writes_nothing(env, monkeypatch):
    client, db = env
    monkeypatch.setenv("TABLEFLOW_AUTH_MODE", "enforced")
    response = _create(client, headers={"X-Agent-Id": "agent-legacy"})
    assert response.status_code == 401
    assert "X-API-Key" in response.json()["error"]
    assert _query(db, "SELECT 1 FROM row_records WHERE table_id='t-ver' AND id='v2'") == []
    audit = _query(db, "SELECT agent_id, key_id, result FROM write_audit ORDER BY id DESC LIMIT 1")[0]
    assert audit["result"] == "failed"
    assert audit["key_id"] is None


def test_enforced_accepts_valid_key(env, monkeypatch):
    client, db = env
    monkeypatch.setenv("TABLEFLOW_AUTH_MODE", "enforced")
    record, raw = _issue(db, "zhang.gong")
    response = _create(client, headers={"X-API-Key": raw})
    assert response.status_code == 200
    assert response.json()["result"] == "success"
    audit = _query(db, "SELECT agent_id, key_id, result FROM write_audit ORDER BY id DESC LIMIT 1")[0]
    assert audit["agent_id"] == "zhang.gong"
    assert audit["key_id"] == record["id"]
    assert audit["result"] == "success"


def test_enforced_rejects_invalid_key(env, monkeypatch):
    client, db = env
    monkeypatch.setenv("TABLEFLOW_AUTH_MODE", "enforced")
    response = _create(client, headers={"X-API-Key": "tfk_not-a-real-key"})
    assert response.status_code == 401
    assert _query(db, "SELECT 1 FROM row_records WHERE table_id='t-ver' AND id='v2'") == []


def test_enforced_health_degrades_without_key(env, monkeypatch):
    client, _ = env
    monkeypatch.setenv("TABLEFLOW_AUTH_MODE", "enforced")
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_enforced_health_ok_with_key(env, monkeypatch):
    client, db = env
    monkeypatch.setenv("TABLEFLOW_AUTH_MODE", "enforced")
    _issue(db, "zhang.gong")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_auth_mode_raises(monkeypatch):
    monkeypatch.setenv("TABLEFLOW_AUTH_MODE", "strictish")
    with pytest.raises(RuntimeError):
        auth.auth_mode()
