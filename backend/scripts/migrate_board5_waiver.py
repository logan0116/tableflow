#!/usr/bin/env python3
"""board@5 迁移（036）：给每个项目的执行记录表补三个放行字段。

新增字段（契约 board@5 `tables.run.fields`）：

- `放行标记` enum：`none` / `waived`
- `放行批准人` text
- `放行理由` text

幂等：按字段名判断，已存在就跳过。默认 dry-run，加 `--apply` 才写。

用法：

    TF_BASE=http://localhost:8090 python3 backend/scripts/migrate_board5_waiver.py
    TF_BASE=http://localhost:8090 python3 backend/scripts/migrate_board5_waiver.py --apply
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

WAIVED_OPTIONS = [
    {"value": "none", "label": "未放行", "tone": "neutral"},
    {"value": "waived", "label": "已放行", "tone": "warning"},
]

FIELD_SPECS = [
    {
        "suffix": "waived",
        "name": "放行标记",
        "type": "enum",
        "options": WAIVED_OPTIONS,
        "note": "执行结果非 pass 时置 waived，表示本次不阻塞发布；须同时给出批准人与理由",
    },
    {
        "suffix": "by",
        "name": "放行批准人",
        "type": "text",
        "options": None,
        "note": "置 waived 时必填",
    },
    {
        "suffix": "reason",
        "name": "放行理由",
        "type": "text",
        "options": None,
        "note": "置 waived 时必填；为什么这次失败不阻塞发布",
    },
]


def _base() -> str:
    return (os.environ.get("TF_BASE") or "http://127.0.0.1:8090").rstrip("/")


def _agent() -> str:
    return os.environ.get("TF_AGENT") or "agent-tf-role"


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(_base() + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", _agent())
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


def find_run_table(table_payload: dict) -> bool:
    """run 表识别：同时存在 {todo,done} 与 {pass,fail,blocked,skip} 两个 enum。"""
    domains = {
        frozenset(values)
        for field in table_payload["fields"]
        if field.get("type") == "enum" and (values := enum_values(field))
    }
    return frozenset(RUN_STATE_VALUES) in domains and frozenset(RUN_RESULT_VALUES) in domains


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

    planned = 0
    for project_id in targets:
        tables = call("GET", f"/api/projects/{project_id}/tables")
        if tables.get("http") != 200:
            print(f"[{project_id}] 读表失败：{tables.get('error')}")
            continue
        for table in tables.get("tables", []):
            payload = call("GET", f"/api/tables/{table['id']}/table")
            if payload.get("http") != 200:
                continue
            if not find_run_table(payload):
                continue
            existing = {field["name"] for field in payload["fields"]}
            prefix = table["id"].split("-", 1)[0]
            for spec in FIELD_SPECS:
                if spec["name"] in existing:
                    print(f"[{project_id}] {table['id']} 已有「{spec['name']}」，跳过")
                    continue
                field_id = f"{prefix}-r-{spec['suffix']}"
                body = {
                    "id": field_id,
                    "name": spec["name"],
                    "type": spec["type"],
                    "options": spec["options"],
                    "note": spec["note"],
                    "visible": 1,
                }
                planned += 1
                if not args.apply:
                    print(f"[{project_id}] 将新建字段 {field_id}「{spec['name']}」")
                    continue
                result = call("POST", f"/api/agent/tables/{table['id']}/fields", body)
                state = "ok" if result.get("http") in (200, 201) else "FAILED"
                print(f"[{project_id}] {field_id}「{spec['name']}」{state} {result.get('error') or ''}")

    mode = "已写入" if args.apply else "待写入（dry-run）"
    print(f"\n合计 {planned} 个字段{mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
