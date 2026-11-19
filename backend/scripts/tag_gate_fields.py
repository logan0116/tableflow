#!/usr/bin/env python3
"""给「发布条件」计算字段补闸门标记（契约 migrations.gate-tag-existing）。

背景：010 用 `fields.options.gate=true` 识别闸门字段并拒绝人工覆盖，但线上7个项目的
「发布条件」字段仍是旧配置。本脚本按契约迁移动作逐项目补 `gate:true` 并回读确认。

用法（在 backend 目录执行）：
    .venv/bin/python scripts/tag_gate_fields.py --dry-run     # 只打印将要提交的 options
    .venv/bin/python scripts/tag_gate_fields.py               # 执行迁移（可重入）
    .venv/bin/python scripts/tag_gate_fields.py --probe-override
        # 仅在已部署v0.6.0+（含010的gate拦截）后使用：对某行写该字段的 overrides，
        # 期望400；若意外成功则立刻清除覆盖并判失败，避免把覆盖留在线上。

行为与边界：
- 只找「发布条件」字段（名称优先，其次字段 id 以 `-v-cond` 结尾），只改它的 options；
  不改其它字段、不改行数据。
- 已有 `gate:true` → 跳过（可重入）；`gate` 存在但不是布尔 → 记为异常并仍改成 true。
- 找不到版本表/「发布条件」字段、同表多个候选、字段已有历史覆盖 → 列为异常项，不静默跳过。
- 退出码：0=全部成功；1=有失败/缺字段；2=参数错误。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "http://192.168.1.155:8090"
DEFAULT_AGENT = "agent-tf-backend"


class Api:
    def __init__(self, base: str, agent: str) -> None:
        self.base = base.rstrip("/")
        self.agent = agent

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("X-Agent-Id", self.agent)
        req.add_header("X-Origin", "human-request")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                return exc.code, json.loads(raw)
            except Exception:  # noqa: BLE001 - 非 JSON 错误体原样带回
                return exc.code, {"raw": raw[:300]}


def find_version_table(api: Api, project_id: str) -> tuple[str | None, str]:
    code, payload = api.call("GET", f"/api/projects/{project_id}/tables")
    if code != 200:
        return None, f"读取项目表格失败：{code}"
    tables = payload.get("tables") or []
    by_suffix = [t for t in tables if str(t.get("id", "")).endswith("-ver")]
    by_name = [t for t in tables if t.get("name") == "版本管理"]
    candidates = by_suffix or by_name
    if not candidates:
        return None, "项目里没有版本表（id以-ver结尾或名称“版本管理”）"
    if len(candidates) > 1:
        return None, "版本表候选不唯一：" + "、".join(t["id"] for t in candidates)
    return candidates[0]["id"], ""


def find_cond_field(api: Api, table_id: str) -> tuple[dict | None, str, dict]:
    code, payload = api.call("GET", f"/api/tables/{table_id}/table")
    if code != 200:
        return None, f"读取版本表失败：{code}", {}
    fields = payload.get("fields") or []
    by_name = [f for f in fields if f.get("name") == "发布条件"]
    by_id = [f for f in fields if str(f.get("id", "")).endswith("-v-cond")]
    candidates = by_name or by_id
    if not candidates:
        return None, "版本表里没有「发布条件」字段", payload
    if len(candidates) > 1:
        return None, "「发布条件」候选不唯一：" + "、".join(f["id"] for f in candidates), payload
    return candidates[0], "", payload


def existing_overrides(payload: dict, field_id: str) -> list[str]:
    hits = []
    for row in payload.get("rows") or []:
        meta = (row.get("computed_meta") or {}).get(field_id) or {}
        if meta.get("overridden"):
            hits.append(row["id"])
    return hits


def tag_project(api: Api, project_id: str, *, dry_run: bool) -> dict:
    result = {
        "project": project_id,
        "status": "failed",
        "table": None,
        "field": None,
        "before": None,
        "after": None,
        "anomalies": [],
    }
    table_id, err = find_version_table(api, project_id)
    if table_id is None:
        result["anomalies"].append(err)
        return result
    result["table"] = table_id
    field, err, payload = find_cond_field(api, table_id)
    if field is None:
        result["anomalies"].append(err)
        return result
    result["field"] = field["id"]
    result["before"] = field.get("options")
    overrides = existing_overrides(payload, field["id"])
    if overrides:
        result["anomalies"].append(f"字段已有历史覆盖的行：{overrides}")

    options = field.get("options")
    if not isinstance(options, dict):
        result["anomalies"].append(f"options 不是对象：{options!r}")
        return result
    if options.get("gate") is True:
        result["status"] = "already"
        result["after"] = options
        return result
    if "gate" in options:
        result["anomalies"].append(f"gate 已存在但不是布尔：{options['gate']!r}，本次改为 true")

    new_options = {**options, "gate": True}
    result["after"] = new_options
    if dry_run:
        result["status"] = "dry-run"
        return result

    code, response = api.call(
        "PATCH", f"/api/agent/fields/{field['id']}", {"options": new_options}
    )
    if code != 200 or response.get("result") != "success":
        result["anomalies"].append(f"PATCH失败：{code} {response}")
        return result

    # 回读确认：gate=true，其余 options 未变
    field2, err2, _ = find_cond_field(api, table_id)
    if field2 is None:
        result["anomalies"].append("回读失败：" + err2)
        return result
    got = field2.get("options") or {}
    if got.get("gate") is not True:
        result["anomalies"].append(f"回读 gate 不为 true：{got.get('gate')!r}")
        return result
    if {k: v for k, v in got.items() if k != "gate"} != options:
        result["anomalies"].append("回读发现其它 options 发生变化")
        return result
    result["status"] = "tagged"
    return result


def probe_override(api: Api, project_id: str) -> dict:
    """验证闸门禁覆盖：写 overrides 应400；意外成功则立刻清除覆盖。"""
    table_id, err = find_version_table(api, project_id)
    if table_id is None:
        return {"project": project_id, "status": "failed", "detail": err}
    field, err, payload = find_cond_field(api, table_id)
    if field is None:
        return {"project": project_id, "status": "failed", "detail": err}
    if (field.get("options") or {}).get("gate") is not True:
        return {"project": project_id, "status": "failed", "detail": "字段未打gate标记"}
    rows = payload.get("rows") or []
    if not rows:
        return {"project": project_id, "status": "failed", "detail": "版本表没有行可探测"}
    row = rows[0]
    current = (row.get("values") or {}).get(field["id"])
    probe_value = False if current is True else True
    code, response = api.call(
        "PATCH",
        f"/api/agent/tables/{table_id}/rows/{row['id']}",
        {"overrides": {field["id"]: {"value": probe_value, "reason": "t19闸门禁覆盖探测"}}},
    )
    if code == 400:
        return {
            "project": project_id,
            "status": "rejected",
            "detail": f"row={row['id']} value={probe_value} → 400 {response.get('error', '')}",
        }
    # 意外通过：立刻清除覆盖，避免污染线上
    clear_code, clear_response = api.call(
        "PATCH",
        f"/api/agent/tables/{table_id}/rows/{row['id']}",
        {"overrides": {field["id"]: {"value": None}}},
    )
    return {
        "project": project_id,
        "status": "not-enforced",
        "detail": (
            f"row={row['id']} value={probe_value} → {code} {response}；"
            f"已尝试清除覆盖：{clear_code} {clear_response}"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="给「发布条件」字段补gate标记（gate-tag-existing）")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"实例地址，默认{DEFAULT_BASE}")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="写接口X-Agent-Id")
    parser.add_argument("--project", action="append", default=None,
                        help="只处理指定项目（可多次）；默认全部项目")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要提交的options，不写")
    parser.add_argument("--probe-override", action="store_true",
                        help="迁移后验证禁覆盖：写overrides应400；意外成功会自动清除覆盖")
    args = parser.parse_args(argv)

    api = Api(args.base, args.agent)
    code, payload = api.call("GET", "/api/projects")
    if code != 200:
        print(f"读取项目清单失败：{code} {payload}", file=sys.stderr)
        return 1
    project_ids = args.project or [p["id"] for p in payload["projects"]]

    failures = 0
    results = []
    print(f"== gate-tag-existing：{len(project_ids)}个项目 {'（dry-run）' if args.dry_run else ''}")
    for project_id in project_ids:
        result = tag_project(api, project_id, dry_run=args.dry_run)
        results.append(result)
        print(f"\n[{project_id}] {result['status']} table={result['table']} field={result['field']}")
        print("  before:", json.dumps(result["before"], ensure_ascii=False))
        print("  after :", json.dumps(result["after"], ensure_ascii=False))
        for anomaly in result["anomalies"]:
            print("  [异常]", anomaly)
        if result["status"] == "failed":
            failures += 1

    if args.probe_override and not args.dry_run:
        print("\n== 禁覆盖探测（需已部署v0.6.0+）")
        for project_id in project_ids:
            probe = probe_override(api, project_id)
            print(f"[{project_id}] {probe['status']} {probe['detail']}")
            if probe["status"] != "rejected":
                failures += 1

    summary = {
        "project_count": len(project_ids),
        "dry_run": args.dry_run,
        "tagged": [r["project"] for r in results if r["status"] == "tagged"],
        "already": [r["project"] for r in results if r["status"] == "already"],
        "dry_run_projects": [r["project"] for r in results if r["status"] == "dry-run"],
        "failed": [r["project"] for r in results if r["status"] == "failed"],
        "anomalies": {r["project"]: r["anomalies"] for r in results if r["anomalies"]},
    }
    print("\n== 汇总:", json.dumps(summary, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
