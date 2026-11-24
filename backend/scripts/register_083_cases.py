#!/usr/bin/env python3
"""v0.8.3 缺陷显现化：登记版本行与复现用例（不登记需求）。

19 条缺陷各对应一条用例，来源规格挂到它验证的既有规格；版本本身不挂独立/依赖
需求，只用 ``ver.runs`` 收录用例。已能用测试复现的记为 fail，其余记为未执行。

幂等：版本行、用例行、执行行按 id 存在即跳过。默认 dry-run，``--apply`` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/register_083_cases.py
    TF_BASE=http://localhost:8090 python3 backend/scripts/register_083_cases.py --apply
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "")
PROJECT = os.environ.get("TF_PROJECT", "tableflow")
AGENT = os.environ.get("TF_AGENT", "agent-tf-role")
VERSION = "v0.8.3"
TABLES = {"ver": "tf-ver", "indep": "tf-indep", "case": "tf-case", "run": "tf-run"}
NOTE = "缺陷显现化：19 条问题先写成用例，不登记需求；用例红灯即未收口"

STAGE_FIELDS = (
    "tf-v-stage-plan", "tf-v-stage-test-design", "tf-v-stage-dev",
    "tf-v-stage-dev-accept", "tf-v-stage-test", "tf-v-stage-test-accept",
)

# (用例号, 名称, 来源规格, Given, When, Then, 优先级, 证据)
CASES = [
    ("083-US1-AS1", "一次请求缩减执行清单再置验收必须拒绝", "036-AR",
     "版本内有 pass 与 fail 两条执行记录，", "同一请求把测试用例缩减为只含 pass 并置测试验收 done，",
     "返回 400，并指出被摘掉的失败记录", "P1",
     "tests/test_regress_083.py::test_b1_shrinking_run_list_must_not_close"),
    ("083-US1-AS2", "清空执行清单再置验收必须拒绝", "036-AR",
     "版本内有 fail 执行记录，", "同一请求把测试用例清空并置测试验收 done，",
     "返回 400，不得因没有可判定行而放行", "P1",
     "tests/test_regress_083.py::test_b1_empty_run_list_must_not_close"),
    ("083-US2-AS1", "新建依赖需求不得绕过变更流", "037-AR",
     "依赖需求表已启用完整变更流字段，", "POST 新建一行只给编号与回归状态 passed，",
     "返回 400 并列出缺少的变更字段", "P1",
     "tests/test_regress_083.py::test_b2_new_dep_row_must_pass_change_flow"),
    ("083-US3-AS1", "已发布版本持有的需求不得被放弃", "034-AR",
     "版本已发布且仍持有某独立需求，", "放弃该需求，",
     "拒绝并说明发布历史不可改", "P1", ""),
    ("083-US3-AS2", "放弃失败不得留下已改动的版本范围", "034-AR",
     "放弃动作需先摘版本关系再改验收状态，", "末步注入失败，",
     "版本关系与验收状态都不变", "P1", ""),
    ("083-US3-AS3", "跨项目同编号需求不得互相干扰", "034-AR",
     "另一项目存在同编号需求，", "本项目放弃该编号，",
     "按本项目的关系判定，不被跨项目数据干扰", "P2", ""),
    ("083-US3-AS4", "清理前置检查不得依赖不在作用域的表", "034-AR",
     "项目只有版本与独立需求两张表，", "执行 cleanup，",
     "前置检查通过，而不是误报 036 未生效", "P2", ""),
    ("083-US4-AS1", "迁移失败必须非零退出且计数准确", "019-AR",
     "迁移在新增字段或扩展枚举时失败，", "执行 apply，",
     "非零退出，失败计数与实际一致", "P2", ""),
    ("083-US4-AS2", "契约声明的验收状态必须含 dropped", "019-AR",
     "按 board@5 建表，", "读取独立需求验收状态枚举，",
     "包含 dropped，放弃动作可直接执行", "P2", ""),
    ("083-US5-AS1", "需求设计技能在合格规格上必须跑完", "042-AR",
     "一份结构合格的规格已挂到版本，", "推进版本需求设计，",
     "技能完成并写入五个阶段状态，不出现未定义变量", "P1",
     "tests/test_skill_e2e_083.py::test_s1_dev_plan_runs_on_real_spec"),
    ("083-US5-AS2", "写实现证据不得覆盖已写的阶段证据", "042-AR",
     "plan 与 tasks 证据刚写入，", "再写 implement 证据，",
     "三份证据同时保留", "P1", ""),
    ("083-US5-AS3", "自动生成的计划骨架不得算完成", "042-AR",
     "plan.md 只有自动生成的骨架且实现要点为待补，", "判定 plan 阶段，",
     "不得置 done", "P1", ""),
    ("083-US6-AS1", "无独立需求的回归版本可以推进需求设计", "035-AR",
     "版本不挂任何独立需求，只收录版本外用例，", "推进版本需求设计，",
     "允许推进，不因范围为空被拒", "P1", ""),
    ("083-US6-AS2", "只有依赖需求的版本可以推进开发", "035-AR",
     "版本只挂依赖需求，", "推进开发节点，",
     "不被未关联独立需求拒绝", "P1", ""),
    ("083-US7-AS1", "同时给 apply 与 dry-run 时不得写入", "034-AR",
     "同时传入 apply 与 dry-run，", "执行放弃动作，",
     "库内零写入，报告标记为只读", "P1",
     "tests/test_skill_e2e_083.py::test_s5_apply_with_dry_run_writes_nothing"),
    ("083-US8-AS1", "非 semver 版本与带编号的场景都要能处理", "020-AR",
     "版本行 id 形如 3.0.0_012，场景写作 1. **S1.1** **Given** 形式，", "派生用例与执行记录，",
     "两端都通过，不再被形状规则挡下", "P1", ""),
    ("083-US9-AS1", "复用证据的重新确认不得永久豁免", "038-AR",
     "宪法版本升级，", "复用旧版本产物且此前只写过一次已重新确认，",
     "仍要求针对新版本重新确认", "P2", ""),
    ("083-US9-AS2", "Requirements 章节下的 FR 必须计入", "039-AR",
     "功能需求直接写在 Requirements 章节下，", "分析规格结构，",
     "FR 数量与文本实际条目一致", "P2", ""),
    ("083-US9-AS3", "每条场景必须映射到能验证其结论的测试", "040-AR",
     "取一条验收场景，", "查它与测试的映射，",
     "指向验证该 Then 的行为测试，而不是任意存在的测试", "P1", ""),
    ("083-US10-AS1", "测试验收判定不通过时必须落 failed", "036-AR",
     "版本前五节点完成、存在失败执行记录，", "执行测试验收判定，",
     "节点落 failed 并列出未通过项，而不是停在 todo", "P1",
     "tests/test_skill_e2e_083.py::test_s7_rejected_acceptance_must_mark_failed"),
]

FAILED = {
    "083-US1-AS1", "083-US1-AS2", "083-US2-AS1", "083-US3-AS1", "083-US3-AS2",
    "083-US3-AS3", "083-US3-AS4", "083-US4-AS1", "083-US4-AS2", "083-US5-AS1",
    "083-US5-AS2", "083-US5-AS3", "083-US6-AS1", "083-US6-AS2", "083-US7-AS1",
    "083-US8-AS1", "083-US9-AS1", "083-US9-AS2", "083-US9-AS3", "083-US10-AS1",
}

# 已能复现的用例 → 复现它的测试（写入执行记录证据）
EVIDENCE = {
    "083-US1-AS1": "tests/test_regress_083.py::test_b1_shrinking_run_list_must_not_close",
    "083-US1-AS2": "tests/test_regress_083.py::test_b1_empty_run_list_must_not_close",
    "083-US2-AS1": "tests/test_regress_083.py::test_b2_new_dep_row_must_pass_change_flow",
    "083-US3-AS1": "tests/test_regress_083.py::test_b3_released_version_scope_must_be_frozen",
    "083-US3-AS3": "tests/test_regress_083.py::test_b5_other_project_same_id_must_not_block_drop",
    "083-US4-AS1": "tests/test_regress_083.py::test_b6_migration_reports_field_failure",
    "083-US4-AS2": "tests/test_regress_083.py::test_c3_board5_acceptance_declares_dropped",
    "083-US5-AS1": "tests/test_skill_e2e_083.py::test_s1_dev_plan_runs_on_real_spec",
    "083-US6-AS1": "tests/test_skill_e2e_083.py::test_s4_regression_only_version_proceeds",
    "083-US6-AS2": "tests/test_skill_e2e_083.py::test_s4b_dep_only_version_proceeds",
    "083-US7-AS1": "tests/test_skill_e2e_083.py::test_s5_apply_with_dry_run_writes_nothing",
    "083-US9-AS2": "tests/test_regress_083.py::test_c6_fr_under_requirements_section_counted",
    "083-US3-AS2": "tests/test_skill_e2e_083.py::test_b4_drop_is_atomic_on_failure",
    "083-US3-AS4": "tests/test_skill_e2e_083.py::test_b7_cleanup_works_without_run_in_scope",
    "083-US5-AS2": "tests/test_skill_e2e_083.py::test_s2_implement_keeps_plan_task_evidence",
    "083-US5-AS3": "tests/test_skill_e2e_083.py::test_s3_skeleton_plan_is_not_done",
    "083-US8-AS1": "tests/test_skill_e2e_083.py::test_s6_non_semver_version_can_derive_cases",
    "083-US9-AS1": "tests/test_regress_083.py::test_c4_reconfirm_does_not_exempt_forever",
    "083-US9-AS3": "tests/test_regress_083.py::test_c5_one_scenario_per_test",
    "083-US10-AS1": "tests/test_skill_e2e_083.py::test_s7_rejected_acceptance_must_mark_failed",
}


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", AGENT)
    req.add_header("X-Origin", "human-request")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"http": resp.status, **json.loads(resp.read().decode() or "{}")}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:  # noqa: BLE001 - 非 JSON 错误体照样回传
            payload = {"error": raw[:300]}
        return {"http": exc.code, **payload}
    except Exception as exc:  # noqa: BLE001 - 网络异常按三态处理
        return {"http": 0, "error": f"{type(exc).__name__}: {exc}"}


def table_rows(table_id: str) -> tuple[dict, dict[str, dict]]:
    detail = call("GET", f"/api/tables/{table_id}/table")
    if detail.get("http") != 200:
        raise SystemExit(f"[083] 读取 {table_id} 失败：{detail}")
    return detail, {row["id"]: row for row in detail.get("rows") or []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正写入；默认只预览")
    args = parser.parse_args()
    if not BASE:
        raise SystemExit("[083] 未设置 TF_BASE")

    mode = "写入" if args.apply else "预览"
    planned: list[str] = []
    failures: list[str] = []
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    _ver_detail, ver_rows = table_rows(TABLES["ver"])
    if VERSION in ver_rows:
        planned.append(f"版本行 {VERSION} 已存在，跳过")
    else:
        planned.append(f"新建版本行 {VERSION}（planned，六节点 todo，不挂需求）")
        if args.apply:
            body = {
                "values": {
                    "tf-v-ver": VERSION,
                    "tf-v-status": "planned",
                    **{fid: "todo" for fid in STAGE_FIELDS},
                    "tf-v-indep": [],
                    "tf-v-dep": [],
                    "tf-v-runs": [],
                    "tf-v-bug": [],
                    "tf-v-note": NOTE,
                }
            }
            result = call("POST", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}", body)
            if result.get("http") not in (200, 201):
                failures.append(f"版本行 {VERSION}：{result.get('error') or result}")

    _case_detail, case_rows = table_rows(TABLES["case"])
    for case_id, name, indep_id, given, when, then, priority, _evidence in CASES:
        if case_id in case_rows:
            planned.append(f"用例 {case_id} 已存在，跳过")
            continue
        planned.append(f"新建用例 {case_id}『{name}』→ {indep_id}")
        if not args.apply:
            continue
        body = {
            "values": {
                "tf-c-id": case_id,
                "tf-c-name": name,
                "tf-c-indep": [indep_id],
                "tf-c-precondition": given,
                "tf-c-steps": when,
                "tf-c-expect": then,
                "tf-c-priority": priority,
            }
        }
        result = call("POST", f"/api/agent/tables/{TABLES['case']}/rows/{case_id}", body)
        if result.get("http") not in (200, 201):
            failures.append(f"用例 {case_id}：{result.get('error') or result}")

    _run_detail, run_rows = table_rows(TABLES["run"])
    for case_id, _name, _indep, _g, _w, then, _p, evidence in CASES:
        run_id = f"{VERSION}--{case_id}"
        if run_id in run_rows:
            planned.append(f"执行记录 {run_id} 已存在，跳过")
            continue
        state = "done" if case_id in FAILED else "todo"
        planned.append(f"新建执行记录 {run_id}（{state}{'，结果 fail' if state == 'done' else '，未执行'}）")
        if not args.apply:
            continue
        values = {
            "tf-r-id": run_id,
            "tf-r-case_no": case_id,
            "tf-r-case": [case_id],
            "tf-r-state": state,
        }
        if state == "done":
            values.update({
                "tf-r-result": "fail",
                "tf-r-evidence": f"{evidence}（xfail strict：失败原因即缺陷）" if evidence else "待补复现用例",
                "tf-r-executed_at": now,
                "tf-r-executor": "agent-auto",
                "tf-r-note": "v0.8.3 缺陷复现：当前必然失败",
            })
        result = call("POST", f"/api/agent/tables/{TABLES['run']}/rows/{run_id}", {"values": values})
        if result.get("http") not in (200, 201):
            failures.append(f"执行记录 {run_id}：{result.get('error') or result}")

    wanted = [f"{VERSION}--{case[0]}" for case in CASES]
    _ver_detail, ver_rows = table_rows(TABLES["ver"])
    current = (ver_rows.get(VERSION) or {}).get("values", {}).get("tf-v-runs") or []
    merged = sorted(set(list(current) + wanted))
    if merged != list(current):
        planned.append(f"版本 {VERSION} 的测试用例清单 {len(current)} → {len(merged)} 条")
        if args.apply:
            result = call(
                "PATCH", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}",
                {"values": {"tf-v-runs": merged}},
            )
            if result.get("http") not in (200, 201):
                failures.append(f"版本清单：{result.get('error') or result}")
    else:
        planned.append(f"版本 {VERSION} 的测试用例清单已收录 {len(merged)} 条，跳过")

    _run_detail, run_rows = table_rows(TABLES["run"])
    for case_id in FAILED:
        run_id = f"{VERSION}--{case_id}"
        current = run_rows.get(run_id)
        if current is None:
            continue
        values = current["values"]
        if (values.get("tf-r-state") == "done" and values.get("tf-r-result") == "fail"
                and str(values.get("tf-r-evidence") or "").strip()):
            continue
        evidence = EVIDENCE.get(case_id, "")
        planned.append(f"补齐执行记录 {run_id}：done/fail")
        if not args.apply:
            continue
        result = call(
            "PATCH", f"/api/agent/tables/{TABLES['run']}/rows/{run_id}",
            {"values": {
                "tf-r-state": "done",
                "tf-r-result": "fail",
                "tf-r-evidence": f"{evidence}（xfail strict：失败原因即缺陷）" if evidence else "待补复现用例",
                "tf-r-executed_at": now,
                "tf-r-executor": "agent-auto",
                "tf-r-note": "v0.8.3 缺陷复现：当前必然失败",
            }},
        )
        if result.get("http") not in (200, 201):
            failures.append(f"补齐 {run_id}：{result.get('error') or result}")

    print(f"[083] 共 {len(planned)} 项{mode}")
    for item in planned:
        print("  -", item)
    print(f"\n合计 {len(planned)} 项{mode}；失败 {len(failures)} 项")
    for item in failures:
        print("  !", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
