"""037 US3：变更逐份产出规格修订。

「受影响条款」点名了哪几份规格，就只有那几份产生修订标识
`<依赖需求编号>@<所在版本>`；未点名的不因该变更产生修订。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tableflow.app import app  # noqa: E402
from tableflow.seed import write_seed  # noqa: E402

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

BASE = {
    "projects": [{
        "id": "p037r", "name": "037 逐份修订",
        "tables": [
            {"id": "r-ver", "name": "版本管理", "order": 1, "fields": [
                {"id": "v-version", "name": "版本号", "type": "text", "options": None, "order": 1, "visible": 1},
                *[{"id": fid, "name": name, "type": "enum", "options": STAGES, "order": i + 2, "visible": 1}
                  for i, (fid, name) in enumerate(STAGE_NAMES)],
                {"id": "v-specs", "name": "独立需求管理", "type": "relation",
                 "options": {"table_id": "r-indep"}, "order": 9, "visible": 1},
                {"id": "v-dep", "name": "依赖需求管理", "type": "relation",
                 "options": {"table_id": "r-dep"}, "order": 10, "visible": 1},
            ], "rows": [{"id": "v0.1.0", "values": {
                "v-version": "v0.1.0", **{fid: "todo" for fid, _ in STAGE_NAMES},
                "v-specs": ["033-AR", "034-AR"], "v-dep": ["DEP-A"]}}]},
            {"id": "r-indep", "name": "独立规格需求", "order": 2, "fields": [
                {"id": "i-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                {"id": "i-accept", "name": "验收状态", "type": "enum", "options": ACCEPT, "order": 2, "visible": 1},
            ], "rows": [
                {"id": "033-AR", "values": {"i-id": "033-AR", "i-accept": "accepted"}},
                {"id": "034-AR", "values": {"i-id": "034-AR", "i-accept": "accepted"}},
            ]},
            {"id": "r-dep", "name": "依赖变更需求", "order": 3, "fields": [
                {"id": "d-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                {"id": "d-spec", "name": "关联的独立规格需求", "type": "relation",
                 "options": {"table_id": "r-indep"}, "order": 2, "visible": 1},
                {"id": "d-regress", "name": "回归状态", "type": "enum", "options": REGRESS, "order": 3, "visible": 1},
                {"id": "d-rev", "name": "规格修订", "type": "enum", "options": REVISION, "order": 4, "visible": 1},
                {"id": "d-affected", "name": "受影响条款", "type": "text", "options": None, "order": 5, "visible": 1},
            ], "rows": [{"id": "DEP-A", "values": {
                "d-id": "DEP-A", "d-spec": ["033-AR", "034-AR"],
                "d-regress": "passed", "d-rev": "done",
                "d-affected": "033-AR US1-AS1、US1-AS2"}}]},
        ],
    }]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "per_spec_rev.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client


def test_affected_clauses_decide_which_spec_gets_revision(env) -> None:
    """只点名了 033-AR，所以修订只挂在 033 上，034 不受影响。"""
    a = env.get("/api/projects/p037r/delivery", params={"spec": "033-AR"}).json()
    b = env.get("/api/projects/p037r/delivery", params={"spec": "034-AR"}).json()

    assert a["current_revision"]["source"] == "change"
    assert a["current_revision"]["dep"] == "DEP-A"
    assert a["current_revision"]["revision_tag"] == "DEP-A@v0.1.0"

    assert b["current_revision"]["source"] == "initial"
    assert b["effective_revisions"] == []
