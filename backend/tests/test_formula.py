"""003 计算字段契约测试：五种 kind、写侧重算、覆盖、失败回滚、读侧零计算。"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow import calculation
from tableflow.app import app
from tableflow.seed import write_seed

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

import rebuild_v030  # noqa: E402

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
            "id": "p",
            "name": "项目",
            "tables": [
                {
                    "id": "t-src",
                    "name": "源",
                    "order": 1,
                    "fields": [
                        {"id": "s-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "s-status", "name": "状态", "type": "enum", "options": STATUS_ITEMS, "order": 2, "visible": 1},
                        {"id": "s-num", "name": "数量", "type": "number", "options": None, "order": 3, "visible": 1},
                        {"id": "s-dt", "name": "日期", "type": "datetime", "options": None, "order": 4, "visible": 1},
                    ],
                    "rows": [
                        {"id": "S1", "values": {"s-id": "S1", "s-status": "done", "s-num": 3,
                                                "s-dt": "2026-01-01T00:00:00+08:00"}},
                        {"id": "S2", "values": {"s-id": "S2", "s-status": "doing", "s-num": 5,
                                                "s-dt": "2026-02-01T00:00:00+08:00"}},
                        {"id": "S3", "values": {"s-id": "S3", "s-status": "done", "s-num": 4,
                                                "s-dt": "2026-03-01T00:00:00+08:00"}},
                    ],
                },
                {
                    "id": "t-ver",
                    "name": "版本",
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
    db = tmp_path / "formula.db"
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


def _computed_values(db, table_id="t-ver"):
    return _query(
        db,
        "SELECT row_id, field_id, value, override_value FROM computed_values"
        " WHERE table_id = ? ORDER BY row_id, field_id",
        (table_id,),
    )


# ---------- 五种 kind ----------

def test_count(env):
    client, _ = env
    assert _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"}).json()["result"] == "success"
    values = _values(client)
    assert values["V1"]["c-count"] == 3
    assert values["V0"]["c-count"] == 0


def test_count_with_where(env):
    client, _ = env
    _add_computed(client, "c-done", {
        "kind": "count", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"},
    })
    values = _values(client)
    assert values["V1"]["c-done"] == 2
    assert values["V0"]["c-done"] == 0


def test_percent(env):
    client, _ = env
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    })
    values = _values(client)
    assert values["V1"]["c-pct"] == 66.7
    assert values["V0"]["c-pct"] is None


def test_percent_full_and_rounding(env):
    client, _ = env
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 0,
    })
    client.patch("/api/agent/tables/t-src/rows/S2", json={"values": {"s-status": "done"}}, headers=HEADERS)
    assert _values(client)["V1"]["c-pct"] == 100.0


def test_sum(env):
    client, _ = env
    _add_computed(client, "c-sum", {"kind": "sum", "source": "v-rel", "field_id": "s-num", "decimals": 0})
    values = _values(client)
    assert values["V1"]["c-sum"] == 12
    assert values["V0"]["c-sum"] == 0


def test_sum_ignores_dirty_values(env):
    client, db = env
    _add_computed(client, "c-sum", {"kind": "sum", "source": "v-rel", "field_id": "s-num", "decimals": 0})
    client.patch("/api/agent/tables/t-src/rows/S1", json={"values": {"s-num": "脏值"}}, headers=HEADERS)
    assert _values(client)["V1"]["c-sum"] == 9


def test_rollup_all_any_none(env):
    client, _ = env
    _add_computed(client, "r-all", {"kind": "rollup", "source": "v-rel", "field_id": "s-status",
                                    "aggregate": "all", "equals": "done"})
    _add_computed(client, "r-any", {"kind": "rollup", "source": "v-rel", "field_id": "s-status",
                                    "aggregate": "any", "equals": "done"})
    _add_computed(client, "r-none", {"kind": "rollup", "source": "v-rel", "field_id": "s-status",
                                     "aggregate": "none", "equals": "failed"})
    values = _values(client)
    assert values["V1"]["r-all"] is False
    assert values["V1"]["r-any"] is True
    assert values["V1"]["r-none"] is True
    # 空集合：all/none 为真，any 为假
    assert values["V0"]["r-all"] is True
    assert values["V0"]["r-any"] is False
    assert values["V0"]["r-none"] is True


def test_rollup_min_max_count_distinct(env):
    client, _ = env
    _add_computed(client, "r-min", {"kind": "rollup", "source": "v-rel", "field_id": "s-num", "aggregate": "min"})
    _add_computed(client, "r-max", {"kind": "rollup", "source": "v-rel", "field_id": "s-num", "aggregate": "max"})
    _add_computed(client, "r-distinct", {"kind": "rollup", "source": "v-rel", "field_id": "s-status",
                                         "aggregate": "count_distinct"})
    _add_computed(client, "r-dt-min", {"kind": "rollup", "source": "v-rel", "field_id": "s-dt", "aggregate": "min"})
    values = _values(client)
    assert values["V1"]["r-min"] == 3
    assert values["V1"]["r-max"] == 5
    assert values["V1"]["r-distinct"] == 2
    assert values["V1"]["r-dt-min"] == "2026-01-01T00:00:00+08:00"
    assert values["V0"]["r-min"] is None


def test_and(env):
    client, _ = env
    _add_computed(client, "a-basic", {
        "kind": "and",
        "conditions": [{"field_id": "v-num", "equals": 2}, {"field_id": "v-doc", "equals": "done"}],
    })
    values = _values(client)
    assert values["V1"]["a-basic"] is True
    assert values["V0"]["a-basic"] is False


def test_and_null_is_false(env):
    client, _ = env
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    })
    _add_computed(client, "a-null", {
        "kind": "and",
        "conditions": [{"field_id": "c-pct", "equals": 100}],
    })
    values = _values(client)
    assert values["V1"]["a-null"] is False
    assert values["V0"]["a-null"] is False


def test_computed_referenced_by_and_uses_computed_value(env):
    client, _ = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    _add_computed(client, "a-count", {
        "kind": "and",
        "conditions": [{"field_id": "c-count", "equals": 3}],
    })
    values = _values(client)
    assert values["V1"]["a-count"] is True
    assert values["V0"]["a-count"] is False


# ---------- 写侧触发与读侧零计算 ----------

def test_source_update_recomputes_in_same_write(env):
    client, _ = env
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    })
    assert _values(client)["V1"]["c-pct"] == 66.7
    client.patch("/api/agent/tables/t-src/rows/S2", json={"values": {"s-status": "done"}}, headers=HEADERS)
    assert _values(client)["V1"]["c-pct"] == 100.0


def test_relation_value_change_recomputes(env):
    client, _ = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    client.patch("/api/agent/tables/t-ver/rows/V1", json={"values": {"v-rel": ["S1"]}}, headers=HEADERS)
    assert _values(client)["V1"]["c-count"] == 1


def test_dangling_relation_is_ignored(env):
    client, _ = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    })
    assert client.delete("/api/agent/tables/t-src/rows/S2", headers=HEADERS).json()["result"] == "success"
    values = _values(client)
    assert values["V1"]["c-count"] == 2
    assert values["V1"]["c-pct"] == 100.0


def test_read_side_does_not_compute(env):
    client, db = env
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    })
    assert _values(client)["V1"]["c-pct"] == 66.7
    # 直接改底层源数据，不触发重算：读接口仍返回落库旧值
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT data FROM row_records WHERE table_id = 't-src' AND id = 'S2'"
        ).fetchone()
        values = json.loads(row[0])
        values["s-status"] = "done"
        conn.execute(
            "UPDATE row_records SET data = ? WHERE table_id = 't-src' AND id = 'S2'",
            (json.dumps(values, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()
    assert _values(client)["V1"]["c-pct"] == 66.7
    # 显式重算后才变化
    recomputed = client.post("/api/agent/tables/t-ver/recompute", headers=HEADERS)
    assert recomputed.json()["result"] == "success"
    assert _values(client)["V1"]["c-pct"] == 100.0


def test_recompute_is_idempotent(env):
    client, db = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    before = _computed_values(db)
    first = client.post("/api/agent/tables/t-ver/recompute", headers=HEADERS).json()
    second = client.post("/api/agent/tables/t-ver/recompute", headers=HEADERS).json()
    assert first["result"] == second["result"] == "success"
    assert second["changed"] == 0
    assert _computed_values(db) == before


def test_recompute_requires_table_and_agent(env):
    client, _ = env
    assert client.post("/api/agent/tables/nope/recompute", headers=HEADERS).status_code == 400
    assert client.post("/api/agent/tables/t-ver/recompute").status_code == 400


# ---------- 覆盖 ----------

def test_override_wins_over_recompute(env):
    client, db = env
    _add_computed(client, "c-bug", {
        "kind": "and",
        "conditions": [{"field_id": "v-num", "equals": 2}],
        "allow_override": True,
    })
    response = client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bug": {"value": False, "reason": "已知问题，不影响发布"}}},
        headers=HEADERS,
    )
    assert response.json()["result"] == "success"
    assert _values(client)["V1"]["c-bug"] is False
    row = _row_payload(client, "t-ver", "V1")
    assert row["computed_meta"]["c-bug"]["overridden"] is True
    assert row["computed_meta"]["c-bug"]["override_reason"] == "已知问题，不影响发布"

    # 改源数据触发重算，覆盖仍然生效
    client.patch("/api/agent/tables/t-ver/rows/V1", json={"values": {"v-num": 9}}, headers=HEADERS)
    assert _values(client)["V1"]["c-bug"] is False
    # 清除覆盖后立即按当前值重算（v-num=9 → 条件不成立）
    client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bug": {"value": None}}},
        headers=HEADERS,
    )
    assert _values(client)["V1"]["c-bug"] is False
    assert _row_payload(client, "t-ver", "V1")["computed_meta"]["c-bug"]["overridden"] is False


def test_clear_override_recomputes_true(env):
    client, _ = env
    _add_computed(client, "c-bug", {
        "kind": "and",
        "conditions": [{"field_id": "v-num", "equals": 2}],
        "allow_override": True,
    })
    client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bug": {"value": False, "reason": "临时关闭"}}},
        headers=HEADERS,
    )
    client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bug": {"value": None}}},
        headers=HEADERS,
    )
    assert _values(client)["V1"]["c-bug"] is True


def test_override_validation(env):
    client, _ = env
    _add_computed(client, "c-bool", {
        "kind": "and",
        "conditions": [{"field_id": "v-num", "equals": 2}],
        "allow_override": True,
    })
    _add_computed(client, "c-locked", {
        "kind": "count", "source": "v-rel",
    })
    # 缺少原因
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bool": {"value": False}}}, headers=HEADERS,
    ).status_code == 400
    # 类型不匹配
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bool": {"value": 1, "reason": "x"}}}, headers=HEADERS,
    ).status_code == 400
    # 非计算字段
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"v-num": {"value": 1, "reason": "x"}}}, headers=HEADERS,
    ).status_code == 400
    # 未开启 allow_override
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-locked": {"value": 1, "reason": "x"}}}, headers=HEADERS,
    ).status_code == 400
    # 清除不存在的覆盖
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bool": {"value": None}}}, headers=HEADERS,
    ).status_code == 400


def test_override_affects_dependent_and(env):
    client, _ = env
    _add_computed(client, "c-base", {
        "kind": "and",
        "conditions": [{"field_id": "v-num", "equals": 2}],
        "allow_override": True,
    })
    _add_computed(client, "c-top", {
        "kind": "and",
        "conditions": [{"field_id": "c-base", "equals": True}],
    })
    assert _values(client)["V1"]["c-top"] is True
    client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-base": {"value": False, "reason": "人工判定"}}},
        headers=HEADERS,
    )
    assert _values(client)["V1"]["c-top"] is False
    client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-base": {"value": None}}},
        headers=HEADERS,
    )
    assert _values(client)["V1"]["c-top"] is True


def test_override_writes_business_change(env):
    client, db = env
    _add_computed(client, "c-bool", {
        "kind": "and",
        "conditions": [{"field_id": "v-num", "equals": 2}],
        "allow_override": True,
    })
    client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"overrides": {"c-bool": {"value": False, "reason": "人工确认"}}},
        headers=HEADERS,
    )
    rows = _query(
        db,
        "SELECT change_kind, old_value, new_value, reason FROM business_changes"
        " WHERE table_id='t-ver' AND row_id='V1' AND field_id='c-bool' ORDER BY id DESC LIMIT 1",
    )
    assert rows[0]["change_kind"] == "override"
    assert json.loads(rows[0]["old_value"]) is True
    assert json.loads(rows[0]["new_value"]) is False
    assert rows[0]["reason"] == "人工确认"


# ---------- 配置校验 ----------

def test_direct_write_computed_rejected(env):
    client, db = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    before = _computed_values(db)
    assert client.post(
        "/api/agent/tables/t-ver/rows/V2", json={"values": {"c-count": 1}}, headers=HEADERS
    ).status_code == 400
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1", json={"values": {"c-count": 1}}, headers=HEADERS
    ).status_code == 400
    assert _computed_values(db) == before


def test_computed_config_validation(env):
    client, db = env
    before = len(_query(db, "SELECT id FROM fields WHERE table_id='t-ver'"))
    bad_configs = [
        {"kind": "unknown", "source": "v-rel"},
        {"kind": "count", "source": "v-missing"},
        {"kind": "count", "source": "v-num"},
        {"kind": "sum", "source": "v-rel"},
        {"kind": "sum", "source": "v-rel", "field_id": "s-status"},
        {"kind": "rollup", "source": "v-rel", "field_id": "s-status", "aggregate": "all"},
        {"kind": "rollup", "source": "v-rel", "field_id": "s-status", "aggregate": "min"},
        {"kind": "percent", "source": "v-rel", "decimals": 2},
        {"kind": "and", "conditions": []},
        {"kind": "and", "conditions": [{"field_id": "v-num", "equals": None}]},
        {"kind": "and", "conditions": [{"field_id": "nope", "equals": 1}]},
    ]
    for index, options in enumerate(bad_configs):
        response = _add_computed(client, f"bad-{index}", options)
        assert response.status_code == 400, (options, response.json())
    after = len(_query(db, "SELECT id FROM fields WHERE table_id='t-ver'"))
    assert after == before


def test_referenced_field_type_change_rejected(env):
    client, db = env
    _add_computed(client, "c-sum", {"kind": "sum", "source": "v-rel", "field_id": "s-num"})
    response = client.patch(
        "/api/agent/fields/s-num", json={"type": "text"}, headers=HEADERS
    )
    assert response.status_code == 400
    field = _query(db, "SELECT type FROM fields WHERE id='s-num'")[0]
    assert field["type"] == "number"


def test_cycle_rejected(env):
    client, _ = env
    assert _add_computed(client, "c-a", {
        "kind": "and", "conditions": [{"field_id": "v-num", "equals": 2}],
    }).json()["result"] == "success"
    assert _add_computed(client, "c-b", {
        "kind": "and", "conditions": [{"field_id": "v-num", "equals": 2}],
    }).json()["result"] == "success"
    first = client.patch(
        "/api/agent/fields/c-a",
        json={"options": {"kind": "and", "conditions": [{"field_id": "c-b", "equals": True}]}},
        headers=HEADERS,
    )
    assert first.json()["result"] == "success"
    second = client.patch(
        "/api/agent/fields/c-b",
        json={"options": {"kind": "and", "conditions": [{"field_id": "c-a", "equals": True}]}},
        headers=HEADERS,
    )
    assert second.status_code == 400
    assert "成环" in second.json()["error"]


def test_delete_referenced_field_and_table_rejected(env):
    client, _ = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    assert client.delete("/api/agent/fields/v-rel", headers=HEADERS).status_code == 400
    assert client.delete("/api/agent/tables/t-src", headers=HEADERS).status_code == 400
    # 先删计算字段，再删 relation 字段即可
    assert client.delete("/api/agent/fields/c-count", headers=HEADERS).json()["result"] == "success"
    assert client.delete("/api/agent/fields/v-rel", headers=HEADERS).json()["result"] == "success"


# ---------- 失败回滚 ----------

def test_recompute_failure_rolls_back(env, monkeypatch):
    client, db = env
    _add_computed(client, "c-pct", {
        "kind": "percent", "source": "v-rel",
        "where": {"field_id": "s-status", "equals": "done"}, "decimals": 1,
    })
    before_rows = _query(db, "SELECT id, data FROM row_records ORDER BY table_id, id")
    before_computed = _computed_values(db)
    before_changes = len(_query(db, "SELECT id FROM business_changes"))
    before_audit = len(_query(db, "SELECT id FROM write_audit"))

    def boom(*args, **kwargs):
        raise RuntimeError("注入的计算异常")

    monkeypatch.setattr(calculation, "compute_value", boom)
    response = client.patch(
        "/api/agent/tables/t-src/rows/S2", json={"values": {"s-status": "done"}}, headers=HEADERS
    )
    assert response.status_code == 400
    assert "计算失败" in response.json()["error"]

    assert _query(db, "SELECT id, data FROM row_records ORDER BY table_id, id") == before_rows
    assert _computed_values(db) == before_computed
    assert len(_query(db, "SELECT id FROM business_changes")) == before_changes
    audit = _query(db, "SELECT result, error FROM write_audit ORDER BY id DESC LIMIT 1")
    assert len(_query(db, "SELECT id FROM write_audit")) == before_audit + 1
    assert audit[0]["result"] == "failed"


def test_repository_does_not_import_calculation():
    from tableflow import repository

    source = Path(repository.__file__).read_text(encoding="utf-8")
    assert "calculation" not in source


def test_hidden_computed_is_computed_but_not_returned(env):
    client, db = env
    response = client.post(
        "/api/agent/tables/t-ver/fields",
        json={"id": "c-hidden", "name": "隐藏计算", "type": "computed", "visible": 0,
              "options": {"kind": "count", "source": "v-rel"}},
        headers=HEADERS,
    )
    assert response.json()["result"] == "success"
    payload = client.get("/api/tables/t-ver/table").json()
    assert "c-hidden" not in {field["id"] for field in payload["fields"]}
    stored = _query(
        db, "SELECT value FROM computed_values WHERE table_id='t-ver' AND row_id='V1' AND field_id='c-hidden'"
    )
    assert stored and json.loads(stored[0]["value"]) == 3


def test_missing_computed_values_returns_null(env):
    client, db = env
    _add_computed(client, "c-count", {"kind": "count", "source": "v-rel"})
    conn = sqlite3.connect(db)
    try:
        conn.execute("DELETE FROM computed_values WHERE table_id='t-ver' AND row_id='V1'")
        conn.commit()
    finally:
        conn.close()
    row = _row_payload(client, "t-ver", "V1")
    assert row["values"]["c-count"] is None
    assert "c-count" not in (row["computed_meta"] or {})


def test_rebuild_computed_values_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "rebuild-computed.db"
    monkeypatch.setenv("TABLEFLOW_DB", str(db))

    def snapshot():
        return _query(
            db,
            "SELECT table_id, row_id, field_id, value, override_value FROM computed_values"
            " ORDER BY table_id, row_id, field_id",
        )

    with TestClient(app) as client:
        rebuild_v030.rebuild(db, client, backup=False)
        first = snapshot()
        rebuild_v030.rebuild(db, client, backup=False)
        second = snapshot()
    assert first and first == second


# ---------- tf 项目落地实例 ----------

def test_tf_project_computed_fields(tmp_path, monkeypatch):
    db = tmp_path / "tf-formula.db"
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        rebuild_v030.rebuild(db, client, backup=False)
        payload = client.get("/api/tables/tf-ver/table").json()
        fields = {field["id"]: field for field in payload["fields"]}
        assert fields["tf-v-dev"]["type"] == "computed"
        assert fields["tf-v-cond"]["type"] == "computed"
        assert "tf-v-bug" not in fields
        assert fields["tf-v-bug-open"]["type"] == "number"

        rows = {row["id"]: row["values"] for row in payload["rows"]}
        assert rows["v0.3.0"]["tf-v-dev"] == 33.3
        assert rows["v0.3.0"]["tf-v-cond"] is False
        assert rows["v0.3.0"]["tf-v-bug-clear"] is True
        assert rows["v0.3.0"]["tf-v-regress"] is True
        assert rows["v0.3.0"]["tf-v-dep-count"] == 1
        assert rows["v0.3.0"]["tf-v-scenes"] == 12
        assert rows["v0.3.0"]["tf-v-tasks"] == 30
        # v0.2.0 四条件全满足
        assert rows["v0.2.0"]["tf-v-dev"] == 100.0
        assert rows["v0.2.0"]["tf-v-cond"] is True

        # 手工改底层数据但不重算：读接口仍返回旧值
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT data FROM row_records WHERE table_id='tf-indep' AND id='003-AR'"
            ).fetchone()
            values = json.loads(row[0])
            values["tf-i-implement"] = "done"
            conn.execute(
                "UPDATE row_records SET data = ? WHERE table_id='tf-indep' AND id='003-AR'",
                (json.dumps(values, ensure_ascii=False),),
            )
            conn.commit()
        finally:
            conn.close()
        rows = {row["id"]: row["values"] for row in client.get("/api/tables/tf-ver/table").json()["rows"]}
        assert rows["v0.3.0"]["tf-v-dev"] == 33.3

        # 显式重算后跟着变（2/3 = 66.7）
        assert client.post("/api/agent/tables/tf-ver/recompute", headers=HEADERS).json()["result"] == "success"
        rows = {row["id"]: row["values"] for row in client.get("/api/tables/tf-ver/table").json()["rows"]}
        assert rows["v0.3.0"]["tf-v-dev"] == 66.7

        # 经写接口把 004 也改为完成 → 100.0；再把文档改为完成 → 发布条件为是
        client.patch(
            "/api/agent/tables/tf-indep/rows/004-AR",
            json={"values": {"tf-i-implement": "done"}},
            headers=HEADERS,
        )
        rows = {row["id"]: row["values"] for row in client.get("/api/tables/tf-ver/table").json()["rows"]}
        assert rows["v0.3.0"]["tf-v-dev"] == 100.0
        assert rows["v0.3.0"]["tf-v-cond"] is False
        client.patch(
            "/api/agent/tables/tf-ver/rows/v0.3.0",
            json={"values": {"tf-v-doc": "done"}},
            headers=HEADERS,
        )
        rows = {row["id"]: row["values"] for row in client.get("/api/tables/tf-ver/table").json()["rows"]}
        assert rows["v0.3.0"]["tf-v-cond"] is True
