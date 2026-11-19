"""016 抽取：`ratio` 计算类型（已完成/总数 文本）。

覆盖：
- 正常比率 "2/3"；
- 空集 "0/0"；
- 悬空引用不计入分母（与 count 同口径）；
- 源行变化后重算并落库；
- ratio 不能标记 gate（400）。
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

STATUS = [
    {"value": "done", "label": "已完成", "tone": "success"},
    {"value": "doing", "label": "进行中", "tone": "info"},
]

BASE = {
    "projects": [
        {
            "id": "p016",
            "name": "ratio",
            "tables": [
                {
                    "id": "t-src",
                    "name": "规格",
                    "order": 1,
                    "fields": [
                        {"id": "s-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "s-status", "name": "验收状态", "type": "enum", "options": STATUS, "order": 2, "visible": 1},
                    ],
                    "rows": [
                        {"id": "S1", "values": {"s-id": "S1", "s-status": "done"}},
                        {"id": "S2", "values": {"s-id": "S2", "s-status": "done"}},
                        {"id": "S3", "values": {"s-id": "S3", "s-status": "doing"}},
                    ],
                },
                {
                    "id": "t-ver",
                    "name": "版本",
                    "order": 2,
                    "fields": [
                        {"id": "v-name", "name": "版本号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "v-rel", "name": "独立需求管理", "type": "relation",
                         "options": {"table_id": "t-src"}, "order": 2, "visible": 1},
                    ],
                    "rows": [
                        {"id": "V1", "values": {"v-name": "1.0", "v-rel": ["S1", "S2", "S3"]}},
                        {"id": "V0", "values": {"v-name": "0.9", "v-rel": []}},
                    ],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "ratio016.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


def _values(client, table_id="t-ver"):
    payload = client.get(f"/api/tables/{table_id}/table").json()
    return {row["id"]: row["values"] for row in payload["rows"]}


def _add(client, field_id, options):
    return client.post(
        "/api/agent/tables/t-ver/fields",
        json={"id": field_id, "name": field_id, "type": "computed", "options": options},
        headers=HEADERS,
    )


def test_ratio_text(env):
    client, _ = env
    resp = _add(client, "v-ratio", {"kind": "ratio", "source": "v-rel",
                                    "where": {"field_id": "s-status", "equals": "done"}})
    assert resp.status_code == 200, resp.text
    values = _values(client)
    assert values["V1"]["v-ratio"] == "2/3"
    assert values["V0"]["v-ratio"] == "0/0"


def test_ratio_ignores_dangling(env):
    client, _ = env
    resp = _add(client, "v-ratio", {"kind": "ratio", "source": "v-rel",
                                    "where": {"field_id": "s-status", "equals": "done"}})
    assert resp.status_code == 200, resp.text
    # 挂一个不存在的行：不计入分母
    client.patch("/api/agent/tables/t-ver/rows/V1",
                 json={"values": {"v-rel": ["S1", "S2", "S3", "S9"]}}, headers=HEADERS)
    assert _values(client)["V1"]["v-ratio"] == "2/3"


def test_ratio_recompute_after_source_change(env):
    client, db = env
    _add(client, "v-ratio", {"kind": "ratio", "source": "v-rel",
                             "where": {"field_id": "s-status", "equals": "done"}})
    client.patch("/api/agent/tables/t-src/rows/S3",
                 json={"values": {"s-status": "done"}}, headers=HEADERS)
    assert _values(client)["V1"]["v-ratio"] == "3/3"
    conn = sqlite3.connect(db)
    try:
        stored = conn.execute(
            "SELECT value FROM computed_values WHERE table_id='t-ver' AND row_id='V1' AND field_id='v-ratio'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert stored.strip('"') == "3/3"


def test_ratio_cannot_be_gate(env):
    client, _ = env
    resp = _add(client, "v-ratio", {"kind": "ratio", "source": "v-rel",
                                    "where": {"field_id": "s-status", "equals": "done"},
                                    "gate": True})
    assert resp.status_code == 400
    assert "gate" in resp.json()["error"]
