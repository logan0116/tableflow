"""v0.10.3 技能链回归：纯回归第三节点、复用参数组合、来源场景校验、--no-stage。

对应 BUG-090-05/19/20/21，使用 test_skill_e2e_083 的真实 uvicorn + 技能子进程夹具。
"""

from __future__ import annotations

import json
import urllib.request

from test_skill_e2e_083 import (  # noqa: F401
    PROJECT,
    REPO_ROOT,
    SPEC_ID,
    VERSION,
    run_skill,
    running_board,
    skill_board,
)

NODES = ("版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收")


def _set_nodes(data, done: int) -> None:
    row = data["projects"][0]["tables"][0]["rows"][0]
    for index in range(done):
        row["values"][f"v-node-{index}"] = "done"


def _ver_row(version: str, *, indep=None, runs=None, status="planned", nodes=0) -> dict:
    return {
        "id": version,
        "values": {
            "v-version": version,
            "v-status": status,
            **{
                f"v-node-{index}": "done" if index < nodes else "todo"
                for index in range(6)
            },
            "v-indep": list(indep or []),
            "v-dep": [],
            "v-runs": list(runs or []),
            "v-bug": [],
        },
    }


def _board_node(base: str, version: str, index: int) -> str:
    with urllib.request.urlopen(
        f"{base}/api/tables/t-ver/rows/{version}", timeout=5
    ) as resp:
        values = json.loads(resp.read())["row"]["values"]
    return values[f"v-node-{index}"]


# ---------- BUG-090-05 纯回归版本可进第三节点 ----------

def test_regression_only_version_reaches_dev_node(tmp_path) -> None:
    run_id = f"{VERSION}--042-US1-AS1"
    data = skill_board(
        version_indep=[],
        version_runs=[run_id],
        runs=[{"id": run_id, "values": {"r-case-no": "042-US1-AS1", "r-state": "todo"}}],
    )
    _set_nodes(data, 2)
    with running_board(data, tmp_path) as (base, _db):
        code, report, raw = run_skill(
            "tf-dev-implement",
            ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--plan-only"],
            base=base,
        )
        assert code == 0, raw[-3000:]
        assert report and report["result"] == "success"


# ---------- BUG-090-19 有独立需求时拒绝 --reuse-from --case ----------

def test_reuse_from_with_indep_is_rejected(tmp_path) -> None:
    data = skill_board()
    _set_nodes(data, 1)
    with running_board(data, tmp_path) as (base, _db):
        code, _report, raw = run_skill(
            "tf-test-plan",
            ["--version", VERSION, "--reuse-from", "v0.8.0", "--case", "042-US1-AS1"],
            base=base,
        )
        assert code != 0
        assert "复用范围会被忽略" in raw


# ---------- BUG-090-20 复用用例必须属于源版本规格场景 ----------

def test_reuse_case_outside_source_specs_is_rejected(tmp_path) -> None:
    bogus = "042-US9-AS99"
    source_run = f"v0.8.0--{bogus}"
    data = skill_board(
        version_indep=[],
        versions=[
            _ver_row(VERSION, indep=[], runs=[], nodes=1),
            _ver_row("v0.8.0", indep=[SPEC_ID], runs=[source_run], status="released", nodes=6),
        ],
        runs=[{"id": source_run, "values": {"r-case-no": bogus, "r-state": "todo"}}],
        cases=[{"id": bogus, "values": {"c-id": bogus, "c-name": "伪造用例"}}],
    )
    with running_board(data, tmp_path) as (base, _db):
        code, _report, raw = run_skill(
            "tf-test-plan",
            ["--version", VERSION, "--reuse-from", "v0.8.0", "--case", bogus],
            base=base,
        )
        assert code != 0
        assert "不属于源版本" in raw


# ---------- BUG-090-21 --no-stage 失败分支不写节点 ----------

def test_no_stage_keeps_node_todo_on_failure(tmp_path) -> None:
    run_id = f"{VERSION}--042-US1-AS1"
    data = skill_board(
        version_runs=[run_id],
        runs=[{
            "id": run_id,
            "values": {
                "r-case-no": "042-US1-AS1",
                "r-case": ["042-US1-AS1"],
                "r-state": "done",
                "r-result": "fail",
            },
        }],
    )
    _set_nodes(data, 5)
    with running_board(data, tmp_path) as (base, _db):
        code, _report, raw = run_skill(
            "tf-test-check", ["--version", VERSION, "--no-stage"], base=base
        )
        assert code != 0, raw[-2000:]
        assert _board_node(base, VERSION, 5) == "todo"
