"""protocol@2：请求体严格校验（012-AR 的 P-019 反转）与枚举值域校验。

对应需求 018-AR 的 US1/US2 验收场景：写错形状、值域外值必须 400 且不落库，
不再"静默 success"。
"""

from __future__ import annotations

import json
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
                    "id": "t-bug",
                    "name": "缺陷",
                    "order": 1,
                    "fields": [
                        {"id": "b-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "b-title", "name": "标题", "type": "text", "options": None, "order": 2, "visible": 1},
                        {
                            "id": "b-source",
                            "name": "来源",
                            "type": "enum",
                            "options": {
                                "items": [
                                    {"value": "test", "label": "测试发现", "tone": "info"},
                                    {"value": "review", "label": "评审发现", "tone": "warning"},
                                ]
                            },
                            "order": 3,
                            "visible": 1,
                        },
                    ],
                    "rows": [{"id": "BUG-01", "values": {"b-id": "BUG-01", "b-title": "示例", "b-source": "test"}}],
                }
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "protocol2.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


def _values(db, table="t-bug", row="BUG-01"):
    conn = sqlite3.connect(db)
    try:
        raw = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table, row)
        ).fetchone()
        return json.loads(raw[0])
    finally:
        conn.close()


def test_unknown_top_level_key_rejected(env):
    """US1-AS1：字段名放顶层（不带 values）→ 400，且该行不变。"""
    client, db = env
    resp = client.patch("/api/agent/tables/t-bug/rows/BUG-01", json={"b-source": "review"}, headers=HEADERS)
    assert resp.status_code == 400
    body = resp.json()
    assert body["result"] == "failed"
    assert "未知顶层键" in body["error"]
    assert _values(db)["b-source"] == "test"


def test_values_not_object_rejected(env):
    """US1-AS2：values 传成数组 → 400，不落库。"""
    client, db = env
    resp = client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01", json={"values": ["b-source", "review"]}, headers=HEADERS
    )
    assert resp.status_code == 400
    assert resp.json()["result"] == "failed"
    assert _values(db)["b-source"] == "test"


def test_body_id_mismatch_rejected(env):
    """US1-AS3：body.id 与路径不一致 → 400。"""
    client, db = env
    resp = client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01",
        json={"id": "BUG-99", "values": {"b-source": "review"}},
        headers=HEADERS,
    )
    assert resp.status_code == 400
    assert resp.json()["result"] == "failed"
    assert _values(db)["b-source"] == "test"


def test_unknown_key_with_valid_values_rejects_whole_request(env):
    """US1-AS4：正确 values 混着未知顶层键 → 整请求失败，无部分写入。"""
    client, db = env
    resp = client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01",
        json={"values": {"b-title": "改标题"}, "note": "顺手带个注释"},
        headers=HEADERS,
    )
    assert resp.status_code == 400
    values = _values(db)
    assert values["b-title"] == "示例"
    assert values["b-source"] == "test"


def test_correct_shape_writes(env):
    """US1-AS5：正确形状 → 200 success，读回等于提交值。"""
    client, db = env
    resp = client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01", json={"values": {"b-source": "review"}}, headers=HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "success"
    assert _values(db)["b-source"] == "review"


def test_enum_out_of_range_rejected(env):
    """US2-AS1：枚举外值 → 400，错误信息列出合法取值，读回不变。"""
    client, db = env
    resp = client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01", json={"values": {"b-source": "manual"}}, headers=HEADERS
    )
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert "枚举范围" in error
    assert "test" in error and "review" in error
    assert _values(db)["b-source"] == "test"


def test_create_row_unknown_key_rejected(env):
    """同一套严格校验也覆盖建行：多带顶层键就拒绝，行不会建出来。"""
    client, db = env
    resp = client.post(
        "/api/agent/tables/t-bug/rows/BUG-02",
        json={"values": {"b-id": "BUG-02", "b-title": "新缺陷"}, "force": True},
        headers=HEADERS,
    )
    assert resp.status_code == 400
    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT 1 FROM row_records WHERE table_id = 't-bug' AND id = 'BUG-02'"
        ).fetchone() is None
    finally:
        conn.close()
