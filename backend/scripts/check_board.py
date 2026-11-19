#!/usr/bin/env python3
"""契约一致性门禁：按 board@N 校验线上项目（以及模板脚本产物）的表结构。

018-AR 的 FR-004/FR-005/FR-007。原来这类漂移全靠人手写脚本抽查，
2026-11-19 一天内漏出的三起（relation 状态列指错、模板还是 board@2、
缺陷表来源枚举与契约不一致）都是这里能自动扫出来的。

用法：
    python3 backend/scripts/check_board.py                       # 校验线上全部项目
    python3 backend/scripts/check_board.py --base http://host:8090
    python3 backend/scripts/check_board.py --template            # 只校验模板脚本产物
    python3 backend/scripts/check_board.py --json                # 机器可读

退出码：0=无差异；1=有差异或执行失败。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "specs/017-bug-relation/board@3.yaml"
ROLES = ("ver", "indep", "dep", "bug")

# 关联弹层第三列指向的完成判据字段（board@3 conventions.relation_status_column）
STATUS_FIELD_BY_ROLE = {"indep": "验收状态", "dep": "回归状态", "bug": "状态"}
GATE_KINDS = {"and", "rollup"}


def api_get(base: str, path: str):
    with urllib.request.urlopen(base.rstrip("/") + path, timeout=15) as resp:
        return json.load(resp)


def load_contract(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tables = {}
    for role, table in (data.get("tables") or {}).items():
        if role not in ROLES:
            continue
        tables[role] = {
            "name": table["name"],
            "fields": [
                {
                    "key": f["key"],
                    "name": f["name"],
                    "type": f["type"],
                    "target": f.get("target"),
                    "values": f.get("values") or [],
                    "gate": bool(f.get("gate")),
                    "rule": f.get("rule") or "",
                }
                for f in table["fields"]
            ],
        }
    return tables


def enum_values(field: dict) -> list[str]:
    opts = field.get("options")
    items = opts.get("items") if isinstance(opts, dict) else opts
    return [i.get("value") for i in (items or []) if isinstance(i, dict)]


def check_tables(prefix: str, tables: list[dict], contract: dict) -> list[str]:
    """tables 是 [{id,name,fields:[{id,name,type,options}]}]（顺序即字段顺序）。"""
    issues: list[str] = []
    by_role: dict[str, dict] = {}
    for table in tables:
        role = table["id"].rsplit("-", 1)[-1]
        if role in ROLES:
            by_role[role] = table
    for role in ROLES:
        if role not in contract:
            continue
        if role not in by_role:
            issues.append(f"[{prefix}] 缺表 {role}（应为 {contract[role]['name']}）")
            continue
        want = [f["name"] for f in contract[role]["fields"]]
        got = [f["name"] for f in by_role[role]["fields"]]
        if want != got:
            missing = [n for n in want if n not in got]
            extra = [n for n in got if n not in want]
            if missing or extra:
                issues.append(f"[{prefix}/{role}] 字段名不符：缺 {missing} 多 {extra}")
            else:
                issues.append(f"[{prefix}/{role}] 字段顺序不符：契约 {want} 实际 {got}")

        actual = {f["name"]: f for f in by_role[role]["fields"]}
        for cf in contract[role]["fields"]:
            af = actual.get(cf["name"])
            if af is None:
                continue
            if af["type"] != cf["type"]:
                issues.append(f"[{prefix}/{role}.{cf['name']}] 类型 {af['type']} ≠ 契约 {cf['type']}")
            if cf["type"] == "enum":
                if set(enum_values(af)) != set(cf["values"]):
                    issues.append(
                        f"[{prefix}/{role}.{cf['name']}] 枚举取值不符："
                        f"实际 {sorted(enum_values(af))} 契约 {sorted(cf['values'])}"
                    )
            if cf["type"] == "relation":
                opts = af.get("options") or {}
                target_role = (opts.get("table_id") or "").rsplit("-", 1)[-1]
                if cf["target"] and target_role != cf["target"]:
                    issues.append(
                        f"[{prefix}/{role}.{cf['name']}] 关系指向 {target_role} ≠ 契约 {cf['target']}"
                    )
                display = opts.get("display_field")
                target_table = next((t for t in tables if t["id"] == opts.get("table_id")), None)
                if target_table:
                    texts = [f["id"] for f in target_table["fields"] if f["type"] == "text"]
                    if display not in texts:
                        issues.append(f"[{prefix}/{role}.{cf['name']}] display_field 不是目标表 text 字段")
                    status = opts.get("status_field")
                    want_status = STATUS_FIELD_BY_ROLE.get(cf["target"] or "")
                    if want_status:
                        fields_by_id = {f["id"]: f for f in target_table["fields"]}
                        if fields_by_id.get(status, {}).get("name") != want_status:
                            issues.append(
                                f"[{prefix}/{role}.{cf['name']}] status_field 应指向目标表「{want_status}」，"
                                f"实际 {status}"
                            )
            if cf["type"] == "computed":
                opts = af.get("options") or {}
                kind = opts.get("kind")
                if cf["gate"] and not opts.get("gate"):
                    issues.append(f"[{prefix}/{role}.{cf['name']}] 契约标了闸门，线上没打 gate:true")
                if not cf["gate"] and opts.get("gate"):
                    issues.append(f"[{prefix}/{role}.{cf['name']}] 线上打了 gate:true，契约未标闸门")
                if kind not in GATE_KINDS and opts.get("gate"):
                    issues.append(f"[{prefix}/{role}.{cf['name']}] kind={kind} 不允许打闸门标记")
    return issues


def check_live(base: str, contract: dict) -> list[str]:
    issues: list[str] = []
    for project in api_get(base, "/api/projects")["projects"]:
        pid = project["id"]
        tables = []
        for t in api_get(base, f"/api/projects/{pid}/tables")["tables"]:
            detail = api_get(base, f"/api/tables/{t['id']}/table")
            tables.append({"id": t["id"], "name": t["name"], "fields": detail["fields"]})
        if not any(t["id"].rsplit("-", 1)[-1] in ROLES for t in tables):
            continue
        issues.extend(check_tables(pid, tables, contract))
    return issues


def template_tables(table_prefix: str = "tf", field_prefix: str = "tf") -> list[dict]:
    """跑模板脚本拿到它要建的表，转成与线上同构的结构。"""
    path = ROOT / "data/template_fd_system.py"
    spec = importlib.util.spec_from_file_location("template_fd_system", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    out = []
    for table in module.build_tables(table_prefix, field_prefix):
        fields = []
        for fid, name, ftype, options in table["fields"]:
            fields.append({"id": fid, "name": name, "type": ftype, "options": options})
        out.append({"id": table["id"], "name": table["name"], "fields": fields})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="按 board@N 校验看板结构一致性")
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    ap.add_argument("--template", action="store_true", help="校验 data/template_fd_system.py 的产物")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    contract = load_contract(Path(args.contract))
    if not contract:
        print(f"契约里没有可校验的表：{args.contract}", file=sys.stderr)
        return 1

    if args.template:
        issues = check_tables("template", template_tables(), contract)
        scope = "template_fd_system.py"
    else:
        try:
            issues = check_live(args.base, contract)
        except (urllib.error.URLError, OSError) as exc:
            print(f"读取线上失败：{exc}", file=sys.stderr)
            return 1
        scope = args.base

    if args.json:
        print(json.dumps({"scope": scope, "issues": issues, "ok": not issues}, ensure_ascii=False, indent=1))
    else:
        print(f"契约：{args.contract}")
        print(f"范围：{scope}")
        if issues:
            print(f"差异 {len(issues)} 处：")
            for issue in issues:
                print("  -", issue)
        else:
            print("差异 0 处")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
