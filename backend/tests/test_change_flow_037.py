"""037：依赖需求的完整变更流。

对应 `specs/037-dep-change-workflow/spec.md` 与 board@5 规则：
- 回归状态置 passed 前，受影响条款、一致性检查、集成验收三项都必须非空；
- 规格修订取 not_needed 时必须有判定依据（证据非空）；
- 新建行（历史导入）不校验；未迁移的表没有这些字段时也不阻断。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

REGRESS = [
    {"value": "todo", "label": "未合入", "tone": "neutral"},
    {"value": "doing", "label": "已合入待验", "tone": "info"},
    {"value": "passed", "label": "通过", "tone": "success"},
    {"value": "failed", "label": "不通过", "tone": "danger"},
]
REVISION = [
    {"value": "not_needed", "label": "无需修订", "tone": "neutral"},
    {"value": "pending", "label": "待写回", "tone": "info"},
    {"value": "done", "label": "已写回", "tone": "success"},
]

FULL_FIELDS = [
    {"id": "d-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
    {"id": "d-regress", "name": "回归状态", "type": "enum", "options": REGRESS, "order": 2, "visible": 1},
    {"id": "d-affected", "name": "受影响条款", "type": "text", "options": None, "order": 3, "visible": 1},
    {"id": "d-consistency", "name": "一致性检查", "type": "text", "options": None, "order": 4, "visible": 1},
    {"id": "d-integration", "name": "集成验收", "type": "text", "options": None, "order": 5, "visible": 1},
    {"id": "d-evidence", "name": "证据", "type": "text", "options": None, "order": 6, "visible": 1},
    {"id": "d-revision", "name": "规格修订", "type": "enum", "options": REVISION, "order": 7, "visible": 1},
    {"id": "d-baselines", "name": "基线修订", "type": "text", "options": None, "order": 8, "visible": 1},
]

LEGACY_FIELDS = [
    {"id": "d-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
    {"id": "d-regress", "name": "回归状态", "type": "enum", "options": REGRESS, "order": 2, "visible": 1},
]

READY = {
    "d-affected": "026-AR US1-AS1、US1-AS2",
    "d-consistency": "026 与 027 的条款无冲突；028 的场景 3 需补充说明",
    "d-integration": "两规格集成验收通过，证据 commit 353ce0e",
}


def project(fields, rows):
    return {
        "projects": [
            {
                "id": "p037",
                "name": "037 变更流",
                "tables": [
                    {
                        "id": "c-dep",
                        "name": "依赖变更需求",
                        "order": 1,
                        "fields": fields,
                        "rows": rows,
                    }
                ],
            }
        ]
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "change_flow_037.db"
    write_seed(db, project(FULL_FIELDS, [
        {"id": "DEP-A", "values": {"d-id": "DEP-A", "d-regress": "todo",
                                   "d-revision": "pending"}},
    ]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client


def patch(env, values, row="DEP-A"):
    return env.patch(f"/api/agent/tables/c-dep/rows/{row}",
                     json={"values": values}, headers=HEADERS)


def test_passed_without_flow_fields_is_rejected(env) -> None:
    resp = patch(env, {"d-regress": "passed"})
    assert resp.status_code == 400
    body = resp.json()["error"]
    assert "受影响条款" in body and "一致性检查" in body and "集成验收" in body


def test_passed_with_full_flow_is_allowed(env) -> None:
    assert patch(env, {"d-regress": "doing"}).status_code == 200
    resp = patch(env, {**READY, "d-regress": "passed"})
    assert resp.status_code == 200, resp.text


def test_missing_one_field_blocks(env) -> None:
    values = {k: v for k, v in READY.items() if k != "d-integration"}
    resp = patch(env, {**values, "d-regress": "passed"})
    assert resp.status_code == 400
    assert "集成验收" in resp.json()["error"]
    assert "受影响条款" not in resp.json()["error"]


def test_not_needed_requires_evidence(env) -> None:
    resp = patch(env, {"d-revision": "not_needed"})
    assert resp.status_code == 400
    assert "判定依据" in resp.json()["error"]


def test_not_needed_with_evidence_is_allowed(env) -> None:
    resp = patch(env, {"d-revision": "not_needed", "d-evidence": "仅确认不受影响，无内容变化"})
    assert resp.status_code == 200, resp.text


def test_new_row_without_evidence_is_rejected(tmp_path, monkeypatch) -> None:
    """新建行不再享有「历史导入」豁免：没有变更证据就不能直接是 passed。

    口径变更（2026-11-24）：历史数据补不齐证据就不进看板，不为此保留旁路。
    """
    db = tmp_path / "change_flow_import.db"
    write_seed(db, project(FULL_FIELDS, []))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        resp = client.post(
            "/api/agent/tables/c-dep/rows/DEP-OLD",
            json={"values": {"d-id": "DEP-OLD", "d-regress": "passed"}},
            headers=HEADERS,
        )
        assert resp.status_code == 400, resp.text
        assert "D1" in resp.json()["error"]


def test_legacy_table_without_fields_is_not_blocked(tmp_path, monkeypatch) -> None:
    """未迁移的表没有流程字段：不猜、不阻断。"""
    db = tmp_path / "change_flow_legacy.db"
    write_seed(db, project(LEGACY_FIELDS, [
        {"id": "DEP-A", "values": {"d-id": "DEP-A", "d-regress": "todo"}},
    ]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        resp = client.patch("/api/agent/tables/c-dep/rows/DEP-A",
                            json={"values": {"d-regress": "passed"}}, headers=HEADERS)
        assert resp.status_code == 200, resp.text


def test_037_us1_as2_single_scenario_change_still_needs_four_parts(env) -> None:
    """US1-AS2：只改一条验收场景，增量说明/基线修订/受影响条款/证据仍须齐全。"""
    assert patch(env, {"d-regress": "doing"}).status_code == 200
    resp = patch(env, {**READY, "d-regress": "passed"})
    assert resp.status_code == 200, resp.text
    row = env.get("/api/tables/c-dep/rows/DEP-A").json()
    values = (row.get("row") or row)["values"]
    assert values["d-affected"], "缺受影响条款"
    assert values["d-consistency"], "缺一致性检查"
    assert values["d-integration"], "缺集成验收"


def test_037_us1_as4_integration_record_is_separate(env) -> None:
    """US1-AS4：集成验收是独立记录，不与单规格验证混同。"""
    assert patch(env, {"d-regress": "doing"}).status_code == 200
    assert patch(env, {**READY, "d-regress": "passed"}).status_code == 200
    row = env.get("/api/tables/c-dep/rows/DEP-A").json()
    values = (row.get("row") or row)["values"]
    assert values["d-integration"].strip() != values["d-consistency"].strip(), (
        "集成验收与一致性检查写成了同一段内容，说明没有独立记录"
    )


def test_037_us1_as1_multi_spec_baselines_are_separate(env) -> None:
    """US1-AS1：关联两份规格时，基线修订要能分别写清每份。"""
    baselines = "026-AR@v0.8.0\n027-AR@v0.8.1"
    assert patch(env, {"d-regress": "doing"}).status_code == 200
    resp = patch(env, {**READY, "d-baselines": baselines, "d-regress": "passed"})
    assert resp.status_code == 200, resp.text
    row = env.get("/api/tables/c-dep/rows/DEP-A").json()
    stored = (row.get("row") or row)["values"]["d-baselines"]
    assert "026-AR" in stored and "027-AR" in stored, stored


def test_037_us4_as1_missing_affected_clause_blocks(env) -> None:
    """US4-AS1：没有受影响条款时拒绝推进，并指出缺这一项。"""
    assert patch(env, {"d-regress": "doing"}).status_code == 200
    resp = patch(env, {"d-regress": "passed", "d-consistency": "无冲突",
                       "d-integration": "集成通过"})
    assert resp.status_code == 400, resp.text
    assert "受影响条款" in resp.json()["error"]
