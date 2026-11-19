#!/usr/bin/env python3
"""给 relation 字段补 display_field / status_field（006-relation-display 迁移）。

关联条目弹层原先按硬编码列名挑「标题」「状态」字段（违反宪法原则 III）。
本脚本把选择结果落到 relation 字段的 options 上，前端只读配置。

规则（按目标表结构，不按运行时猜）：
- display_field：目标表第 2 个 text 字段（第 1 个是编号）
- status_field：目标表的**完成判据字段**（按表角色认，见 COMPLETION_FIELD_BY_ROLE）
  indep→验收状态、dep→回归状态、bug→状态；认不出角色才回退到第 1 个 enum。
  历史口径是"第 1 个 enum"，在 board@3 下会选错：indep 表第 1 个 enum 是
  speckit-constitution状态，不是完成判据（BUG-03，2026-11-19 修正）。

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

# relation 弹层第三列要回答"这条关联条目做完了没有"，所以指向该表的完成判据字段
# （board@3 status_definitions 里各域唯一判定字段），而不是表里第一个 enum。
COMPLETION_FIELD_BY_ROLE = {
    "indep": "验收状态",  # spec.acceptance
    "dep": "回归状态",    # change.regress
    "bug": "状态",        # bug.status
}


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


def pick_status_field(target_table_id: str, target_fields: list[dict]) -> str | None:
    """状态列：优先取该表角色的完成判据字段，认不出角色才回退第 1 个 enum。"""
    role = target_table_id.rsplit("-", 1)[-1]
    want = COMPLETION_FIELD_BY_ROLE.get(role)
    if want:
        for field in target_fields:
            if field["name"] == want and field["type"] == "enum":
                return field["id"]
    enums = [f for f in target_fields if f["type"] == "enum"]
    return enums[0]["id"] if enums else None


def pick_columns(
    target_table_id: str, target_fields: list[dict]
) -> tuple[str | None, str | None]:
    texts = [f for f in target_fields if f["type"] == "text"]
    display = texts[1]["id"] if len(texts) >= 2 else (texts[0]["id"] if texts else None)
    return display, pick_status_field(target_table_id, target_fields)


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
                display, status = pick_columns(target, target_fields)
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
