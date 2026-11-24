"""v0.8.3 一致性守卫：看板数字与灯必须跟着数据走。

这三条源自线上观察（v0.8.3 建了 19 条用例后，“测试”列仍显示 0/0、六灯全灰）。
本地按同一顺序复现，引擎的计算是即时正确的——所以这里写成**守卫测试**：
守住“写入后立即正确”，防止将来回退成需要手工 recompute 才刷新。

字段定义取自线上 board@5 实际形态（count / count+where / rollup all / and gate）。
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
NODES = (
    ("v-stage-plan", "版本需求设计"),
    ("v-stage-test-design", "测试设计"),
    ("v-stage-dev", "开发"),
    ("v-stage-dev-accept", "开发验收"),
    ("v-stage-test", "测试"),
    ("v-stage-test-accept", "测试验收"),
)
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
VERSION = "v0.1.0"
RUN_PASS = f"{VERSION}--042-US1-AS1"
RUN_TODO = f"{VERSION}--042-US1-AS2"


def _field(fid, name, type_, options, order):
    return {"id": fid, "name": name, "type": type_, "options": options, "order": order, "visible": 1}


def _board(nodes: dict[str, str]) -> dict:
    return {
        "projects": [
            {
                "id": "p083c",
                "name": "083 一致性",
                "tables": [
                    {
                        "id": "t-ver",
                        "name": "版本管理",
                        "order": 1,
                        "fields": [
                            _field("tf-v-ver", "版本号", "text", None, 1),
                            *[_field(fid, name, "enum", STAGES, i + 2) for i, (fid, name) in enumerate(NODES)],
                            _field("tf-v-runs", "测试用例", "relation", {"table_id": "t-run"}, 9),
                            _field("tf-v-case-total", "用例总数", "computed",
                                   {"kind": "count", "source": "tf-v-runs"}, 10),
                            _field("tf-v-case-done-count", "已完成用例数", "computed",
                                   {"kind": "count", "source": "tf-v-runs",
                                    "where": {"field_id": "tf-r-state", "equals": "done"}}, 11),
                            _field("tf-v-case-done", "用例是否完成", "computed",
                                   {"kind": "rollup", "source": "tf-v-runs", "field_id": "tf-r-state",
                                    "aggregate": "all", "equals": "done",
                                    "true_label": "是", "false_label": "否"}, 12),
                            _field("tf-v-stage-done", "六节点是否全部完成", "computed",
                                   {"kind": "and", "gate": True, "true_label": "是", "false_label": "否",
                                    "conditions": [{"field_id": fid, "equals": "done"} for fid, _ in NODES]}, 13),
                            _field("tf-v-cond", "发布条件", "computed",
                                   {"kind": "and", "gate": True, "true_label": "是", "false_label": "否",
                                    "conditions": [{"field_id": "tf-v-stage-done", "equals": True}]}, 14),
                        ],
                        "rows": [
                            {
                                "id": VERSION,
                                "values": {"tf-v-ver": VERSION, **nodes, "tf-v-runs": []},
                            }
                        ],
                    },
                    {
                        "id": "t-run",
                        "name": "用例执行情况",
                        "order": 2,
                        "fields": [
                            _field("tf-r-id", "执行编号", "text", None, 1),
                            _field("tf-r-case_no", "用例号", "text", None, 2),
                            _field("tf-r-state", "执行状态", "enum", RUN_STATE, 3),
                            _field("tf-r-result", "执行结果", "enum", RUN_RESULT, 4),
                        ],
                        "rows": [
                            {"id": RUN_PASS, "values": {
                                "tf-r-id": RUN_PASS, "tf-r-case_no": "042-US1-AS1",
                                "tf-r-state": "done", "tf-r-result": "pass"}},
                            {"id": RUN_TODO, "values": {
                                "tf-r-id": RUN_TODO, "tf-r-case_no": "042-US1-AS2",
                                "tf-r-state": "todo"}},
                        ],
                    },
                ],
            }
        ]
    }


@pytest.fixture()
def client(tmp_path, monkeypatch):
    def _make(nodes: dict[str, str]) -> TestClient:
        db = tmp_path / "consistency.db"
        write_seed(db, _board(nodes))
        monkeypatch.setenv("TABLEFLOW_DB", str(db))
        raw = TestClient(app)
        # seed 只写数据不跑计算；先算一次，等价于线上写入后的状态。
        for table in ("t-run", "t-ver"):
            raw.post(f"/api/agent/tables/{table}/recompute", headers=HEADERS)
        return raw

    return _make


def _values(raw: TestClient, row_id: str = VERSION) -> dict:
    payload = raw.get("/api/tables/t-ver/table").json()
    return next(item for item in payload["rows"] if item["id"] == row_id)["values"]


def _link_runs(raw: TestClient) -> None:
    resp = raw.patch(
        f"/api/agent/tables/t-ver/rows/{VERSION}",
        json={"values": {"tf-v-runs": [RUN_PASS, RUN_TODO]}},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text


ALL_TODO = {fid: "todo" for fid, _ in NODES}


def test_ratio_refreshes_immediately_after_linking_runs(client) -> None:
    """版本收录用例后，“用例完成/总数”必须立刻反映，不能等手工 recompute。"""
    with client(ALL_TODO) as raw:
        _link_runs(raw)
        values = _values(raw)
        assert values["tf-v-case-total"] == 2, "总数没有跟着 relation 刷新"
        assert values["tf-v-case-done-count"] == 1, "已完成数没有跟着执行状态刷新"


def test_case_done_is_false_while_any_run_unexecuted(client) -> None:
    """只要还有未执行用例，“用例是否完成”就必须为否。"""
    with client(ALL_TODO) as raw:
        _link_runs(raw)
        assert _values(raw)["tf-v-case-done"] is False


def test_gate_stays_false_until_all_six_nodes_done(client) -> None:
    """四灯 done + 一灯 doing + 一灯 todo 时，发布条件必须是“否”。"""
    partial = {**ALL_TODO, "v-stage-plan": "done", "v-stage-test-design": "done",
               "v-stage-dev": "done", "v-stage-dev-accept": "done", "v-stage-test": "doing"}
    with client(partial) as raw:
        values = _values(raw)
        assert values["tf-v-stage-done"] is False
        assert values["tf-v-cond"] is False, "有节点没完成却显示为可发布"

    with client({fid: "done" for fid, _ in NODES}) as raw:
        values = _values(raw)
        assert values["tf-v-stage-done"] is True
        assert values["tf-v-cond"] is True
