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
PUBLISH = [
    {"value": "planned", "label": "计划中", "tone": "info"},
    {"value": "released", "label": "已发布", "tone": "success"},
    {"value": "dropped", "label": "已终止", "tone": "neutral"},
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
        "v-status": "planned",
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
                            _field("v-status", "发布状态", "enum", PUBLISH, 13),
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
                            _field("i-reason", "放弃理由", "text", None, 3),
                            _field("i-at", "放弃时间", "datetime", None, 4),
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


def test_b1_shrinking_run_list_must_not_close(env) -> None:
    """同一请求里把 runs 缩减为只含 pass，再置测试验收 done，必须 400（036 FR-009）。"""
    runs = [run_row(PASS_RUN, "done", "pass"), run_row(FAIL_RUN, "done", "fail")]
    with env(board(runs=runs, version_values={TEST_ACCEPT: "todo"})) as client:
        resp = _patched(client, {TEST_ACCEPT: "done", "v-runs": [PASS_RUN]})
        assert resp.status_code == 400, f"缩减执行清单后仍然通过了验收：{resp.status_code} {resp.text}"
        assert FAIL_RUN in resp.json()["error"]


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


# ---------- B3/B5：发布历史与跨项目 ----------

def _mini_project(prefix: str, *, version_id: str, holding: list[str], status: str = "planned") -> dict:
    """一个只含版本表与独立需求表的最小项目；表 id 与字段 id 都带前缀。"""
    def fid(name: str) -> str:
        return f"{prefix}-fld-{name}"

    def f(name, label, type_, options, order):
        return {"id": fid(name), "name": label, "type": type_, "options": options,
                "order": order, "visible": 1}

    nodes = [f(f"node{i}", label, "enum", STAGES, i + 3) for i, (_, label) in enumerate(STAGE_NAMES)]
    return {
        "id": f"{prefix}-proj",
        "name": prefix,
        "tables": [
            {
                "id": f"{prefix}-ver",
                "name": "版本管理",
                "order": 1,
                "fields": [
                    f("version", "版本号", "text", None, 1),
                    f("status", "发布状态", "enum", PUBLISH, 2),
                    *nodes,
                    f("indep", "独立需求管理", "relation", {"table_id": f"{prefix}-indep"}, 9),
                ],
                "rows": [
                    {
                        "id": version_id,
                        "values": {
                            fid("version"): version_id,
                            fid("status"): status,
                            fid("indep"): holding,
                            **{fid(f"node{i}"): "done" for i in range(6)},
                        },
                    }
                ],
            },
            {
                "id": f"{prefix}-indep",
                "name": "独立规格需求",
                "order": 2,
                "fields": [
                    f("iid", "编号", "text", None, 1),
                    f("accept", "验收状态", "enum", ACCEPT, 2),
                    f("reason", "放弃理由", "text", None, 3),
                    f("at", "放弃时间", "datetime", None, 4),
                ],
                "rows": [
                    {
                        "id": "042-AR",
                        "values": {fid("iid"): "042-AR", fid("accept"): "pending"},
                    }
                ],
            },
        ],
    }


def _cross_board() -> dict:
    """A 项目没有版本持有 042-AR；B 项目有。"""
    a = _mini_project("a", version_id="v0.8.3", holding=[], status="planned")
    b = _mini_project("b", version_id="v9.9.9", holding=["042-AR"], status="planned")
    return {"projects": [a, b]}


@pytest.mark.xfail(strict=True, reason="B3：版本已发布后仍可摘除交付范围，发布历史被改写")
def test_b3_released_version_scope_must_be_frozen(env) -> None:
    """已发布版本摘掉一条独立需求，必须 400（034 FR-011：发布历史不可改）。"""
    data = board(runs=[], version_values={"v-status": "released", "v-indep": ["042-AR"]})
    with env(data) as client:
        resp = _patched(client, {"v-indep": []})
        assert resp.status_code == 400, f"已发布版本的范围被改掉了：{resp.status_code} {resp.text}"
        assert "已发布" in resp.json()["error"]


def test_b5_other_project_same_id_must_not_block_drop(env) -> None:
    """本项目没有任何版本持有 042-AR，另一项目有，放弃本项目这条应当成功。"""
    with env(_cross_board()) as client:
        resp = client.patch(
            "/api/agent/tables/a-indep/rows/042-AR",
            json={"values": {"a-fld-accept": "dropped", "a-fld-reason": "083 复现用",
                             "a-fld-at": "2026-11-24T09:00:00+08:00"}},
            headers=HEADERS,
        )
        assert resp.status_code == 200, f"被另一项目的同编号需求误拒：{resp.status_code} {resp.text}"


# ---------- B6：迁移失败处理 ----------

def test_b6_migration_reports_field_failure(monkeypatch) -> None:
    """新建字段失败时必须把失败项交回调用方，而不是抛 NameError。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import migrate_board5

    monkeypatch.setattr(migrate_board5, "call", lambda *a, **k: {"http": 500, "error": "boom"})
    planned: list[str] = []
    failures = migrate_board5.add_fields(
        {"id": "x-ver", "fields": []},
        [{"name": "新字段", "suffix": "x", "type": "text", "options": None}],
        "a", True, planned,
    )
    assert failures, "失败项没有交回调用方"
    assert any("boom" in item for item in failures)


# ---------- C3/C6：契约与结构分析 ----------

def test_c3_board5_acceptance_declares_dropped() -> None:
    """契约声明支持放弃，验收状态枚举就必须含 dropped。"""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "specs/019-test-contract/board@5.yaml").read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if "key: spec.acceptance" in line)
    block = "\n".join(lines[start:start + 14])
    assert "dropped" in block, f"board@5 的验收枚举缺 dropped：\n{block}"


def test_c6_fr_under_requirements_section_counted() -> None:
    """026 把 FR 直接写在 Requirements 下，分析器必须计入。"""
    from pathlib import Path

    from tableflow.spec_structure import analyze

    text = (Path(__file__).resolve().parents[2] / "specs/026-ver-columns/spec.md").read_text(encoding="utf-8")
    result = analyze(text)
    assert result["counts"]["fr"] >= 6, f"FR 计数为 {result['counts']['fr']}，文本里实际有 7 条"


# ---------- C4：复用证据的重新确认 ----------

def _evidence_board() -> dict:
    """独立需求带宪法版本与阶段证据，用于复用豁免校验。"""
    stage_values = [
        {"value": "todo", "label": "未开始", "tone": "neutral"},
        {"value": "doing", "label": "进行中", "tone": "info"},
        {"value": "done", "label": "完成", "tone": "success"},
        {"value": "na", "label": "不适用", "tone": "neutral"},
    ]
    const_stages = [
        "speckit-constitution状态", "speckit-specify状态", "speckit-clarify状态",
        "speckit-analyze状态", "speckit-checklist状态",
    ]
    return {
        "projects": [{
            "id": "p083e",
            "name": "083 证据",
            "tables": [{
                "id": "e-indep",
                "name": "独立规格需求",
                "order": 1,
                "fields": [
                    _field("e-id", "编号", "text", None, 1),
                    _field("e-accept", "验收状态", "enum", ACCEPT, 2),
                    _field("e-constitution", "宪法版本", "text", None, 3),
                    _field("e-evidence", "阶段证据", "text", None, 4),
                    *[_field(f"e-stage-{i}", name, "enum", stage_values, i + 5)
                      for i, name in enumerate(const_stages)],
                ],
                "rows": [{
                    "id": "042-AR",
                    "values": {
                        "e-id": "042-AR",
                        "e-accept": "pending",
                        "e-constitution": "",
                        "e-evidence": "",
                        **{f"e-stage-{i}": "todo" for i in range(5)},
                    },
                }],
            }],
        }],
    }


@pytest.mark.xfail(strict=True, reason="C4：一次「已重新确认」永久豁免后续宪法版本升级")
def test_c4_reconfirm_does_not_exempt_forever(env) -> None:
    """宪法版本从 v1 升到 v2 后，旧版本上的「已重新确认」不能继续用。"""
    reused = "constitution=reused:.specify/memory/constitution.md@v1 已重新确认仍适用"
    with env(_evidence_board()) as client:
        first = client.patch(
            "/api/agent/tables/e-indep/rows/042-AR",
            json={"values": {"e-constitution": "v1", "e-evidence": reused,
                             "e-stage-0": "done"}},
            headers=HEADERS,
        )
        assert first.status_code == 200, first.text

        second = client.patch(
            "/api/agent/tables/e-indep/rows/042-AR",
            json={"values": {"e-constitution": "v2", "e-evidence": reused,
                             "e-stage-0": "done"}},
            headers=HEADERS,
        )
        assert second.status_code == 400, (
            f"宪法版本升到 v2 后仍沿用 v1 的重新确认：{second.status_code} {second.text}"
        )


# ---------- C5：映射不得一测多场景 ----------

@pytest.mark.xfail(strict=True, reason="C5：一个测试函数被多个场景共用，映射冒充覆盖")
def test_c5_one_scenario_per_test() -> None:
    """每条场景必须有自己的测试，不能几个场景共用一个。"""
    import sys
    from collections import Counter
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from acceptance_manifest import COVERED

    counts = Counter(ref for refs in COVERED.values() for ref in refs)
    shared = {ref: n for ref, n in counts.items() if n > 1}
    assert not shared, "以下测试承担了多个场景：" + "；".join(
        f"{ref}（{n} 条）" for ref, n in sorted(shared.items(), key=lambda kv: -kv[1])[:5]
    )
