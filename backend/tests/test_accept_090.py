"""v0.10.2 冻结与验收回归：发布状态冻结、执行状态与结果同集合、执行行不可删。

对应 BUG-090-01/02/03。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}
RUN_ID = "v1--C1"

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

BASE = {
    "projects": [
        {
            "id": "p090a",
            "name": "090 冻结与验收",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本管理",
                    "order": 1,
                    "fields": [
                        {"id": "tf-v-version", "name": "版本号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        *[
                            {"id": field_id, "name": name, "type": "enum", "options": STAGES,
                             "order": index + 2, "visible": 1}
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
                        {"id": "tf-v-status", "name": "发布状态", "type": "enum", "options": [
                            {"value": "planned", "label": "计划", "tone": "neutral"},
                            {"value": "released", "label": "已发布", "tone": "success"},
                            {"value": "dropped", "label": "已终止", "tone": "danger"},
                        ], "order": 13, "visible": 1},
                    ],
                    "rows": [
                        {
                            "id": "v1",
                            "values": {
                                "tf-v-version": "v1",
                                **{field_id: "todo" for field_id, _ in STAGE_NAMES},
                                "tf-v-specs": [],
                                "tf-v-changes": [],
                                "tf-v-runs": [RUN_ID],
                                "tf-v-bugs": [],
                                "tf-v-status": "released",
                            },
                        },
                        {
                            "id": "v2",
                            "values": {
                                "tf-v-version": "v2",
                                **{field_id: "todo" for field_id, _ in STAGE_NAMES},
                                "tf-v-specs": [],
                                "tf-v-changes": [],
                                "tf-v-runs": ["v2--C1"],
                                "tf-v-bugs": [],
                                "tf-v-status": "planned",
                            },
                        },
                    ],
                },
                {
                    "id": "t-indep",
                    "name": "独立规格需求",
                    "order": 2,
                    "fields": [
                        {"id": "i-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "i-acceptance", "name": "验收状态", "type": "enum", "options": [
                            {"value": "pending", "label": "待验收", "tone": "neutral"},
                            {"value": "accepted", "label": "已验收", "tone": "success"},
                            {"value": "rejected", "label": "已拒绝", "tone": "danger"},
                        ], "order": 2, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-dep",
                    "name": "依赖需求",
                    "order": 3,
                    "fields": [
                        {"id": "d-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "d-regress", "name": "回归状态", "type": "enum", "options": [
                            {"value": "todo", "label": "未合入", "tone": "neutral"},
                            {"value": "doing", "label": "待验", "tone": "info"},
                            {"value": "passed", "label": "通过", "tone": "success"},
                            {"value": "failed", "label": "失败", "tone": "danger"},
                        ], "order": 2, "visible": 1},
                    ],
                    "rows": [],
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
                        {"id": "r-state", "name": "执行状态", "type": "enum", "options": [
                            {"value": "todo", "label": "待执行", "tone": "neutral"},
                            {"value": "done", "label": "已执行", "tone": "success"},
                        ], "order": 3, "visible": 1},
                        {"id": "r-result", "name": "执行结果", "type": "enum", "options": [
                            {"value": "pass", "label": "通过", "tone": "success"},
                            {"value": "fail", "label": "失败", "tone": "danger"},
                            {"value": "blocked", "label": "阻塞", "tone": "warning"},
                            {"value": "skip", "label": "跳过", "tone": "info"},
                        ], "order": 4, "visible": 1},
                        {"id": "r-waiver", "name": "放行标记", "type": "enum", "options": [
                            {"value": "none", "label": "未放行", "tone": "neutral"},
                            {"value": "waived", "label": "已放行", "tone": "warning"},
                        ], "order": 5, "visible": 1},
                        {"id": "r-waiver-by", "name": "放行批准人", "type": "text", "options": None,
                         "order": 6, "visible": 1},
                        {"id": "r-waiver-reason", "name": "放行理由", "type": "text", "options": None,
                         "order": 7, "visible": 1},
                    ],
                    "rows": [
                        {"id": RUN_ID, "values": {"r-case_no": "C1", "r-state": "todo",
                                                  "r-result": None, "r-waiver": "none"}},
                        {"id": "v2--C1", "values": {"r-case_no": "C1", "r-state": "todo",
                                                    "r-result": None, "r-waiver": "waived",
                                                    "r-waiver-by": "张三",
                                                    "r-waiver-reason": "已知问题，延期验证"}},
                    ],
                },
                {
                    "id": "t-bug",
                    "name": "缺陷",
                    "order": 5,
                    "fields": [
                        {"id": "b-id", "name": "编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "b-status", "name": "状态", "type": "enum", "options": [
                            {"value": "open", "label": "待修", "tone": "danger"},
                            {"value": "fixing", "label": "修复中", "tone": "warning"},
                            {"value": "verifying", "label": "待验", "tone": "info"},
                            {"value": "closed", "label": "已关闭", "tone": "success"},
                        ], "order": 2, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-run2",
                    "name": "孤立执行表",
                    "order": 6,
                    "fields": [
                        {"id": "r2-id", "name": "执行编号", "type": "text", "options": None,
                         "order": 1, "visible": 1},
                        {"id": "r2-case_no", "name": "用例号", "type": "text", "options": None,
                         "order": 2, "visible": 1},
                        {"id": "r2-state", "name": "执行状态", "type": "enum", "options": [
                            {"value": "todo", "label": "待执行", "tone": "neutral"},
                            {"value": "done", "label": "已执行", "tone": "success"},
                        ], "order": 3, "visible": 1},
                        {"id": "r2-result", "name": "执行结果", "type": "enum", "options": [
                            {"value": "pass", "label": "通过", "tone": "success"},
                            {"value": "fail", "label": "失败", "tone": "danger"},
                            {"value": "blocked", "label": "阻塞", "tone": "warning"},
                            {"value": "skip", "label": "跳过", "tone": "info"},
                        ], "order": 4, "visible": 1},
                    ],
                    "rows": [{"id": "x--C1", "values": {"r2-case_no": "C1", "r2-state": "todo"}}],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "accept-090.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    monkeypatch.delenv("TABLEFLOW_AUTH_MODE", raising=False)
    with TestClient(app) as client:
        yield client, db


def _patch(client, row, values):
    return client.patch(f"/api/agent/tables/t-ver/rows/{row}",
                        json={"values": values}, headers=HEADERS)


def _advance_to_test(client, version="v2"):
    for name in ("版本需求设计", "测试设计", "开发", "开发验收"):
        response = _patch(client, version, {NODE[name]: "done"})
        assert response.status_code == 200, response.text


# ---------- BUG-090-03 发布状态冻结 ----------

def test_released_status_cannot_revert_to_planned(env):
    client, _ = env
    response = _patch(client, "v1", {"tf-v-status": "planned"})
    assert response.status_code == 400
    assert "发布状态" in response.json()["error"]


def test_released_status_cannot_drop(env):
    client, _ = env
    response = _patch(client, "v1", {"tf-v-status": "dropped"})
    assert response.status_code == 400


# ---------- BUG-090-01/02 执行状态与结果同集合 ----------

def test_pending_run_cannot_be_removed_from_manifest_to_pass(env):
    client, _ = env
    _advance_to_test(client)
    # 把 todo 行从 ver.runs 摘掉，同时置「测试」done：owned 并集仍含 v2--C1，state=todo
    response = _patch(client, "v2", {"tf-v-runs": [], NODE["测试"]: "done"})
    assert response.status_code == 400
    assert "v2--C1" in response.json()["error"]


def test_done_run_passes_after_manifest_removal(env):
    client, _ = env
    _advance_to_test(client)
    assert client.patch(
        "/api/agent/tables/t-run/rows/v2--C1",
        json={"values": {"r-state": "done", "r-result": "pass"}},
        headers=HEADERS,
    ).status_code == 200
    response = _patch(client, "v2", {"tf-v-runs": [], NODE["测试"]: "done"})
    assert response.status_code == 200, response.text


# ---------- BUG-090-01 执行行不可删除 ----------

def test_delete_run_row_is_rejected(env):
    client, _ = env
    response = client.delete("/api/agent/tables/t-run/rows/v2--C1", headers=HEADERS)
    assert response.status_code == 400
    assert "不可物理删除" in response.json()["error"]


def test_delete_non_empty_run_table_is_rejected(env):
    client, _ = env
    # 被 relation 引用的表先报引用；孤立非空执行表才走到"非空"检查
    referenced = client.delete("/api/agent/tables/t-run", headers=HEADERS)
    assert referenced.status_code == 400
    response = client.delete("/api/agent/tables/t-run2", headers=HEADERS)
    assert response.status_code == 400
    assert "非空" in response.json()["error"]
