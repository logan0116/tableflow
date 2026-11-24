#!/usr/bin/env python3
"""v0.8.3 缺陷登记：把 19 条问题写进缺陷表，并挂到版本。

`tf-test-check` 靠 `ver.Bug管理` 反查缺陷状态，缺陷不登记就复算不到——
版本会因为没有未关闭缺陷而看起来“干净”。本脚本补这一步。

幂等：按编号存在即跳过。默认 dry-run，``--apply`` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/register_083_bugs.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "")
VERSION = "v0.8.3"
TABLES = {"ver": "tf-ver", "bug": "tf-bug"}

# (缺陷编号, 标题, 严重度, 关联规格, 证据, 剩余事项)
BUGS = [
    ("BUG-083-01", "测试验收可被同一请求缩减执行清单绕过", "critical", "036-AR",
     "tests/test_regress_083.py::test_b1_shrinking_run_list_must_not_close（PATCH runs 只留 pass 后置 done → 200）",
     "判定必须读版本实际持有的执行行，而不是本次请求提交的清单"),
    ("BUG-083-02", "执行清单清空后测试验收直接通过", "critical", "036-AR",
     "tests/test_regress_083.py::test_b1_empty_run_list_must_not_close（runs=[] + done → 200）",
     "空清单必须判失败，不得当作“没有可判定行”"),
    ("BUG-083-03", "新建依赖需求行绕过变更流校验", "critical", "037-AR",
     "tests/test_regress_083.py::test_b2_new_dep_row_must_pass_change_flow（POST 只给编号+passed → 200）",
     "新建行要参与 D1/D2；历史导入需要独立受控入口"),
    ("BUG-083-04", "已发布版本的交付范围可被修改", "critical", "034-AR",
     "tests/test_regress_083.py::test_b3_released_version_scope_must_be_frozen（released 版本摘需求 → 200）",
     "已发布版本禁止改交付范围；发布历史不可回写"),
    ("BUG-083-05", "放弃需求失败后留下已改动的版本关联", "critical", "034-AR",
     "tests/test_skill_e2e_083.py::test_b4_drop_is_atomic_on_failure（末步失败，关系已被摘）",
     "放弃需要后端事务化动作，不能靠客户端逐条补偿"),
    ("BUG-083-06", "跨项目同编号需求导致误拒", "major", "034-AR",
     "tests/test_regress_083.py::test_b5_other_project_same_id_must_not_block_drop（被另一项目 v9.9.9 拦住）",
     "查持有版本必须限定本项目"),
    ("BUG-083-07", "cleanup 前置检查恒为假，永远无法执行", "major", "034-AR",
     "tests/test_skill_e2e_083.py::test_b7_cleanup_works_without_run_in_scope（报 036 未生效）",
     "前置检查只应读作用域内的表，或把 run 加入作用域"),
    ("BUG-083-08", "迁移脚本失败处理抛 NameError 且可能退出 0", "major", "019-AR",
     "tests/test_regress_083.py::test_b6_migration_reports_field_failure（failures 未定义）",
     "失败计入失败数并以非零退出；扩展枚举失败也要计"),
    ("BUG-083-09", "board@5 验收状态枚举缺 dropped", "major", "019-AR",
     "tests/test_regress_083.py::test_c3_board5_acceptance_declares_dropped（只有 pending/accepted/rejected）",
     "契约补 dropped，与放弃动作一致"),
    ("BUG-083-10", "需求设计技能在合格规格上因 spec_rel 未定义崩溃", "critical", "042-AR",
     "tests/test_skill_e2e_083.py::test_s1_dev_plan_runs_on_real_spec（NameError: spec_rel）",
     "改用实际路径变量，补齐证据行"),
    ("BUG-083-11", "写实现证据覆盖已写的计划与任务证据", "critical", "042-AR",
     "tests/test_skill_e2e_083.py::test_s2_implement_keeps_plan_task_evidence（证据只剩 implement=）",
     "写后重读行再合并，不要合并构造时的缓存"),
    ("BUG-083-12", "自动生成的计划骨架被判定为完成", "critical", "042-AR",
     "tests/test_skill_e2e_083.py::test_s3_skeleton_plan_is_not_done（实现要点全为待补，plan=done）",
     "骨架不算完成，必须有实质内容"),
    ("BUG-083-13", "纯回归版本被需求设计节点拒绝", "critical", "035-AR",
     "tests/test_skill_e2e_083.py::test_s4_regression_only_version_proceeds（未挂需求/变更单）",
     "空交付范围应允许推进，与 ver.runs 解耦一致"),
    ("BUG-083-14", "只有依赖需求的版本被开发节点拒绝", "critical", "035-AR",
     "tests/test_skill_e2e_083.py::test_s4b_dep_only_version_proceeds（未关联任何独立规格需求）",
     "开发节点不应要求独立需求非空"),
    ("BUG-083-15", "同时给 apply 与 dry-run 时真实写入", "critical", "034-AR",
     "tests/test_skill_e2e_083.py::test_s5_apply_with_dry_run_writes_nothing（关系被摘）",
     "统一计算写入模式，所有写路径共用同一判断"),
    ("BUG-083-16", "技能与服务端把版本号形状硬编码为 semver", "critical", "020-AR",
     "tests/test_skill_e2e_083.py::test_s6_non_semver_version_can_derive_cases（4.0.0_001 被拦）",
     "版本号取版本行 id 本身，不假设 vX.Y.Z"),
    ("BUG-083-17", "复用证据一次“已重新确认”永久豁免", "major", "038-AR",
     "tests/test_regress_083.py::test_c4_reconfirm_does_not_exempt_forever（宪法版本升 v2 仍 200）",
     "豁免只对当次版本有效，宪法版本变化后需重新确认"),
    ("BUG-083-18", "Requirements 章节下的功能需求不被计数", "major", "039-AR",
     "tests/test_regress_083.py::test_c6_fr_under_requirements_section_counted（026 计 0，实有 7）",
     "FR 统计不区分章节层级"),
    ("BUG-083-19", "验收映射一测多场景，覆盖被高估", "critical", "040-AR",
     "tests/test_regress_083.py::test_c5_one_scenario_per_test（83 个测试承担 121 场景）",
     "按场景逐条写行为测试，映射自检校验语义对应"),
]


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", os.environ.get("TF_AGENT", "agent-tf-role"))
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正写入；默认只预览")
    args = parser.parse_args()
    if not BASE:
        raise SystemExit("[083] 未设置 TF_BASE")

    mode = "写入" if args.apply else "预览"
    planned: list[str] = []
    failures: list[str] = []

    detail = call("GET", f"/api/tables/{TABLES['bug']}/table")
    if detail.get("http") != 200:
        raise SystemExit(f"[083] 读取缺陷表失败：{detail}")
    existing = {row["id"] for row in detail.get("rows") or []}

    for bug_id, title, severity, indep, evidence, rest in BUGS:
        if bug_id in existing:
            planned.append(f"缺陷 {bug_id} 已存在，跳过")
            continue
        planned.append(f"新建缺陷 {bug_id}『{title}』({severity})")
        if not args.apply:
            continue
        result = call("POST", f"/api/agent/tables/{TABLES['bug']}/rows/{bug_id}", {"values": {
            "tf-b-id": bug_id,
            "tf-b-title": title,
            "tf-b-status": "open",
            "tf-b-severity": severity,
            "tf-b-source": "review",
            "tf-b-indep": [indep],
            "tf-b-found-ver": VERSION,
            "tf-b-evidence": evidence,
            "tf-b-rest": rest,
        }})
        if result.get("http") not in (200, 201):
            failures.append(f"缺陷 {bug_id}：{result.get('error') or result}")

    wanted = [bug[0] for bug in BUGS]
    ver = call("GET", f"/api/tables/{TABLES['ver']}/table")
    row = next((item for item in (ver.get("rows") or []) if item["id"] == VERSION), None)
    current = (row or {}).get("values", {}).get("tf-v-bug") or []
    merged = sorted(set(list(current) + wanted))
    if merged != list(current):
        planned.append(f"版本 {VERSION} 的 Bug管理 {len(current)} → {len(merged)} 条")
        if args.apply:
            result = call("PATCH", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}",
                          {"values": {"tf-v-bug": merged}})
            if result.get("http") not in (200, 201):
                failures.append(f"版本 Bug管理：{result.get('error') or result}")
    else:
        planned.append(f"版本 {VERSION} 的 Bug管理已收录 {len(merged)} 条，跳过")

    print(f"[083] 共 {len(planned)} 项{mode}")
    for item in planned:
        print("  -", item)
    print(f"\n合计 {len(planned)} 项{mode}；失败 {len(failures)} 项")
    for item in failures:
        print("  !", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
