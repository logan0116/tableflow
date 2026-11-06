#!/usr/bin/env python3
"""用 Agent 写接口把 tableflow 自己的规格与版本灌进 tableflow。

表结构与 fd_system 完全一致（共用 data/template_fd_system.py）。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_tableflow.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fd_system import build_tables  # noqa: E402

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-Agent-Id": "agent-tableflow"}
PROJECT_ID = "tableflow"

TABLES = build_tables("tf", "tf")

ROWS = {
    "tf-ver": [
        ("tf-v-010", {
            "tf-v-ver": "v0.1.0",
            "tf-v-status": "dropped",
            "tf-v-note": "单表只读看板（已被 v0.2.0 取代）",
        }),
        ("tf-v-020", {
            "tf-v-ver": "v0.2.0",
            "tf-v-date": "2026-11-30T00:00:00+08:00",
            "tf-v-status": "planned",
            "tf-v-indep": ["tf-spec-001"],
            "tf-v-dev": "34/36 任务完成",
            "tf-v-test": "pytest 27 passed",
            "tf-v-bug": "—",
            "tf-v-doc": "README / quickstart 已更新",
            "tf-v-cond": "T034/T035 性能验收通过",
            "tf-v-note": "多维表格：项目→多表 + relation 关联 + Agent 写接口",
        }),
    ],
    "tf-indep": [
        ("tf-spec-001", {
            "tf-i-id": "001",
            "tf-i-clause": "多维表格看板",
            "tf-i-dir": "specs/001-readonly-dashboard",
            "tf-i-scenes": 3,
            "tf-i-tasks": 36,
            "tf-i-status": "实现中",
            "tf-i-constitution": "完成（v5.0.0）",
            "tf-i-specify": "完成",
            "tf-i-plan": "完成",
            "tf-i-task": "完成",
            "tf-i-implement": "进行中（34/36）",
        }),
    ],
    "tf-dep": [],
}


def call(method: str, path: str, body: dict | None = None) -> dict:
    response = httpx.request(method, f"{BASE}{path}", json=body, headers=HEADERS, timeout=10)
    data = response.json()
    if data.get("result") != "success":
        print(f"  ! {method} {path} → {response.status_code} {data}")
    return data


def main() -> int:
    call("POST", "/api/agent/projects", {"id": PROJECT_ID, "name": "tableflow"})

    for table in TABLES:
        call("POST", f"/api/agent/projects/{PROJECT_ID}/tables",
             {"id": table["id"], "name": table["name"], "order": table["order"]})
    for table in TABLES:
        for field_id, name, field_type, options in table["fields"]:
            call("POST", f"/api/agent/tables/{table['id']}/fields",
                 {"id": field_id, "name": name, "type": field_type, "options": options})
    for table in TABLES:
        for row_id, values in ROWS.get(table["id"], []):
            call("POST", f"/api/agent/tables/{table['id']}/rows",
                 {"id": row_id, "values": values})

    print("完成：tableflow（3 表，结构同 fd_system）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
