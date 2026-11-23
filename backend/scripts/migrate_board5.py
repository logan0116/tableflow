#!/usr/bin/env python3
"""board@5 迁移：执行记录放行字段（036）+ 独立需求生命周期字段（034）。

对每个项目按表的实际形态识别目标，不依赖表 id：

- **执行记录表**（同时有 `{todo,done}` 与 `{pass,fail,blocked,skip}` 两个 enum）
  补三个字段：`放行标记`（enum none/waived）、`放行批准人`（text）、`放行理由`（text）。
- **独立需求表**（有验收状态 enum，值域为 pending/accepted/rejected[/dropped]）
  补三个字段：`放弃理由`（text）、`放弃时间`（datetime）、`拆分记录`（text）；
  并把验收状态的枚举补上 `dropped`（终态）。

幂等：字段按名称判断、枚举按取值判断，已齐备就跳过。默认 dry-run，`--apply` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/migrate_board5.py
    TF_BASE=http://localhost:8090 python3 backend/scripts/migrate_board5.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

RUN_STATE_VALUES = {"todo", "done"}
RUN_RESULT_VALUES = {"pass", "fail", "blocked", "skip"}
REGRESS_VALUES = {"todo", "doing", "passed", "failed"}
ACCEPTANCE_DOMAINS = (
    {"pending", "accepted", "rejected", "dropped"},
    {"pending", "accepted", "rejected"},
)

DROPPED_OPTION = {"value": "dropped", "label": "已放弃", "tone": "neutral"}

RUN_FIELDS = [
    {"suffix": "waived", "name": "放行标记", "type": "enum",
     "options": [{"value": "none", "label": "未放行", "tone": "neutral"},
                 {"value": "waived", "label": "已放行", "tone": "warning"}],
     "note": "执行结果非 pass 时置 waived，表示本次不阻塞发布；须同时给出批准人与理由"},
    {"suffix": "by", "name": "放行批准人", "type": "text", "options": None,
     "note": "置 waived 时必填"},
    {"suffix": "reason", "name": "放行理由", "type": "text", "options": None,
     "note": "置 waived 时必填；为什么这次失败不阻塞发布"},
]

CHANGE_FIELDS = [
    {"suffix": "increment", "name": "增量说明", "type": "text", "options": None,
     "note": "本次改什么、为什么改"},
    {"suffix": "baselines", "name": "基线修订", "type": "text", "options": None,
     "note": "一行一份：<规格编号>@<基线版本或修订标识>"},
    {"suffix": "affected", "name": "受影响条款", "type": "text", "options": None,
     "note": "一行一份：<规格编号> <条款号或场景号>；置 passed 前必须非空"},
    {"suffix": "plan", "name": "设计与任务", "type": "text", "options": None,
     "note": "统一设计只写一次，差异按规格分列；复用需写来源版本"},
    {"suffix": "consistency", "name": "一致性检查", "type": "text", "options": None,
     "note": "逐份规格的一致性结论；冲突与遗漏必须列明"},
    {"suffix": "integration", "name": "集成验收", "type": "text", "options": None,
     "note": "跨规格集成验收的结论与证据"},
]

INDEP_FIELDS = [
    {"suffix": "abandon-reason", "name": "放弃理由", "type": "text", "options": None,
     "note": "置 dropped 时必填；为什么不做"},
    {"suffix": "abandoned-at", "name": "放弃时间", "type": "datetime", "options": None,
     "note": "置 dropped 时必填；放弃的时点"},
    {"suffix": "split-log", "name": "拆分记录", "type": "text", "options": None,
     "note": "一行一条：<时间> 移交 <条款或场景号清单> -> <承接方编号>；仅在需求未 accepted 时允许"},
    {"suffix": "stage-evidence", "name": "阶段证据", "type": "text", "options": None,
     "note": "每行一条 <阶段>=<证据>；阶段置 done 时必须有对应行（038）"},
]


def base() -> str:
    return (os.environ.get("TF_BASE") or "http://127.0.0.1:8090").rstrip("/")


def agent() -> str:
    return os.environ.get("TF_AGENT") or "agent-tf-role"


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(base() + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", agent())
    req.add_header("X-Origin", "human-request")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"http": resp.status, **json.loads(resp.read().decode() or "{}")}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"error": raw[:300]}
        return {"http": exc.code, **payload}
    except Exception as exc:  # noqa: BLE001
        return {"http": 0, "error": f"{type(exc).__name__}: {exc}"}


def enum_values(field: dict) -> set[str] | None:
    options = field.get("options")
    items = options.get("items") if isinstance(options, dict) else options
    if not isinstance(items, list):
        return None
    return {
        item.get("value")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("value"), str)
    }


def acceptance_field(fields: list[dict]) -> dict | None:
    hits = [
        field for field in fields
        if field.get("type") == "enum" and enum_values(field) in ACCEPTANCE_DOMAINS
    ]
    return hits[0] if len(hits) == 1 else None


def is_change_table(fields: list[dict]) -> bool:
    """依赖需求表识别：恰好一个 {todo,doing,passed,failed} 的 enum。"""
    hits = [f for f in fields if f.get("type") == "enum" and enum_values(f) == set(REGRESS_VALUES)]
    return len(hits) == 1


def is_run_table(fields: list[dict]) -> bool:
    domains = {frozenset(v) for f in fields if f.get("type") == "enum" and (v := enum_values(f))}
    return frozenset(RUN_STATE_VALUES) in domains and frozenset(RUN_RESULT_VALUES) in domains


def add_fields(table: dict, specs: list[dict], letter: str, apply: bool, planned: list[str]) -> None:
    existing = {field["name"] for field in table["fields"]}
    prefix = table["id"].split("-", 1)[0]
    for spec in specs:
        if spec["name"] in existing:
            continue
        field_id = f"{prefix}-{letter}-{spec['suffix']}"
        planned.append(f"{table['id']} 新建字段 {field_id}「{spec['name']}」")
        if not apply:
            continue
        result = call("POST", f"/api/agent/tables/{table['id']}/fields", {
            "id": field_id, "name": spec["name"], "type": spec["type"],
            "options": spec["options"], "note": spec["note"], "visible": 1,
        })
        state = "ok" if result.get("http") in (200, 201) else f"FAILED {result.get('error') or ''}"
        planned[-1] += f" -> {state}"


def extend_acceptance(field: dict, apply: bool, planned: list[str]) -> None:
    values = enum_values(field) or set()
    if "dropped" in values:
        return
    options = field.get("options")
    raw = options.get("items") if isinstance(options, dict) else options
    items = list(raw or [])
    items = items + [DROPPED_OPTION]
    planned.append(f"字段 {field['id']}「{field['name']}」补枚举值 dropped")
    if not apply:
        return
    result = call("PATCH", f"/api/agent/fields/{field['id']}", {"options": items})
    state = "ok" if result.get("http") in (200, 201) else f"FAILED {result.get('error') or ''}"
    planned[-1] += f" -> {state}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正写入；默认只预览")
    parser.add_argument("--project", action="append", default=[], help="只处理这些项目")
    args = parser.parse_args()

    projects = call("GET", "/api/projects")
    if projects.get("http") != 200:
        print(f"[migrate] 读取项目列表失败：{projects}", file=sys.stderr)
        return 1
    targets = [p["id"] for p in projects.get("projects", [])]
    if args.project:
        targets = [p for p in targets if p in set(args.project)]

    planned: list[str] = []
    for project_id in targets:
        tables = call("GET", f"/api/projects/{project_id}/tables")
        if tables.get("http") != 200:
            print(f"[{project_id}] 读表失败：{tables.get('error')}")
            continue
        for summary in tables.get("tables", []):
            payload = call("GET", f"/api/tables/{summary['id']}/table")
            if payload.get("http") != 200:
                continue
            table = {"id": summary["id"], "fields": payload["fields"]}
            before = len(planned)
            if is_run_table(table["fields"]):
                add_fields(table, RUN_FIELDS, "r", args.apply, planned)
            if is_change_table(table["fields"]):
                add_fields(table, CHANGE_FIELDS, "d", args.apply, planned)
            accept = acceptance_field(table["fields"])
            if accept is not None:
                extend_acceptance(accept, args.apply, planned)
                add_fields(table, INDEP_FIELDS, "i", args.apply, planned)
            for line in planned[before:]:
                print(f"[{project_id}] {line}")

    mode = "已写入" if args.apply else "待写入（dry-run）"
    print(f"\n合计 {len(planned)} 项{mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
