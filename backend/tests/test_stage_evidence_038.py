"""038：阶段置 done 必须留下可定位证据。

对应 `specs/038-stage-evidence/spec.md` 与 board@5 规则：
- `stage_done_needs_evidence` 状态从非 done 变为 done 时，`阶段证据` 必须有对应行；
- `stage_unprovable` 历史已 done 但无证据视为「无法证明」，不回改、不阻断无关编辑；
- 只校验状态变化的那一次写入。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

STAGE = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "na", "label": "不适用", "tone": "neutral"},
]
ACCEPT = [
    {"value": "pending", "label": "未验收", "tone": "neutral"},
    {"value": "accepted", "label": "已验收", "tone": "success"},
    {"value": "rejected", "label": "未通过", "tone": "danger"},
    {"value": "dropped", "label": "已放弃", "tone": "neutral"},
]


def project(rows):
    return {
        "projects": [
            {
                "id": "p038",
                "name": "038 阶段证据",
                "tables": [
                    {
                        "id": "e-indep",
                        "name": "独立规格需求",
                        "order": 1,
                        "fields": [
                            {"id": "i-id", "name": "编号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            {"id": "i-plan", "name": "speckit-plan状态", "type": "enum",
                             "options": STAGE, "order": 2, "visible": 1},
                            {"id": "i-implement", "name": "speckit-implement状态", "type": "enum",
                             "options": STAGE, "order": 3, "visible": 1},
                            {"id": "i-evidence", "name": "阶段证据", "type": "text",
                             "options": None, "order": 4, "visible": 1},
                            {"id": "i-accept", "name": "验收状态", "type": "enum",
                             "options": ACCEPT, "order": 5, "visible": 1},
                        ],
                        "rows": rows,
                    }
                ],
            }
        ]
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "stage_evidence_038.db"
    write_seed(db, project([
        {"id": "038-AR", "values": {"i-id": "038-AR", "i-plan": "todo",
                                    "i-accept": "pending"}},
    ]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client


def patch(env, values):
    return env.patch("/api/agent/tables/e-indep/rows/038-AR",
                     json={"values": values}, headers=HEADERS)


def test_done_without_evidence_is_rejected(env) -> None:
    resp = patch(env, {"i-plan": "done"})
    assert resp.status_code == 400
    assert "必须留下证据" in resp.json()["error"]
    assert "plan=" in resp.json()["error"]


def test_done_with_evidence_is_allowed(env) -> None:
    resp = patch(env, {"i-evidence": "plan=specs/038/plan.md（回链 11 条场景）",
                       "i-plan": "done"})
    assert resp.status_code == 200, resp.text


def test_evidence_written_first_then_status(env) -> None:
    assert patch(env, {"i-evidence": "plan=specs/038/plan.md"}).status_code == 200
    assert patch(env, {"i-plan": "done"}).status_code == 200


def test_na_does_not_need_evidence(env) -> None:
    assert patch(env, {"i-plan": "na"}).status_code == 200


def test_doing_does_not_need_evidence(env) -> None:
    assert patch(env, {"i-plan": "doing"}).status_code == 200


def test_historical_done_without_evidence_is_not_rewritten(tmp_path, monkeypatch) -> None:
    """存量已 done 但无证据：改无关字段不得被拦，也不回改状态。"""
    db = tmp_path / "stage_evidence_legacy.db"
    write_seed(db, project([
        {"id": "038-AR", "values": {"i-id": "038-AR", "i-plan": "done",
                                    "i-accept": "accepted"}},
    ]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        resp = client.patch("/api/agent/tables/e-indep/rows/038-AR",
                            json={"values": {"i-accept": "accepted"}}, headers=HEADERS)
        assert resp.status_code == 200, resp.text


def test_evidence_keys_are_independent(env) -> None:
    """有 plan 证据不能顺带满足 implement。"""
    resp = patch(env, {"i-evidence": "plan=specs/038/plan.md", "i-implement": "done"})
    assert resp.status_code == 400
    assert "implement=" in resp.json()["error"]


def test_parse_evidence_ignores_noise() -> None:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    src = root / "backend" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from tableflow import stage_evidence

    parsed = stage_evidence.parse_evidence(
        "随便一句没有等号的话\nplan=specs/a/plan.md\n  task = tasks.md  \n=空键\n"
    )
    assert parsed == {"plan": "specs/a/plan.md", "task": "tasks.md"}


def test_stage_report_marks_missing_evidence_unprovable(tmp_path, monkeypatch) -> None:
    """历史 done 但无证据 -> unprovable；有证据的不算。"""
    db = tmp_path / "stage_report.db"
    write_seed(db, project([
        {"id": "038-AR", "values": {"i-id": "038-AR", "i-plan": "done",
                                    "i-implement": "done",
                                    "i-evidence": "implement=pytest 260 passed",
                                    "i-accept": "pending"}},
    ]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        body = client.get("/api/projects/p038/stages", params={"spec": "038-AR"}).json()
    assert body["stages"]["plan"]["value"] == "done"
    assert body["stages"]["plan"]["unprovable"] is True
    assert body["stages"]["implement"]["unprovable"] is False
    assert body["unprovable"] == ["plan"]


def test_stage_report_404_for_unknown_spec(env) -> None:
    assert env.get("/api/projects/p038/stages", params={"spec": "nope"}).status_code == 404
