"""036：测试验收以执行结果为主判据，放行标记需批准人与理由。

对应 `specs/036-acceptance-own-snapshot/spec.md` 与 board@5
`rules.run_result_judgement` / `rules.run_waiver` / `rules.test_accept_gate`：

- 本版执行结果全部 pass 才可置「测试验收」done；
- fail/blocked/skip 必须带有效放行标记（放行标记=waived 且批准人、理由都不为空）；
- 缺少任一项按未放行处理，返回 400 且零写入；
- 缺陷关闭只作旁证，不替代执行结果。
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
]
REGRESS = [
    {"value": "todo", "label": "未合入", "tone": "neutral"},
    {"value": "doing", "label": "已合入待验", "tone": "info"},
    {"value": "passed", "label": "通过", "tone": "success"},
    {"value": "failed", "label": "不通过", "tone": "danger"},
]
BUG_STATUS = [
    {"value": "open", "label": "待修", "tone": "danger"},
    {"value": "fixing", "label": "修复中", "tone": "info"},
    {"value": "verifying", "label": "已修待验", "tone": "info"},
    {"value": "closed", "label": "已关闭", "tone": "success"},
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
RUN_A = "v0.1.0--033-US1-AS1"
RUN_B = "v0.1.0--033-US1-AS2"


def run_row(row_id: str, state: str, result: str | None, **extra):
    values = {
        "r-id": row_id,
        "r-case-no": row_id.split("--", 1)[1],
        "r-state": state,
        "r-result": result,
        "r-waived": "none",
    }
    values.update(extra)
    return {"id": row_id, "values": values}


def base_project(runs):
    return {
        "projects": [
            {
                "id": "p036",
                "name": "036 测试验收",
                "tables": [
                    {
                        "id": "t-ver",
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
                            {"id": "v-runs", "name": "测试用例", "type": "relation",
                             "options": {"table_id": "t-run"}, "order": 9, "visible": 1},
                            {"id": "v-bugs", "name": "Bug管理", "type": "relation",
                             "options": {"table_id": "t-bug"}, "order": 10, "visible": 1},
                            {"id": "v-dep", "name": "依赖需求管理", "type": "relation",
                             "options": {"table_id": "t-dep"}, "order": 11, "visible": 1},
                        ],
                        "rows": [
                            {
                                "id": "v0.1.0",
                                "values": {
                                    "v-version": "v0.1.0",
                                    **{
                                        fid: ("todo" if fid == TEST_ACCEPT else "done")
                                        for fid, _ in STAGE_NAMES
                                    },
                                    "v-runs": [row["id"] for row in runs],
                                    "v-bugs": [],
                                    "v-dep": [],
                                },
                            }
                        ],
                    },
                    {
                        "id": "t-run",
                        "name": "用例执行情况",
                        "order": 2,
                        "fields": [
                            {"id": "r-id", "name": "执行编号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            {"id": "r-case-no", "name": "用例号", "type": "text",
                             "options": None, "order": 2, "visible": 1},
                            {"id": "r-state", "name": "执行状态", "type": "enum",
                             "options": RUN_STATE, "order": 3, "visible": 1},
                            {"id": "r-result", "name": "执行结果", "type": "enum",
                             "options": RUN_RESULT, "order": 4, "visible": 1},
                            {"id": "r-waived", "name": "放行标记", "type": "enum",
                             "options": WAIVED, "order": 5, "visible": 1},
                            {"id": "r-by", "name": "放行批准人", "type": "text",
                             "options": None, "order": 6, "visible": 1},
                            {"id": "r-reason", "name": "放行理由", "type": "text",
                             "options": None, "order": 7, "visible": 1},
                        ],
                        "rows": runs,
                    },
                    {
                        "id": "t-bug",
                        "name": "缺陷",
                        "order": 3,
                        "fields": [
                            {"id": "b-id", "name": "编号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            {"id": "b-status", "name": "状态", "type": "enum",
                             "options": BUG_STATUS, "order": 2, "visible": 1},
                        ],
                        "rows": [],
                    },
                    {
                        "id": "t-dep",
                        "name": "依赖变更需求",
                        "order": 4,
                        "fields": [
                            {"id": "d-id", "name": "编号", "type": "text",
                             "options": None, "order": 1, "visible": 1},
                            {"id": "d-regress", "name": "回归状态", "type": "enum",
                             "options": REGRESS, "order": 2, "visible": 1},
                        ],
                        "rows": [],
                    },
                ],
            }
        ]
    }


def make_env(tmp_path, monkeypatch, runs):
    db = tmp_path / "test_accept_036.db"
    write_seed(db, base_project(runs))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    return TestClient(app)


def close_version(env):
    return env.patch(
        "/api/agent/tables/t-ver/rows/v0.1.0",
        json={"values": {TEST_ACCEPT: "done"}},
        headers=HEADERS,
    )


def test_all_pass_allows_close(tmp_path, monkeypatch) -> None:
    with make_env(tmp_path, monkeypatch, [run_row(RUN_A, "done", "pass")]) as env:
        assert close_version(env).status_code == 200


def test_failing_run_blocks_close(tmp_path, monkeypatch) -> None:
    with make_env(tmp_path, monkeypatch, [run_row(RUN_A, "done", "fail")]) as env:
        resp = close_version(env)
        assert resp.status_code == 400
        assert "执行结果必须全部 pass" in resp.json()["error"]
        assert RUN_A in resp.json()["error"]
        # 零写入
        row = env.get("/api/tables/t-ver/rows/v0.1.0").json()
        assert (row.get("row") or row)["values"][TEST_ACCEPT] == "todo"


def test_blocked_run_without_waiver_blocks_close(tmp_path, monkeypatch) -> None:
    with make_env(tmp_path, monkeypatch, [run_row(RUN_A, "done", "blocked")]) as env:
        assert close_version(env).status_code == 400


def test_valid_waiver_allows_close(tmp_path, monkeypatch) -> None:
    runs = [
        run_row(RUN_A, "done", "fail", **{"r-waived": "waived",
                                          "r-by": "张三",
                                          "r-reason": "已知问题，下版修复"}),
        run_row(RUN_B, "done", "pass"),
    ]
    with make_env(tmp_path, monkeypatch, runs) as env:
        assert close_version(env).status_code == 200


def test_waiver_without_approver_blocks_close(tmp_path, monkeypatch) -> None:
    runs = [run_row(RUN_A, "done", "fail", **{"r-waived": "waived",
                                              "r-reason": "已知问题"})]
    with make_env(tmp_path, monkeypatch, runs) as env:
        assert close_version(env).status_code == 400


def test_waiver_without_reason_blocks_close(tmp_path, monkeypatch) -> None:
    runs = [run_row(RUN_A, "done", "fail", **{"r-waived": "waived", "r-by": "张三"})]
    with make_env(tmp_path, monkeypatch, runs) as env:
        assert close_version(env).status_code == 400


def test_unexecuted_run_blocks_close(tmp_path, monkeypatch) -> None:
    with make_env(tmp_path, monkeypatch, [run_row(RUN_A, "todo", None)]) as env:
        resp = close_version(env)
        assert resp.status_code == 400
        assert "必须全部执行" in resp.json()["error"]
