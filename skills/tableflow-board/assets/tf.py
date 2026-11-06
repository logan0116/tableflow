#!/usr/bin/env python3
"""tableflow 命令行小工具（只用标准库）。

用法：
    export TF_BASE=http://127.0.0.1:8000 TF_AGENT=agent-cli
    python tf.py projects
    python tf.py tables proj-x
    python tf.py table t-a
    python tf.py row t-a r-1
    python tf.py call POST /api/agent/tables/t-a/rows '{"id":"r-2","values":{}}'
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "http://127.0.0.1:8000").rstrip("/")
AGENT = os.environ.get("TF_AGENT", "agent-cli")


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", AGENT)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return {"result": "failed", "status": exc.code, "body": exc.read().decode()[:500]}


def print_table(payload: dict) -> None:
    fields = payload["fields"]
    rows = payload["rows"]
    print(" | ".join(f["name"] for f in fields))
    for row in rows:
        cells = []
        for field in fields:
            value = row["values"].get(field["id"])
            if isinstance(value, list):
                value = "、".join(str(item) for item in value)
            cells.append("" if value is None else str(value))
        print(" | ".join(cells))
    print(f"-- {len(rows)} 行")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    command, args = argv[0], argv[1:]
    if command == "projects":
        print(json.dumps(request("GET", "/api/projects"), ensure_ascii=False, indent=2))
    elif command == "tables":
        print(json.dumps(request("GET", f"/api/projects/{args[0]}/tables"), ensure_ascii=False, indent=2))
    elif command == "table":
        print_table(request("GET", f"/api/tables/{args[0]}/table"))
    elif command == "row":
        print(json.dumps(request("GET", f"/api/tables/{args[0]}/rows/{args[1]}"), ensure_ascii=False, indent=2))
    elif command == "call":
        method, path = args[0], args[1]
        body = json.loads(args[2]) if len(args) > 2 else None
        print(json.dumps(request(method, path, body), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
