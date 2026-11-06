#!/usr/bin/env python3
"""用 Agent 写接口把 fd_system 项目灌进 tableflow（真实项目试用）。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_fd_system.py

幂等：已存在的表/字段/行会返回 failed，可忽略；重复执行不会重复建。
"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-Agent-Id": "agent-fd-system"}
PROJECT_ID = "fd_system"


def call(method: str, path: str, body: dict | None = None) -> dict:
    response = httpx.request(method, f"{BASE}{path}", json=body, headers=HEADERS, timeout=10)
    data = response.json()
    if data.get("result") != "success":
        print(f"  ! {method} {path} → {response.status_code} {data}")
    return data


def create_project(project_id: str, name: str) -> None:
    call("POST", "/api/agent/projects", {"id": project_id, "name": name})


TABLES = [
    {
        "id": "fd-ver",
        "name": "版本管理",
        "order": 1,
        "fields": [
            ("v-ver", "版本号", "text", None),
            ("v-date", "发布时间", "datetime", None),
            ("v-status", "发布状态", "enum", [
                {"value": "released", "label": "已发布"},
                {"value": "planned", "label": "计划中"},
                {"value": "dropped", "label": "已废弃"},
            ]),
            ("v-indep", "需求关联（独立）", "relation", {"table_id": "fd-indep"}),
            ("v-dep", "需求关联（依赖）", "relation", {"table_id": "fd-dep"}),
            ("v-dev", "开发进度", "text", None),
            ("v-test", "测试进度", "text", None),
            ("v-bug", "Bug已清空", "text", None),
            ("v-doc", "文档状态", "text", None),
            ("v-cond", "发布条件", "text", None),
            ("v-owner", "负责人", "text", None),
            ("v-note", "变更说明", "text", None),
        ],
        "rows": [
            ("v-700", {"v-ver": "7.0.0", "v-status": "released"}),
            ("v-701", {"v-ver": "7.0.1", "v-date": "2026-11-10T00:00:00+08:00", "v-status": "planned"}),
            ("v-702", {"v-ver": "7.0.2", "v-date": "2026-11-20T00:00:00+08:00", "v-status": "planned"}),
            ("v-710", {
                "v-ver": "7.1.0",
                "v-date": "2026-11-30T00:00:00+08:00",
                "v-status": "planned",
                "v-dep": ["fd-ud-01", "fd-ud-02", "fd-ud-03"],
            }),
        ],
    },
    {
        "id": "fd-indep",
        "name": "独立规格需求",
        "order": 2,
        "fields": [
            ("i-id", "编号", "text", None),
            ("i-clause", "条款", "text", None),
            ("i-dir", "规格目录", "text", None),
            ("i-scenes", "场景数", "number", None),
            ("i-tasks", "任务总数", "number", None),
            ("i-status", "状态", "text", None),
            ("i-constitution", "speckit-constitution状态", "text", None),
            ("i-specify", "speckit-specify状态", "text", None),
            ("i-plan", "speckit-plan状态", "text", None),
            ("i-task", "speckit-task状态", "text", None),
            ("i-implement", "speckit-implement状态", "text", None),
        ],
        "rows": [
            ("fd-ud-04", {"i-id": "UD-04", "i-clause": "安装脚本更新"}),
        ],
    },
    {
        "id": "fd-dep",
        "name": "依赖变更需求",
        "order": 3,
        "fields": [
            ("d-id", "编号", "text", None),
            ("d-clause", "条款", "text", None),
            ("d-spec", "依赖规格", "text", None),
            ("d-indep", "关联的独立规格需求", "relation", {"table_id": "fd-indep"}),
            ("d-impact", "影响面", "text", None),
            ("d-regress", "回归状态", "text", None),
            ("d-status", "状态", "text", None),
            ("d-version", "所属版本", "relation", {"table_id": "fd-ver"}),
        ],
        "rows": [
            ("fd-ud-03", {"d-id": "UD-03", "d-clause": "界面推荐案例更新", "d-version": ["v-710"]}),
            ("fd-ud-02", {"d-id": "UD-02", "d-clause": "embedding 更新", "d-version": ["v-710"]}),
            ("fd-ud-01", {
                "d-id": "UD-01",
                "d-clause": "基于新版本知识图谱的图谱相关 skill 的更新",
                "d-version": ["v-710"],
            }),
        ],
    },
]


def main() -> int:
    create_project(PROJECT_ID, "fd_system")
    # 先建全部表格，再建字段（relation 需要目标表已存在），最后写行
    for table in TABLES:
        call("POST", f"/api/agent/projects/{PROJECT_ID}/tables",
             {"id": table["id"], "name": table["name"], "order": table["order"]})
    for table in TABLES:
        print(f"表：{table['name']}")
        for field_id, name, field_type, options in table["fields"]:
            call("POST", f"/api/agent/tables/{table['id']}/fields",
                 {"id": field_id, "name": name, "type": field_type, "options": options})
    for table in TABLES:
        for row_id, values in table["rows"]:
            call("POST", f"/api/agent/tables/{table['id']}/rows",
                 {"id": row_id, "values": values})
    print("完成：http://127.0.0.1:5173/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
