#!/usr/bin/env python3
"""用 Agent 写接口把 tableflow 自己的规格与任务灌进 tableflow（吃自己的狗粮）。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_tableflow.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-Agent-Id": "agent-tableflow"}
PROJECT_ID = "tableflow"
REPO = Path(__file__).resolve().parents[1]

TASK_RE = re.compile(r"^- \[([ xX])\] (T\d{3}) (.+)$")
PHASE_RE = re.compile(r"^## Phase (\d+): (.+)$")


def call(method: str, path: str, body: dict | None = None) -> dict:
    response = httpx.request(method, f"{BASE}{path}", json=body, headers=HEADERS, timeout=10)
    data = response.json()
    if data.get("result") != "success":
        print(f"  ! {method} {path} → {response.status_code} {data}")
    return data


def parse_tasks(path: Path) -> list[dict]:
    tasks: list[dict] = []
    phase = "未分组"
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PHASE_RE.match(line)
        if match:
            phase = match.group(2).strip()
            continue
        match = TASK_RE.match(line)
        if not match:
            continue
        mark, task_id, title = match.groups()
        title = title.replace("`", "").strip(" ：:")
        title = re.sub(r"[、，]{2,}", "、", title).strip("、")
        tasks.append(
            {
                "id": f"task-{task_id[1:]}",
                "values": {
                    "k-id": task_id,
                    "k-title": title[:80],
                    "k-phase": phase,
                    "k-status": "done" if mark.lower() == "x" else "todo",
                    "k-spec": ["spec-001"],
                },
            }
        )
    return tasks


TABLES = [
    {
        "id": "tf-spec",
        "name": "规格需求",
        "order": 1,
        "fields": [
            ("s-id", "编号", "text", None),
            ("s-name", "名称", "text", None),
            ("s-dir", "目录", "text", None),
            ("s-status", "状态", "enum", [
                {"value": "draft", "label": "草稿"},
                {"value": "approved", "label": "已批准"},
                {"value": "implementing", "label": "实现中"},
                {"value": "done", "label": "已完成"},
            ]),
            ("s-fr", "需求数", "number", None),
            ("s-sc", "成功标准数", "number", None),
            ("s-constitution", "宪法版本", "text", None),
        ],
        "rows": [
            ("spec-001", {
                "s-id": "001",
                "s-name": "多维表格看板",
                "s-dir": "specs/001-readonly-dashboard",
                "s-status": "implementing",
                "s-fr": 19,
                "s-sc": 7,
                "s-constitution": "v5.0.0",
            }),
        ],
    },
    {
        "id": "tf-task",
        "name": "任务",
        "order": 2,
        "fields": [
            ("k-id", "编号", "text", None),
            ("k-title", "标题", "text", None),
            ("k-phase", "阶段", "text", None),
            ("k-status", "状态", "enum", [
                {"value": "todo", "label": "未开始"},
                {"value": "doing", "label": "进行中"},
                {"value": "done", "label": "已完成"},
            ]),
            ("k-spec", "所属规格", "relation", {"table_id": "tf-spec"}),
        ],
        "rows": [],  # 由 tasks.md 解析后填充
    },
    {
        "id": "tf-release",
        "name": "版本",
        "order": 3,
        "fields": [
            ("r-ver", "版本号", "text", None),
            ("r-status", "状态", "enum", [
                {"value": "developing", "label": "开发中"},
                {"value": "released", "label": "已发布"},
            ]),
            ("r-spec", "规格关联", "relation", {"table_id": "tf-spec"}),
            ("r-note", "备注", "text", None),
        ],
        "rows": [
            ("rel-020", {
                "r-ver": "v0.2.0",
                "r-status": "developing",
                "r-spec": ["spec-001"],
                "r-note": "项目→多表 + relation 关联 + Agent 写接口（契约/审计/三态）",
            }),
        ],
    },
]


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
        for row_id, values in table["rows"]:
            call("POST", f"/api/agent/tables/{table['id']}/rows",
                 {"id": row_id, "values": values})

    tasks = parse_tasks(REPO / "specs" / "001-readonly-dashboard" / "tasks.md")
    for task in tasks:
        call("POST", "/api/agent/tables/tf-task/rows", {"id": task["id"], "values": task["values"]})

    done = sum(1 for task in tasks if task["values"]["k-status"] == "done")
    print(f"完成：{len(tasks)} 个任务（已完成 {done}，未开始 {len(tasks) - done}）")
    print("打开 http://127.0.0.1:5173/ 选择 tableflow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
