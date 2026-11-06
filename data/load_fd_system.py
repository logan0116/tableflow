#!/usr/bin/env python3
"""用 Agent 写接口把 fd_system 项目灌进 tableflow（真实项目试用）。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_fd_system.py

v0.3.0：行 id 使用业务编号；依赖变更需求表删除「所属版本」；enum 选项带 tone。
行写入顺序按依赖：独立需求 → 依赖需求 → 版本（relation 目标行先存在）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fd_system import build_tables  # noqa: E402

BASE = os.environ.get("TABLEFLOW_API_BASE", "http://127.0.0.1:8000")
HEADERS = {"X-Agent-Id": "agent-fd-system", "X-Origin": "seed"}
PROJECT_ID = "fd_system"

TABLES = build_tables("fd", "")

# 行 id 即业务编号（与「编号」「版本号」列一致）。
ROWS = {
    "fd-indep": [
        ("UD-04-AR", {"i-id": "UD-04-AR", "i-clause": "安装脚本更新"}),
    ],
    "fd-dep": [
        ("UD-01-BR", {
            "d-id": "UD-01-BR",
            "d-clause": "基于新版本知识图谱的图谱相关 skill 的更新",
        }),
        ("UD-02-BR", {"d-id": "UD-02-BR", "d-clause": "embedding 更新"}),
        ("UD-03-BR", {"d-id": "UD-03-BR", "d-clause": "界面推荐案例更新"}),
    ],
    "fd-ver": [
        ("7.0.0", {"v-ver": "7.0.0", "v-status": "released"}),
        ("7.0.1", {
            "v-ver": "7.0.1",
            "v-date": "2026-11-10T00:00:00+08:00",
            "v-status": "planned",
            "v-indep": ["UD-04-AR"],
            "v-dep": ["UD-01-BR", "UD-02-BR", "UD-03-BR"],
        }),
        ("7.0.2", {
            "v-ver": "7.0.2",
            "v-date": "2026-11-20T00:00:00+08:00",
            "v-status": "planned",
        }),
        ("7.1.0", {
            "v-ver": "7.1.0",
            "v-date": "2026-11-30T00:00:00+08:00",
            "v-status": "planned",
        }),
    ],
}

ROW_ORDER = ["fd-indep", "fd-dep", "fd-ver"]


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
    call(client, "POST", "/api/agent/projects", {"id": PROJECT_ID, "name": "fd_system"}, strict=strict)
    # 先建全部表格，再建字段（relation 需要目标表已存在），最后按依赖顺序写行。
    for table in TABLES:
        call(client, "POST", f"/api/agent/projects/{PROJECT_ID}/tables",
             {"id": table["id"], "name": table["name"], "order": table["order"]}, strict=strict)
    for table in TABLES:
        print(f"表：{table['name']}")
        for field_id, name, field_type, options in table["fields"]:
            call(client, "POST", f"/api/agent/tables/{table['id']}/fields",
                 {"id": field_id, "name": name, "type": field_type, "options": options}, strict=strict)
    for table_id in ROW_ORDER:
        for row_id, values in ROWS.get(table_id, []):
            call(client, "POST", f"/api/agent/tables/{table_id}/rows/{row_id}",
                 {"values": values}, strict=strict)


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as client:
        run(client)
    print("完成：http://127.0.0.1:5173/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
