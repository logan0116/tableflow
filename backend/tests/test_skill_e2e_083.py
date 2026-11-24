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
                version_indep: list[str] | None = None, version_runs: list[str] | None = None):
    """技能可用的最小看板：表名必须与 board 契约一致（技能按名称解析）。"""
    ver_values = {
        "v-version": VERSION,
        "v-status": version_status,
        **{f"v-node-{i}": "todo" for i in range(6)},
        "v-indep": list(version_indep if version_indep is not None else [SPEC_ID]),
        "v-dep": [],
        "v-runs": list(version_runs or []),
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
                        ],
                        "rows": [{"id": VERSION, "values": ver_values}],
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
                        ],
                        "rows": [
                            {
                                "id": SPEC_ID,
                                "values": {
                                    "i-id": SPEC_ID,
                                    "i-clause": "US1-US4",
                                    "i-dir": SPEC_DIR,
                                    "i-scen": 13,
                                    "i-accept": indep_accept,
                                    "i-constitution": "",
                                    "i-evidence": "",
                                    **{f"i-stage-{i}": "todo" for i in range(5)},
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
                        "rows": [],
                    },
                    {
                        "id": "t-run",
                        "name": "用例执行情况",
                        "order": 4,
                        "fields": [
                            _field("r-id", "执行编号", "text", None, 1),
                            _field("r-case-no", "用例号", "text", None, 2),
                        ],
                        "rows": [],
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


@pytest.mark.xfail(strict=True, reason="S1：spec_rel 未定义，结构检查通过后 NameError")
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


@pytest.mark.xfail(strict=True, reason="S5：写路径只看 args.apply，忽略 args.dry_run")
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
