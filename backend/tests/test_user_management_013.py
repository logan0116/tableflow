"""013 用户管理（兼容期）测试：旧 X-Agent-Id 不变、key 识别与审计、无效 key 拒绝、负责人填充。

四情形各有用例：
- 旧 X-Agent-Id 写入仍成功，审计无 key 标识；
- 新 X-API-Key 写入成功，审计带 key 标识与 key 的 label 身份；
- 无效/已吊销 key 被 401 拒绝，不写业务数据，但留 failed 审计；
- 负责人缺省由调用者身份填充（仅 key 鉴权；显式值优先；多义不猜；旧调用不填）。
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow import auth
from tableflow.app import app
from tableflow.db import connect_write, init_schema
from tableflow.seed import write_seed

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
KEYS_CLI = BACKEND_DIR / "scripts" / "tf_keys.py"
LEGACY_HEADERS = {"X-Agent-Id": "agent-legacy"}

BASE = {
    "projects": [
        {
            "id": "p13",
            "name": "013 用户管理",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本",
                    "order": 1,
                    "fields": [
                        {"id": "v-name", "name": "版本", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "v-owner", "name": "负责人", "type": "text", "options": None, "order": 2, "visible": 1},
                    ],
                    "rows": [{"id": "v1", "values": {"v-name": "1.0"}}],
                },
                {
                    "id": "t-name",
                    "name": "按名称识别的负责人",
                    "order": 2,
                    "fields": [
                        {"id": "tn-text", "name": "内容", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "tn-owner-name", "name": "负责人", "type": "text", "options": None, "order": 2, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-amb",
                    "name": "负责人多义",
                    "order": 3,
                    "fields": [
                        {"id": "amb-owner", "name": "负责人甲", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "amb2-owner", "name": "负责人乙", "type": "text", "options": None, "order": 2, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-note",
                    "name": "无负责人字段",
                    "order": 4,
                    "fields": [
                        {"id": "nt-text", "name": "内容", "type": "text", "options": None, "order": 1, "visible": 1},
                    ],
                    "rows": [],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "user-management.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


# ---------- 工具 ----------

def _query(db, sql, params=()):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _issue(db, label, note=None):
    conn = connect_write(db)
    try:
        init_schema(conn)
        return auth.issue_key(conn, label, note=note)
    finally:
        conn.close()


def _revoke(db, key_id, by="agent-test"):
    conn = connect_write(db)
    try:
        init_schema(conn)
        return auth.revoke_key(conn, key_id, by=by)
    finally:
        conn.close()


def _last_audit(db):
    rows = _query(
        db,
        "SELECT agent_id, key_id, action, result, error FROM write_audit ORDER BY id DESC LIMIT 1",
    )
    return rows[0] if rows else None


def _row_values(client, table_id, row_id):
    payload = client.get(f"/api/tables/{table_id}/rows/{row_id}")
    assert payload.status_code == 200, payload.text
    return payload.json()["row"]["values"]


def _create_row(client, table_id, row_id, values, headers):
    return client.post(
        f"/api/agent/tables/{table_id}/rows/{row_id}", json={"values": values}, headers=headers
    )


# ---------- 情形 1：旧 X-Agent-Id 调用不被改变 ----------

def test_legacy_x_agent_id_write_still_succeeds(env):
    client, db = env
    response = _create_row(client, "t-ver", "v2", {"v-name": "2.0"}, LEGACY_HEADERS)
    assert response.status_code == 200
    assert response.json() == {"result": "success", "id": "v2"}

    # 旧调用不触发负责人填充：写入内容与改造前一致
    values = _row_values(client, "t-ver", "v2")
    assert values["v-name"] == "2.0"
    assert values.get("v-owner") is None

    audit = _last_audit(db)
    assert audit["agent_id"] == "agent-legacy"
    assert audit["key_id"] is None
    assert audit["result"] == "success"
    changes = _query(
        db,
        "SELECT actor FROM business_changes WHERE table_id = 't-ver' AND row_id = 'v2'"
        " AND field_id = 'v-name'",
    )
    assert [row["actor"] for row in changes] == ["agent-legacy"]


def test_missing_identity_keeps_old_400_and_mentions_agent_header(env):
    client, db = env
    response = client.post("/api/agent/tables/t-ver/rows/v9", json={"values": {"v-name": "9.0"}})
    assert response.status_code == 400
    assert "X-Agent-Id" in response.json()["error"]
    assert _query(db, "SELECT 1 FROM row_records WHERE table_id='t-ver' AND id='v9'") == []
    audit = _last_audit(db)
    assert audit["result"] == "failed"
    assert audit["error"]


def test_read_side_needs_no_key(env):
    client, _ = env
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/tables/t-ver/table").status_code == 200


# ---------- 情形 2：key 识别调用者，写审计带 key 标识 ----------

def test_api_key_write_audited_with_key_id(env):
    client, db = env
    record, raw = _issue(db, "zhang.gong")
    response = _create_row(client, "t-ver", "v3", {"v-name": "3.0"}, {"X-API-Key": raw})
    assert response.json()["result"] == "success"

    audit = _last_audit(db)
    assert audit["agent_id"] == "zhang.gong"
    assert audit["key_id"] == record["id"]
    assert audit["result"] == "success"
    # 业务变更记录的 actor 也是 key 的 label
    changes = _query(
        db,
        "SELECT actor FROM business_changes WHERE table_id='t-ver' AND row_id='v3'"
        " AND field_id='v-name'",
    )
    assert [row["actor"] for row in changes] == ["zhang.gong"]
    # 库里只有摘要，不存明文
    stored = _query(db, "SELECT key_hash FROM api_keys WHERE id = ?", (record["id"],))
    assert stored[0]["key_hash"] != raw
    assert len(stored[0]["key_hash"]) == 64


def test_key_takes_priority_over_legacy_header(env):
    client, db = env
    record, raw = _issue(db, "li.si")
    response = _create_row(
        client, "t-note", "n1", {"nt-text": "x"},
        {"X-API-Key": raw, "X-Agent-Id": "agent-legacy"},
    )
    assert response.json()["result"] == "success"
    audit = _last_audit(db)
    assert audit["agent_id"] == "li.si"
    assert audit["key_id"] == record["id"]


# ---------- 情形 3：无效/已吊销 key 被拒 ----------

def test_invalid_key_rejected_without_writing(env):
    client, db = env
    response = _create_row(
        client, "t-ver", "v4", {"v-name": "4.0"},
        {"X-API-Key": "tfk_not-a-real-key", "X-Agent-Id": "agent-legacy"},
    )
    assert response.status_code == 401
    assert response.json()["result"] == "failed"
    assert "API key" in response.json()["error"]
    assert _query(db, "SELECT 1 FROM row_records WHERE table_id='t-ver' AND id='v4'") == []
    audit = _last_audit(db)
    assert audit["result"] == "failed"
    assert "API key" in audit["error"]


def test_revoked_key_rejected(env):
    client, db = env
    record, raw = _issue(db, "wang.wu")
    _revoke(db, record["id"])
    response = _create_row(client, "t-ver", "v5", {"v-name": "5.0"}, {"X-API-Key": raw})
    assert response.status_code == 401
    assert "已吊销" in response.json()["error"]
    assert _query(db, "SELECT 1 FROM row_records WHERE table_id='t-ver' AND id='v5'") == []


# ---------- 情形 4：负责人缺省由调用者身份填充 ----------

def test_owner_autofilled_for_key_caller(env):
    client, db = env
    _, raw = _issue(db, "zhang.gong")
    headers = {"X-API-Key": raw}

    # 缺省：填充为 key 的 label
    assert _create_row(client, "t-ver", "v6", {"v-name": "6.0"}, headers).json()["result"] == "success"
    assert _row_values(client, "t-ver", "v6")["v-owner"] == "zhang.gong"

    # 显式值优先
    assert _create_row(
        client, "t-ver", "v7", {"v-name": "7.0", "v-owner": "指定负责人"}, headers
    ).json()["result"] == "success"
    assert _row_values(client, "t-ver", "v7")["v-owner"] == "指定负责人"

    # 按名称识别（字段 id 不以 -owner 结尾时）
    assert _create_row(client, "t-name", "n2", {"tn-text": "x"}, headers).json()["result"] == "success"
    assert _row_values(client, "t-name", "n2")["tn-owner-name"] == "zhang.gong"

    # 无负责人字段：不凭空造字段
    assert _create_row(client, "t-note", "n3", {"nt-text": "y"}, headers).json()["result"] == "success"
    assert "nt-owner" not in _row_values(client, "t-note", "n3")

    # 多义（两个 -owner 同表）：不猜、不填
    assert _create_row(client, "t-amb", "a1", {"amb-owner": None}, headers).json()["result"] == "success"
    assert _row_values(client, "t-amb", "a1").get("amb-owner") is None


def test_owner_not_autofilled_on_update_or_legacy(env):
    client, db = env
    _, raw = _issue(db, "zhang.gong")

    # 旧调用新建：不填
    assert _create_row(client, "t-ver", "v8", {"v-name": "8.0"}, LEGACY_HEADERS).json()["result"] == "success"
    assert _row_values(client, "t-ver", "v8").get("v-owner") is None

    # key 调用更新已有行：不填（显式写入才改）
    patched = client.patch(
        "/api/agent/tables/t-ver/rows/v8",
        json={"values": {"v-name": "8.1"}},
        headers={"X-API-Key": raw},
    )
    assert patched.json()["result"] == "success"
    assert _row_values(client, "t-ver", "v8").get("v-owner") is None

    # 覆盖率字段的创建：row 级 business_changes 记 owner=label
    assert _create_row(client, "t-ver", "v10", {"v-name": "10.0"}, {"X-API-Key": raw}).json()["result"] == "success"
    changes = _query(
        db,
        "SELECT new_value FROM business_changes WHERE table_id='t-ver' AND row_id='v10'"
        " AND field_id='v-owner'",
    )
    assert [json.loads(row["new_value"]) for row in changes] == ["zhang.gong"]


# ---------- CLI：签发 / 吊销 / 列出 / 审计查询 ----------

def _cli(db, *args):
    result = subprocess.run(
        [sys.executable, str(KEYS_CLI), *args, "--db", str(db)],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result


def test_cli_issue_list_revoke_audit(env):
    client, db = env
    issued = _cli(db, "issue", "--label", "cli.user", "--note", "脚本签发")
    assert issued.returncode == 0, issued.stderr
    key_id = next(
        line.split(":", 1)[1].strip() for line in issued.stdout.splitlines() if line.startswith("key_id:")
    )
    raw = next(
        line.split(":", 1)[1].strip() for line in issued.stdout.splitlines() if line.startswith("key:")
    )
    assert raw.startswith(auth.KEY_PREFIX)

    listed = _cli(db, "list")
    assert listed.returncode == 0
    assert "cli.user" in listed.stdout and "有效" in listed.stdout
    assert raw not in listed.stdout  # 列表不回显明文

    # 用 CLI 签发的 key 写入成功，审计带 key_id
    assert _create_row(client, "t-note", "n4", {"nt-text": "z"}, {"X-API-Key": raw}).json()["result"] == "success"
    assert _last_audit(db)["key_id"] == key_id

    revoked = _cli(db, "revoke", "--id", key_id, "--by", "captain")
    assert revoked.returncode == 0, revoked.stderr
    assert "已吊销" in revoked.stdout
    assert _create_row(client, "t-note", "n5", {"nt-text": "w"}, {"X-API-Key": raw}).status_code == 401

    audited = _cli(db, "audit", "--limit", "10")
    assert audited.returncode == 0
    assert "key.issue" in audited.stdout and "key.revoke" in audited.stdout
    assert key_id in audited.stdout


def test_cli_revoke_unknown_key_fails(env):
    _, db = env
    result = _cli(db, "revoke", "--id", "k-00000000")
    assert result.returncode == 1
    assert "不存在" in result.stderr


# ---------- 旧库迁移：启动时幂等补表补列 ----------

def test_old_database_upgraded_on_startup(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE write_audit (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id   TEXT NOT NULL,
            origin     TEXT NOT NULL DEFAULT 'agent',
            action     TEXT NOT NULL,
            target     TEXT NOT NULL,
            payload    TEXT,
            result     TEXT NOT NULL,
            error      TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO write_audit (agent_id, origin, action, target, result, created_at)
        VALUES ('old-agent', 'agent', 'row.create', 'old/1', 'success', '2026-11-01T00:00:00+08:00');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("TABLEFLOW_DB", str(db))

    with TestClient(app) as client:
        # 启动迁移后，旧调用照常可写
        created = client.post(
            "/api/agent/projects", json={"id": "p-old", "name": "旧库"}, headers=LEGACY_HEADERS
        )
        assert created.json()["result"] == "success"
        record, raw = _issue(db, "after.migrate")
        keyed = client.post(
            "/api/agent/projects/p-old/tables", json={"id": "t-old", "name": "表"}, headers={"X-API-Key": raw}
        )
        assert keyed.json()["result"] == "success"
        assert _last_audit(db)["key_id"] == record["id"]

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(write_audit)")}
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        old_row = conn.execute(
            "SELECT agent_id, key_id FROM write_audit WHERE agent_id = 'old-agent'"
        ).fetchone()
    finally:
        conn.close()
    assert "key_id" in columns
    assert "api_keys" in tables
    # 旧审计行保留，key_id 为空
    assert old_row["agent_id"] == "old-agent"
    assert old_row["key_id"] is None
