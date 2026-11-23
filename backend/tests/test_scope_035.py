"""035：交付范围与测试范围解耦（board 侧可观测的行为）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "backend" / "src", REPO_ROOT / "skills" / "tf-test-plan" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tableflow.app import app  # noqa: E402
from tableflow.seed import write_seed  # noqa: E402
import tf_test_plan  # noqa: E402

HEADERS = {"X-Agent-Id": "agent-test"}

STAGES = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]
STAGE_NAMES = (
    ("v-stage-plan", "版本需求设计"), ("v-stage-test-design", "测试设计"),
    ("v-stage-dev", "开发"), ("v-stage-dev-accept", "开发验收"),
    ("v-stage-test", "测试"), ("v-stage-test-accept", "测试验收"),
)
ACCEPT = [
    {"value": "pending", "label": "未验收", "tone": "neutral"},
    {"value": "accepted", "label": "已验收", "tone": "success"},
    {"value": "rejected", "label": "未通过", "tone": "danger"},
    {"value": "dropped", "label": "已放弃", "tone": "neutral"},
]
RUN_STATE = [
    {"value": "todo", "label": "未执行", "tone": "neutral"},
    {"value": "done", "label": "已执行", "tone": "success"},
]
RUN_RESULT = [
    {"value": "pass", "label": "通过", "tone": "success"},
    {"value": "fail", "label": "失败", "tone": "danger"},
    {"value": "blocked", "label": "阻塞", "tone": "warning"},
    {"value": "skip", "label": "不执行", "tone": "neutral"},
]

CASE_A = "019-US1-AS1"
RUN_A = f"v0.8.0--{CASE_A}"


def base(version_specs, runs=()):
    return {"projects": [{"id": "p035", "name": "035 范围解耦", "tables": [
        {"id": "s-ver", "name": "版本管理", "order": 1, "fields": [
            {"id": "v-version", "name": "版本号", "type": "text", "options": None, "order": 1, "visible": 1},
            *[{"id": fid, "name": name, "type": "enum", "options": STAGES, "order": i + 2, "visible": 1}
              for i, (fid, name) in enumerate(STAGE_NAMES)],
            {"id": "v-specs", "name": "独立需求管理", "type": "relation",
             "options": {"table_id": "s-indep"}, "order": 9, "visible": 1},
            {"id": "v-runs", "name": "测试用例", "type": "relation",
             "options": {"table_id": "s-run"}, "order": 10, "visible": 1},
        ], "rows": [{"id": "v0.8.0", "values": {
            "v-version": "v0.8.0", **{fid: "todo" for fid, _ in STAGE_NAMES},
            "v-specs": list(version_specs), "v-runs": [r["id"] for r in runs]}}]},
        {"id": "s-indep", "name": "独立规格需求", "order": 2, "fields": [
            {"id": "i-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
            {"id": "i-accept", "name": "验收状态", "type": "enum", "options": ACCEPT, "order": 2, "visible": 1},
        ], "rows": [
            {"id": "019-AR", "values": {"i-id": "019-AR", "i-accept": "accepted"}},
            {"id": "033-AR", "values": {"i-id": "033-AR", "i-accept": "pending"}},
        ]},
        {"id": "s-case", "name": "测试用例", "order": 3, "fields": [
            {"id": "c-id", "name": "用例号", "type": "text", "options": None, "order": 1, "visible": 1},
            {"id": "c-indep", "name": "来源规格", "type": "relation",
             "options": {"table_id": "s-indep"}, "order": 2, "visible": 1},
        ], "rows": [{"id": CASE_A, "values": {"c-id": CASE_A, "c-indep": ["019-AR"]}}]},
        {"id": "s-run", "name": "用例执行情况", "order": 4, "fields": [
            {"id": "r-id", "name": "执行编号", "type": "text", "options": None, "order": 1, "visible": 1},
            {"id": "r-case", "name": "用例", "type": "relation",
             "options": {"table_id": "s-case"}, "order": 2, "visible": 1},
            {"id": "r-state", "name": "执行状态", "type": "enum", "options": RUN_STATE, "order": 3, "visible": 1},
            {"id": "r-result", "name": "执行结果", "type": "enum", "options": RUN_RESULT, "order": 4, "visible": 1},
        ], "rows": list(runs)},
    ]}]}


def make(tmp_path, monkeypatch, version_specs, runs=()):
    db = tmp_path / "scope_035.db"
    write_seed(db, base(version_specs, runs))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    return TestClient(app)


def test_version_accepts_out_of_scope_runs(tmp_path, monkeypatch) -> None:
    """v0.8.0 交付范围只有 033-AR，仍可纳入 019-AR 的用例。"""
    with make(tmp_path, monkeypatch, ["033-AR"]) as env:
        resp = env.patch(
            "/api/agent/tables/s-ver/rows/v0.8.0",
            json={"values": {"v-runs": [RUN_A]}}, headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text


def test_out_of_scope_case_does_not_change_delivery_ratio(tmp_path, monkeypatch) -> None:
    """纳入版本外用例后，交付范围仍然只有本版工作，用例范围才变化。"""
    with make(tmp_path, monkeypatch, ["033-AR"]) as env:
        before = (env.get("/api/tables/s-ver/rows/v0.8.0").json())
        before = (before.get("row") or before)["values"]
        assert before["v-specs"] == ["033-AR"]
        assert before["v-runs"] == []

        env.patch("/api/agent/tables/s-ver/rows/v0.8.0",
                  json={"values": {"v-runs": [RUN_A]}}, headers=HEADERS)
        after = (env.get("/api/tables/s-ver/rows/v0.8.0").json())
        after = (after.get("row") or after)["values"]
        assert after["v-specs"] == ["033-AR"]      # 交付范围不变
        assert after["v-runs"] == [RUN_A]          # 用例范围变了


def test_case_still_traces_to_its_spec(tmp_path, monkeypatch) -> None:
    with make(tmp_path, monkeypatch, ["033-AR"]) as env:
        row = env.get(f"/api/tables/s-case/rows/{CASE_A}").json()
        assert (row.get("row") or row)["values"]["c-indep"] == ["019-AR"]


def test_delivery_scope_only_lists_own_work(tmp_path, monkeypatch) -> None:
    with make(tmp_path, monkeypatch, ["033-AR"]) as env:
        row = env.get("/api/tables/s-ver/rows/v0.8.0").json()
        assert (row.get("row") or row)["values"]["v-specs"] == ["033-AR"]


def test_pure_regression_version_has_empty_delivery(tmp_path, monkeypatch) -> None:
    with make(tmp_path, monkeypatch, []) as env:
        row = env.get("/api/tables/s-ver/rows/v0.8.0").json()
        values = (row.get("row") or row)["values"]
        assert values["v-specs"] == []
        assert values["v-runs"] == []


def test_pure_regression_version_still_advances_nodes(tmp_path, monkeypatch) -> None:
    """交付范围为空不阻断节点推进（前序节点逐个写 done）。"""
    with make(tmp_path, monkeypatch, []) as env:
        for fid, _ in STAGE_NAMES:
            resp = env.patch("/api/agent/tables/s-ver/rows/v0.8.0",
                             json={"values": {fid: "done"}}, headers=HEADERS)
            assert resp.status_code == 200, f"{fid}: {resp.text}"


def test_missing_source_scenario_is_reported_as_orphan() -> None:
    orphans = tf_test_plan.find_orphans(
        ["019-US1-AS1", "019-US1-AS9", "033-US1-AS1"],
        ["019-US1-AS1"],
        "019",
    )
    assert orphans == ["019-US1-AS9"]


def test_same_case_gets_independent_run_per_version(tmp_path, monkeypatch) -> None:
    runs = [
        {"id": RUN_A, "values": {"r-id": RUN_A, "r-case": [CASE_A],
                                 "r-state": "todo", "r-result": None}},
        {"id": f"v0.7.4--{CASE_A}", "values": {"r-id": f"v0.7.4--{CASE_A}",
                                               "r-case": [CASE_A],
                                               "r-state": "done", "r-result": "pass"}},
    ]
    with make(tmp_path, monkeypatch, ["033-AR"], runs) as env:
        a = env.get(f"/api/tables/s-run/rows/{RUN_A}").json()
        b = env.get(f"/api/tables/s-run/rows/v0.7.4--{CASE_A}").json()
        assert (a.get("row") or a)["values"]["r-state"] == "todo"
        assert (b.get("row") or b)["values"]["r-state"] == "done"
