#!/usr/bin/env python3
"""在线上tableflow项目建缺陷表tf-bug（011-bug-table一次性建表脚本）。

契约唯一来源：specs/011-bug-table/board@2.yaml的tables.bug（12字段）。
本脚本只做一件事：确保线上存在tf-bug表与其12个字段，建后回读逐字段核对。

性质：
- 可重入：以字段id为准，已存在且配置一致则跳过；配置冲突只报错，不修改、不删除；
  重复执行不产生重复字段。
- 只写tf-bug：不碰tf-ver/tf-indep/tf-dep的字段与行。
- 三态语义：接口返回result=unknown视为失败，不当成功。

用法：
    python3 backend/scripts/create_bug_table.py --dry-run       # 只打印计划，0次写
    python3 backend/scripts/create_bug_table.py                 # 建表建字段并回读核对
    python3 backend/scripts/create_bug_table.py --base http://127.0.0.1:8000
    python3 backend/scripts/create_bug_table.py --contract specs/011-bug-table/board@2.yaml

退出码：0=全部就绪（含"本来就一致"）；1=存在冲突、创建失败或回读不一致。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = os.environ.get("TF_BASE", "http://192.168.1.155:8090")
PROJECT_ID = "tableflow"
TABLE_ID = "tf-bug"
TABLE_NAME = "缺陷"
TABLE_ORDER = 4
AGENT_ID = "agent-tf-doc"
ORIGIN = "human-request"
DEFAULT_CONTRACT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "specs/011-bug-table/board@2.yaml",
)

ENUM_STATUS = [
    {"value": "open", "label": "待修", "tone": "danger"},
    {"value": "fixing", "label": "修复中", "tone": "warning"},
    {"value": "verifying", "label": "已修待验", "tone": "info"},
    {"value": "closed", "label": "已关闭", "tone": "success"},
]
ENUM_SEVERITY = [
    {"value": "blocker", "label": "阻断", "tone": "danger"},
    {"value": "critical", "label": "严重", "tone": "warning"},
    {"value": "major", "label": "一般", "tone": "info"},
    {"value": "minor", "label": "轻微", "tone": "neutral"},
]
ENUM_SOURCE = [
    {"value": "test", "label": "测试发现", "tone": "info"},
    {"value": "prod", "label": "线上发现", "tone": "danger"},
    {"value": "review", "label": "评审发现", "tone": "warning"},
    {"value": "user", "label": "用户反馈", "tone": "warning"},
]

# 与board@2.yaml的tables.bug逐项对应；key用于和契约交叉核对。
FIELDS: list[dict] = [
    {
        "key": "bug.id",
        "id": "tf-b-id",
        "name": "编号",
        "type": "text",
        "options": {"constraints": {"required": True}},
    },
    {
        "key": "bug.title",
        "id": "tf-b-title",
        "name": "标题",
        "type": "text",
        "options": {"constraints": {"required": True}},
    },
    {
        "key": "bug.status",
        "id": "tf-b-status",
        "name": "状态",
        "type": "enum",
        "options": {"items": ENUM_STATUS, "constraints": {"required": True}},
    },
    {
        "key": "bug.severity",
        "id": "tf-b-severity",
        "name": "严重度",
        "type": "enum",
        "options": {"items": ENUM_SEVERITY, "constraints": {"required": True}},
    },
    {
        "key": "bug.source",
        "id": "tf-b-source",
        "name": "来源",
        "type": "enum",
        "options": {"items": ENUM_SOURCE, "constraints": {"required": True}},
    },
    {
        "key": "bug.specs",
        "id": "tf-b-indep",
        "name": "关联规格",
        "type": "relation",
        "options": {
            "table_id": "tf-indep",
            "display_field": "tf-i-clause",
            "status_field": "tf-i-implement",
            "constraints": {"relation_must_exist": True},
        },
    },
    {
        "key": "bug.found",
        "id": "tf-b-found",
        "name": "发现版本",
        "type": "relation",
        "options": {
            "table_id": "tf-ver",
            "display_field": "tf-v-ver",
            "status_field": "tf-v-status",
            "constraints": {"required": True, "relation_must_exist": True},
        },
    },
    {
        "key": "bug.fix",
        "id": "tf-b-fix",
        "name": "修复版本",
        "type": "relation",
        "options": {
            "table_id": "tf-ver",
            "display_field": "tf-v-ver",
            "status_field": "tf-v-status",
            "constraints": {"relation_must_exist": True},
        },
    },
    {
        "key": "bug.evidence",
        "id": "tf-b-evidence",
        "name": "证据",
        "type": "text",
        "options": None,
    },
    {
        "key": "bug.rest",
        "id": "tf-b-rest",
        "name": "剩余事项",
        "type": "text",
        "options": None,
    },
    {
        "key": "bug.ms_case",
        "id": "tf-b-ms",
        "name": "MS用例号",
        "type": "text",
        "options": None,
    },
    {
        "key": "bug.owner",
        "id": "tf-b-owner",
        "name": "负责人",
        "type": "text",
        "options": None,
    },
]


class ApiError(RuntimeError):
    pass


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if method != "GET":
        headers["X-Agent-Id"] = AGENT_ID
        headers["X-Origin"] = ORIGIN
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise ApiError(f"无法连接{base}：{exc.reason}") from exc


def require_success(action: str, status: int, payload: dict) -> dict:
    result = payload.get("result")
    if status != 200 or result == "failed":
        raise ApiError(f"{action}失败（HTTP {status}）：{payload.get('error') or payload}")
    if result == "unknown":
        raise ApiError(f"{action}结果未知（不得当成功）：{payload.get('error') or payload}")
    return payload


def options_match(actual, expected) -> bool:
    """契约声明的键必须一致；服务端追加的键不视为冲突。"""
    if expected is None:
        return actual in (None, {}, [])
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and options_match(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            options_match(a, e) for a, e in zip(actual, expected)
        )
    return actual == expected


def check_contract(contract_path: str) -> list[str]:
    """用契约文件交叉核对脚本内期望，防止两处漂移。返回问题清单（空=一致）。"""
    problems: list[str] = []
    try:
        import yaml  # type: ignore
    except ImportError:
        print(f"[warn] 未安装PyYAML，跳过契约交叉核对：{contract_path}")
        return problems
    if not os.path.exists(contract_path):
        print(f"[warn] 契约文件不存在，跳过交叉核对：{contract_path}")
        return problems
    with open(contract_path, encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    bug_fields = contract["tables"]["bug"]["fields"]
    by_key = {item["key"]: item for item in bug_fields}
    if len(bug_fields) != len(FIELDS):
        problems.append(f"契约bug字段数{len(bug_fields)}≠脚本期望{len(FIELDS)}")
    for field in FIELDS:
        spec = by_key.get(field["key"])
        if spec is None:
            problems.append(f"{field['key']}在契约中不存在")
            continue
        if spec.get("name") != field["name"]:
            problems.append(f"{field['key']}名称不一致：契约{spec.get('name')}≠脚本{field['name']}")
        if spec.get("type") != field["type"]:
            problems.append(f"{field['key']}类型不一致：契约{spec.get('type')}≠脚本{field['type']}")
        if field["type"] == "enum":
            items = field["options"]["items"]
            expected_values = [item["value"] for item in items]
            if spec.get("values") != expected_values:
                problems.append(f"{field['key']}枚举不一致：契约{spec.get('values')}≠脚本{expected_values}")
        if field["type"] == "relation":
            if spec.get("target") != field["options"]["table_id"].removeprefix("tf-"):
                problems.append(f"{field['key']}关联目标不一致：契约{spec.get('target')}≠脚本{field['options']['table_id']}")
        declared_required = (
            bool(field["options"].get("constraints", {}).get("required"))
            if isinstance(field["options"], dict)
            else False
        )
        if bool(spec.get("required")) != declared_required:
            problems.append(f"{field['key']}必填标记不一致：契约{spec.get('required')}≠脚本{declared_required}")
    return problems


def fetch_table(base: str) -> tuple[int, dict]:
    return call(base, "GET", f"/api/tables/{TABLE_ID}/table")


def plan_actions(existing_fields: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    by_id = {field["id"]: field for field in existing_fields}
    creates: list[dict] = []
    conflicts: list[str] = []
    skips: list[str] = []
    for order, field in enumerate(FIELDS, start=1):
        current = by_id.get(field["id"])
        if current is None:
            creates.append({"order": order, **field})
            continue
        issues = []
        if current.get("name") != field["name"]:
            issues.append(f"名称{current.get('name')}≠{field['name']}")
        if current.get("type") != field["type"]:
            issues.append(f"类型{current.get('type')}≠{field['type']}")
        if not options_match(current.get("options"), field["options"]):
            issues.append(f"options不一致：现有{current.get('options')}≠契约{field['options']}")
        if issues:
            conflicts.append(f"{field['id']}：" + "；".join(issues))
        else:
            skips.append(field["id"])
    extra = sorted(set(by_id) - {field["id"] for field in FIELDS})
    return creates, conflicts, skips + ([f"多余字段：{','.join(extra)}"] if extra else [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="在线上tableflow项目建缺陷表tf-bug（可重入）")
    parser.add_argument("--base", default=DEFAULT_BASE, help="看板地址，默认取TF_BASE或线上实例")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不写任何数据")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT, help="用于交叉核对的契约文件路径")
    args = parser.parse_args(argv)
    base = args.base.rstrip("/")

    print(f"目标：{base}，项目={PROJECT_ID}，表={TABLE_ID}（{TABLE_NAME}）")

    problems = check_contract(args.contract)
    if problems:
        print("[FAIL] 脚本内字段期望与契约不一致：")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[ok] 契约交叉核对通过（{len(FIELDS)}字段）：{args.contract}")

    for dependency in ("tf-indep", "tf-ver"):
        status, _ = call(base, "GET", f"/api/tables/{dependency}/table")
        if status != 200:
            print(f"[FAIL] 依赖表{dependency}不存在（HTTP {status}），先确认项目里有三表")
            return 1
    print("[ok] 依赖表tf-ver/tf-indep均在")

    try:
        status, payload = fetch_table(base)
        if status == 404:
            existing_fields: list[dict] = []
            if args.dry_run:
                print(f"[plan] 建表{TABLE_ID}（{TABLE_NAME}，order {TABLE_ORDER}）")
            else:
                write_status, write_payload = call(
                    base,
                    "POST",
                    f"/api/agent/projects/{PROJECT_ID}/tables",
                    {"id": TABLE_ID, "name": TABLE_NAME, "order": TABLE_ORDER},
                )
                require_success("建表", write_status, write_payload)
                print(f"[ok] 已建表{TABLE_ID}（{TABLE_NAME}，order {TABLE_ORDER}）")
        elif status == 200:
            existing_fields = payload.get("fields", [])
            print(f"[ok] 表{TABLE_ID}已存在，现有{len(existing_fields)}字段")
        else:
            print(f"[FAIL] 读取{TABLE_ID}失败（HTTP {status}）：{payload}")
            return 1

        creates, conflicts, notes = plan_actions(existing_fields)
        for field in creates:
            if args.dry_run:
                print(f"[plan] 建字段{field['id']}（{field['name']}，{field['type']}）")
            else:
                write_status, write_payload = call(
                    base,
                    "POST",
                    f"/api/agent/tables/{TABLE_ID}/fields",
                    {
                        "id": field["id"],
                        "name": field["name"],
                        "type": field["type"],
                        "options": field["options"],
                        "order": field["order"],
                    },
                )
                require_success("建字段", write_status, write_payload)
                print(f"[ok] 已建字段{field['id']}（{field['name']}，{field['type']}）")
        for note in notes:
            print(f"[skip] {note}")
        if conflicts:
            print("[FAIL] 已存在字段与契约冲突（不修改、不删除）：")
            for item in conflicts:
                print(f"  - {item}")
            return 1
        if args.dry_run:
            print(f"[plan] 合计：新建表{0 if existing_fields else 1}张、新建字段{len(creates)}个、跳过{len(notes)}个")
            return 0

        status, payload = fetch_table(base)
        if status != 200:
            print(f"[FAIL] 回读{TABLE_ID}失败（HTTP {status}）：{payload}")
            return 1
    except ApiError as exc:
        print(f"[FAIL] {exc}")
        return 1

    actual_fields = payload.get("fields", [])
    by_id = {field["id"]: field for field in actual_fields}
    expected_ids = {field["id"] for field in FIELDS}
    actual_ids = set(by_id)
    print(f"\n回读核对：{TABLE_ID}字段数={len(actual_fields)}（契约期望{len(FIELDS)}）")
    failures: list[str] = []
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing:
        failures.append(f"缺字段：{','.join(missing)}")
    if extra:
        failures.append(f"多余字段：{','.join(extra)}")
    for field in FIELDS:
        current = by_id.get(field["id"])
        if current is None:
            print(f"  MISMATCH {field['id']}：不存在")
            continue
        ok = (
            current.get("name") == field["name"]
            and current.get("type") == field["type"]
            and options_match(current.get("options"), field["options"])
        )
        print(f"  {'OK  ' if ok else 'FAIL'} {field['id']}（{field['name']}，{field['type']}）")
        if not ok:
            failures.append(
                f"{field['id']}：现有(name={current.get('name')},type={current.get('type')},options={current.get('options')})"
                f"≠契约(name={field['name']},type={field['type']},options={field['options']})"
            )
    rows = payload.get("rows", [])
    if rows:
        print(f"[warn] {TABLE_ID}已有{len(rows)}行数据；本脚本不写行，仅提示")
    if failures:
        print("[FAIL] 回读核对未通过：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"[ok] 回读核对通过：{len(FIELDS)}字段与契约一致，无多余字段，行数={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
