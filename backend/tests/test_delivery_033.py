"""033 T001：交付记录与当前生效修订查询。

对应 `specs/033-delivery-vs-spec/spec.md` US1 与 FR-006：

- 给定 spec 编号或规格目录，返回首次建立它的独立需求所在版本；
- 返回历次依赖需求（含回归状态与规格修订）；
- 当前生效修订 = 最近一条「回归状态=passed 且 规格修订=done」的依赖需求；
  没有则为首次修订，来源指向独立需求。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

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


def version(row_id, specs=(), deps=()):
    return {
        "id": row_id,
        "values": {
            "v-version": row_id,
            **{fid: "todo" for fid, _ in STAGE_NAMES},
            "v-specs": list(specs),
            "v-dep": list(deps),
        },
    }


BASE = {
    "projects": [
        {
            "id": "p033q",
            "name": "033 交付记录",
            "tables": [
                {
                    "id": "q-ver",
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
                         "options": {"table_id": "q-indep"}, "order": 9, "visible": 1},
                        {"id": "v-dep", "name": "依赖需求管理", "type": "relation",
                         "options": {"table_id": "q-dep"}, "order": 10, "visible": 1},
                    ],
                    "rows": [
                        version("v0.1.0", specs=["026-AR"], deps=[]),
                        version("v0.2.0", specs=["027-AR"], deps=["DEP-A", "DEP-B"]),
                    ],
                },
                {
                    "id": "q-indep",
                    "name": "独立规格需求",
                    "order": 2,
                    "fields": [
                        {"id": "i-id", "name": "编号", "type": "text",
                         "options": None, "order": 1, "visible": 1},
                        {"id": "i-dir", "name": "规格目录", "type": "text",
                         "options": None, "order": 2, "visible": 1},
                        {"id": "i-accept", "name": "验收状态", "type": "enum",
                         "options": ACCEPT, "order": 3, "visible": 1},
                    ],
                    "rows": [
                        {"id": "026-AR", "values": {"i-id": "026-AR",
                                                    "i-dir": "specs/026-ver-columns/",
                                                    "i-accept": "accepted"}},
                        {"id": "027-AR", "values": {"i-id": "027-AR",
                                                    "i-dir": "specs/027-ver-filter/",
                                                    "i-accept": "accepted"}},
                    ],
                },
                {
                    "id": "q-dep",
                    "name": "依赖变更需求",
                    "order": 3,
                    "fields": [
                        {"id": "d-id", "name": "编号", "type": "text",
                         "options": None, "order": 1, "visible": 1},
                        {"id": "d-spec", "name": "关联的独立规格需求", "type": "relation",
                         "options": {"table_id": "q-indep"}, "order": 2, "visible": 1},
                        {"id": "d-regress", "name": "回归状态", "type": "enum",
                         "options": REGRESS, "order": 3, "visible": 1},
                        {"id": "d-rev", "name": "规格修订", "type": "enum",
                         "options": REVISION, "order": 4, "visible": 1},
                    ],
                    "rows": [
                        {"id": "DEP-A", "values": {"d-id": "DEP-A", "d-spec": ["027-AR"],
                                                   "d-regress": "passed", "d-rev": "done"}},
                        {"id": "DEP-B", "values": {"d-id": "DEP-B", "d-spec": ["026-AR"],
                                                   "d-regress": "failed", "d-rev": "pending"}},
                    ],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "delivery_033.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client


def get(env, **params):
    return env.get("/api/projects/p033q/delivery", params=params)


def test_spec_without_changes_reports_initial_revision(env) -> None:
    body = get(env, spec="026-AR").json()
    assert body["delivered_in"] == "v0.1.0"
    assert body["current_revision"]["source"] == "initial"
    assert body["current_revision"]["version"] == "v0.1.0"
    assert body["current_revision"]["dep"] is None


def test_spec_with_effective_change_reports_that_change(env) -> None:
    body = get(env, spec="027-AR").json()
    assert body["current_revision"]["source"] == "change"
    assert body["current_revision"]["dep"] == "DEP-A"
    assert body["current_revision"]["version"] == "v0.2.0"


def test_unpassed_change_is_listed_but_not_effective(env) -> None:
    body = get(env, spec="026-AR").json()
    assert [item["dep"] for item in body["all_changes"]] == ["DEP-B"]
    assert body["effective_revisions"] == []
    assert body["current_revision"]["source"] == "initial"


def test_lookup_by_spec_dir(env) -> None:
    body = get(env, dir="specs/026-ver-columns/").json()
    assert body["spec"] == "026-AR"


def test_lookup_by_spec_dir_without_slash(env) -> None:
    body = get(env, dir="specs/027-ver-filter").json()
    assert body["spec"] == "027-AR"


def test_unknown_dir_returns_404(env) -> None:
    assert get(env, dir="specs/does-not-exist/").status_code == 404


def test_missing_params_returns_404(env) -> None:
    assert get(env).status_code == 404
