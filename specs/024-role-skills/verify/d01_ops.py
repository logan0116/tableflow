#!/usr/bin/env python3
"""D-01（--apply）回放夹具的 HTTP 操作与逐场景断言。

只服务 ``specs/024-role-skills/verify/run_d01_apply.sh``：
- 通过 Agent 写接口做测试前置（改一条用例名、加一条孤儿用例、放开 099 的验收）；
- 读取技能报告与看板状态，对 024 US3-AS1..5 / US4-AS1..4 逐条断言。
不直接连数据库，不打印凭据。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "tf-dev-plan" / "scripts"))

from _tf_common import derive_cases  # noqa: E402

BASE = (os.environ.get("TF_BASE") or "http://127.0.0.1:18090").rstrip("/")
AGENT = os.environ.get("TF_AGENT", "agent-tf-024-d01")
PROJECT = os.environ.get("TF024_PROJECT", "tf024verify")
VERSION = os.environ.get("TF024_VERSION", "v0.7.0")
TABLE_NAMES = {
    "ver": "版本管理",
    "indep": "独立规格需求",
    "dep": "依赖变更需求",
    "case": "测试用例",
    "run": "用例执行情况",
    "bug": "缺陷",
}
NODES = ["版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收"]


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Agent-Id", AGENT)
    request.add_header("X-Origin", "human-request")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return {"http": response.status, **(json.loads(response.read().decode("utf-8") or "{}"))}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"detail": raw[:300]}
        return {"http": exc.code, **payload}


def must(resp: dict, action: str) -> dict:
    if resp.get("http") != 200 or resp.get("result") != "success":
        raise SystemExit(f"[d01] {action} 失败：{json.dumps(resp, ensure_ascii=False)}")
    return resp


def tables() -> dict[str, str]:
    data = call("GET", f"/api/projects/{PROJECT}/tables")
    return {item["name"]: item["id"] for item in data.get("tables", [])}


def table_id(key: str) -> str:
    name = TABLE_NAMES[key]
    mapping = tables()
    if name not in mapping:
        raise SystemExit(f"[d01] 项目缺表：{name}")
    return mapping[name]


def field_ids(table: str) -> dict[str, str]:
    data = call("GET", f"/api/tables/{table}/table")
    return {field["name"]: field["id"] for field in data.get("fields", [])}


def values_of(table: str, row_id: str) -> dict | None:
    resp = call("GET", f"/api/tables/{table}/rows/{row_id}")
    if resp.get("http") == 404:
        return None
    if resp.get("http") != 200:
        raise SystemExit(f"[d01] 读行 {row_id} 失败：{resp}")
    return (resp.get("row") or {}).get("values") or {}


def value(table: str, row_id: str, name: str, default=None):
    ids = field_ids(table)
    if name not in ids:
        return default
    values = values_of(table, row_id) or {}
    return values.get(ids[name], default)


def patch_by_name(table: str, row_id: str, wanted: dict) -> dict:
    ids = field_ids(table)
    values = {ids[name]: value for name, value in wanted.items() if name in ids}
    missing = [name for name in wanted if name not in ids]
    if missing:
        raise SystemExit(f"[d01] 表缺字段：{missing}")
    return must(
        call("PATCH", f"/api/agent/tables/{table}/rows/{row_id}", {"values": values}),
        f"PATCH {table}/{row_id}",
    )


# ---------- 测试前置 ----------


def corrupt_case() -> None:
    case = table_id("case")
    patch_by_name(case, "019-US1-AS1", {"用例名": "STALE-019-US1-AS1"})
    print(json.dumps({"ok": True, "op": "corrupt-case", "row": "019-US1-AS1"}, ensure_ascii=False))


def add_orphan() -> None:
    case = table_id("case")
    ids = field_ids(case)
    values = {
        ids["用例号"]: "019-US9-AS1",
        ids["用例名"]: "源场景已删除的孤儿用例",
        ids["来源规格"]: ["019-AR"],
        ids["前置条件"]: "孤儿夹具",
        ids["操作步骤"]: "模拟 spec 删掉一条场景",
        ids["预期结果"]: "派生报告 orphans",
        ids["优先级"]: "P2",
    }
    must(call("POST", f"/api/agent/tables/{case}/rows/019-US9-AS1", {"values": values}), "建孤儿用例")
    print(json.dumps({"ok": True, "op": "add-orphan", "row": "019-US9-AS1"}, ensure_ascii=False))


def accept_099() -> None:
    indep = table_id("indep")
    patch_by_name(
        indep,
        "099-AR",
        {"验收状态": "accepted", "speckit-implement状态": "done"},
    )
    print(json.dumps({"ok": True, "op": "accept-099"}, ensure_ascii=False))


# ---------- 断言 ----------


def _load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError("报告不是 JSON 对象")
    return data


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _report_errors(report: dict) -> str:
    return " | ".join(str(item) for item in report.get("errors", []))


def _readback_nodes(report: dict) -> dict:
    return (report.get("readback") or {}).get(f"ver/{VERSION}#nodes") or {}


def _version_nodes() -> dict:
    ver = table_id("ver")
    ids = field_ids(ver)
    values = values_of(ver, VERSION) or {}
    return {name: values.get(ids.get(name)) for name in NODES}


def _expected_cases() -> list[str]:
    """真源派生：019-AR 的 Acceptance Scenario 对应的用例行 id。"""
    path = ROOT / "specs" / "019-test-contract" / "spec.md"
    return [case["id"] for case in derive_cases("019-AR", path)]


def _case_table_ids() -> dict[str, dict]:
    case = table_id("case")
    resp = call("GET", f"/api/tables/{case}/table")
    return {row.get("id"): (row.get("values") or {}) for row in resp.get("rows", [])}


def assert_as1(report: dict) -> dict:
    counts = report.get("counts", {})
    _expect(report.get("result") == "success", f"result={report.get('result')}")
    _expect(counts.get("created_cases", 0) > 0, f"created_cases={counts.get('created_cases')}")
    _expect(
        counts.get("created_cases") == counts.get("derived_cases"),
        f"created={counts.get('created_cases')} derived={counts.get('derived_cases')}",
    )
    derived = _expected_cases()
    case = table_id("case")
    ids = field_ids(case)
    existing = _case_table_ids()
    _expect(len(derived) == counts.get("derived_cases"), f"真源派生 {len(derived)} 条")
    for case_id in derived:
        _expect(case_id in existing, f"缺用例行 {case_id}")
        _expect((existing[case_id].get(ids["来源规格"]) or []) == ["019-AR"], f"{case_id} 来源不对")
    _expect(all(item.split("-")[0] == "019" for item in derived), "用例行 id 前缀不是 019")
    return {
        "created_cases": counts.get("created_cases"),
        "created_runs": counts.get("created_runs"),
        "derived_cases": counts.get("derived_cases"),
        "sample_ids": derived[:3],
        "source_ok": True,
    }


def assert_as2(report: dict) -> dict:
    counts = report.get("counts", {})
    _expect(report.get("result") == "success", f"result={report.get('result')}")
    _expect(counts.get("created_cases") == 0, f"created_cases={counts.get('created_cases')}")
    _expect(counts.get("created_runs") == 0, f"created_runs={counts.get('created_runs')}")
    _expect(counts.get("updated_cases", 0) >= 1, f"updated_cases={counts.get('updated_cases')}")
    name = value(table_id("case"), "019-US1-AS1", "用例名")
    _expect(name != "STALE-019-US1-AS1", f"用例名未就地更新：{name}")
    return {
        "created_cases": counts.get("created_cases"),
        "created_runs": counts.get("created_runs"),
        "updated_cases": counts.get("updated_cases"),
        "case_name_after": name,
    }


def assert_as3(report: dict) -> dict:
    orphans = report.get("orphans") or []
    ids = [item.get("case") for item in orphans]
    _expect(report.get("result") == "success", f"result={report.get('result')}")
    _expect("019-US9-AS1" in ids, f"orphans={ids}")
    still = values_of(table_id("case"), "019-US9-AS1")
    _expect(still is not None, "orphan 行被静默删除")
    return {"orphans": ids, "orphan_still_exists": True}


def assert_as4(report: dict) -> dict:
    mapping = tables()
    plan_tables = [name for name in mapping if "计划" in name or name.lower().endswith("-plan")]
    _expect(not plan_tables, f"出现测试计划表：{plan_tables}")
    case = table_id("case")
    run = table_id("run")
    ver = table_id("ver")
    case_ids = field_ids(case)
    run_ids = field_ids(run)
    ver_ids = field_ids(ver)
    derived = _expected_cases()
    run_table = call("GET", f"/api/tables/{run}/table").get("rows", [])
    runs = {row["id"]: row.get("values") or {} for row in run_table}
    todo_ok = 0
    for case_id in derived:
        run_id = f"{VERSION}--{case_id}"
        _expect(run_id in runs, f"缺执行记录 {run_id}")
        values = runs[run_id]
        _expect(values.get(run_ids["执行状态"]) == "todo", f"{run_id} state != todo")
        _expect(values.get(run_ids["用例号"]) == case_id, f"{run_id} case_no 不一致")
        _expect(values.get(run_ids["用例"]) == [case_id], f"{run_id} case 关系不一致")
        _expect(not values.get(run_ids["执行结果"]), f"{run_id} result 非空")
        todo_ok += 1
    ver_values = values_of(ver, VERSION) or {}
    linked = ver_values.get(ver_ids["测试用例"]) or []
    _expect(len(linked) == len(derived), f"ver.runs={len(linked)} derived={len(derived)}")
    return {
        "derived_cases": len(derived),
        "runs_todo_ok": todo_ok,
        "ver_runs": len(linked),
        "plan_tables": [],
        "case_fields_ok": bool(case_ids),
    }


def assert_as5(report: dict) -> dict:
    _expect(report.get("result") == "failed", f"result={report.get('result')}")
    _expect(report.get("writes") == [], f"writes={report.get('writes')}")
    errors = _report_errors(report)
    _expect("前序节点" in errors and "版本需求设计" in errors, f"errors={errors}")
    return {"result": "failed", "writes": 0, "error": errors}


def assert_us4_as1(report: dict) -> dict:
    _expect(report.get("result") == "failed", f"result={report.get('result')}")
    _expect(report.get("writes") == [], f"writes={report.get('writes')}")
    errors = _report_errors(report)
    _expect("未完成任务" in errors or "tasks.md" in errors, f"errors={errors}")
    nodes = _version_nodes()
    _expect(nodes["开发"] != "done", f"开发节点变了：{nodes['开发']}")
    _expect(value(table_id("indep"), "099-AR", "speckit-implement状态") == "todo", "099 implement 变了")
    return {"result": "failed", "writes": 0, "dev_node": nodes["开发"], "error": errors}


def assert_us4_as2(report: dict) -> dict:
    _expect(report.get("result") == "success", f"result={report.get('result')}")
    _expect((report.get("readback") or {}).get("indep/017-AR", {}).get("ok") is True, "indep 读回不一致")
    nodes = _readback_nodes(report)
    _expect(nodes.get("开发") == "done", f"开发={nodes.get('开发')}")
    return {"result": "success", "dev_node": nodes.get("开发"), "indep_017_ok": True}


def assert_us4_as3(report: dict) -> dict:
    _expect(report.get("result") == "failed", f"result={report.get('result')}")
    _expect(report.get("writes") == [], f"writes={report.get('writes')}")
    errors = _report_errors(report)
    _expect("099-AR" in errors and "验收状态" in errors, f"errors={errors}")
    nodes = _version_nodes()
    _expect(nodes["开发验收"] != "done", f"开发验收变了：{nodes['开发验收']}")
    return {"result": "failed", "writes": 0, "dev_accept": nodes["开发验收"], "error": errors}


def assert_us4_as4(report: dict) -> dict:
    _expect(report.get("result") == "success", f"result={report.get('result')}")
    nodes = _readback_nodes(report)
    _expect(nodes.get("开发验收") == "done", f"开发验收={nodes.get('开发验收')}")
    return {"result": "success", "dev_accept": nodes.get("开发验收")}


def assert_flag_dry(report: dict) -> dict:
    _expect(report.get("result") == "success", f"result={report.get('result')}")
    writes = report.get("writes") or []
    _expect(all(item.get("state") == "skipped" for item in writes), "存在非 skipped 写入")
    _expect(report.get("mode") == "dry-run", f"mode={report.get('mode')}")
    _expect(report.get("apply") is True, "报告未记录 --apply")
    _expect(report.get("apply_ignored_by") == "dry-run", "未记录 dry-run 优先")
    return {"mode": "dry-run", "apply": True, "writes": 0, "apply_ignored_by": "dry-run"}


ASSERTIONS = {
    "US3-AS1": assert_as1,
    "US3-AS2": assert_as2,
    "US3-AS3": assert_as3,
    "US3-AS4": assert_as4,
    "US3-AS5": assert_as5,
    "US4-AS1": assert_us4_as1,
    "US4-AS2": assert_us4_as2,
    "US4-AS3": assert_us4_as3,
    "US4-AS4": assert_us4_as4,
    "FLAG-DRY-PRIORITY": assert_flag_dry,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("用法：d01_ops.py <corrupt-case|add-orphan|accept-099|assert> ...")
    command = argv[1]
    if command == "corrupt-case":
        corrupt_case()
        return 0
    if command == "add-orphan":
        add_orphan()
        return 0
    if command == "accept-099":
        accept_099()
        return 0
    if command == "assert":
        as_id, path = argv[2], argv[3]
        report = _load(path)
        try:
            key = ASSERTIONS[as_id](report)
        except AssertionError as exc:
            print(json.dumps({"as": as_id, "ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps({"as": as_id, "ok": True, "key": key}, ensure_ascii=False))
        return 0
    raise SystemExit(f"未知命令：{command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
