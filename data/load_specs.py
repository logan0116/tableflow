#!/usr/bin/env python3
"""把 002/003/004 三个 spec 与 1 条依赖需求写进 tf 项目，并清掉历史 TF 条目。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_specs.py

v0.3.0：行 id 使用业务编号（002-AR / v0.3.0 / DEP-01-BR）；
依赖变更需求表不再写「所属版本」；独立规格需求补齐 clarify/analyze/checklist 三态与治理字段。
计算字段（003）：v0.3.0 的开发进度 / 发布条件由写侧按关联需求与回归/Bug/文档状态算出。
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("TABLEFLOW_API_BASE", "http://127.0.0.1:8000")
HEADERS = {"X-Agent-Id": "agent-tableflow", "X-Origin": "seed"}

GOVERNANCE = {
    "tf-i-constitution-version": "v6.0.0",
    "tf-i-acceptance": "pending",
}

SPECS = [
    ("002-AR", {
        "tf-i-id": "002-AR",
        "tf-i-clause": "字段体系与关联",
        "tf-i-dir": "specs/002-field-system",
        "tf-i-scenes": 5,
        "tf-i-tasks": 12,
        "tf-i-status": "已完成",
        "tf-i-constitution": "完成（v6.0.0）",
        "tf-i-specify": "完成",
        "tf-i-plan": "完成",
        "tf-i-task": "完成",
        "tf-i-implement": "done",
        "tf-i-clarify": "done",
        "tf-i-analyze": "done",
        "tf-i-checklist": "done",
        "tf-i-owner": "schema-dev",
        "tf-i-priority": "P0",
        **GOVERNANCE,
    }),
    ("003-AR", {
        "tf-i-id": "003-AR",
        "tf-i-clause": "计算字段与发布判定",
        "tf-i-dir": "specs/003-calculated-fields",
        "tf-i-scenes": 4,
        "tf-i-tasks": 10,
        "tf-i-status": "已完成",
        "tf-i-constitution": "完成（v6.0.0）",
        "tf-i-specify": "完成",
        "tf-i-plan": "完成",
        "tf-i-task": "完成",
        "tf-i-implement": "done",
        "tf-i-clarify": "todo",
        "tf-i-analyze": "todo",
        "tf-i-checklist": "done",
        "tf-i-owner": "schema-dev",
        "tf-i-priority": "P1",
        **GOVERNANCE,
    }),
    ("004-AR", {
        "tf-i-id": "004-AR",
        "tf-i-clause": "界面体验",
        "tf-i-dir": "specs/004-ui-polish",
        "tf-i-scenes": 3,
        "tf-i-tasks": 8,
        "tf-i-status": "已完成",
        "tf-i-constitution": "完成（v6.0.0）",
        "tf-i-specify": "完成",
        "tf-i-plan": "完成",
        "tf-i-task": "完成",
        "tf-i-implement": "done",
        "tf-i-clarify": "todo",
        "tf-i-analyze": "todo",
        "tf-i-checklist": "done",
        "tf-i-owner": "ui-dev",
        "tf-i-priority": "P1",
        **GOVERNANCE,
    }),
]

VERSION = ("v0.3.0", {
    "tf-v-ver": "v0.3.0",
    "tf-v-date": "2026-11-06T23:59:00+08:00",
    "tf-v-status": "released",
    "tf-v-indep": ["002-AR", "003-AR", "004-AR"],
    "tf-v-dep": ["DEP-01-BR"],
    "tf-v-bug-open": 0,
    "tf-v-doc": "done",
    "tf-v-test": "pytest 97 passed",
    "tf-v-note": "字段体系 + 计算字段 + 界面体验",
})

DEP = ("DEP-01-BR", {
    "tf-d-id": "DEP-01-BR",
    "tf-d-clause": "宪法 v6.0.0（计算字段、人经 Agent 写）与 v7.0.0（只读筛选）修订",
    "tf-d-spec": "constitution.md",
    "tf-d-indep": ["003-AR"],
    "tf-d-impact": "003 全部；004 的状态色依赖 002 的 tone 字段；筛选受 v7.0.0 约束",
    "tf-d-regress": "passed",
    "tf-d-status": "已完成",
})


def call(
    client: httpx.Client,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    strict: bool = False,
    quiet: bool = False,
) -> dict:
    response = client.request(method, path, json=body, headers=HEADERS)
    data = response.json()
    if data.get("result") != "success":
        message = f"{method} {path} → {response.status_code} {data}"
        if strict:
            raise RuntimeError(message)
        if not quiet:
            print(f"  ! {message}")
    return data


def run(client: httpx.Client, *, strict: bool = False) -> None:
    removed = 0
    for index in range(1, 22):
        row_id = f"TF-{index:02d}"
        exists = client.get(f"/api/tables/tf-indep/rows/{row_id}")
        if exists.status_code != 200:
            continue
        result = call(client, "DELETE", f"/api/agent/tables/tf-indep/rows/{row_id}", quiet=True)
        if result.get("result") == "success":
            removed += 1
    print(f"已删除历史 TF 条目 {removed} 条")

    for row_id, values in SPECS:
        call(client, "POST", f"/api/agent/tables/tf-indep/rows/{row_id}", {"values": values}, strict=strict)
    # 依赖需求先于版本写入：版本表的 v-dep 是唯一挂载点，relation_must_exist 要求目标行已存在。
    call(client, "POST", f"/api/agent/tables/tf-dep/rows/{DEP[0]}", {"values": DEP[1]}, strict=strict)
    call(client, "POST", f"/api/agent/tables/tf-ver/rows/{VERSION[0]}", {"values": VERSION[1]}, strict=strict)

    print("完成：3 个 spec + 1 个版本 + 1 条依赖需求")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=10) as client:
        run(client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
