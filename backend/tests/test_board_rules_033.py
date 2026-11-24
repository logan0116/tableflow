"""033：交付唯一性与先后校验（C1/C2/C3）。

对应 `specs/033-delivery-vs-spec/spec.md` 与 board@5 规则：
- C1 同一独立需求在所有版本中最多出现一次；
- C2 同一依赖需求在所有版本中最多出现一次；
- C3 依赖需求所在版本不得早于其关联独立需求所在版本，允许同版本，多份取最晚；
- 只校验本次新增：存量违规不阻断无关字段的编辑。

表识别口径：恰好六个四态 enum 的版本表；关系角色按目标表判据枚举值域识别
（acceptance → indep，regress → dep）。
"""

from __future__ import annotations

import copy

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
]
REGRESS = [
    {"value": "todo", "label": "未合入", "tone": "neutral"},
    {"value": "doing", "label": "已合入待验", "tone": "info"},
    {"value": "passed", "label": "通过", "tone": "success"},
    {"value": "failed", "label": "不通过", "tone": "danger"},
]


def _version_row(row_id: str, specs=(), deps=(), **extra):
    return {
        "id": row_id,
        "values": {
            "v-version": row_id,
            **{fid: "todo" for fid, _ in STAGE_NAMES},
            "v-specs": list(specs),
            "v-dep": list(deps),
            **extra,
        },
    }


BASE = {
    "projects": [
        {
            "id": "p033",
            "name": "033 交付唯一性",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本管理",
                    "order": 1,
                    "fields": [
                        {"id": "v-version", "name": "版本号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        *[
                            {"id": fid, "name": name, "type": "enum", "options": STAGES,
                             "order": i + 2, "visible": 1}
                            for i, (fid, name) in enumerate(STAGE_NAMES)
                        ],
                        {"id": "v-specs", "name": "独立需求管理", "type": "relation",
                         "options": {"table_id": "t-indep"}, "order": 9, "visible": 1},
                        {"id": "v-dep", "name": "依赖需求管理", "type": "relation",
                         "options": {"table_id": "t-dep"}, "order": 10, "visible": 1},
                        {"id": "v-note", "name": "变更说明", "type": "text", "options": None,
                         "order": 11, "visible": 1},
                    ],
                    "rows": [_version_row("v0.1.0"), _version_row("v0.2.0")],
                },
                {
                    "id": "t-indep",
                    "name": "独立规格需求",
                    "order": 2,
                    "fields": [
                        {"id": "i-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "i-accept", "name": "验收状态", "type": "enum",
                         "options": ACCEPT, "order": 2, "visible": 1},
                    ],
                    "rows": [
                        {"id": "033-AR", "values": {"i-id": "033-AR", "i-accept": "accepted"}},
                        {"id": "034-AR", "values": {"i-id": "034-AR", "i-accept": "accepted"}},
                    ],
                },
                {
                    "id": "t-dep",
                    "name": "依赖变更需求",
                    "order": 3,
                    "fields": [
                        {"id": "d-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "d-regress", "name": "回归状态", "type": "enum",
                         "options": REGRESS, "order": 2, "visible": 1},
                        {"id": "d-spec", "name": "关联的独立规格需求", "type": "relation",
                         "options": {"table_id": "t-indep"}, "order": 3, "visible": 1},
                    ],
                    "rows": [
                        {"id": "DEP-A", "values": {"d-id": "DEP-A", "d-regress": "todo",
                                                   "d-spec": ["033-AR"]}},
                        {"id": "DEP-B", "values": {"d-id": "DEP-B", "d-regress": "todo",
                                                   "d-spec": ["033-AR", "034-AR"]}},
                    ],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "board_rules_033.db"
    # BASE 是模块级夹具，个别用例会就地改它；深拷贝避免跨用例污染。
    write_seed(db, copy.deepcopy(BASE))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client


def attach(env, version: str, field: str, ids: list[str]):
    return env.patch(
        f"/api/agent/tables/t-ver/rows/{version}", json={"values": {field: ids}}, headers=HEADERS
    )


# ---------- C1 ----------


def test_c1_rejects_same_spec_in_second_version(env) -> None:
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    resp = attach(env, "v0.2.0", "v-specs", ["033-AR"])
    assert resp.status_code == 400
    body = resp.json()
    assert "C1" in body["error"]
    assert "v0.1.0" in body["error"]
    # 零写入
    row = env.get("/api/tables/t-ver/rows/v0.2.0").json()
    assert not (row.get("row") or row)["values"].get("v-specs")


def test_c1_allows_distinct_specs(env) -> None:
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    assert attach(env, "v0.2.0", "v-specs", ["034-AR"]).status_code == 200


# ---------- C2 ----------


def test_c2_rejects_same_change_in_second_version(env) -> None:
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    assert attach(env, "v0.1.0", "v-dep", ["DEP-A"]).status_code == 200
    resp = attach(env, "v0.2.0", "v-dep", ["DEP-A"])
    assert resp.status_code == 400
    assert "C2" in resp.json()["error"]


# ---------- C3 ----------


def test_c3_rejects_dep_before_spec_version(env) -> None:
    assert attach(env, "v0.2.0", "v-specs", ["033-AR"]).status_code == 200
    resp = attach(env, "v0.1.0", "v-dep", ["DEP-A"])
    assert resp.status_code == 400
    assert "C3" in resp.json()["error"]
    assert "v0.2.0" in resp.json()["error"]


def test_c3_allows_same_version(env) -> None:
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    assert attach(env, "v0.1.0", "v-dep", ["DEP-A"]).status_code == 200


def test_c3_same_request_attach_spec_and_dep(env) -> None:
    resp = env.patch(
        "/api/agent/tables/t-ver/rows/v0.1.0",
        json={"values": {"v-specs": ["033-AR"], "v-dep": ["DEP-A"]}},
        headers=HEADERS,
    )
    assert resp.status_code == 200


def test_c3_multi_spec_uses_latest(env) -> None:
    # DEP-B 关联 033-AR 与 034-AR；后者在 v0.2.0，因此 DEP-B 不能挂到 v0.1.0
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    assert attach(env, "v0.2.0", "v-specs", ["034-AR"]).status_code == 200
    resp = attach(env, "v0.1.0", "v-dep", ["DEP-B"])
    assert resp.status_code == 400
    assert "C3" in resp.json()["error"]
    assert "v0.2.0" in resp.json()["error"]


# ---------- 只校验新增 ----------


def test_existing_violation_does_not_block_unrelated_edit(tmp_path, monkeypatch) -> None:
    """存量已违规时（两个版本共享同一规格），改无关字段不得被拦。"""
    base = copy.deepcopy(BASE["projects"][0])
    for table in base["tables"]:
        if table["id"] == "t-ver":
            table["rows"] = [
                _version_row("v0.1.0", specs=["033-AR"]),
                _version_row("v0.2.0", specs=["033-AR"]),
            ]
    db = tmp_path / "board_rules_033_legacy.db"
    write_seed(db, {"projects": [base]})
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        resp = client.patch(
            "/api/agent/tables/t-ver/rows/v0.2.0",
            json={"values": {"v-note": "只改备注"}},
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text


def test_rejection_is_atomic(env) -> None:
    """拒绝时目标行保持操作前状态，且返回体带规则号与已占用版本。"""
    # 同一文件的测试共用底层连接，先清干净两个版本的关联
    for version in ("v0.1.0", "v0.2.0"):
        assert attach(env, version, "v-specs", []).status_code == 200
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    before = env.get("/api/tables/t-ver/rows/v0.2.0").json()
    before = (before.get("row") or before)["values"]

    resp = attach(env, "v0.2.0", "v-specs", ["033-AR"])
    assert resp.status_code == 400
    body = resp.json()["error"]
    assert body.startswith("C1")
    assert "v0.1.0" in body

    after = env.get("/api/tables/t-ver/rows/v0.2.0").json()
    after = (after.get("row") or after)["values"]
    assert after.get("v-specs") == before.get("v-specs")


def test_033_us4_as1_rejection_carries_four_elements(env) -> None:
    """US4-AS1：拒绝体必须含规则号、冲突行 id、已占用版本号与修复建议。"""
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    after = env.get("/api/tables/t-ver/rows/v0.1.0").json()
    assert (after.get("row") or after)["values"]["v-specs"] == ["033-AR"], "第一次挂载没写入"
    resp = attach(env, "v0.2.0", "v-specs", ["033-AR"])
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert "C1" in error, "缺规则号"
    assert "033-AR" in error, "缺冲突行 id"
    assert "v0.1.0" in error, "缺已占用版本号"
    assert "纳入" in error or "建议" in error, "缺修复建议"


def test_035_us4_as1_rejection_suggests_using_cases(env) -> None:
    """US4-AS1（035）：复测历史能力时提示改为纳入用例，而不是重复挂需求。"""
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    resp = attach(env, "v0.2.0", "v-specs", ["033-AR"])
    assert resp.status_code == 400, resp.text
    assert "用例" in resp.json()["error"], "没有提示改为纳入用例"


def test_040_us1_as1_direct_api_write_is_rejected(env) -> None:
    """US1-AS1（040）：直接调接口挂载重复需求返回 4xx，且零写入。"""
    assert attach(env, "v0.1.0", "v-specs", ["033-AR"]).status_code == 200
    resp = attach(env, "v0.2.0", "v-specs", ["033-AR"])
    assert 400 <= resp.status_code < 500, resp.text
    row = env.get("/api/tables/t-ver/rows/v0.2.0").json()
    assert not (row.get("row") or row)["values"].get("v-specs"), "被拒绝后仍写入了关联"
