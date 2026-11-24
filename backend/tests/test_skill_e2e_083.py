"""v0.8.3 缺陷显现化：技能端到端基座（L2 层）。

此前的“技能测试”只 import 了两个纯函数，从不执行入口。这里起一个真的 uvicorn
（临时库），再用 subprocess 跑技能脚本，等于按用户真实用法调用。

S1：`tf-dev-plan` 在结构合格的规格上必然崩在 `spec_rel` 未定义。
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tableflow.seed import write_seed

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
SKILLS = REPO_ROOT / "skills"
SPEC_DIR = "specs/042-implement-full-flow"

STAGES = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]
SPEC_STAGES = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "na", "label": "不适用", "tone": "neutral"},
]
ACCEPT = [
    {"value": "pending", "label": "未验收", "tone": "neutral"},
    {"value": "accepted", "label": "已验收", "tone": "success"},
    {"value": "rejected", "label": "未通过", "tone": "danger"},
    {"value": "dropped", "label": "已放弃", "tone": "neutral"},
]
PUBLISH = [
    {"value": "planned", "label": "计划中", "tone": "info"},
    {"value": "released", "label": "已发布", "tone": "success"},
    {"value": "dropped", "label": "已终止", "tone": "neutral"},
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
NODE_NAMES = ("版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收")
SPEC_STAGE_NAMES = (
    "speckit-constitution状态",
    "speckit-specify状态",
    "speckit-clarify状态",
    "speckit-analyze状态",
    "speckit-checklist状态",
)

VERSION = "v0.8.3"
PROJECT = "p083e2e"
SPEC_ID = "042-AR"


def _field(fid, name, type_, options, order):
    return {"id": fid, "name": name, "type": type_, "options": options, "order": order, "visible": 1}


def skill_board(*, version_status: str = "planned", indep_accept: str = "pending",
                version_indep: list[str] | None = None, version_dep: list[str] | None = None,
                version_runs: list[str] | None = None, versions: list[dict] | None = None,
                deps: list[dict] | None = None, runs: list[dict] | None = None,
                cases: list[dict] | None = None, version_id: str = VERSION,
                spec_dir: str = SPEC_DIR, bugs: list[dict] | None = None,
                version_bugs: list[str] | None = None):
    """技能可用的最小看板：表名必须与 board 契约一致（技能按名称解析）。"""
    ver_values = {
        "v-version": version_id,
        "v-status": version_status,
        **{f"v-node-{i}": "todo" for i in range(6)},
        "v-indep": list(version_indep if version_indep is not None else [SPEC_ID]),
        "v-dep": list(version_dep or []),
        "v-runs": list(version_runs or []),
        "v-bug": list(version_bugs or []),
    }
    return {
        "projects": [
            {
                "id": PROJECT,
                "name": "083 技能 e2e",
                "tables": [
                    {
                        "id": "t-ver",
                        "name": "版本管理",
                        "order": 1,
                        "fields": [
                            _field("v-version", "版本号", "text", None, 1),
                            _field("v-status", "发布状态", "enum", PUBLISH, 2),
                            *[_field(f"v-node-{i}", name, "enum", STAGES, i + 3) for i, name in enumerate(NODE_NAMES)],
                            _field("v-indep", "独立需求管理", "relation", {"table_id": "t-indep"}, 9),
                            _field("v-dep", "依赖需求管理", "relation", {"table_id": "t-dep"}, 10),
                            _field("v-runs", "测试用例", "relation", {"table_id": "t-run"}, 11),
                            _field("v-bug", "Bug管理", "relation", {"table_id": "t-bug"}, 12),
                        ],
                        "rows": versions or [{"id": version_id, "values": ver_values}],
                    },
                    {
                        "id": "t-indep",
                        "name": "独立规格需求",
                        "order": 2,
                        "fields": [
                            _field("i-id", "编号", "text", None, 1),
                            _field("i-clause", "条款", "text", None, 2),
                            _field("i-dir", "规格目录", "text", None, 3),
                            _field("i-scen", "场景数", "number", None, 4),
                            _field("i-accept", "验收状态", "enum", ACCEPT, 5),
                            _field("i-constitution", "宪法版本", "text", None, 6),
                            *[_field(f"i-stage-{i}", name, "enum", SPEC_STAGES, i + 7)
                              for i, name in enumerate(SPEC_STAGE_NAMES)],
                            _field("i-evidence", "阶段证据", "text", None, 12),
                            _field("i-plan", "speckit-plan状态", "enum", SPEC_STAGES, 13),
                            _field("i-task", "speckit-task状态", "enum", SPEC_STAGES, 14),
                            _field("i-implement", "speckit-implement状态", "enum", SPEC_STAGES, 15),
                        ],
                        "rows": [
                            {
                                "id": SPEC_ID,
                                "values": {
                                    "i-id": SPEC_ID,
                                    "i-clause": "US1-US4",
                                    "i-dir": spec_dir,
                                    "i-scen": 13,
                                    "i-accept": indep_accept,
                                    "i-constitution": "",
                                    "i-evidence": "",
                                    **{f"i-stage-{i}": "todo" for i in range(5)},
                                    "i-plan": "todo", "i-task": "todo", "i-implement": "todo",
                                },
                            }
                        ],
                    },
                    {
                        "id": "t-dep",
                        "name": "依赖变更需求",
                        "order": 3,
                        "fields": [
                            _field("d-id", "编号", "text", None, 1),
                            _field("d-clause", "条款", "text", None, 2),
                            _field("d-specs", "关联的独立规格需求", "relation", {"table_id": "t-indep"}, 3),
                            _field("d-regress", "回归状态", "enum", REGRESS, 4),
                        ],
                        "rows": deps or [],
                    },
                    {
                        "id": "t-run",
                        "name": "用例执行情况",
                        "order": 4,
                        "fields": [
                            _field("r-id", "执行编号", "text", None, 1),
                            _field("r-case-no", "用例号", "text", None, 2),
                            _field("r-case", "用例", "relation", {"table_id": "t-case"}, 3),
                            _field("r-state", "执行状态", "enum", RUN_STATE, 4),
                            _field("r-result", "执行结果", "enum", RUN_RESULT, 5),
                        ],
                        "rows": runs or [],
                    },
                    {
                        "id": "t-bug",
                        "name": "缺陷",
                        "order": 6,
                        "fields": [
                            _field("b-id", "编号", "text", None, 1),
                            _field("b-status", "状态", "enum", [
                                {"value": "open", "label": "待修", "tone": "danger"},
                                {"value": "fixing", "label": "修复中", "tone": "info"},
                                {"value": "verifying", "label": "已修待验", "tone": "info"},
                                {"value": "closed", "label": "已关闭", "tone": "success"},
                            ], 2),
                            _field("b-evidence", "证据", "text", None, 3),
                            _field("b-rest", "剩余事项", "text", None, 4),
                        ],
                        "rows": bugs or [],
                    },
                    {
                        "id": "t-case",
                        "name": "测试用例",
                        "order": 5,
                        "fields": [
                            _field("c-id", "用例号", "text", None, 1),
                            _field("c-spec", "来源规格", "relation", {"table_id": "t-indep"}, 2),
                            _field("c-name", "用例名", "text", None, 3),
                            _field("c-pre", "前置条件", "text", None, 4),
                            _field("c-steps", "操作步骤", "text", None, 5),
                            _field("c-expect", "预期结果", "text", None, 6),
                            _field("c-priority", "优先级", "enum", [
                                {"value": "P0", "label": "P0", "tone": "danger"},
                                {"value": "P1", "label": "P1", "tone": "warning"},
                                {"value": "P2", "label": "P2", "tone": "neutral"},
                            ], 7),
                        ],
                        "rows": cases or [],
                    },
                ],
            }
        ]
    }


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_ready(port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/projects"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:  # noqa: S310 - 本机回环
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    raise RuntimeError(f"服务端 {url} 未在 {timeout}s 内就绪")


@contextlib.contextmanager
def running_board(data: dict, tmp_path: Path):
    """起一个真的 uvicorn（临时库），yield base_url。"""
    db = tmp_path / "e2e.db"
    write_seed(db, data)
    port = _free_port()
    env = {
        **os.environ,
        "TABLEFLOW_DB": str(db),
        "PYTHONPATH": str(BACKEND / "src"),
        "PYTHONUNBUFFERED": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tableflow.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
        cwd=str(BACKEND), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        _wait_ready(port)
        yield f"http://127.0.0.1:{port}", db
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - 清理兜底
            proc.kill()


def run_skill(name: str, args: list[str], *, base: str, timeout: float = 120.0):
    """按用户用法跑技能脚本，返回 (退出码, 报告 dict | None, 原始输出)。"""
    script = SKILLS / name / "scripts" / f"{name.replace('-', '_')}.py"
    env = {
        **os.environ,
        "TF_BASE": base,
        "TF_PROJECT": PROJECT,
        "TF_ORIGIN": "agent",
        "TF_AGENT": "agent-tf-role",
    }
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, env=env, timeout=timeout, cwd=str(REPO_ROOT),
    )
    raw = (proc.stdout or "") + (proc.stderr or "")
    report = None
    start = (proc.stdout or "").find("{")
    if start >= 0:
        try:
            report = json.loads(proc.stdout[start:])
        except json.JSONDecodeError:
            report = None
    return proc.returncode, report, raw


def test_s1_dev_plan_runs_on_real_spec(tmp_path) -> None:
    """用结构合格的 042 规格推进第一个节点，应当成功。"""
    with running_board(skill_board(), tmp_path) as (base, _db):
        code, report, raw = run_skill(
            "tf-dev-plan",
            ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply"],
            base=base,
        )
        assert code == 0, f"tf-dev-plan 未完成：\n{raw[-3000:]}"
        assert report and report["result"] == "success"


def _row(db: Path, table_id: str, row_id: str) -> dict:
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id)
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return json.loads(row[0]) if row else {}


def test_s5_apply_with_dry_run_writes_nothing(tmp_path) -> None:
    """`--apply --dry-run` 按契约只能只读：库里的版本范围与验收状态都不得变化。"""
    with running_board(skill_board(), tmp_path) as (base, db):
        before_ver = _row(db, "t-ver", VERSION)
        before_indep = _row(db, "t-indep", SPEC_ID)
        assert before_ver["v-indep"] == [SPEC_ID]
        assert before_indep["i-accept"] == "pending"

        code, report, raw = run_skill(
            "tf-lifecycle",
            ["--version", VERSION, "--action", "drop", "--spec", SPEC_ID,
             "--reason", "083 复现用", "--apply", "--dry-run"],
            base=base,
        )

        after_ver = _row(db, "t-ver", VERSION)
        after_indep = _row(db, "t-indep", SPEC_ID)
        assert after_ver["v-indep"] == [SPEC_ID], f"dry-run 摘掉了版本关联：{after_ver['v-indep']}\n{raw[-1500:]}"
        assert after_indep["i-accept"] == "pending", f"dry-run 改了验收状态：{after_indep['i-accept']}\n{raw[-1500:]}"
        assert code == 0, raw[-1500:]


def test_s4_regression_only_version_proceeds(tmp_path) -> None:
    """版本不挂任何需求、只收录版本外用例（035 解耦），应当能推进需求设计。"""
    run_id = "v0.8.3--042-US1-AS1"
    data = skill_board(
        version_indep=[],
        version_runs=[run_id],
        runs=[{"id": run_id, "values": {"r-id": run_id, "r-case-no": "042-US1-AS1"}}],
        cases=[{"id": "042-US1-AS1", "values": {"c-id": "042-US1-AS1", "c-spec": [SPEC_ID]}}],
    )
    with running_board(data, tmp_path) as (base, _db):
        code, report, raw = run_skill(
            "tf-dev-plan", ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply"], base=base,
        )
        assert code == 0, f"纯回归版本被拒：\n{raw[-2000:]}"


def test_s4b_dep_only_version_proceeds(tmp_path) -> None:
    """版本只挂依赖需求时，开发节点也应可推进。"""
    dep_id = "DEP-083"
    nodes = {f"v-node-{i}": ("done" if i < 2 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [], "v-dep": [dep_id], "v-runs": [],
    }}
    data = skill_board(
        versions=[version],
        version_dep=[dep_id],
        deps=[{"id": dep_id, "values": {
            "d-id": dep_id, "d-clause": "US1", "d-specs": [SPEC_ID], "d-regress": "todo",
        }}],
    )
    with running_board(data, tmp_path) as (base, _db):
        code, report, raw = run_skill(
            "tf-dev-implement",
            ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply",
             "--test-cmd", "true", "--plan-only"],
            base=base,
        )
        assert code == 0, f"只有依赖需求的版本被拒：\n{raw[-2000:]}"


@pytest.mark.xfail(strict=True, reason="B7：cleanup 前置检查去读不在作用域内的 run 表，恒为 False")
def test_b7_cleanup_works_without_run_in_scope(tmp_path) -> None:
    """同一需求挂在两个版本时，cleanup 应当能真正执行去重。"""
    def ver(vid):
        return {"id": vid, "values": {
            "v-version": vid, "v-status": "planned",
            **{f"v-node-{i}": "todo" for i in range(6)},
            "v-indep": [SPEC_ID], "v-dep": [], "v-runs": [],
        }}

    data = skill_board(versions=[ver("v0.8.3"), ver("v0.8.4")])
    with running_board(data, tmp_path) as (base, db):
        code, report, raw = run_skill(
            "tf-lifecycle",
            ["--version", "v0.8.4", "--action", "cleanup", "--apply"], base=base,
        )
        assert code == 0, f"cleanup 被前置检查挡住：\n{raw[-2000:]}"
        assert _row(db, "t-ver", "v0.8.4")["v-indep"] == [], "重复挂载没有被摘除"


@pytest.mark.xfail(strict=True, reason="S3：自动生成的计划骨架（实现要点等全为“待补”）仍被判为 plan 完成")
def test_s3_skeleton_plan_is_not_done(tmp_path) -> None:
    """只有骨架的 plan.md 不能算完成的设计。"""
    repo = tmp_path / "repo"
    spec_dir = repo / "specs" / "099-dummy"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        (REPO_ROOT / "specs/042-implement-full-flow/spec.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    nodes = {f"v-node-{i}": ("done" if i < 2 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [SPEC_ID], "v-dep": [], "v-runs": [],
    }}
    data = skill_board(versions=[version], spec_dir="specs/099-dummy")
    with running_board(data, tmp_path) as (base, db):
        _code, _rep, raw = run_skill(
            "tf-dev-implement",
            ["--version", VERSION, "--repo-root", str(repo), "--apply", "--test-cmd", "true"],
            base=base,
        )
        values = _row(db, "t-indep", SPEC_ID)
        assert values["i-plan"] != "done", (
            f"骨架被当成完成的设计（plan={values['i-plan']}）：\n{raw[-1200:]}"
        )


@pytest.mark.xfail(strict=True, reason="S6：技能侧仍用 ^v\\d+\\.\\d+\\.\\d+$ 校验版本号")
def test_s6_non_semver_version_can_derive_cases(tmp_path) -> None:
    """版本行 id 形如 4.0.0_001 时，测试设计技能也要能派生用例。"""
    version_id = "4.0.0_001"
    nodes = {f"v-node-{i}": ("done" if i < 1 else "todo") for i in range(6)}
    version = {"id": version_id, "values": {
        "v-version": version_id, "v-status": "planned", **nodes,
        "v-indep": [SPEC_ID], "v-dep": [], "v-runs": [],
    }}
    data = skill_board(versions=[version], version_id=version_id)
    with running_board(data, tmp_path) as (base, _db):
        code, _rep, raw = run_skill(
            "tf-test-plan",
            ["--version", version_id, "--repo-root", str(REPO_ROOT), "--apply"],
            base=base,
        )
        assert code == 0, f"非 semver 版本被客户端拦下：\n{raw[-1500:]}"


@pytest.mark.xfail(strict=True, reason="S2：写 implement 证据时用缓存的旧行合并，覆盖刚写的 plan/task 证据")
def test_s2_implement_keeps_plan_task_evidence(tmp_path) -> None:
    """一次开发推进里写的三份阶段证据必须同时留存。"""
    nodes = {f"v-node-{i}": ("done" if i < 2 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [SPEC_ID], "v-dep": [], "v-runs": [],
    }}
    data = skill_board(versions=[version])
    with running_board(data, tmp_path) as (base, db):
        code, _rep, raw = run_skill(
            "tf-dev-implement",
            ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply", "--test-cmd", "true"],
            base=base,
        )
        evidence = (_row(db, "t-indep", SPEC_ID) or {}).get("i-evidence") or ""
        assert code == 0, f"开发推进未完成：\n{raw[-1500:]}"
        for key in ("plan=", "task=", "implement="):
            assert key in evidence, f"阶段证据缺 {key}：当前为 {evidence!r}"


@pytest.mark.xfail(strict=True, reason="S6：场景解析只认 1. **Given**，带编号的 1. **S1.1** **Given** 被漏掉")
def test_s6_numbered_scenario_prefix_parsed(tmp_path) -> None:
    """场景写作 `1. **S1.1** **Given** ...` 时也要能派生用例。"""
    repo = tmp_path / "repo"
    spec_dir = repo / "specs" / "098-numbered"
    spec_dir.mkdir(parents=True)
    import re

    text = (REPO_ROOT / "specs/042-implement-full-flow/spec.md").read_text(encoding="utf-8")
    text, replaced = re.subn(r"^(\d+)\. \*\*Given\*\*", lambda m: f"{m.group(1)}. **S{m.group(1)}** **Given**",
                             text, flags=re.M)
    assert replaced >= 10, f"没有改造成带编号的场景（只改了 {replaced} 条）"
    (spec_dir / "spec.md").write_text(text, encoding="utf-8")
    nodes = {f"v-node-{i}": ("done" if i < 1 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [SPEC_ID], "v-dep": [], "v-runs": [],
    }}
    data = skill_board(versions=[version], spec_dir="specs/098-numbered")
    with running_board(data, tmp_path) as (base, db):
        code, _rep, raw = run_skill(
            "tf-test-plan",
            ["--version", VERSION, "--repo-root", str(repo), "--apply"],
            base=base,
        )
        import sqlite3

        conn = sqlite3.connect(db)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM row_records WHERE table_id = 't-case'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert code == 0, f"带编号的场景没有被解析：\n{raw[-1500:]}"
        assert count == 13, f"带编号的 13 条场景只派生出 {count} 条用例"


class _FakeTable:
    def __init__(self, rows: dict):
        self.rows = rows

    def fid(self, name, required=True):
        return f"f-{name}"

    def value(self, row_id, name, default=None):
        return (self.rows.get(row_id) or {}).get(f"f-{name}", default)

    def row_exists(self, row_id) -> bool:
        return row_id in self.rows

    def relation(self, row_id, name) -> list:
        return list(self.value(row_id, name) or [])

    def require(self, names) -> None:
        return None


class _FakeClient:
    """只在内存里改行；indep 的写入固定失败，用来模拟末步失败。"""

    def __init__(self, ver_rows: dict, indep_rows: dict):
        self.ver = _FakeTable(ver_rows)
        self.indep = _FakeTable(indep_rows)

    def table(self, key, refresh=False):
        return {"ver": self.ver, "indep": self.indep}[key]

    def write_verified(self, op, table_key, row_id, values, expected):
        if table_key == "indep":
            return {"state": "failed", "http": 500, "error": "注入失败"}
        self.table(table_key).rows.setdefault(row_id, {}).update(values)
        return {"state": "success", "http": 200}


class _FakeReport:
    def __init__(self):
        self.writes: list = []

    def check(self, *a, **k):
        return None

    def note(self, *a, **k):
        return None

    def write(self, *a, **k):
        self.writes.append((a, k))

    def finish(self, *a, **k):
        return None


@pytest.mark.xfail(strict=True, reason="B4：放弃先摘版本关系再改状态，末步失败不回滚")
def test_b4_drop_is_atomic_on_failure() -> None:
    """最后一步失败时，前面摘掉的版本关联必须还在。"""
    import argparse
    import sys

    sys.path.insert(0, str(SKILLS / "tf-lifecycle" / "scripts"))
    import tf_lifecycle

    ver_rows = {VERSION: {f"f-独立需求管理": [SPEC_ID]}}
    indep_rows = {SPEC_ID: {"f-验收状态": "pending"}}
    client = _FakeClient(ver_rows, indep_rows)
    args = argparse.Namespace(spec=SPEC_ID, reason="083 复现用", apply=True, dry_run=False)
    report = _FakeReport()

    with pytest.raises(Exception):
        tf_lifecycle.do_drop(args, report, client, client.ver, client.indep)

    assert client.ver.rows[VERSION]["f-独立需求管理"] == [SPEC_ID], (
        "置 dropped 失败后，版本关联已经被摘掉了（半改）"
    )


@pytest.mark.xfail(strict=True, reason="S7：测试验收判定不通过时只抛错退出，不把节点落成 failed")
def test_s7_rejected_acceptance_must_mark_failed(tmp_path) -> None:
    """跑了验收且结论不通过，节点必须是 failed，不能停在 todo。"""
    run_id = f"{VERSION}--042-US1-AS1"
    nodes = {f"v-node-{i}": ("done" if i < 5 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [SPEC_ID], "v-dep": [], "v-runs": [run_id], "v-bug": [],
    }}
    data = skill_board(
        versions=[version],
        runs=[{"id": run_id, "values": {
            "r-id": run_id, "r-case-no": "042-US1-AS1",
            "r-case": ["042-US1-AS1"], "r-state": "done", "r-result": "fail",
        }}],
    )
    with running_board(data, tmp_path) as (base, db):
        code, _rep, raw = run_skill(
            "tf-test-check", ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply"],
            base=base,
        )
        values = _row(db, "t-ver", VERSION)
        assert code != 0, f"有失败执行记录却通过了验收：\n{raw[-1200:]}"
        assert values["v-node-5"] == "failed", (
            f"验收不通过但节点停在 {values['v-node-5']!r}，无法区分“没做”与“没过”"
        )


def test_s4c_defect_only_version_advances(tmp_path) -> None:
    """只挂缺陷的版本：缺陷脱离 open 且单测通过，开发节点就能推进（v0.8.4 的形态）。"""
    bug_id = "BUG-083-01"
    nodes = {f"v-node-{i}": ("done" if i < 2 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [], "v-dep": [], "v-runs": [], "v-bug": [bug_id],
    }}
    data = skill_board(
        versions=[version],
        bugs=[{"id": bug_id, "values": {"b-id": bug_id, "b-status": "fixing"}}],
        version_bugs=[bug_id],
    )
    with running_board(data, tmp_path) as (base, db):
        code, report, raw = run_skill(
            "tf-dev-implement",
            ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply", "--test-cmd", "true"],
            base=base,
        )
        assert code == 0, f"缺陷修复版本推不动开发节点：\n{raw[-1500:]}"
        assert _row(db, "t-ver", VERSION)["v-node-2"] == "done"


def test_s4d_open_defect_blocks_dev_node(tmp_path) -> None:
    """缺陷还是 open 时，开发节点不能收口——状态没动过就没有修复证据。"""
    bug_id = "BUG-083-02"
    nodes = {f"v-node-{i}": ("done" if i < 2 else "todo") for i in range(6)}
    version = {"id": VERSION, "values": {
        "v-version": VERSION, "v-status": "planned", **nodes,
        "v-indep": [], "v-dep": [], "v-runs": [], "v-bug": [bug_id],
    }}
    data = skill_board(
        versions=[version],
        bugs=[{"id": bug_id, "values": {"b-id": bug_id, "b-status": "open"}}],
        version_bugs=[bug_id],
    )
    with running_board(data, tmp_path) as (base, db):
        code, _rep, raw = run_skill(
            "tf-dev-implement",
            ["--version", VERSION, "--repo-root", str(REPO_ROOT), "--apply", "--test-cmd", "true"],
            base=base,
        )
        assert code != 0, f"缺陷仍是 open 却收口了开发节点：\n{raw[-1000:]}"
        assert _row(db, "t-ver", VERSION)["v-node-2"] == "todo"


def test_test_plan_reuse_from_previous_version(tmp_path) -> None:
    """修复版复用上一版用例：只为本版新建执行记录，不重新派生。"""
    src_run = f"{VERSION}--042-US1-AS1"
    new_version = "v0.8.4"

    def ver(vid, nodes_done, runs):
        return {"id": vid, "values": {
            "v-version": vid, "v-status": "planned",
            **{f"v-node-{i}": ("done" if i < nodes_done else "todo") for i in range(6)},
            "v-indep": [], "v-dep": [], "v-runs": runs, "v-bug": [],
        }}

    data = skill_board(
        versions=[ver(VERSION, 2, [src_run]), ver(new_version, 1, [])],
        runs=[{"id": src_run, "values": {
            "r-id": src_run, "r-case-no": "042-US1-AS1",
            "r-case": ["042-US1-AS1"], "r-state": "done", "r-result": "fail",
        }}],
        cases=[{"id": "042-US1-AS1", "values": {"c-id": "042-US1-AS1", "c-spec": [SPEC_ID]}}],
    )
    with running_board(data, tmp_path) as (base, db):
        code, _rep, raw = run_skill(
            "tf-test-plan",
            ["--version", new_version, "--reuse-from", VERSION,
             "--repo-root", str(REPO_ROOT), "--apply"],
            base=base,
        )
        assert code == 0, f"复用用例失败：\n{raw[-1500:]}"
        values = _row(db, "t-ver", new_version)
        assert values["v-runs"] == [f"{new_version}--042-US1-AS1"]
        assert values["v-node-1"] == "done", "测试设计节点没有推进"
