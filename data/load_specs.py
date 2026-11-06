#!/usr/bin/env python3
"""把 002/003/004 三个 spec 与 1 条依赖需求写进 tf 项目，并清掉 21 条 TF 条目。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_specs.py
"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-Agent-Id": "agent-tableflow"}

SPECS = [
    ("tf-spec-002", {
        "tf-i-id": "002",
        "tf-i-clause": "字段体系与关联",
        "tf-i-dir": "specs/002-field-system",
        "tf-i-status": "待启动",
        "tf-i-constitution": "未开始",
        "tf-i-specify": "未开始",
        "tf-i-plan": "未开始",
        "tf-i-task": "未开始",
        "tf-i-implement": "未开始",
    }),
    ("tf-spec-003", {
        "tf-i-id": "003",
        "tf-i-clause": "计算字段与发布判定",
        "tf-i-dir": "specs/003-calculated-fields",
        "tf-i-status": "阻塞：需先修订宪法",
        "tf-i-constitution": "未开始",
        "tf-i-specify": "未开始",
        "tf-i-plan": "未开始",
        "tf-i-task": "未开始",
        "tf-i-implement": "未开始",
    }),
    ("tf-spec-004", {
        "tf-i-id": "004",
        "tf-i-clause": "界面体验",
        "tf-i-dir": "specs/004-ui-polish",
        "tf-i-status": "待启动",
        "tf-i-constitution": "未开始",
        "tf-i-specify": "未开始",
        "tf-i-plan": "未开始",
        "tf-i-task": "未开始",
        "tf-i-implement": "未开始",
    }),
]

VERSION = ("tf-v-030", {
    "tf-v-ver": "v0.3.0",
    "tf-v-date": "2026-12-15T00:00:00+08:00",
    "tf-v-status": "planned",
    "tf-v-indep": ["tf-spec-002", "tf-spec-003", "tf-spec-004"],
    "tf-v-note": "字段体系 + 计算字段 + 界面体验",
})

DEP = ("tf-dep-01", {
    "tf-d-id": "DEP-01",
    "tf-d-clause": "宪法 v6.0.0 修订（计算字段、人经 Agent 写）",
    "tf-d-spec": "constitution.md",
    "tf-d-indep": ["tf-spec-003"],
    "tf-d-impact": "003 全部；004 的状态色依赖 002 的 tone 字段",
    "tf-d-regress": "未开始",
    "tf-d-status": "待办",
    "tf-d-version": ["tf-v-030"],
})


def call(method: str, path: str, body: dict | None = None) -> dict:
    response = httpx.request(method, f"{BASE}{path}", json=body, headers=HEADERS, timeout=10)
    data = response.json()
    if data.get("result") != "success":
        print(f"  ! {method} {path} → {response.status_code} {data}")
    return data


def main() -> int:
    removed = 0
    for index in range(1, 22):
        row_id = f"TF-{index:02d}"
        if call("DELETE", f"/api/agent/rows/{row_id}").get("result") == "success":
            removed += 1
    print(f"已删除 TF 条目 {removed} 条")

    for row_id, values in SPECS:
        call("POST", "/api/agent/tables/tf-indep/rows", {"id": row_id, "values": values})
    call("POST", "/api/agent/tables/tf-ver/rows", {"id": VERSION[0], "values": VERSION[1]})
    call("POST", "/api/agent/tables/tf-dep/rows", {"id": DEP[0], "values": DEP[1]})

    print("完成：3 个 spec + 1 个版本 + 1 条依赖需求")
    return 0


if __name__ == "__main__":
    sys.exit(main())
