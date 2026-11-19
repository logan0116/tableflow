"""010 计算口径测试：空集语义、悬空关联、闸门字段禁止覆盖、写行后重算下游。

对应 specs/010-computation/spec.md：
- a 空集：count=0、sum=0、rollup all=true、percent 空集仍 null。
- b 悬空：布尔 rollup 不把悬空当"没有"，就绪不得变真；数量类维持 003 的忽略悬空。
- c 闸门：`options.gate=true` 的计算字段拒绝人工覆盖（400），清除历史覆盖仍允许。
- d 下游：写行后同事务重算依赖表并落库，读侧只读。
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

HEADERS = {"X-Agent-Id": "agent-test"}

STATUS_ITEMS = [
    {"value": "todo", "label": "待办", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "已完成", "tone": "success"},
]

DOC_ITEMS = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "done", "label": "完成", "tone": "success"},
]

BASE = {
    "projects": [
        {
            "id": "p010",
            "name": "010 计算口径",
            "tables": [
                {
                    "id": "t-src",
                    "name": "源行",
                    "order": 1,
                    "fields": [
                        {"id": "s-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "s-status", "name": "状态", "type": "enum", "options": STATUS_ITEMS, "order": 2, "visible": 1},
                        {"id": "s-num", "name": "数量", "type": "number", "options": None, "order": 3, "visible": 1},
                    ],
                    "rows": [
                        {"id": "S1", "values": {"s-id": "S1", "s-status": "done", "s-num": 3}},
                        {"id": "S2", "values": {"s-id": "S2", "s-status": "doing", "s-num": 5}},
                        {"id": "S3", "values": {"s-id": "S3", "s-status": "done", "s-num": 4}},
                    ],
                },
                {
                    "id": "t-ver",
                    "name": "汇总行",
                    "order": 2,
                    "fields": [
                        {"id": "v-name", "name": "版本", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "v-rel", "name": "关联", "type": "relation",
                         "options": {"table_id": "t-src"}, "order": 2, "visible": 1},
                        {"id": "v-num", "name": "数字", "type": "number", "options": None, "order": 3, "visible": 1},
                        {"id": "v-doc", "name": "文档", "type": "enum", "options": DOC_ITEMS, "order": 4, "visible": 1},
                    ],
                    "rows": [
                        {"id": "V1", "values": {"v-name": "1.0", "v-rel": ["S1", "S2", "S3"],
                                                "v-num": 2, "v-doc": "done"}},
                        {"id": "V0", "values": {"v-name": "0.9", "v-rel": [], "v-num": 5, "v-doc": "todo"}},
                    ],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "computation010.db"
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


def _add_computed(client, field_id, options, *, table_id="t-ver", name=None):
    return client.post(
        f"/api/agent/tables/{table_id}/fields",
        json={"id": field_id, "name": name or field_id, "type": "computed", "options": options},
        headers=HEADERS,
    )


def _values(client, table_id="t-ver"):
    payload = client.get(f"/api/tables/{table_id}/table").json()
    return {row["id"]: row["values"] for row in payload["rows"]}


def _row_payload(client, table_id, row_id):
    payload = client.get(f"/api/tables/{table_id}/table").json()
    return next(row for row in payload["rows"] if row["id"] == row_id)


def _stored(db, row_id, field_id, table_id="t-ver"):
    """直接读落库的计算值（读侧零计算，落库值就是真相）。"""
    rows = _query(
        db,
        "SELECT value, override_value FROM computed_values"
        " WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (table_id, row_id, field_id),
    )
    assert rows, f"缺少计算值 {table_id}/{row_id}/{field_id}"
    value = rows[0]["value"]
    override = rows[0]["override_value"]
    return (
        json.loads(value) if value is not None else None,
        json.loads(override) if override is not None else None,
    )


# ---------- a 空集语义 ----------

def test_a_empty_set_semantics(env):
    client, db = env
    assert _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"}).json()["result"] == "success"
    assert _add_computed(client, "c-sum", {
        "kind": "sum", "source": "v-rel", "field_id": "s-num", "decimals": 0,
    }).json()["result"] == "success"
    assert _add_computed(client, "r-all", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "all", "equals": "done",
    }).json()["result"] == "success"
    assert _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    }).json()["result"] == "success"

    # 非空集合先确认口径正常（对照）
    assert _values(client)["V1"] == {
        "v-name": "1.0", "v-rel": ["S1", "S2", "S3"], "v-num": 2, "v-doc": "done",
        "c-count": 3, "c-sum": 12, "r-all": False, "c-pct": 66.7,
    }

    # 空集：count=0、sum=0、rollup all=true、percent 仍 null
    empty = _values(client)["V0"]
    assert empty["c-count"] == 0
    assert empty["c-sum"] == 0
    assert empty["r-all"] is True
    assert empty["c-pct"] is None

    # 落库值与读接口同口径（读侧不重算、不兜底）
    assert _stored(db, "V0", "c-count") == (0, None)
    assert _stored(db, "V0", "c-sum") == (0, None)
    assert _stored(db, "V0", "r-all") == (True, None)
    assert _stored(db, "V0", "c-pct") == (None, None)


# ---------- b 悬空关联 ----------

def _add_ready_fields(client):
    assert _add_computed(client, "r-all", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "all", "equals": "done",
    }).json()["result"] == "success"
    assert _add_computed(client, "a-ready", {
        "kind": "and", "conditions": [{"field_id": "r-all", "equals": True}],
        "gate": True,
    }).json()["result"] == "success"


def test_b_dangling_does_not_make_ready_true(env):
    client, db = env
    _add_ready_fields(client)
    assert _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"}).json()["result"] == "success"
    assert _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    }).json()["result"] == "success"

    assert _values(client)["V1"]["r-all"] is False
    # 删除被关联行（003 允许；010 不改写侧语义），S2 在 v-rel 里变成悬空引用
    deleted = client.delete("/api/agent/tables/t-src/rows/S2", headers=HEADERS)
    assert deleted.json()["result"] == "success"

    v1 = _values(client)["V1"]
    # 剩下 S1/S3 都 done，但关联里 S2 已不存在：就绪不得因此变真
    assert v1["r-all"] is False
    assert v1["a-ready"] is False
    # 数量类维持 003 的"忽略悬空"：描述仍然存在的行
    assert v1["c-count"] == 2
    assert v1["c-pct"] == 100.0
    assert _stored(db, "V1", "r-all") == (False, None)
    assert _stored(db, "V1", "c-count") == (2, None)


def test_b_dangling_all_any_none(env):
    client, _ = env
    assert _add_computed(client, "r-all", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "all", "equals": "done",
    }).json()["result"] == "success"
    assert _add_computed(client, "r-any", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "any", "equals": "done",
    }).json()["result"] == "success"
    assert _add_computed(client, "r-none", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "none", "equals": "failed",
    }).json()["result"] == "success"

    client.delete("/api/agent/tables/t-src/rows/S2", headers=HEADERS)
    v1 = _values(client)["V1"]
    # all/none 无法在悬空集合上确立 → 否；any 只断言"存在"，已核验成员命中即真
    assert v1["r-all"] is False
    assert v1["r-none"] is False
    assert v1["r-any"] is True


def test_b_removing_dangling_reference_restores_ready(env):
    client, _ = env
    _add_ready_fields(client)
    client.delete("/api/agent/tables/t-src/rows/S2", headers=HEADERS)
    assert _values(client)["V1"]["a-ready"] is False
    # 人工修法：从关联里摘掉失效 id（此时集合 = 现存行）
    patched = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"v-rel": ["S1", "S3"]}},
        headers=HEADERS,
    )
    assert patched.json()["result"] == "success"
    assert _values(client)["V1"]["r-all"] is True
    assert _values(client)["V1"]["a-ready"] is True


# ---------- c 闸门字段禁止覆盖 ----------

def _add_gate_rollup(client):
    return _add_computed(client, "r-gate", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "all", "equals": "done",
        "gate": True, "allow_override": True,
    })


def test_c_gate_override_rejected(env):
    client, db = env
    assert _add_gate_rollup(client).json()["result"] == "success"
    assert _values(client)["V1"]["r-gate"] is False

    response = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"r-gate": {"value": True, "reason": "人工放行"}}},
        headers=HEADERS,
    )
    assert response.status_code == 400
    assert "闸门" in response.json()["error"]
    # 覆盖没有落库，判定值不变
    assert _stored(db, "V1", "r-gate") == (False, None)
    assert _row_payload(client, "t-ver", "V1")["computed_meta"]["r-gate"]["overridden"] is False


def test_c_gate_config_validation(env):
    client, _ = env
    # gate 必须是布尔
    assert _add_computed(client, "bad-gate-type", {
        "kind": "rollup", "source": "v-rel", "field_id": "s-status",
        "aggregate": "all", "equals": "done", "gate": "yes",
    }).status_code == 400
    # 数量类不是布尔判定，不能当闸门
    bad = _add_computed(client, "bad-gate-count", {"kind": "count", "source": "v-rel", "gate": True})
    assert bad.status_code == 400
    assert "布尔判定" in bad.json()["error"]
    # and 是布尔判定，允许打闸门标记
    assert _add_computed(client, "a-gate", {
        "kind": "and", "conditions": [{"field_id": "v-num", "equals": 2}], "gate": True,
    }).json()["result"] == "success"


def test_c_gate_clear_legacy_override_allowed(env):
    client, db = env
    assert _add_gate_rollup(client).json()["result"] == "success"
    # 模拟打闸门标记之前遗留的覆盖
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "UPDATE computed_values SET override_value = 'true', override_reason = '历史覆盖',"
            " override_by = 'agent-test', override_at = '2026-11-01T00:00:00+08:00'"
            " WHERE table_id = 't-ver' AND row_id = 'V1' AND field_id = 'r-gate'"
        )
        conn.commit()
    finally:
        conn.close()
    assert _values(client)["V1"]["r-gate"] is True
    # 清除是撤回，不是伪造资格：放行
    cleared = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"r-gate": {"value": None}}},
        headers=HEADERS,
    )
    assert cleared.json()["result"] == "success"
    assert _stored(db, "V1", "r-gate") == (False, None)
    assert _row_payload(client, "t-ver", "V1")["computed_meta"]["r-gate"]["overridden"] is False


def test_c_non_gate_bool_override_still_allowed(env):
    client, _ = env
    assert _add_computed(client, "a-free", {
        "kind": "and", "conditions": [{"field_id": "v-num", "equals": 2}],
        "allow_override": True,
    }).json()["result"] == "success"
    assert _values(client)["V1"]["a-free"] is True
    response = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"a-free": {"value": False, "reason": "人工确认"}}},
        headers=HEADERS,
    )
    assert response.json()["result"] == "success"
    assert _values(client)["V1"]["a-free"] is False


# ---------- d 写行后重算下游 ----------

def test_d_source_write_recomputes_downstream_in_same_write(env):
    client, db = env
    _add_ready_fields(client)
    assert _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"}).json()["result"] == "success"
    assert _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    }).json()["result"] == "success"
    assert _add_computed(client, "a-done", {
        "kind": "and",
        "conditions": [{"field_id": "c-pct", "equals": 100}, {"field_id": "c-count", "equals": 3}],
    }).json()["result"] == "success"
    assert _values(client)["V1"]["c-pct"] == 66.7
    assert _values(client)["V1"]["a-done"] is False

    # 只写源表一行；不额外调 recompute
    response = client.patch(
        "/api/agent/tables/t-src/rows/S2",
        json={"values": {"s-status": "done"}},
        headers=HEADERS,
    )
    assert response.json()["result"] == "success"

    # 下游值在同一次写事务里落库
    assert _stored(db, "V1", "c-pct") == (100.0, None)
    assert _stored(db, "V1", "c-count") == (3, None)
    assert _stored(db, "V1", "r-all") == (True, None)
    assert _stored(db, "V1", "a-done") == (True, None)
    row = _row_payload(client, "t-ver", "V1")
    assert row["values"]["a-done"] is True
    assert row["computed_meta"]["a-done"]["computed_at"]


def test_d_new_rows_recompute_downstream(env):
    client, db = env
    assert _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"}).json()["result"] == "success"
    # 新增源行不改变已有关联的计数
    assert client.post(
        "/api/agent/tables/t-src/rows/S4",
        json={"values": {"s-id": "S4", "s-status": "done", "s-num": 1}},
        headers=HEADERS,
    ).json()["result"] == "success"
    assert _values(client)["V1"]["c-count"] == 3

    # 关联加一行 → 下游计数同写落库
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"v-rel": ["S1", "S2", "S3", "S4"]}},
        headers=HEADERS,
    ).json()["result"] == "success"
    assert _stored(db, "V1", "c-count") == (4, None)

    # 新建汇总行 → 新行也立刻有计算值
    assert client.post(
        "/api/agent/tables/t-ver/rows/V2",
        json={"values": {"v-name": "2.0", "v-rel": ["S4"]}},
        headers=HEADERS,
    ).json()["result"] == "success"
    assert _stored(db, "V2", "c-count") == (1, None)
    assert _values(client)["V2"]["c-count"] == 1


def test_d_source_delete_recomputes_downstream(env):
    client, db = env
    assert _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"}).json()["result"] == "success"
    assert client.delete("/api/agent/tables/t-src/rows/S1", headers=HEADERS).json()["result"] == "success"
    assert _stored(db, "V1", "c-count") == (2, None)
    assert _values(client)["V1"]["c-count"] == 2
