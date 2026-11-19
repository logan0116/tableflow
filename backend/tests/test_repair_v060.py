"""v0.6.0 缺陷回归（t9）：V060-04 悬空关联不锁死编辑。

V060-07（sum 空集落0.0）由契约rev3明确接受浮点口径，不改代码，故无回归用例。
对应 specs/verify-v060.md 第六节缺陷登记；修复记录追加在报告第十节。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-repair"}

BASE = {
    "projects": [
        {
            "id": "p-repair",
            "name": "v0.6.0 缺陷回归",
            "tables": [
                {
                    "id": "t-src",
                    "name": "源行",
                    "order": 1,
                    "fields": [
                        {"id": "s-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "s-num", "name": "数量", "type": "number", "options": None, "order": 2, "visible": 1},
                    ],
                    "rows": [
                        {"id": "S1", "values": {"s-id": "S1", "s-num": 6}},
                    ],
                },
                {
                    "id": "t-ver",
                    "name": "汇总行",
                    "order": 2,
                    "fields": [
                        {"id": "v-name", "name": "版本号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "v-rel", "name": "关联", "type": "relation",
                         "options": {"table_id": "t-src",
                                     "constraints": {"relation_must_exist": True}},
                         "order": 2, "visible": 1},
                    ],
                    "rows": [
                        {"id": "V1", "values": {"v-name": "1.0", "v-rel": ["S1"]}},
                        {"id": "V0", "values": {"v-name": "0.9", "v-rel": []}},
                    ],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "repair-v060.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


def _values(client, table_id, row_id):
    payload = client.get(f"/api/tables/{table_id}/rows/{row_id}")
    assert payload.status_code == 200, payload.text
    return payload.json()["row"]["values"]


def _raw_computed(db, table_id, row_id, field_id):
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT value FROM computed_values WHERE table_id=? AND row_id=? AND field_id=?",
            (table_id, row_id, field_id),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, (table_id, row_id, field_id)
    return json.loads(row[0]), row[0]


# ---------- V060-04：悬空关联不锁死无关字段的编辑 ----------

def test_v060_04_dangling_relation_does_not_block_unrelated_edit(env):
    client, _ = env
    # 删除被关联行（003 允许），V1 的 v-rel 变成悬空引用
    assert client.delete("/api/agent/tables/t-src/rows/S1", headers=HEADERS).json()["result"] == "success"
    assert _values(client, "t-ver", "V1")["v-rel"] == ["S1"]

    # 改无关字段：不再被悬空引用拦住
    patched = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"v-name": "1.1"}},
        headers=HEADERS,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["result"] == "success"
    values = _values(client, "t-ver", "V1")
    assert values["v-name"] == "1.1"
    assert values["v-rel"] == ["S1"]  # 悬空值原样保留，不替人清理


def test_v060_04_explicit_dangling_value_still_rejected(env):
    client, _ = env
    client.delete("/api/agent/tables/t-src/rows/S1", headers=HEADERS)

    # 显式提交悬空值仍必须失败（别把修复做成放松校验）
    rejected = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"v-rel": ["S1"]}},
        headers=HEADERS,
    )
    assert rejected.status_code == 400
    assert "关联目标行不存在" in rejected.json()["error"]

    # 清空失效关联是合法修法
    cleared = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"v-rel": []}},
        headers=HEADERS,
    )
    assert cleared.json()["result"] == "success"
    assert _values(client, "t-ver", "V1")["v-rel"] == []


def test_v060_04_create_row_still_checks_relation_target(env):
    client, _ = env
    # 新建行不走“本次提交”豁免：初始悬空值必须被拒
    created = client.post(
        "/api/agent/tables/t-ver/rows/V9",
        json={"values": {"v-name": "9.0", "v-rel": ["S404"]}},
        headers=HEADERS,
    )
    assert created.status_code == 400
    assert "关联目标行不存在" in created.json()["error"]
