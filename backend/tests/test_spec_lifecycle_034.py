"""034：独立需求的生命周期——拆分与放弃。

对应 `specs/034-scope-split-drop/spec.md` 与 board@5 规则：
- 终态只有 accepted 与 dropped；
- 放弃必须同时给出放弃理由与放弃时间，且必须先摘除版本关联；
- dropped 不可回退，已放弃的需求不得挂版本，其规格不得新开依赖需求；
- 拆分（split_log）只在需求尚未 accepted 时允许。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

STAGES = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]
STAGE_NAMES = (
    ("v-stage-plan", "版本需求设计"),
    ("v-stage-test-design", "测试设计"),
    ("v-stage-dev", "开发"),
    ("v-stage-dev-accept", "开发验收"),
    ("v-stage-test", "测试"),
    ("v-stage-test-accept", "测试验收"),
)
ACCEPT = [
    {"value": "pending", "label": "未验收", "tone": "neutral"},
    {"value": "accepted", "label": "已验收", "tone": "success"},
    {"value": "rejected", "label": "未通过", "tone": "danger"},
    {"value": "dropped", "label": "已放弃", "tone": "neutral"},
]
REGRESS = [
    {"value": "todo", "label": "未合入", "tone": "neutral"},
    {"value": "doing", "label": "已合入待验", "tone": "info"},
    {"value": "passed", "label": "通过", "tone": "success"},
    {"value": "failed", "label": "不通过", "tone": "danger"},
]
AT = "2026-11-23T20:00:00+08:00"


def base(version_specs):
    return {
        "projects": [
            {
                "id": "p034",
                "name": "034 生命周期",
                "tables": [
                    {
                        "id": "l-ver",
                        "name": "版本管理",
                        "order": 1,
                        "fields": [
                            {"id": "v-version", "name": "版本号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            *[
                                {"id": fid, "name": name, "type": "enum", "options": STAGES,
                                 "order": i + 2, "visible": 1}
                                for i, (fid, name) in enumerate(STAGE_NAMES)
                            ],
                            {"id": "v-specs", "name": "独立需求管理", "type": "relation",
                             "options": {"table_id": "l-indep"}, "order": 9, "visible": 1},
                            {"id": "v-dep", "name": "依赖需求管理", "type": "relation",
                             "options": {"table_id": "l-dep"}, "order": 10, "visible": 1},
                        ],
                        "rows": [
                            {
                                "id": "v0.1.0",
                                "values": {
                                    "v-version": "v0.1.0",
                                    **{fid: "todo" for fid, _ in STAGE_NAMES},
                                    "v-specs": list(version_specs),
                                    "v-dep": [],
                                },
                            }
                        ],
                    },
                    {
                        "id": "l-indep",
                        "name": "独立规格需求",
                        "order": 2,
                        "fields": [
                            {"id": "i-id", "name": "编号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            {"id": "i-reason", "name": "放弃理由", "type": "text",
                             "options": None, "order": 2, "visible": 1},
                            {"id": "i-at", "name": "放弃时间", "type": "datetime",
                             "options": None, "order": 3, "visible": 1},
                            {"id": "i-split", "name": "拆分记录", "type": "text",
                             "options": None, "order": 4, "visible": 1},
                            {"id": "i-accept", "name": "验收状态", "type": "enum",
                             "options": ACCEPT, "order": 5, "visible": 1},
                        ],
                        "rows": [
                            {"id": "034-AR", "values": {"i-id": "034-AR", "i-accept": "pending"}},
                            {"id": "035-AR", "values": {"i-id": "035-AR", "i-accept": "pending"}},
                            {"id": "036-AR", "values": {"i-id": "036-AR", "i-accept": "accepted"}},
                        ],
                    },
                    {
                        "id": "l-dep",
                        "name": "依赖变更需求",
                        "order": 3,
                        "fields": [
                            {"id": "d-id", "name": "编号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            {"id": "d-spec", "name": "关联的独立规格需求", "type": "relation",
                             "options": {"table_id": "l-indep"}, "order": 2, "visible": 1},
                            {"id": "d-regress", "name": "回归状态", "type": "enum",
                             "options": REGRESS, "order": 3, "visible": 1},
                        ],
                        "rows": [],
                    },
                ],
            }
        ]
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "lifecycle_034.db"
    write_seed(db, base(["034-AR"]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client


def drop(env, spec_id, **extra):
    values = {"i-accept": "dropped", **extra}
    return env.patch(f"/api/agent/tables/l-indep/rows/{spec_id}",
                     json={"values": values}, headers=HEADERS)


def test_drop_requires_reason_and_time(env) -> None:
    resp = drop(env, "034-AR")
    assert resp.status_code == 400
    assert "放弃理由" in resp.json()["error"]
    assert "放弃时间" in resp.json()["error"]


def test_drop_requires_detaching_from_version(env) -> None:
    resp = drop(env, "034-AR", **{"i-reason": "不做了", "i-at": AT})
    assert resp.status_code == 400
    assert "先摘除" in resp.json()["error"]
    assert "v0.1.0" in resp.json()["error"]


def test_drop_succeeds_after_detaching(env) -> None:
    assert env.patch("/api/agent/tables/l-ver/rows/v0.1.0",
                     json={"values": {"v-specs": []}}, headers=HEADERS).status_code == 200
    resp = drop(env, "034-AR", **{"i-reason": "能力取消", "i-at": AT})
    assert resp.status_code == 200, resp.text
    row = env.get("/api/tables/l-indep/rows/034-AR").json()
    assert (row.get("row") or row)["values"]["i-accept"] == "dropped"


def test_dropped_is_terminal(env) -> None:
    assert env.patch("/api/agent/tables/l-ver/rows/v0.1.0",
                     json={"values": {"v-specs": []}}, headers=HEADERS).status_code == 200
    assert drop(env, "034-AR", **{"i-reason": "能力取消", "i-at": AT}).status_code == 200
    resp = env.patch("/api/agent/tables/l-indep/rows/034-AR",
                     json={"values": {"i-accept": "accepted"}}, headers=HEADERS)
    assert resp.status_code == 400
    assert "终态" in resp.json()["error"]


def test_dropped_spec_cannot_be_attached(env) -> None:
    assert env.patch("/api/agent/tables/l-ver/rows/v0.1.0",
                     json={"values": {"v-specs": []}}, headers=HEADERS).status_code == 200
    assert drop(env, "034-AR", **{"i-reason": "能力取消", "i-at": AT}).status_code == 200
    resp = env.patch("/api/agent/tables/l-ver/rows/v0.1.0",
                     json={"values": {"v-specs": ["034-AR"]}}, headers=HEADERS)
    assert resp.status_code == 400
    assert "已放弃" in resp.json()["error"]


def test_dropped_spec_cannot_open_change(env) -> None:
    assert env.patch("/api/agent/tables/l-ver/rows/v0.1.0",
                     json={"values": {"v-specs": []}}, headers=HEADERS).status_code == 200
    assert drop(env, "034-AR", **{"i-reason": "能力取消", "i-at": AT}).status_code == 200
    resp = env.post("/api/agent/tables/l-dep/rows/DEP-NEW",
                    json={"values": {"d-id": "DEP-NEW", "d-spec": ["034-AR"],
                                     "d-regress": "todo"}}, headers=HEADERS)
    assert resp.status_code == 400
    assert "已放弃" in resp.json()["error"]


def test_split_allowed_before_accepted(env) -> None:
    resp = env.patch("/api/agent/tables/l-indep/rows/034-AR",
                     json={"values": {"i-split": f"{AT} 移交 US3 -> 039-AR"}}, headers=HEADERS)
    assert resp.status_code == 200, resp.text


def test_split_rejected_after_accepted(env) -> None:
    resp = env.patch("/api/agent/tables/l-indep/rows/036-AR",
                     json={"values": {"i-split": f"{AT} 移交 US1 -> 040-AR"}}, headers=HEADERS)
    assert resp.status_code == 400
    assert "尚未 accepted" in resp.json()["error"]


def test_lifecycle_report_parses_split_chain(env) -> None:
    """拆分链双向可追：本需求拆出去、以及谁拆到了本需求。"""
    # 034-AR 拆出 US3 给 035-AR（035-AR 已存在则换一个不存在的承接方）
    assert env.patch(
        "/api/agent/tables/l-indep/rows/034-AR",
        json={"values": {"i-split": "2026-11-23T20:00:00+08:00 移交 US3 -> 099-AR"}},
        headers=HEADERS,
    ).status_code == 200
    body = env.get("/api/projects/p034/lifecycle", params={"spec": "034-AR"}).json()
    assert body["split_out"] == [
        {"at": "2026-11-23T20:00:00+08:00", "clauses": "US3", "to": "099-AR"}
    ]
    # 099-AR 不存在，链节点标 exists=false
    assert body["chain"] == [{"spec": "099-AR", "exists": False}]


def test_lifecycle_report_finds_split_in(env) -> None:
    assert env.patch(
        "/api/agent/tables/l-indep/rows/034-AR",
        json={"values": {"i-split": "2026-11-23T20:00:00+08:00 移交 US3 -> 035-AR"}},
        headers=HEADERS,
    ).status_code == 200
    body = env.get("/api/projects/p034/lifecycle", params={"spec": "035-AR"}).json()
    assert [item["from"] for item in body["split_in"]] == ["034-AR"]


def test_lifecycle_report_shows_abandon_trace(tmp_path, monkeypatch) -> None:
    db = tmp_path / "lifecycle_trace.db"
    write_seed(db, base([]))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        assert client.patch(
            "/api/agent/tables/l-indep/rows/034-AR",
            json={"values": {"i-accept": "dropped", "i-reason": "能力取消", "i-at": AT}},
            headers=HEADERS,
        ).status_code == 200
        body = client.get("/api/projects/p034/lifecycle", params={"spec": "034-AR"}).json()
    assert body["acceptance"] == "dropped"
    assert body["abandon_reason"] == "能力取消"
    assert body["abandoned_at"]


def test_lifecycle_report_404_for_unknown_spec(env) -> None:
    assert env.get("/api/projects/p034/lifecycle", params={"spec": "nope"}).status_code == 404
