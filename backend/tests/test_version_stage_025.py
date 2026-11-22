"""025：版本表六节点四态与串行/闸门校验。

对应 `specs/025-version-stage/spec.md`：
- 串行推进：后序节点置 done 要求前序全部 done；前序 failed 时后序不得推进（跳级 400）；
- 节点闸门一致性：「测试」要求用例全部执行、「测试验收」要求缺陷清零且变更回归通过、
  「开发验收」要求本版规格全部 accepted；任一不满足 400 且零写入；
- 不自动回退下游节点、不提供跳过取值；
- 六节点全 done 时 `stage_done`/`gate`（夹具按 board@4 规则定义，真实迁移归 T4）为真。

识别口径：恰好六个值域为 {todo,doing,done,failed} 的 enum 字段即六节点；
节点闸门依赖的 relation 按目标表值域识别（run/bug/dep/indep）。
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}
RUN_ID = "v0.7.0--025-US1-AS1"

STAGES = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]
STAGE_NAMES = (
    ("tf-v-stage-plan", "版本需求设计"),
    ("tf-v-stage-test-design", "测试设计"),
    ("tf-v-stage-dev", "开发"),
    ("tf-v-stage-dev-accept", "开发验收"),
    ("tf-v-stage-test", "测试"),
    ("tf-v-stage-test-accept", "测试验收"),
)
NODE = {name: field_id for field_id, name in STAGE_NAMES}
PLAN, TEST_DESIGN, DEV = NODE["版本需求设计"], NODE["测试设计"], NODE["开发"]
DEV_ACCEPT, TEST, TEST_ACCEPT = NODE["开发验收"], NODE["测试"], NODE["测试验收"]

BASE = {
    "projects": [
        {
            "id": "p025",
            "name": "025 六节点",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本管理",
                    "order": 1,
                    "fields": [
                        {"id": "tf-v-version", "name": "版本号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        *[
                            {
                                "id": field_id,
                                "name": name,
                                "type": "enum",
                                "options": STAGES,
                                "order": index + 2,
                                "visible": 1,
                            }
                            for index, (field_id, name) in enumerate(STAGE_NAMES)
                        ],
                        {"id": "tf-v-specs", "name": "独立需求管理", "type": "relation",
                         "options": {"table_id": "t-indep"}, "order": 9, "visible": 1},
                        {"id": "tf-v-changes", "name": "依赖需求管理", "type": "relation",
                         "options": {"table_id": "t-dep"}, "order": 10, "visible": 1},
                        {"id": "tf-v-runs", "name": "测试用例", "type": "relation",
                         "options": {"table_id": "t-run"}, "order": 11, "visible": 1},
                        {"id": "tf-v-bugs", "name": "Bug管理", "type": "relation",
                         "options": {"table_id": "t-bug"}, "order": 12, "visible": 1},
                        {"id": "tf-v-note", "name": "变更说明", "type": "text", "options": None,
                         "order": 13, "visible": 1},
                    ],
                    "rows": [
                        {
                            "id": "v0.7.0",
                            "values": {
                                "tf-v-version": "v0.7.0",
                                **{field_id: "todo" for field_id, _ in STAGE_NAMES},
                                "tf-v-specs": ["025-AR"],
                                "tf-v-changes": ["D01"],
                                "tf-v-runs": [RUN_ID],
                                "tf-v-bugs": ["BUG-01"],
                            },
                        }
                    ],
                },
                {
                    "id": "t-indep",
                    "name": "独立规格需求",
                    "order": 2,
                    "fields": [
                        {"id": "i-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "i-acceptance", "name": "验收状态", "type": "enum",
                         "options": [
                             {"value": "pending", "label": "待验收", "tone": "neutral"},
                             {"value": "accepted", "label": "已验收", "tone": "success"},
                             {"value": "rejected", "label": "已拒绝", "tone": "danger"},
                         ], "order": 2, "visible": 1},
                    ],
                    "rows": [{"id": "025-AR", "values": {"i-id": "025-AR", "i-acceptance": "pending"}}],
                },
                {
                    "id": "t-dep",
                    "name": "依赖需求",
                    "order": 3,
                    "fields": [
                        {"id": "d-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "d-regress", "name": "回归状态", "type": "enum",
                         "options": [
                             {"value": "todo", "label": "未合入", "tone": "neutral"},
                             {"value": "doing", "label": "待验", "tone": "info"},
                             {"value": "passed", "label": "通过", "tone": "success"},
                             {"value": "failed", "label": "失败", "tone": "danger"},
                         ], "order": 2, "visible": 1},
                    ],
                    "rows": [{"id": "D01", "values": {"d-id": "D01", "d-regress": "todo"}}],
                },
                {
                    "id": "t-run",
                    "name": "用例执行情况",
                    "order": 4,
                    "fields": [
                        {"id": "r-id", "name": "执行编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "r-case_no", "name": "用例号", "type": "text", "options": None,
                         "order": 2, "visible": 1},
                        {"id": "r-state", "name": "执行状态", "type": "enum",
                         "options": [
                             {"value": "todo", "label": "待执行", "tone": "neutral"},
                             {"value": "done", "label": "已执行", "tone": "success"},
                         ], "order": 3, "visible": 1},
                        {"id": "r-result", "name": "执行结果", "type": "enum",
                         "options": [
                             {"value": "pass", "label": "通过", "tone": "success"},
                             {"value": "fail", "label": "失败", "tone": "danger"},
                             {"value": "blocked", "label": "阻塞", "tone": "warning"},
                             {"value": "skip", "label": "跳过", "tone": "info"},
                         ], "order": 4, "visible": 1},
                    ],
                    "rows": [
                        {
                            "id": RUN_ID,
                            "values": {"r-case_no": "025-US1-AS1", "r-state": "todo"},
                        }
                    ],
                },
                {
                    "id": "t-bug",
                    "name": "缺陷",
                    "order": 5,
                    "fields": [
                        {"id": "b-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "b-status", "name": "状态", "type": "enum",
                         "options": [
                             {"value": "open", "label": "待修", "tone": "danger"},
                             {"value": "fixing", "label": "修复中", "tone": "warning"},
                             {"value": "verifying", "label": "待验", "tone": "info"},
                             {"value": "closed", "label": "已关闭", "tone": "success"},
                         ], "order": 2, "visible": 1},
                    ],
                    "rows": [{"id": "BUG-01", "values": {"b-id": "BUG-01", "b-status": "open"}}],
                },
                {
                    "id": "t-other",
                    "name": "其它表",
                    "order": 6,
                    "fields": [
                        {"id": "o-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "o-status", "name": "状态", "type": "enum", "options": STAGES,
                         "order": 2, "visible": 1},
                    ],
                    "rows": [{"id": "O1", "values": {"o-id": "O1", "o-status": "todo"}}],
                },
                {
                    "id": "t-ver-odd",
                    "name": "版本（非惯例字段 id）",
                    "order": 7,
                    "fields": [
                        {"id": "s0", "name": "版本号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        *[
                            {"id": f"s{index + 1}", "name": name, "type": "enum",
                             "options": STAGES, "order": index + 2, "visible": 1}
                            for index, (_field_id, name) in enumerate(STAGE_NAMES)
                        ],
                    ],
                    "rows": [{"id": "v9.9.9", "values": {"s0": "v9.9.9", **{f"s{i}": "todo" for i in range(1, 7)}}}],
                },
            ],
        }
    ]
}

STAGE_DONE = "tf-v-stage-done"
GATE = "tf-v-gate"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "version_stage_025.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        # 夹具按 board@4 契约定义 stage_done / gate（真实数据层迁移归 T4，这里只验证计算口径）
        created = client.post(
            "/api/agent/tables/t-ver/fields",
            json={
                "id": STAGE_DONE,
                "name": "六节点是否全部完成",
                "type": "computed",
                "options": {
                    "kind": "and",
                    "gate": True,
                    "conditions": [
                        {"field_id": field_id, "equals": "done"}
                        for field_id, _name in STAGE_NAMES
                    ],
                },
            },
            headers=HEADERS,
        )
        assert created.status_code == 200, created.text
        created = client.post(
            "/api/agent/tables/t-ver/fields",
            json={
                "id": GATE,
                "name": "发布条件",
                "type": "computed",
                "options": {
                    "kind": "and",
                    "gate": True,
                    "conditions": [{"field_id": STAGE_DONE, "equals": True}],
                },
            },
            headers=HEADERS,
        )
        assert created.status_code == 200, created.text
        yield client, db


def _patch_ver(client, values: dict):
    return client.patch(
        "/api/agent/tables/t-ver/rows/v0.7.0", json={"values": values}, headers=HEADERS
    )


def _stage(**values: str) -> dict:
    return {NODE[name]: value for name, value in values.items()}


def _row(db, table: str, row_id: str) -> dict:
    conn = sqlite3.connect(db)
    try:
        raw = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table, row_id)
        ).fetchone()
        return json.loads(raw[0]) if raw else {}
    finally:
        conn.close()


def _values(client, table: str) -> dict[str, dict]:
    payload = client.get(f"/api/tables/{table}/table").json()
    return {row["id"]: row["values"] for row in payload["rows"]}


def _changes(db, table: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT count(*) FROM business_changes WHERE table_id = ?", (table,)
        ).fetchone()[0]
    finally:
        conn.close()


def _satisfy_evidence(client) -> None:
    """把三类证据一次性做到满足：规格 accepted、用例 done、缺陷 closed、变更 passed。"""
    assert client.patch(
        "/api/agent/tables/t-indep/rows/025-AR",
        json={"values": {"i-acceptance": "accepted"}}, headers=HEADERS,
    ).status_code == 200
    assert client.patch(
        f"/api/agent/tables/t-run/rows/{RUN_ID}",
        json={"values": {"r-state": "done", "r-result": "pass"}}, headers=HEADERS,
    ).status_code == 200
    assert client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01",
        json={"values": {"b-status": "closed"}}, headers=HEADERS,
    ).status_code == 200
    assert client.patch(
        "/api/agent/tables/t-dep/rows/D01",
        json={"values": {"d-regress": "passed"}}, headers=HEADERS,
    ).status_code == 200


def _advance_all_six(client) -> None:
    for key in ("版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收"):
        resp = _patch_ver(client, _stage(**{key: "done"}))
        assert resp.status_code == 200, (key, resp.text)


# ---------- 一、串行推进 ----------

def test_skip_node_rejected_zero_write(env):
    """US1-AS1：跳级（第2节点直接 done）→ 400，零写入。"""
    client, db = env
    before = _changes(db, "t-ver")

    resp = _patch_ver(client, _stage(测试设计="done"))

    assert resp.status_code == 400
    body = resp.json()
    assert body["result"] == "failed"
    assert "串行推进" in body["error"]
    assert _row(db, "t-ver", "v0.7.0")[TEST_DESIGN] == "todo"
    assert _changes(db, "t-ver") == before


def test_skip_to_later_node_rejected(env):
    """US1-AS2：第4节点直接 done（前三个 todo）→ 400，错误列出未完成前序。"""
    client, _db = env
    resp = _patch_ver(client, _stage(开发验收="done"))

    assert resp.status_code == 400
    error = resp.json()["error"]
    assert "串行推进" in error
    assert "版本需求设计" in error and "测试设计" in error and "开发" in error


def test_serial_forward_allowed_in_order(env):
    """US1-AS3：按顺序逐节点推进（证据同步满足）→ 全 200。"""
    client, _db = env
    _satisfy_evidence(client)

    assert _patch_ver(client, _stage(版本需求设计="done")).status_code == 200
    assert _patch_ver(client, _stage(测试设计="done")).status_code == 200
    assert _patch_ver(client, _stage(开发="done")).status_code == 200
    assert _patch_ver(client, _stage(开发验收="done")).status_code == 200
    assert _patch_ver(client, _stage(测试="done")).status_code == 200
    assert _patch_ver(client, _stage(测试验收="done")).status_code == 200


def test_failed_predecessor_blocks_forward_and_rework_unblocks(env):
    """US1-AS4：前序 failed 时后序不得推进；返工改回 doing 后可继续。"""
    client, db = env
    assert _patch_ver(client, _stage(版本需求设计="done")).status_code == 200
    assert _patch_ver(client, _stage(测试设计="done")).status_code == 200
    assert _patch_ver(client, _stage(开发="failed")).status_code == 200

    blocked = _patch_ver(client, _stage(开发验收="doing"))
    assert blocked.status_code == 400
    assert "failed" in blocked.json()["error"]
    assert _row(db, "t-ver", "v0.7.0")[DEV_ACCEPT] == "todo"

    # 反向移动不受串行规则约束（未"推进"）
    assert _patch_ver(client, _stage(开发验收="todo")).status_code == 200
    # 返工：失败节点改回 doing，再推进
    assert _patch_ver(client, _stage(开发="doing")).status_code == 200
    assert _patch_ver(client, _stage(开发验收="doing")).status_code == 200


def test_no_auto_rollback_of_downstream(env):
    """US1-AS5：把前序节点改回 failed 不自动回退下游节点（契约由人判断影响面）。"""
    client, db = env
    _satisfy_evidence(client)
    _advance_all_six(client)

    resp = _patch_ver(client, _stage(开发="failed"))

    assert resp.status_code == 200
    values = _row(db, "t-ver", "v0.7.0")
    assert values[DEV] == "failed"
    assert values[DEV_ACCEPT] == "done"
    assert values[TEST] == "done"
    assert values[TEST_ACCEPT] == "done"


# ---------- 二、节点闸门一致性 ----------

def test_dev_accept_requires_specs_accepted(env):
    """US2-AS1：开发验收置 done 而本版规格仍 pending → 400，零写入。"""
    client, db = env
    for key in ("版本需求设计", "测试设计", "开发"):
        assert _patch_ver(client, _stage(**{key: "done"})).status_code == 200

    resp = _patch_ver(client, _stage(开发验收="done"))

    assert resp.status_code == 400
    error = resp.json()["error"]
    assert "开发验收" in error and "accepted" in error and "025-AR" in error
    assert _row(db, "t-ver", "v0.7.0")[DEV_ACCEPT] == "todo"

    assert client.patch(
        "/api/agent/tables/t-indep/rows/025-AR",
        json={"values": {"i-acceptance": "accepted"}}, headers=HEADERS,
    ).status_code == 200
    assert _patch_ver(client, _stage(开发验收="done")).status_code == 200


def test_test_requires_all_runs_done(env):
    """US2-AS2：测试置 done 而本版仍有未执行用例 → 400；执行后可推进。"""
    client, db = env
    _satisfy_evidence(client)
    assert client.patch(
        f"/api/agent/tables/t-run/rows/{RUN_ID}",
        json={"values": {"r-state": "todo", "r-result": None}}, headers=HEADERS,
    ).status_code == 200
    for key in ("版本需求设计", "测试设计", "开发", "开发验收"):
        assert _patch_ver(client, _stage(**{key: "done"})).status_code == 200

    resp = _patch_ver(client, _stage(测试="done"))

    assert resp.status_code == 400
    assert RUN_ID in resp.json()["error"] and "done" in resp.json()["error"]
    assert _row(db, "t-ver", "v0.7.0")[TEST] == "todo"

    assert client.patch(
        f"/api/agent/tables/t-run/rows/{RUN_ID}",
        json={"values": {"r-state": "done", "r-result": "pass"}}, headers=HEADERS,
    ).status_code == 200
    assert _patch_ver(client, _stage(测试="done")).status_code == 200


def test_test_accept_requires_bug_clear(env):
    """US2-AS3：测试验收置 done 而缺陷未清零 → 400（错误指名未关闭缺陷）。"""
    client, db = env
    _satisfy_evidence(client)
    assert client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01",
        json={"values": {"b-status": "fixing"}}, headers=HEADERS,
    ).status_code == 200
    for key in ("版本需求设计", "测试设计", "开发", "开发验收", "测试"):
        assert _patch_ver(client, _stage(**{key: "done"})).status_code == 200

    resp = _patch_ver(client, _stage(测试验收="done"))

    assert resp.status_code == 400
    assert "BUG-01" in resp.json()["error"] and "closed" in resp.json()["error"]
    assert _row(db, "t-ver", "v0.7.0")[TEST_ACCEPT] == "todo"


def test_test_accept_requires_change_regressed(env):
    """US2-AS4：缺陷清零但变更回归未通过 → 400（错误指名变更单）。"""
    client, db = env
    _satisfy_evidence(client)
    assert client.patch(
        "/api/agent/tables/t-dep/rows/D01",
        json={"values": {"d-regress": "doing"}}, headers=HEADERS,
    ).status_code == 200
    for key in ("版本需求设计", "测试设计", "开发", "开发验收", "测试"):
        assert _patch_ver(client, _stage(**{key: "done"})).status_code == 200

    resp = _patch_ver(client, _stage(测试验收="done"))

    assert resp.status_code == 400
    assert "D01" in resp.json()["error"] and "passed" in resp.json()["error"]
    assert _row(db, "t-ver", "v0.7.0")[TEST_ACCEPT] == "todo"


def test_gate_computed_true_when_all_six_done(env):
    """US3-AS1：六节点全 done 时 stage_done 与 gate 为真（夹具按 board@4 规则定义）。"""
    client, _db = env
    _satisfy_evidence(client)
    _advance_all_six(client)

    values = _values(client, "t-ver")["v0.7.0"]
    assert values[STAGE_DONE] is True
    assert values[GATE] is True


def test_gate_turns_false_after_node_rollback(env):
    """US3-AS3：六节点全 done 后把某节点改回 doing，stage_done 与 gate 随重算转假。"""
    client, _db = env
    _satisfy_evidence(client)
    _advance_all_six(client)

    assert _values(client, "t-ver")["v0.7.0"][GATE] is True
    assert _patch_ver(client, _stage(开发="doing")).status_code == 200
    values = _values(client, "t-ver")["v0.7.0"]
    assert values[STAGE_DONE] is False
    assert values[GATE] is False


def test_empty_set_gates_pass_on_new_version(env):
    """US2-AS5：新建版本未关联任何证据时，空集语义让三处闸门放行（create 路径同样受校验）。"""
    client, db = env
    created = client.post(
        "/api/agent/tables/t-ver/rows/v0.8.0",
        json={
            "values": {
                "tf-v-version": "v0.8.0",
                **{field_id: "todo" for field_id, _name in STAGE_NAMES},
            }
        },
        headers=HEADERS,
    )
    assert created.status_code == 200, created.text
    # 新建时把第 2 节点直接置 done（跳级）→ 400，零写入
    skipped = client.post(
        "/api/agent/tables/t-ver/rows/v0.9.0",
        json={
            "values": {
                "tf-v-version": "v0.9.0",
                **{field_id: "todo" for field_id, _name in STAGE_NAMES},
                TEST_DESIGN: "done",
            }
        },
        headers=HEADERS,
    )
    assert skipped.status_code == 400
    assert "串行推进" in skipped.json()["error"]

    for key in ("版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收"):
        resp = client.patch(
            "/api/agent/tables/t-ver/rows/v0.8.0",
            json={"values": _stage(**{key: "done"})},
            headers=HEADERS,
        )
        assert resp.status_code == 200, (key, resp.text)
    values = _values(client, "t-ver")["v0.8.0"]
    assert values[STAGE_DONE] is True and values[GATE] is True
    assert _row(db, "t-ver", "v0.8.0")[TEST_ACCEPT] == "done"


def test_replay_same_done_does_not_revalidate_gate(env):
    """US3-AS2：节点已是 done 时改无关字段不再验闸门（闸门只在到达 done 那一刻把关）。"""
    client, db = env
    _satisfy_evidence(client)
    _advance_all_six(client)
    # 缺陷回退后 gate 不自动转假（六节点仍全 done）；修无关字段也不被卡住
    assert client.patch(
        "/api/agent/tables/t-bug/rows/BUG-01",
        json={"values": {"b-status": "open"}}, headers=HEADERS,
    ).status_code == 200

    resp = _patch_ver(client, {"tf-v-note": "只改说明"})

    assert resp.status_code == 200
    assert _values(client, "t-ver")["v0.7.0"][GATE] is True
    assert _row(db, "t-ver", "v0.7.0")[TEST_ACCEPT] == "done"


# ---------- 三、识别口径与不误伤 ----------

def test_non_version_table_with_one_stage_enum_untouched(env):
    """US4-AS1：只有 1 个四态 enum 的普通表不套用六节点校验。"""
    client, db = env
    resp = client.patch(
        "/api/agent/tables/t-other/rows/O1",
        json={"values": {"o-status": "done"}}, headers=HEADERS,
    )

    assert resp.status_code == 200
    assert _row(db, "t-other", "O1")["o-status"] == "done"


def test_stage_nodes_resolved_by_name_when_ids_unconventional(env):
    """US4-AS2：节点字段 id 非 `stage-*` 时按契约名称解析顺序，串行校验仍生效。"""
    client, db = env

    def patch_odd(values: dict):
        return client.patch(
            "/api/agent/tables/t-ver-odd/rows/v9.9.9",
            json={"values": values}, headers=HEADERS,
        )

    # s4 = 开发验收（第4节点），前三个 todo → 400
    resp = patch_odd({"s4": "done"})
    assert resp.status_code == 400
    assert "串行推进" in resp.json()["error"]

    assert patch_odd({"s1": "done"}).status_code == 200
    assert patch_odd({"s2": "done"}).status_code == 200
    assert _row(db, "t-ver-odd", "v9.9.9")["s2"] == "done"
