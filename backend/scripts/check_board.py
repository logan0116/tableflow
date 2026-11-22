#!/usr/bin/env python3
"""契约一致性门禁：按 board@N 校验线上项目（以及模板脚本产物）的表结构。

018-AR 的 FR-004/FR-005/FR-007；019（board@4）扩到六表。原来这类漂移全靠人手写脚本抽查，
2026-11-19 一天内漏出的三起（relation 状态列指错、模板还是 board@2、
缺陷表来源枚举与契约不一致）都是这里能自动扫出来的。

board@4（019）新增比对项：
- 六表齐备：ver / indep / dep / case / run / bug；仍四表的项目会明确报缺 case、run；
- 表名与表级 `kind`（run=detail，其余 board）；
- 新表字段名/类型/顺序，case/run 的 relation 显示列与状态列（case 不给状态列）；
- 闸门标记：只有 and 或 rollup(all/any/none) 允许打 gate；board@4 起只有
  「六节点是否全部完成」「发布条件」两个闸门，三个展示布尔必须摘掉 gate；
- 计算规则语义：按契约 `rule` 校验 kind、source、conditions/where/field/aggregate/equals，
  防止「字段名对、公式还是 board@3」这种假通过。

用法：
    python3 backend/scripts/check_board.py                       # 校验线上全部项目（默认 board@4）
    python3 backend/scripts/check_board.py --base http://host:8090
    python3 backend/scripts/check_board.py --template            # 只校验模板脚本产物
    python3 backend/scripts/check_board.py --json                # 机器可读
    python3 backend/scripts/check_board.py --contract specs/017-bug-relation/board@3.yaml

退出码：0=无差异；1=有差异或执行失败。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "specs/019-test-contract/board@4.yaml"

# 关联弹层第三列：指向目标表的完成判据字段（board@4 conventions.relation_status_column）。
# case 是指向「用例」的关系不给状态列——用例是资产，没有完成判据。
STATUS_FIELD_BY_ROLE = {
    "indep": "验收状态",
    "dep": "回归状态",
    "bug": "状态",
    "run": "执行状态",
}
NO_STATUS_BY_ROLE = {"case"}
GATE_KINDS = {"and", "rollup"}
GATE_ROLLUP_AGGREGATES = {"all", "any", "none"}
RULE_RE = re.compile(r"^([A-Za-z_]+)\((.*)\)$", re.S)
ROLE_ALIASES = {
    "ver": "ver",
    "spec": "indep",
    "indep": "indep",
    "change": "dep",
    "dep": "dep",
    "bug": "bug",
    "case": "case",
    "run": "run",
}


def api_get(base: str, path: str):
    with urllib.request.urlopen(base.rstrip("/") + path, timeout=15) as resp:
        return json.load(resp)


def load_contract(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tables = {}
    for role, table in (data.get("tables") or {}).items():
        tables[role] = {
            "name": table["name"],
            "kind": table.get("kind") or "board",
            "fields": [
                {
                    "key": f.get("key") or "",
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


def _options(field: dict) -> dict:
    opts = field.get("options")
    return opts if isinstance(opts, dict) else {}


def _table_by_role(tables: list[dict], role: str) -> dict | None:
    for table in tables:
        if table["id"].rsplit("-", 1)[-1] == role:
            return table
    return None


def _field_by_name(table: dict | None, name: str) -> dict | None:
    if table is None:
        return None
    for field in table.get("fields") or []:
        if field["name"] == name:
            return field
    return None


def _expected_display(table: dict) -> str | None:
    """关联弹层第二列：目标表第 2 个 text 字段（第 1 个是行 id）；不足两列时取第 1 个。"""
    texts = [f["id"] for f in table.get("fields") or [] if f["type"] == "text"]
    if len(texts) >= 2:
        return texts[1]
    return texts[0] if texts else None


def _split_args(raw: str) -> list[str]:
    """拆分规则参数；支持括号嵌套（当前契约没有，但门禁不该脆弱）。"""
    args: list[str] = []
    depth = 0
    current: list[str] = []
    for char in raw:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


def _parse_rule(rule: str) -> tuple[str, list[str]] | None:
    match = RULE_RE.match(rule.strip())
    if match is None:
        return None
    return match.group(1), _split_args(match.group(2))


def _literal(raw: str) -> Any:
    text = raw.strip()
    if text == "true":
        return True
    if text == "false":
        return False
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def _parse_comparison(raw: str) -> tuple[str, Any]:
    if "==" in raw:
        left, right = raw.split("==", 1)
        return left.strip(), _literal(right)
    return raw.strip(), True


def _resolve_rule_field(
    key: str,
    current_role: str,
    contract: dict,
    tables: list[dict],
    key_to_actual: dict[str, dict],
) -> dict | None:
    """把契约规则里的语义键（ver.stage.plan / run.state）解析成实际字段。"""
    namespace, _, _ = key.partition(".")
    role = ROLE_ALIASES.get(namespace)
    if role is None:
        return None
    if role == current_role:
        return key_to_actual.get(key)
    target_table = _table_by_role(tables, role)
    if target_table is None:
        return None
    for contract_field in contract.get(role, {}).get("fields", []):
        if contract_field["key"] == key:
            return _field_by_name(target_table, contract_field["name"])
    return None


def _same_conditions(actual: Any, expected: list[tuple[str, Any]]) -> bool:
    if not isinstance(actual, list):
        return False
    normalized = []
    for item in actual:
        if not isinstance(item, dict):
            return False
        normalized.append((item.get("field_id"), item.get("equals")))
    return sorted(normalized, key=repr) == sorted(expected, key=repr)


def _check_rule(
    prefix: str,
    role: str,
    contract_field: dict,
    actual_field: dict,
    contract: dict,
    tables: list[dict],
    key_to_actual: dict[str, dict],
) -> list[str]:
    """按契约 rule 校验计算字段配置；不认识的规则形态也报出来，不静默跳过。"""
    issues: list[str] = []
    label = f"[{prefix}/{role}.{contract_field['name']}]"
    rule = contract_field["rule"]
    if not rule:
        return issues
    parsed = _parse_rule(rule)
    if parsed is None:
        return [f"{label} 契约规则无法解析：{rule!r}"]
    kind, args = parsed
    opts = _options(actual_field)
    if opts.get("kind") != kind:
        issues.append(
            f"{label} 计算类型 {opts.get('kind')!r} ≠ 契约规则 {kind!r}（rule={rule}）"
        )

    if kind == "and":
        expected_conditions: list[tuple[str, Any]] = []
        for arg in args:
            field_key, equals = _parse_comparison(arg)
            field = _resolve_rule_field(field_key, role, contract, tables, key_to_actual)
            if field is None:
                issues.append(f"{label} 规则引用的字段未落地：{field_key}")
                continue
            expected_conditions.append((field["id"], equals))
        if expected_conditions and not _same_conditions(opts.get("conditions"), expected_conditions):
            issues.append(
                f"{label} and 条件与契约规则不一致："
                f"实际 {opts.get('conditions')!r}，契约 {expected_conditions!r}"
            )
        return issues

    if kind in {"count", "ratio"}:
        if not args:
            issues.append(f"{label} 契约规则缺少 source：{rule}")
            return issues
        source = _resolve_rule_field(args[0], role, contract, tables, key_to_actual)
        if source is None:
            issues.append(f"{label} 规则 source 未落地：{args[0]}")
        elif opts.get("source") != source["id"]:
            issues.append(
                f"{label} source={opts.get('source')!r} ≠ 契约 {source['id']!r}（{args[0]}）"
            )
        where_expected = None
        if len(args) > 1:
            where_key, where_value = _parse_comparison(args[1])
            where_field = _resolve_rule_field(where_key, role, contract, tables, key_to_actual)
            if where_field is None:
                issues.append(f"{label} 规则 where 字段未落地：{where_key}")
            else:
                where_expected = {"field_id": where_field["id"], "equals": where_value}
        where_actual = opts.get("where")
        normalized_actual = None
        if isinstance(where_actual, dict):
            normalized_actual = {
                "field_id": where_actual.get("field_id"),
                "equals": where_actual.get("equals"),
            }
        if normalized_actual != where_expected:
            issues.append(
                f"{label} where={normalized_actual!r} ≠ 契约 {where_expected!r}"
            )
        return issues

    if kind == "rollup":
        if len(args) < 3:
            issues.append(f"{label} 契约规则参数不足：{rule}")
            return issues
        source = _resolve_rule_field(args[0], role, contract, tables, key_to_actual)
        if source is None:
            issues.append(f"{label} 规则 source 未落地：{args[0]}")
        elif opts.get("source") != source["id"]:
            issues.append(
                f"{label} source={opts.get('source')!r} ≠ 契约 {source['id']!r}（{args[0]}）"
            )
        target_field = _resolve_rule_field(args[1], role, contract, tables, key_to_actual)
        if target_field is None:
            issues.append(f"{label} 规则目标字段未落地：{args[1]}")
        elif opts.get("field_id") != target_field["id"]:
            issues.append(
                f"{label} field_id={opts.get('field_id')!r} ≠ 契约 {target_field['id']!r}（{args[1]}）"
            )
        aggregate_expr = args[2]
        if "==" in aggregate_expr:
            aggregate, equals = aggregate_expr.split("==", 1)
            expected_equals: Any = _literal(equals)
        else:
            aggregate, expected_equals = aggregate_expr, None
        aggregate = aggregate.strip()
        if opts.get("aggregate") != aggregate:
            issues.append(
                f"{label} aggregate={opts.get('aggregate')!r} ≠ 契约 {aggregate!r}"
            )
        if expected_equals is not None and opts.get("equals") != expected_equals:
            issues.append(
                f"{label} equals={opts.get('equals')!r} ≠ 契约 {expected_equals!r}"
            )
        return issues

    issues.append(f"{label} 门禁尚未支持的计算规则：{rule}")
    return issues


def check_tables(prefix: str, tables: list[dict], contract: dict) -> list[str]:
    """tables 是 [{id,name,kind,fields:[{id,name,type,options}]}]（顺序即字段顺序）。"""
    issues: list[str] = []
    by_role: dict[str, dict] = {}
    for table in tables:
        role = table["id"].rsplit("-", 1)[-1]
        if role in contract:
            by_role[role] = table

    # 只按契约声明的表校验；契约里的每一张表都必须存在，缺表一律报出（不静默跳过）。
    for role, contract_table in contract.items():
        expected_name = contract_table["name"]
        if role not in by_role:
            issues.append(f"[{prefix}] 缺表 {role}（应为 {expected_name}）")
            continue

        table = by_role[role]
        if table.get("name") != expected_name:
            issues.append(
                f"[{prefix}/{role}] 表名 {table.get('name')!r} ≠ 契约 {expected_name!r}"
            )
        actual_kind = table.get("kind")
        if actual_kind != contract_table["kind"]:
            shown = "缺失" if actual_kind in (None, "") else actual_kind
            issues.append(
                f"[{prefix}/{role}] 表级 kind={shown!r} ≠ 契约 {contract_table['kind']!r}"
            )

        want = [f["name"] for f in contract_table["fields"]]
        got = [f["name"] for f in table["fields"]]
        if want != got:
            missing = [n for n in want if n not in got]
            extra = [n for n in got if n not in want]
            if missing or extra:
                issues.append(f"[{prefix}/{role}] 字段名不符：缺 {missing} 多 {extra}")
            else:
                issues.append(f"[{prefix}/{role}] 字段顺序不符：契约 {want} 实际 {got}")

        actual = {f["name"]: f for f in table["fields"]}
        key_to_actual = {
            cf["key"]: actual.get(cf["name"])
            for cf in contract_table["fields"]
            if cf["key"] and actual.get(cf["name"]) is not None
        }
        for cf in contract_table["fields"]:
            af = actual.get(cf["name"])
            if af is None:
                continue
            label = f"[{prefix}/{role}.{cf['name']}]"
            if af["type"] != cf["type"]:
                issues.append(f"{label} 类型 {af['type']} ≠ 契约 {cf['type']}")
            if cf["type"] == "enum":
                if set(enum_values(af)) != set(cf["values"]):
                    issues.append(
                        f"{label} 枚举取值不符："
                        f"实际 {sorted(enum_values(af))} 契约 {sorted(cf['values'])}"
                    )
            if cf["type"] == "relation":
                opts = _options(af)
                target_role = (opts.get("table_id") or "").rsplit("-", 1)[-1]
                if cf["target"] and target_role != cf["target"]:
                    issues.append(
                        f"{label} 关系指向 {target_role} ≠ 契约 {cf['target']}"
                    )
                    continue
                target_table = _table_by_role(tables, target_role)
                if target_table is None:
                    issues.append(f"{label} 关系目标表 {target_role} 不存在")
                    continue
                display = opts.get("display_field")
                expected_display = _expected_display(target_table)
                if expected_display and display != expected_display:
                    issues.append(
                        f"{label} display_field={display!r} ≠ 目标表可读文本列 "
                        f"{expected_display!r}"
                    )
                want_status_name = STATUS_FIELD_BY_ROLE.get(target_role)
                status = opts.get("status_field")
                if target_role in NO_STATUS_BY_ROLE:
                    if status:
                        issues.append(
                            f"{label} 指向 {target_role} 的关系不应配置 status_field（用例无完成判据），"
                            f"实际 {status!r}"
                        )
                elif want_status_name:
                    status_field = None
                    for field in target_table.get("fields") or []:
                        if field["id"] == status:
                            status_field = field
                            break
                    if status_field is None or status_field.get("name") != want_status_name:
                        issues.append(
                            f"{label} status_field 应指向目标表「{want_status_name}」，"
                            f"实际 {status!r}"
                        )
            if cf["type"] == "computed":
                opts = _options(af)
                kind = opts.get("kind")
                if cf["gate"] and not opts.get("gate"):
                    issues.append(f"{label} 契约标了闸门，线上没打 gate:true")
                if not cf["gate"] and opts.get("gate"):
                    issues.append(f"{label} 线上打了 gate:true，契约未标闸门")
                gate_allowed = kind == "and" or (
                    kind == "rollup" and opts.get("aggregate") in GATE_ROLLUP_AGGREGATES
                )
                if opts.get("gate") and not gate_allowed:
                    issues.append(f"{label} kind={kind} 不允许打闸门标记")
                issues.extend(
                    _check_rule(prefix, role, cf, af, contract, tables, key_to_actual)
                )
    return issues


def check_live(base: str, contract: dict) -> list[str]:
    issues: list[str] = []
    for project in api_get(base, "/api/projects")["projects"]:
        pid = project["id"]
        tables = []
        for summary in api_get(base, f"/api/projects/{pid}/tables")["tables"]:
            detail = api_get(base, f"/api/tables/{summary['id']}/table")
            tables.append(
                {
                    "id": summary["id"],
                    "name": summary.get("name"),
                    "kind": (detail.get("table") or {}).get("kind"),
                    "fields": detail["fields"],
                }
            )
        # 不跳过任何项目：四表项目会在这里被报缺 case/run，而不是静默通过。
        issues.extend(check_tables(pid, tables, contract))
    return issues


def template_tables(table_prefix: str = "tf", field_prefix: str = "tf") -> list[dict]:
    """跑模板脚本拿到它要建的表，转成与线上同构的结构。"""
    path = ROOT / "data/template_board5.py"
    spec = importlib.util.spec_from_file_location("template_board5", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    out = []
    for table in module.build_tables(table_prefix, field_prefix):
        fields = []
        for fid, name, ftype, options in table["fields"]:
            fields.append({"id": fid, "name": name, "type": ftype, "options": options})
        out.append(
            {
                "id": table["id"],
                "name": table["name"],
                "kind": table.get("kind") or "board",
                "fields": fields,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="按 board@N 校验看板结构一致性")
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    ap.add_argument("--template", action="store_true", help="校验 data/template_board5.py 的产物")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    contract = load_contract(Path(args.contract))
    if not contract:
        print(f"契约里没有可校验的表：{args.contract}", file=sys.stderr)
        return 1

    if args.template:
        issues = check_tables("template", template_tables(), contract)
        scope = "template_board5.py"
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
