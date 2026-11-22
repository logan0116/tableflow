#!/usr/bin/env python3
"""board@4 验证夹具：经 Agent 写接口在**临时库**建六表并写一版两条规格。

只服务 ``specs/024-role-skills`` 的技能验证，不替代 T1 的正式迁移，也永远不碰真实库。
运行前先启动一个指向临时库的本地后端，并把 ``TF_BASE`` 指过去：

    TABLEFLOW_DB=/tmp/tf024/tf024.db \\
      backend/.venv/bin/python -m uvicorn tableflow.app:app --port 18090
    TF_BASE=http://127.0.0.1:18090 python3 specs/024-role-skills/verify/seed_board4_fixture.py

字段按 board@4 的名称与类型建，计算字段从简（技能在客户端复算，不依赖看板计算值）。
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = (os.environ.get("TF_BASE") or "http://127.0.0.1:18090").rstrip("/")
AGENT = os.environ.get("TF_AGENT", "agent-tf-024-fixture")
PROJECT = os.environ.get("TF024_PROJECT", "tf024verify")
PREFIX = os.environ.get("TF024_PREFIX", "v024")
REPO_ROOT = Path(__file__).resolve().parents[3]

TABLE_NAMES = {
    "ver": "版本管理",
    "indep": "独立规格需求",
    "dep": "依赖变更需求",
    "case": "测试用例",
    "run": "用例执行情况",
    "bug": "缺陷",
}

ENUM = {
    "stage4": [
        {"value": "todo", "label": "未开始", "tone": "neutral"},
        {"value": "doing", "label": "进行中", "tone": "info"},
        {"value": "done", "label": "已完成", "tone": "success"},
        {"value": "failed", "label": "失败", "tone": "danger"},
    ],
    "stage4na": [
        {"value": "todo", "label": "未开始", "tone": "neutral"},
        {"value": "doing", "label": "进行中", "tone": "info"},
        {"value": "done", "label": "已完成", "tone": "success"},
        {"value": "failed", "label": "失败", "tone": "danger"},
        {"value": "na", "label": "不适用", "tone": "neutral"},
    ],
    "acceptance": [
        {"value": "pending", "label": "待验收", "tone": "warning"},
        {"value": "accepted", "label": "已验收", "tone": "success"},
        {"value": "rejected", "label": "已拒绝", "tone": "danger"},
    ],
    "release": [
        {"value": "planned", "label": "计划中", "tone": "info"},
        {"value": "released", "label": "已发布", "tone": "success"},
        {"value": "dropped", "label": "已放弃", "tone": "neutral"},
    ],
    "regress": [
        {"value": "todo", "label": "未合入", "tone": "neutral"},
        {"value": "doing", "label": "待验证", "tone": "info"},
        {"value": "passed", "label": "通过", "tone": "success"},
        {"value": "failed", "label": "不通过", "tone": "danger"},
    ],
    "run_state": [
        {"value": "todo", "label": "未执行", "tone": "neutral"},
        {"value": "done", "label": "已执行", "tone": "success"},
    ],
    "run_result": [
        {"value": "pass", "label": "通过", "tone": "success"},
        {"value": "fail", "label": "失败", "tone": "danger"},
        {"value": "blocked", "label": "阻塞", "tone": "warning"},
        {"value": "skip", "label": "跳过", "tone": "neutral"},
    ],
    "priority": [
        {"value": "P0", "label": "P0", "tone": "danger"},
        {"value": "P1", "label": "P1", "tone": "warning"},
        {"value": "P2", "label": "P2", "tone": "neutral"},
    ],
    "bug_status": [
        {"value": "open", "label": "待修", "tone": "danger"},
        {"value": "fixing", "label": "修复中", "tone": "warning"},
        {"value": "verifying", "label": "待验证", "tone": "info"},
        {"value": "closed", "label": "已关闭", "tone": "success"},
    ],
    "severity": [
        {"value": "blocker", "label": "阻塞", "tone": "danger"},
        {"value": "critical", "label": "严重", "tone": "danger"},
        {"value": "major", "label": "主要", "tone": "warning"},
        {"value": "minor", "label": "次要", "tone": "neutral"},
    ],
    "bug_source": [
        {"value": "ms_case", "label": "MS用例", "tone": "info"},
        {"value": "manual", "label": "手工", "tone": "neutral"},
        {"value": "prod", "label": "生产", "tone": "danger"},
        {"value": "review", "label": "评审", "tone": "warning"},
    ],
    "spec_revision": [
        {"value": "not_needed", "label": "不需要", "tone": "neutral"},
        {"value": "pending", "label": "待写回", "tone": "warning"},
        {"value": "done", "label": "已写回", "tone": "success"},
    ],
}


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Agent-Id", AGENT)
    request.add_header("X-Origin", "human-request")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
            return {"http": response.status, **payload}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"detail": raw[:300]}
        return {"http": exc.code, **payload}


def must(resp: dict, action: str) -> dict:
    if resp.get("http") != 200 or resp.get("result") != "success":
        raise SystemExit(f"[fixture] {action} 失败：{json.dumps(resp, ensure_ascii=False)}")
    return resp


def create_table(key: str, order: int) -> str:
    table_id = f"{PREFIX}-{key}"
    if call("GET", f"/api/tables/{table_id}/table").get("http") == 200:
        return table_id
    must(
        call(
            "POST",
            f"/api/agent/projects/{PROJECT}/tables",
            {"id": table_id, "name": TABLE_NAMES[key], "order": order},
        ),
        f"建表 {key}",
    )
    return table_id


def create_field(
    table_id: str, field_id: str, name: str, field_type: str, order: int, options: dict | None = None
) -> None:
    if any(
        field.get("id") == field_id
        for field in call("GET", f"/api/tables/{table_id}/table").get("fields", [])
    ):
        return
    must(
        call(
            "POST",
            f"/api/agent/tables/{table_id}/fields",
            {
                "id": field_id,
                "name": name,
                "type": field_type,
                "options": options,
                "order": order,
            },
        ),
        f"建字段 {table_id}.{name}",
    )


def enum(name: str) -> dict:
    return {"items": ENUM[name]}


def relation(target: str) -> dict:
    return {"table_id": target}


def scenario_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(
        re.findall(
            r"^\d+\. \*\*Given\*\* .+?\s*\*\*When\*\* .+?\s*\*\*Then\*\* .+$",
            text,
            flags=re.M,
        )
    )


def main() -> int:
    # 项目（临时库内）
    if call("GET", f"/api/projects/{PROJECT}/tables").get("http") == 404:
        must(
            call("POST", "/api/agent/projects", {"id": PROJECT, "name": "024 角色技能验证夹具"}),
            "建项目",
        )

    tables = {key: create_table(key, order) for order, key in enumerate(TABLE_NAMES, start=1)}

    # indep
    indep = tables["indep"]
    indep_fields = [
        ("v024-i-id", "编号", "text", None),
        ("v024-i-clause", "条款", "text", None),
        ("v024-i-dir", "规格目录", "text", None),
        ("v024-i-scenes", "场景数", "number", {"decimals": 0}),
        ("v024-i-tasks", "任务总数", "number", {"decimals": 0}),
        ("v024-i-stage-constitution", "speckit-constitution状态", "enum", enum("stage4na")),
        ("v024-i-stage-specify", "speckit-specify状态", "enum", enum("stage4na")),
        ("v024-i-stage-plan", "speckit-plan状态", "enum", enum("stage4na")),
        ("v024-i-stage-task", "speckit-task状态", "enum", enum("stage4na")),
        ("v024-i-stage-implement", "speckit-implement状态", "enum", enum("stage4")),
        ("v024-i-stage-clarify", "speckit-clarify状态", "enum", enum("stage4na")),
        ("v024-i-stage-analyze", "speckit-analyze状态", "enum", enum("stage4na")),
        ("v024-i-stage-checklist", "speckit-checklist状态", "enum", enum("stage4na")),
        ("v024-i-acceptance", "验收状态", "enum", enum("acceptance")),
        ("v024-i-owner", "负责人", "text", None),
    ]
    for order, (fid, name, ftype, options) in enumerate(indep_fields, start=1):
        create_field(indep, fid, name, ftype, order, options)

    # case
    case = tables["case"]
    case_fields = [
        ("v024-c-id", "用例号", "text", None),
        ("v024-c-name", "用例名", "text", None),
        ("v024-c-indep", "来源规格", "relation", relation(indep)),
        ("v024-c-precondition", "前置条件", "text", None),
        ("v024-c-steps", "操作步骤", "text", None),
        ("v024-c-expect", "预期结果", "text", None),
        ("v024-c-priority", "优先级", "enum", enum("priority")),
        ("v024-c-owner", "负责人", "text", None),
    ]
    for order, (fid, name, ftype, options) in enumerate(case_fields, start=1):
        create_field(case, fid, name, ftype, order, options)

    # run（字段 id 后缀 -state/-result/-case_no 供 020 协议识别）
    run = tables["run"]
    run_fields = [
        ("v024-r-id", "执行编号", "text", None),
        ("v024-r-case_no", "用例号", "text", None),
        ("v024-r-case", "用例", "relation", relation(case)),
        ("v024-r-state", "执行状态", "enum", enum("run_state")),
        ("v024-r-result", "执行结果", "enum", enum("run_result")),
        ("v024-r-evidence", "证据", "text", None),
        ("v024-r-executed_at", "执行时间", "datetime", {"with_time": True}),
        ("v024-r-executor", "执行人", "text", None),
        ("v024-r-note", "备注", "text", None),
    ]
    for order, (fid, name, ftype, options) in enumerate(run_fields, start=1):
        create_field(run, fid, name, ftype, order, options)

    # dep
    dep = tables["dep"]
    dep_fields = [
        ("v024-d-id", "编号", "text", None),
        ("v024-d-clause", "条款", "text", None),
        ("v024-d-spec", "关联的独立规格需求", "relation", relation(indep)),
        ("v024-d-impact", "影响面", "text", None),
        ("v024-d-regress", "回归状态", "enum", enum("regress")),
        ("v024-d-evidence", "证据", "text", None),
        ("v024-d-rest", "剩余事项", "text", None),
        ("v024-d-spec-revision", "规格修订", "enum", enum("spec_revision")),
        ("v024-d-owner", "负责人", "text", None),
    ]
    for order, (fid, name, ftype, options) in enumerate(dep_fields, start=1):
        create_field(dep, fid, name, ftype, order, options)

    # bug
    bug = tables["bug"]
    bug_fields = [
        ("v024-b-id", "编号", "text", None),
        ("v024-b-title", "标题", "text", None),
        ("v024-b-status", "状态", "enum", enum("bug_status")),
        ("v024-b-severity", "严重度", "enum", enum("severity")),
        ("v024-b-source", "来源", "enum", enum("bug_source")),
        ("v024-b-indep", "关联规格", "relation", relation(indep)),
        ("v024-b-found", "发现版本号", "text", None),
        ("v024-b-evidence", "证据", "text", None),
        ("v024-b-rest", "剩余事项", "text", None),
        ("v024-b-ms", "MS用例号", "text", None),
        ("v024-b-owner", "负责人", "text", None),
    ]
    for order, (fid, name, ftype, options) in enumerate(bug_fields, start=1):
        create_field(bug, fid, name, ftype, order, options)

    # ver（最后建，relation 指向已完成表）
    ver = tables["ver"]
    ver_fields = [
        ("v024-v-id", "版本号", "text", None),
        ("v024-v-release_date", "发布时间", "datetime", {"with_time": False}),
        ("v024-v-stage-plan", "版本需求设计", "enum", enum("stage4")),
        ("v024-v-stage-test_design", "测试设计", "enum", enum("stage4")),
        ("v024-v-stage-dev", "开发", "enum", enum("stage4")),
        ("v024-v-stage-dev_accept", "开发验收", "enum", enum("stage4")),
        ("v024-v-stage-test", "测试", "enum", enum("stage4")),
        ("v024-v-stage-test_accept", "测试验收", "enum", enum("stage4")),
        ("v024-v-status", "发布状态", "enum", enum("release")),
        ("v024-v-specs", "独立需求管理", "relation", relation(indep)),
        ("v024-v-changes", "依赖需求管理", "relation", relation(dep)),
        ("v024-v-runs", "测试用例", "relation", relation(run)),
        ("v024-v-bugs", "Bug管理", "relation", relation(bug)),
        ("v024-v-note", "变更说明", "text", None),
        ("v024-v-owner", "负责人", "text", None),
    ]
    for order, (fid, name, ftype, options) in enumerate(ver_fields, start=1):
        create_field(ver, fid, name, ftype, order, options)

    # 两条规格：017（tasks 全勾选，供开发节点），019（场景最多，供测试设计/执行）。
    # TF024_WITH_099=1 时追加 099-AR（D-01 的 --apply 回放：未勾任务 + 待验收）。
    specs = [
        {
            "id": "017-AR",
            "clause": "Bug表与版本表关系补正",
            "dir": "specs/017-bug-relation/",
            "implement": "todo",
            "acceptance": "accepted",
            "tasks": 6,
        },
        {
            "id": "019-AR",
            "clause": "看板测试体系契约 board@4（六表）",
            "dir": "specs/019-test-contract/",
            "implement": "done",
            "acceptance": "accepted",
            "tasks": 0,
        },
    ]
    if os.environ.get("TF024_WITH_099") == "1":
        specs.append(
            {
                "id": "099-AR",
                "clause": "D-01 --apply 回放夹具",
                "dir": "specs/024-role-skills/verify/fixtures/099-d01/",
                "implement": "todo",
                "acceptance": "pending",
                "tasks": 1,
            }
        )
    for spec in specs:
        spec_id = spec["id"]
        if call("GET", f"/api/tables/{indep}/rows/{spec_id}").get("http") == 200:
            continue
        path = REPO_ROOT / spec["dir"] / "spec.md"
        scenes = scenario_count(path)
        values = {
            "v024-i-id": spec_id,
            "v024-i-clause": spec["clause"],
            "v024-i-dir": spec["dir"],
            "v024-i-scenes": scenes,
            "v024-i-tasks": spec["tasks"],
            "v024-i-stage-constitution": "na",
            "v024-i-stage-specify": "done",
            "v024-i-stage-plan": "done",
            "v024-i-stage-task": "done",
            "v024-i-stage-implement": spec["implement"],
            "v024-i-stage-clarify": "na",
            "v024-i-stage-analyze": "na",
            "v024-i-stage-checklist": "na",
            "v024-i-acceptance": spec["acceptance"],
            "v024-i-owner": "agent-tf-024-fixture",
        }
        must(call("POST", f"/api/agent/tables/{indep}/rows/{spec_id}", {"values": values}), f"写规格 {spec_id}")

    version = "v0.7.0"
    if call("GET", f"/api/tables/{ver}/rows/{version}").get("http") == 404:
        values = {
            "v024-v-id": version,
            "v024-v-stage-plan": "todo",
            "v024-v-stage-test_design": "todo",
            "v024-v-stage-dev": "todo",
            "v024-v-stage-dev_accept": "todo",
            "v024-v-stage-test": "todo",
            "v024-v-stage-test_accept": "todo",
            "v024-v-status": "planned",
            "v024-v-specs": [spec["id"] for spec in specs],
            "v024-v-changes": [],
            "v024-v-runs": [],
            "v024-v-bugs": [],
            "v024-v-note": "024 技能验证夹具",
            "v024-v-owner": "agent-tf-024-fixture",
        }
        must(call("POST", f"/api/agent/tables/{ver}/rows/{version}", {"values": values}), "写版本")

    print(
        json.dumps(
            {
                "ok": True,
                "base": BASE,
                "project": PROJECT,
                "tables": tables,
                "version": version,
                "specs": [spec["id"] for spec in specs],
                "scenario_counts": {
                    spec["id"]: scenario_count(REPO_ROOT / spec["dir"] / "spec.md")
                    for spec in specs
                },
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
