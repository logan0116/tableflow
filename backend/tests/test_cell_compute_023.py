"""023 计算字段条件表达式测试：`and(字段 == 取值)`。

对应 specs/023-cell-compute/spec.md：
- A 成立与不成立：and(六节点 == done) 六个枚举节点全 done 为真，任一非 done 为假。
- B 条件跟随写入：节点状态变化后同事务重算，and 结果跟着翻转。
- C 与既有能力共存：and 引用计算字段、数字/布尔条件保持 010 口径；闸门字段拒绝覆盖。
- D 非法条件：取值类型与字段取值域不符 → 400 且不落库。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

STAGES = [
    {"value": "todo", "label": "待办", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "已完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]

# board@4 的 six nodes：六个四态枚举字段 + 版本行
NODES = ["n-plan", "n-test-design", "n-dev", "n-dev-accept", "n-test", "n-test-accept"]

DONE = {node: "done" for node in NODES}

BASE = {
    "projects": [
        {
            "id": "p023",
            "name": "023 条件表达式",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本",
                    "order": 1,
                    "fields": [
                        {"id": "v-id", "name": "版本号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        *[
                            {"id": node, "name": node, "type": "enum", "options": STAGES,
                             "order": index + 2, "visible": 1}
                            for index, node in enumerate(NODES)
                        ],
                        {"id": "v-num", "name": "数字", "type": "number", "options": None,
                         "order": 8, "visible": 1},
                        {"id": "v-cases", "name": "用例", "type": "relation",
                         "options": {"table_id": "t-case"}, "order": 9, "visible": 1},
                    ],
                    "rows": [
                        {"id": "V1", "values": {"v-id": "1.0", "v-num": 2, **DONE}},
                        {"id": "V2", "values": {"v-id": "2.0", "v-num": 2,
                                                **{**DONE, "n-test": "doing"}}},
                        {"id": "V3", "values": {"v-id": "3.0", "v-num": 5, **{
                            node: "todo" for node in NODES}}},
                        # 六节点一个都没填：null 不参与相等，条件判否
                        {"id": "V4", "values": {"v-id": "4.0"}},
                    ],
                },
                {
                    "id": "t-case",
                    "name": "用例",
                    "order": 2,
                    "fields": [
                        {"id": "c-id", "name": "用例号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                    ],
                    "rows": [{"id": "C1", "values": {"c-id": "C1"}}],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "cell_compute_023.db"
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


def _add_computed(client, field_id, options, *, table_id="t-ver"):
    return client.post(
        f"/api/agent/tables/{table_id}/fields",
        json={"id": field_id, "name": field_id, "type": "computed", "options": options},
        headers=HEADERS,
    )


def _values(client, table_id="t-ver"):
    payload = client.get(f"/api/tables/{table_id}/table").json()
    return {row["id"]: row["values"] for row in payload["rows"]}


def _stored(db, row_id, field_id, table_id="t-ver"):
    rows = _query(
        db,
        "SELECT value, override_value FROM computed_values"
        " WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (table_id, row_id, field_id),
    )
    assert rows, f"缺少计算值 {table_id}/{row_id}/{field_id}"
    value = rows[0]["value"]
    return json.loads(value) if value is not None else None


def _stage_done_options():
    return {
        "kind": "and",
        "conditions": [{"field_id": node, "equals": "done"} for node in NODES],
        "gate": True,
    }


def _field_rows_count(db):
    return len(_query(db, "SELECT id FROM fields"))


# ---------- A 成立与不成立 ----------

def test_a_and_enum_done_true_and_false(env):
    client, db = env
    assert _add_computed(client, "stage_done", _stage_done_options()).json()["result"] == "success"

    values = _values(client)
    # 六个枚举节点全 done → 真
    assert values["V1"]["stage_done"] is True
    assert _stored(db, "V1", "stage_done") is True
    # 任一节点非 done（doing / todo）→ 假
    assert values["V2"]["stage_done"] is False
    assert values["V3"]["stage_done"] is False
    assert _stored(db, "V2", "stage_done") is False
    assert _stored(db, "V3", "stage_done") is False
    # 条件字段为 null 与任何取值都不相等 → 假，不把"没填"当"完成"
    assert values["V4"]["stage_done"] is False
    assert _stored(db, "V4", "stage_done") is False


def test_a_and_single_condition_true_and_false(env):
    client, _ = env
    assert _add_computed(client, "dev_done", {
        "kind": "and", "conditions": [{"field_id": "n-dev", "equals": "done"}],
    }).json()["result"] == "success"
    values = _values(client)
    assert values["V1"]["dev_done"] is True
    assert values["V2"]["dev_done"] is True  # V2 的 dev 也是 done
    assert values["V3"]["dev_done"] is False
    assert values["V4"]["dev_done"] is False


# ---------- B 条件跟随写入 ----------

def test_b_enum_condition_follows_writes(env):
    client, db = env
    assert _add_computed(client, "stage_done", _stage_done_options()).json()["result"] == "success"
    assert _values(client)["V2"]["stage_done"] is False

    # 把最后一个非 done 节点改成 done：同一次写事务内重算，不额外调 recompute
    patched = client.patch(
        "/api/agent/tables/t-ver/rows/V2",
        json={"values": {"n-test": "done"}},
        headers=HEADERS,
    )
    assert patched.json()["result"] == "success"
    assert _values(client)["V2"]["stage_done"] is True
    assert _stored(db, "V2", "stage_done") is True

    # 任一节点退回 doing → 闸门重新判否
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"n-dev": "doing"}},
        headers=HEADERS,
    ).json()["result"] == "success"
    assert _values(client)["V1"]["stage_done"] is False
    assert _stored(db, "V1", "stage_done") is False

    # failed 与 done 不相等：不能把"失败待返工"算成完成
    assert client.patch(
        "/api/agent/tables/t-ver/rows/V1",
        json={"values": {"n-dev": "failed"}},
        headers=HEADERS,
    ).json()["result"] == "success"
    assert _values(client)["V1"]["stage_done"] is False


# ---------- C 与既有能力共存 ----------

def test_c_and_of_computed_condition_and_gate_override(env):
    client, db = env
    assert _add_computed(client, "stage_done", _stage_done_options()).json()["result"] == "success"
    # and 可引用同表计算字段：发布条件 = and(六节点是否全部完成 == true)
    assert _add_computed(client, "release_gate", {
        "kind": "and",
        "conditions": [{"field_id": "stage_done", "equals": True}],
        "gate": True,
    }).json()["result"] == "success"

    values = _values(client)
    assert values["V1"]["release_gate"] is True
    assert values["V2"]["release_gate"] is False
    assert values["V4"]["release_gate"] is False

    # 闸门字段仍拒绝人工覆盖（010），清除仍允许
    rejected = client.patch(
        "/api/agent/tables/t-ver/rows/V2",
        json={"overrides": {"release_gate": {"value": True, "reason": "人工放行"}}},
        headers=HEADERS,
    )
    assert rejected.status_code == 400
    assert "闸门" in rejected.json()["error"]
    assert _stored(db, "V2", "release_gate") is False


def test_c_existing_bool_and_number_conditions_unchanged(env):
    client, _ = env
    # 数字条件（010 已有能力）：V1/V2 的 v-num == 2
    assert _add_computed(client, "num_ok", {
        "kind": "and", "conditions": [{"field_id": "v-num", "equals": 2}],
    }).json()["result"] == "success"
    # 布尔条件引用计算字段：and(num_ok == true)
    assert _add_computed(client, "num_ok_nested", {
        "kind": "and", "conditions": [{"field_id": "num_ok", "equals": True}],
    }).json()["result"] == "success"
    # 多条件与：枚举 + 数字
    assert _add_computed(client, "mixed", {
        "kind": "and",
        "conditions": [
            {"field_id": "n-plan", "equals": "done"},
            {"field_id": "v-num", "equals": 2},
        ],
    }).json()["result"] == "success"

    values = _values(client)
    assert values["V1"]["num_ok"] is True
    assert values["V2"]["num_ok"] is True
    assert values["V3"]["num_ok"] is False
    assert values["V1"]["num_ok_nested"] is True
    assert values["V1"]["mixed"] is True
    assert values["V3"]["mixed"] is False


# ---------- D 非法条件：400 且不落库 ----------

def _invalid_condition_configs():
    return [
        # 取值类型与字段取值域不符
        ("bad-enum-number", {"kind": "and", "conditions": [{"field_id": "n-plan", "equals": 5}]}),
        ("bad-enum-bool", {"kind": "and", "conditions": [{"field_id": "n-plan", "equals": True}]}),
        # 枚举取值不在声明域内（大小写写错即永远为假）
        ("bad-enum-value", {"kind": "and", "conditions": [{"field_id": "n-plan", "equals": "Done"}]}),
        # 数字字段不能等于字符串
        ("bad-number", {"kind": "and", "conditions": [{"field_id": "v-num", "equals": "2"}]}),
        # 关联字段的值是数组，不能与标量比较
        ("bad-relation", {"kind": "and", "conditions": [{"field_id": "v-cases", "equals": "C1"}]}),
        # 结构类非法条件（既有口径，保持不变）
        ("bad-empty", {"kind": "and", "conditions": []}),
        ("bad-null", {"kind": "and", "conditions": [{"field_id": "n-plan", "equals": None}]}),
        ("bad-missing", {"kind": "and", "conditions": [{"field_id": "nope", "equals": "done"}]}),
        ("bad-item", {"kind": "and", "conditions": ["n-plan"]}),
        # 布尔计算字段不能等于数字 1
        ("bad-bool-number", {"kind": "and", "conditions": [{"field_id": "any_done", "equals": 1}]}),
    ]


def test_d_invalid_conditions_rejected_without_persistence(env):
    client, db = env
    # 造一个布尔计算字段，用于校验"布尔条件等于 1"
    assert _add_computed(client, "any_done", {
        "kind": "and", "conditions": [{"field_id": "n-plan", "equals": "done"}],
    }).json()["result"] == "success"
    before = _field_rows_count(db)

    for field_id, options in _invalid_condition_configs():
        response = _add_computed(client, field_id, options)
        assert response.status_code == 400, (field_id, response.json())
        assert isinstance(response.json().get("error"), str), (field_id, response.json())

    # 400 的配置一个都不落库：字段与计算值都没有新增
    assert _field_rows_count(db) == before
    for field_id, _ in _invalid_condition_configs():
        assert not _query(db, "SELECT id FROM fields WHERE id = ?", (field_id,))
        assert not _query(
            db, "SELECT field_id FROM computed_values WHERE field_id = ?", (field_id,)
        )


def test_d_valid_enum_value_from_declared_domain_accepted(env):
    client, _ = env
    # 域内的非 done 取值是合法条件（例如"失败待返工"单独建一个观察字段）
    assert _add_computed(client, "any_failed", {
        "kind": "and", "conditions": [{"field_id": "n-test", "equals": "failed"}],
    }).json()["result"] == "success"
    assert _values(client)["V1"]["any_failed"] is False
