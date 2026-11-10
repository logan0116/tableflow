#!/usr/bin/env python3
"""给 relation 字段补 display_field / status_field（006-relation-display 迁移）。

关联条目弹层原先按硬编码列名挑「标题」「状态」字段（违反宪法原则 III）。
本脚本把选择结果落到 relation 字段的 options 上，前端只读配置。

规则（按目标表结构，不按运行时猜）：
- display_field：目标表第 2 个 text 字段（第 1 个是编号）
- status_field：目标表第 1 个 enum 字段

用法：
    python3 data/migrate_relation_display.py --dry-run     # 只打印映射
    python3 data/migrate_relation_display.py               # 写入（幂等）
    python3 data/migrate_relation_display.py --base http://<host>:8090
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8000"
AGENT_ID = "agent-006-migrate"


def get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return json.load(resp)


def patch_field(base: str, field_id: str, options: dict) -> dict:
    body = json.dumps({"options": options}).encode()
    request = urllib.request.Request(
        f"{base}/api/agent/fields/{field_id}",
        data=body,
        method="PATCH",
        headers={
            "Content-Type": "application/json",
            "X-Agent-Id": AGENT_ID,
            "X-Origin": "human-request",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as resp:
        return json.load(resp)


def pick_columns(target_fields: list[dict]) -> tuple[str | None, str | None]:
    texts = [f for f in target_fields if f["type"] == "text"]
    enums = [f for f in target_fields if f["type"] == "enum"]
    display = texts[1]["id"] if len(texts) >= 2 else (texts[0]["id"] if texts else None)
    status = enums[0]["id"] if enums else None
    return display, status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    plans: list[dict] = []
    for project in get(base, "/api/projects")["projects"]:
        pid = project["id"]
        for table in get(base, f"/api/projects/{pid}/tables")["tables"]:
            tid = table["id"]
            detail = get(base, f"/api/tables/{tid}/table")
            for field in detail["fields"]:
                if field["type"] != "relation":
                    continue
                options = field.get("options") or {}
                target = options.get("table_id")
                if not target:
                    continue
                target_fields = get(base, f"/api/tables/{target}/table")["fields"]
                display, status = pick_columns(target_fields)
                if not display and not status:
                    continue
                merged = dict(options)
                if display:
                    merged["display_field"] = display
                if status:
                    merged["status_field"] = status
                changed = merged != options
                plans.append(
                    {
                        "project": pid,
                        "table": tid,
                        "field": field["id"],
                        "field_name": field["name"],
                        "target": target,
                        "options": merged,
                        "changed": changed,
                    }
                )

    names = {}
    for item in plans:
        target_fields = get(base, f"/api/tables/{item['target']}/table")["fields"]
        for f in target_fields:
            names[f["id"]] = f["name"]

    print(f"共 {len(plans)} 个 relation 字段，待变更 {sum(1 for p in plans if p['changed'])} 个")
    for item in plans:
        display = item["options"].get("display_field")
        status = item["options"].get("status_field")
        mark = "写入" if item["changed"] else "跳过（已一致）"
        print(
            f"  [{mark}] {item['project']}/{item['table']}.{item['field']} ({item['field_name']})"
            f" -> {item['target']}"
            f" | display={display}({names.get(display, '?')})"
            f" | status={status}({names.get(status, '?')})"
        )

    if args.dry_run:
        print("dry-run：未写入")
        return 0

    failed = 0
    for item in plans:
        if not item["changed"]:
            continue
        result = patch_field(base, item["field"], item["options"])
        if result.get("result") != "success":
            print(f"  写入失败：{item['field']} -> {result}", file=sys.stderr)
            failed += 1
    print("迁移完成" if failed == 0 else f"迁移结束，{failed} 个失败")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
