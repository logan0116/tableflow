"""v0.8.3 缺陷显现化：后端复现用例（第一批）。

这些用例描述的是**期望行为**，在 v0.8.2 上全部失败——失败本身就是交付物：
它证明“这个问题我们能自己测出来”，而不是靠人工点。

编号与 `specs/verify-v080.md` 的台账一致（B1/B2/B5…）。
修复完成前用 `xfail(strict=True)` 标记：测试必须失败才算通过登记；
一旦修复，strict 会让 xpass 变成硬失败，强制移除标记。
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
WAIVED = [
    {"value": "none", "label": "未放行", "tone": "neutral"},
    {"value": "waived", "label": "已放行", "tone": "warning"},
]

TEST_ACCEPT = "v-stage-test-accept"
PASS_RUN = "v0.8.3--042-US1-AS1"
FAIL_RUN = "v0.8.3--042-US1-AS2"


def _field(fid, name, type_, options, order):
    return {"id": fid, "name": name, "type": type_, "options": options, "order": order, "visible": 1}


def run_row(row_id: str, state: str, result: str | None) -> dict:
    return {
        "id": row_id,
        "values": {
            "r-id": row_id,
            "r-case-no": row_id.split("--", 1)[1],
            "r-state": state,
            "r-result": result,
            "r-waived": "none",
        },
    }


def board(*, runs, version_values=None, deps=None, versions=None, project_id="p083"):
    """六表最小集合；``versions`` 给定时覆盖默认版本行（多版本测试用）。"""
    ver_values = {
        "v-version": "v0.8.3",
        **{fid: "done" for fid, _ in STAGE_NAMES},
        "v-runs": [row["id"] for row in runs],
        "v-bugs": [],
        "v-dep": [],
    }
    ver_values.update(version_values or {})
    rows = versions or [{"id": "v0.8.3", "values": ver_values}]
    return {
        "projects": [
            {
                "id": project_id,
                "name": "083 缺陷复现",
                "tables": [
                    {
                        "id": "t-ver",
                        "name": "版本管理",
                        "order": 1,
                        "fields": [
                            _field("v-version", "版本号", "text", None, 1),
                            *[_field(fid, name, "enum", STAGES, i + 2) for i, (fid, name) in enumerate(STAGE_NAMES)],
                            _field("v-runs", "测试用例", "relation", {"table_id": "t-run"}, 9),
                            _field("v-bugs", "Bug管理", "relation", {"table_id": "t-bug"}, 10),
                            _field("v-indep", "独立需求管理", "relation", {"table_id": "t-indep"}, 11),
                            _field("v-dep", "依赖需求管理", "relation", {"table_id": "t-dep"}, 12),
                        ],
                        "rows": rows,
                    },
                    {
                        "id": "t-run",
                        "name": "用例执行情况",
                        "order": 2,
                        "fields": [
                            _field("r-id", "执行编号", "text", None, 1),
                            _field("r-case-no", "用例号", "text", None, 2),
                            _field("r-state", "执行状态", "enum", RUN_STATE, 3),
                            _field("r-result", "执行结果", "enum", RUN_RESULT, 4),
                            _field("r-waived", "放行标记", "enum", WAIVED, 5),
                            _field("r-by", "放行批准人", "text", None, 6),
                            _field("r-reason", "放行理由", "text", None, 7),
                        ],
                        "rows": runs,
                    },
                    {
                        "id": "t-case",
                        "name": "测试用例",
                        "order": 3,
                        "fields": [
                            _field("c-id", "用例编号", "text", None, 1),
                            _field("c-spec", "来源规格", "relation", {"table_id": "t-indep"}, 2),
                        ],
                        "rows": [],
                    },
                    {
                        "id": "t-indep",
                        "name": "独立规格需求",
                        "order": 4,
                        "fields": [
                            _field("i-id", "编号", "text", None, 1),
                            _field("i-accept", "验收状态", "enum", ACCEPT, 2),
                        ],
                        "rows": [
                            {"id": "042-AR", "values": {"i-id": "042-AR", "i-accept": "accepted"}},
                        ],
                    },
                    {
                        "id": "t-dep",
                        "name": "依赖变更需求",
                        "order": 5,
                        "fields": [
                            _field("d-id", "编号", "text", None, 1),
                            _field("d-regress", "回归状态", "enum", REGRESS, 2),
                            _field("d-affected", "受影响范围", "text", None, 3),
                            _field("d-consistency", "一致性检查", "text", None, 4),
                            _field("d-integration", "集成验证", "text", None, 5),
                            _field("d-evidence", "证据", "text", None, 6),
                        ],
                        "rows": deps or [],
                    },
                    {
                        "id": "t-bug",
                        "name": "缺陷",
                        "order": 6,
                        "fields": [
                            _field("b-id", "编号", "text", None, 1),
                        ],
                        "rows": [],
                    },
                ],
            }
        ]
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """按需构造：``env(build=...)`` 返回指向新库的 TestClient。"""

    def _make(data: dict) -> TestClient:
        db = tmp_path / "regress_083.db"
        write_seed(db, data)
        monkeypatch.setenv("TABLEFLOW_DB", str(db))
        return TestClient(app)

    return _make


def _patched(env, values: dict):
    return env.patch(
        "/api/agent/tables/t-ver/rows/v0.8.3",
        json={"values": values},
        headers=HEADERS,
    )


@pytest.mark.xfail(strict=True, reason="B1：判定只读本请求提交的执行行，摘掉 fail 行即可通过验收")
def test_b1_shrinking_run_list_must_not_close(env) -> None:
    """同一请求里把 runs 缩减为只含 pass，再置测试验收 done，必须 400（036 FR-009）。"""
    runs = [run_row(PASS_RUN, "done", "pass"), run_row(FAIL_RUN, "done", "fail")]
    with env(board(runs=runs, version_values={TEST_ACCEPT: "todo"})) as client:
        resp = _patched(client, {TEST_ACCEPT: "done", "v-runs": [PASS_RUN]})
        assert resp.status_code == 400, f"缩减执行清单后仍然通过了验收：{resp.status_code} {resp.text}"
        assert FAIL_RUN in resp.json()["error"]


@pytest.mark.xfail(strict=True, reason="B1：空执行清单被当成“没有可判定的行”，直接放行")
def test_b1_empty_run_list_must_not_close(env) -> None:
    """把 runs 清空再置 done，必须 400——没有任何执行记录不等于验收通过。"""
    runs = [run_row(FAIL_RUN, "done", "fail")]
    with env(board(runs=runs, version_values={TEST_ACCEPT: "todo"})) as client:
        resp = _patched(client, {TEST_ACCEPT: "done", "v-runs": []})
        assert resp.status_code == 400, f"空执行清单仍然通过了验收：{resp.status_code} {resp.text}"


@pytest.mark.xfail(strict=True, reason="B2：新建行被当成历史导入，D1 变更流校验被整体跳过")
def test_b2_new_dep_row_must_pass_change_flow(env) -> None:
    """普通 POST 新建一条 dep 并直接给 passed，缺变更证据，必须 400。"""
    with env(board(runs=[])) as client:
        resp = client.post(
            "/api/agent/tables/t-dep/rows/NEW-01",
            json={"values": {"d-id": "NEW-01", "d-regress": "passed"}},
            headers=HEADERS,
        )
        assert resp.status_code == 400, f"新建行绕过变更流：{resp.status_code} {resp.text}"
        assert "D1" in resp.json()["error"]
