#!/usr/bin/env python3
"""用 Agent 写接口把 tableflow 自己的规格与版本灌进 tableflow。

表结构与 fd_system 完全一致（共用 data/template_fd_system.py）。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_tableflow.py

v0.3.0：行 id 使用业务编号；行写入顺序按依赖（独立需求先于版本）。
计算字段（003）由写侧算好落库，行数据不再手写开发进度 / Bug / 发布条件。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fd_system import build_tables  # noqa: E402

BASE = os.environ.get("TABLEFLOW_API_BASE", "http://127.0.0.1:8000")
HEADERS = {"X-Agent-Id": "agent-tableflow", "X-Origin": "seed"}
PROJECT_ID = "tableflow"

TABLES = build_tables("tf", "tf")

ROWS = {
    "tf-indep": [
        ("001-AR", {
            "tf-i-id": "001-AR",
            "tf-i-clause": "多维表格看板",
            "tf-i-dir": "specs/001-readonly-dashboard",
            "tf-i-scenes": 3,
            "tf-i-tasks": 36,
            "tf-i-status": "实现中",
            "tf-i-constitution": "完成（v5.0.0）",
            "tf-i-specify": "完成",
            "tf-i-plan": "完成",
            "tf-i-task": "完成",
            "tf-i-implement": "done",
            "tf-i-clarify": "done",
            "tf-i-analyze": "done",
            "tf-i-checklist": "done",
            "tf-i-constitution-version": "v5.0.0",
            "tf-i-acceptance": "accepted",
            "tf-i-owner": "captain",
            "tf-i-priority": "P0",
        }),
    ],
    "tf-dep": [],
    "tf-ver": [
        ("v0.1.0", {
            "tf-v-ver": "v0.1.0",
            "tf-v-status": "dropped",
            "tf-v-bug-open": 0,
            "tf-v-doc": "na",
            "tf-v-note": "单表只读看板（已被 v0.2.0 取代）",
        }),
        ("v0.2.0", {
            "tf-v-ver": "v0.2.0",
            "tf-v-date": "2026-11-30T00:00:00+08:00",
            "tf-v-status": "planned",
            "tf-v-indep": ["001-AR"],
            "tf-v-test": "pytest 27 passed",
            "tf-v-bug-open": 0,
            "tf-v-doc": "done",
            "tf-v-note": "多维表格：项目→多表 + relation 关联 + Agent 写接口",
        }),
    ],
}

FIELD_ORDER = ["tf-indep", "tf-dep", "tf-ver"]
ROW_ORDER = ["tf-indep", "tf-dep", "tf-ver"]


def call(
    client: httpx.Client,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    strict: bool = False,
) -> dict:
    response = client.request(method, path, json=body, headers=HEADERS)
    data = response.json()
    if data.get("result") != "success":
        message = f"{method} {path} → {response.status_code} {data}"
        if strict:
            raise RuntimeError(message)
        print(f"  ! {message}")
    return data


def run(client: httpx.Client, *, strict: bool = False) -> None:
    call(client, "POST", "/api/agent/projects", {"id": PROJECT_ID, "name": "tableflow"})

    for table in TABLES:
        call(client, "POST", f"/api/agent/projects/{PROJECT_ID}/tables",
             {"id": table["id"], "name": table["name"], "order": table["order"]}, strict=strict)
    table_by_id = {table["id"]: table for table in TABLES}
    for table_id in FIELD_ORDER:
        table = table_by_id[table_id]
        for field_id, name, field_type, options in table["fields"]:
            call(client, "POST", f"/api/agent/tables/{table_id}/fields",
                 {"id": field_id, "name": name, "type": field_type, "options": options}, strict=strict)
    for table_id in ROW_ORDER:
        for row_id, values in ROWS.get(table_id, []):
            call(client, "POST", f"/api/agent/tables/{table_id}/rows/{row_id}",
                 {"values": values}, strict=strict)


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as client:
        run(client)
    print("完成：tableflow（3 表，结构同 fd_system）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
