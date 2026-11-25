"""045 设置页：管理口令 + API key 管理接口。

覆盖口令 fail-closed（未配置/过短/错误）、列表不含明文与摘要、签发一次性明文、
吊销立即生效、审计落 `key.issue` / `key.revoke`、label 校验零写入。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow import auth
from tableflow.admin import ADMIN_TOKEN_ENV
from tableflow.app import app
from tableflow.db import connect_write, init_schema
from tableflow.seed import write_seed

TOKEN = "admin-token-for-test"
BASE = {
    "projects": [
        {
            "id": "p45",
            "name": "045 设置页",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本",
                    "order": 1,
                    "fields": [
                        {
                            "id": "v-name",
                            "name": "版本",
                            "type": "text",
                            "options": None,
                            "order": 1,
                            "visible": 1,
                        }
                    ],
                    "rows": [],
                }
            ],
        }
    ]
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "admin-045.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    monkeypatch.delenv("TABLEFLOW_AUTH_MODE", raising=False)
    with TestClient(app) as test_client:
        yield test_client, db


@pytest.fixture()
def admin_env(client, monkeypatch):
    test_client, db = client
    monkeypatch.setenv(ADMIN_TOKEN_ENV, TOKEN)
    return test_client, db


def _headers(token: str | None = TOKEN) -> dict[str, str]:
    return {"X-Admin-Token": token} if token is not None else {}


def _get(test_client: TestClient, path: str, **kwargs):
    kwargs.setdefault("headers", _headers())
    return test_client.get(path, **kwargs)


def _post(test_client: TestClient, path: str, **kwargs):
    kwargs.setdefault("headers", _headers())
    return test_client.post(path, **kwargs)


def _count(db: Path, sql: str, params: tuple = ()) -> int:
    conn = connect_write(db)
    try:
        init_schema(conn)
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def _db_path() -> Path:
    return Path(os.environ["TABLEFLOW_DB"])


def test_unconfigured_token_is_fail_closed(client):
    """未配置口令：管理接口 503，绝不「无口令放行」。"""
    test_client, _ = client
    assert test_client.get("/api/admin/keys").status_code == 503
    assert test_client.post("/api/admin/keys", json={"label": "x-agent"}).status_code == 503
    assert test_client.post("/api/admin/keys/k-00000000/revoke").status_code == 503
    assert test_client.post("/api/admin/unlock").status_code == 503


def test_short_token_counts_as_disabled(client, monkeypatch):
    """口令过短按未配置处理——避免用 `123` 这种口令打开设置页。"""
    test_client, _ = client
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "short")
    assert test_client.get("/api/admin/keys", headers=_headers("short")).status_code == 503


def test_wrong_token_rejected(admin_env):
    """口令错误 401，且响应不回显正确口令。"""
    test_client, _ = admin_env
    response = _get(test_client, "/api/admin/keys", headers=_headers("wrong-token"))
    assert response.status_code == 401
    body = response.json()
    assert body["result"] == "failed"
    assert TOKEN not in str(body)


def test_missing_token_header_rejected(admin_env):
    """配了口令但不带头：401，不是 503。"""
    test_client, _ = admin_env
    assert test_client.get("/api/admin/keys").status_code == 401


def test_unlock_and_list(admin_env):
    """正确口令可解锁并读到 key 列表。"""
    test_client, _ = admin_env
    assert _post(test_client, "/api/admin/unlock").status_code == 200
    response = _get(test_client, "/api/admin/keys")
    assert response.status_code == 200
    assert response.json()["keys"] == []


def test_issue_returns_plaintext_once(admin_env):
    """签发返回一次性明文；之后列表只有标识、没有明文与摘要。"""
    test_client, db = admin_env
    response = _post(
        test_client, "/api/admin/keys", json={"label": "demo-agent", "note": "演示"}
    )
    assert response.status_code == 200
    payload = response.json()
    plaintext = payload["plaintext"]
    assert plaintext.startswith(auth.KEY_PREFIX)
    key_id = payload["key"]["id"]

    listed = _get(test_client, "/api/admin/keys").json()["keys"]
    assert [row["id"] for row in listed] == [key_id]
    assert listed[0]["label"] == "demo-agent"
    assert listed[0]["note"] == "演示"
    assert "plaintext" not in listed[0]
    assert "key_hash" not in listed[0]
    assert plaintext not in str(listed)

    # 库里只存摘要：按摘要能命中，按明文命不中
    assert _count(db, "SELECT COUNT(*) FROM api_keys WHERE key_hash = ?", (auth.hash_key(plaintext),)) == 1
    assert _count(db, "SELECT COUNT(*) FROM api_keys WHERE key_hash = ?", (plaintext,)) == 0


def test_audit_records_admin_actor(admin_env):
    """签发与吊销都落 write_audit，actor=admin。"""
    test_client, db = admin_env
    key_id = _post(test_client, "/api/admin/keys", json={"label": "audit-agent"}).json()["key"]["id"]
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM write_audit WHERE action='key.issue' AND agent_id='admin' AND target=?",
            (key_id,),
        )
        == 1
    )
    _post(test_client, f"/api/admin/keys/{key_id}/revoke")
    assert (
        _count(
            db,
            "SELECT COUNT(*) FROM write_audit WHERE action='key.revoke' AND agent_id='admin' AND target=?",
            (key_id,),
        )
        == 1
    )


def test_revoke_takes_effect_immediately(admin_env):
    """吊销后：列表状态变为已吊销，且用该 key 调写接口立即 401。"""
    test_client, _ = admin_env
    issued = _post(test_client, "/api/admin/keys", json={"label": "revoke-me"}).json()
    key_id, plaintext = issued["key"]["id"], issued["plaintext"]

    # 吊销前：写接口可用（legacy 模式下带 key 即识别调用者）
    ok = test_client.post(
        "/api/agent/tables/t-ver/rows/v0.0.1",
        json={"values": {"v-name": "v0.0.1"}},
        headers={"X-API-Key": plaintext},
    )
    assert ok.status_code == 200

    revoked = _post(test_client, f"/api/admin/keys/{key_id}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["key"]["revoked_at"] is not None

    listed = _get(test_client, "/api/admin/keys").json()["keys"]
    assert listed[0]["revoked_at"] is not None

    denied = test_client.post(
        "/api/agent/tables/t-ver/rows/v0.0.2",
        json={"values": {"v-name": "v0.0.2"}},
        headers={"X-API-Key": plaintext},
    )
    assert denied.status_code == 401
    assert _count(_db_path(), "SELECT COUNT(*) FROM row_records WHERE id='v0.0.2'") == 0


def test_revoke_twice_rejected(admin_env):
    """重复吊销 400，保持状态可信。"""
    test_client, _ = admin_env
    key_id = _post(test_client, "/api/admin/keys", json={"label": "twice"}).json()["key"]["id"]
    assert _post(test_client, f"/api/admin/keys/{key_id}/revoke").status_code == 200
    assert _post(test_client, f"/api/admin/keys/{key_id}/revoke").status_code == 400


def test_revoke_unknown_key_rejected(admin_env):
    """吊销不存在的 key 400。"""
    test_client, _ = admin_env
    assert _post(test_client, "/api/admin/keys/k-deadbeef/revoke").status_code == 400


def test_invalid_label_rejected_without_write(admin_env):
    """label 为空或超长 400，且不落库。"""
    test_client, db = admin_env
    before = _count(db, "SELECT COUNT(*) FROM api_keys")
    assert _post(test_client, "/api/admin/keys", json={"label": "  "}).status_code == 400
    assert _post(test_client, "/api/admin/keys", json={"label": "x" * 65}).status_code == 400
    assert _post(test_client, "/api/admin/keys", json={}).status_code == 400
    assert _count(db, "SELECT COUNT(*) FROM api_keys") == before


def test_credential_not_leaked_in_health(client):
    """口令不应出现在只读健康检查里。"""
    test_client, _ = client
    assert TOKEN not in test_client.get("/api/health").text
