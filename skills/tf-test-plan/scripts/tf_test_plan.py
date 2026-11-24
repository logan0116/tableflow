#!/usr/bin/env python3
"""tf-test-plan：推进版本第 2 节点「测试设计」（软件测试角色）。

从 ``specs/<dir>/spec.md`` 的 Acceptance Scenario 派生 ``case`` 行（行 id 即场景号），
再把用例纳入目标版本：为每条用例建 ``run`` 行（``<版本号>--<用例号>``，state=todo），
并追加到 ``ver.runs``。重复运行幂等：第二次新建 0 条。不建任何测试计划。

表作用域：读 ``ver``/``indep``/``case``/``run``；写 ``case``/``run``/``ver``。
"""

from __future__ import annotations

import re

from _tf_common import (
    SkillFailure,
    advance_node,
    base_parser,
    derive_cases,
    ensure_prior_nodes,
    entry,
    make_client,
    parse_spec,
    readback_nodes,
    require_run_version,
    require_version,
    resolve_repo_root,
    same_value,
    scenario_count,
    spec_file,
)

ALLOWED = ("ver", "indep", "case", "run")
NODE = "测试设计"
CASE_FIELDS = ("用例号", "用例名", "来源规格", "前置条件", "操作步骤", "预期结果", "优先级")
RUN_FIELDS = ("执行编号", "用例号", "用例", "执行状态", "执行结果")


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    parser = base_parser(
        "推进版本第 2 节点「测试设计」：从 spec 场景派生用例、纳入版本，写 ver.测试设计=done"
    )
    parser.add_argument(
        "--spec",
        action="append",
        default=[],
        metavar="SPEC_ID",
        help="只派生这些规格（如 019-AR）；默认版本内全部规格。可重复。",
    )
    parser.add_argument(
        "--reuse-from",
        metavar="VERSION",
        help="修复/回归版：复用该版本已收录的用例，为本版新建执行记录（不重新派生用例）",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="CASE_ID",
        help="配合 --reuse-from：只复用这些用例号（如 083-US2-AS1）；可重复，不传则复用全部",
    )
    return parser


def _case_values(case_table, case: dict, spec_id: str) -> dict:
    return {
        case_table.fid("用例号"): case["id"],
        case_table.fid("用例名"): case["name"],
        case_table.fid("来源规格"): [spec_id],
        case_table.fid("前置条件"): case["precondition"],
        case_table.fid("操作步骤"): case["steps"],
        case_table.fid("预期结果"): case["expect"],
        case_table.fid("优先级"): case["priority"],
    }


def _case_expected(case: dict, spec_id: str) -> dict:
    return {
        "用例号": case["id"],
        "用例名": case["name"],
        "来源规格": [spec_id],
        "前置条件": case["precondition"],
        "操作步骤": case["steps"],
        "预期结果": case["expect"],
        "优先级": case["priority"],
    }


def find_orphans(existing_ids: list[str], derived_ids: list[str], spec_prefix: str) -> list[str]:
    """同前缀但不在本次派生集合里的既有用例：源场景已消失，报告而不是静默删除。"""
    derived = set(derived_ids)
    return sorted(
        case_id
        for case_id in existing_ids
        if case_id.startswith(f"{spec_prefix}-") and case_id not in derived
    )


def split_scope(wanted: list[str], version_specs: list[str]) -> tuple[list[str], list[str]]:
    """035：交付范围与测试范围分离——把用例来源拆成「本版交付内」与「本版交付外」。

    返回 ``(in_scope, out_of_scope)``。交付外来源照常派生用例，只是不计入本版交付。
    """
    version_set = set(version_specs)
    in_scope = [spec_id for spec_id in wanted if spec_id in version_set]
    out_of_scope = [spec_id for spec_id in wanted if spec_id not in version_set]
    return in_scope, out_of_scope


def _reuse_cases(args, report, client, ver) -> None:
    """把源版本收录的用例复制到本版：新建 ``<本版>--<用例号>`` 的执行记录。"""
    source = args.reuse_from
    source_runs = ver.relation(source, "测试用例")
    report.check("源版本有用例", bool(source_runs), f"{source}：{len(source_runs)} 条")
    if not source_runs:
        raise SkillFailure(f"源版本 {source} 没有收录任何用例，无法复用")

    case_table = client.table("case")
    case_table.require(list(CASE_FIELDS))
    run_table = client.table("run")
    run_table.require(list(RUN_FIELDS))

    case_ids: list[str] = []
    for run_id in source_runs:
        case_no = str(run_id).split("--", 1)[1] if "--" in str(run_id) else str(run_id)
        if not case_table.row_exists(case_no):
            raise SkillFailure(f"源版本 {source} 的执行记录 {run_id} 找不到对应用例 {case_no}")
        case_ids.append(case_no)
    case_ids = sorted(set(case_ids))
    if args.case:
        wanted = list(dict.fromkeys(args.case))
        missing = [item for item in wanted if item not in case_ids]
        report.check(
            "指定的用例都在源版本里",
            not missing,
            f"{len(wanted)} 条已确认" if not missing else f"源版本没有：{'、'.join(missing)}",
        )
        if missing:
            raise SkillFailure(
                f"源版本 {source} 没有这些用例，无法复用：{'、'.join(missing)}"
            )
        case_ids = sorted(set(wanted))
        report.check("按用例号过滤", True, f"只复用 {len(case_ids)} 条：{'、'.join(case_ids)}")

    created = 0
    new_runs: list[str] = []
    for case_no in case_ids:
        run_id = f"{args.version}--{case_no}"
        new_runs.append(run_id)
        if run_table.row_exists(run_id):
            report.check(f"执行记录 {run_id}", True, "已存在，跳过")
            continue
        created += 1
        values = {
            run_table.fid("执行编号"): run_id,
            run_table.fid("用例号"): case_no,
            run_table.fid("用例"): [case_no],
            run_table.fid("执行状态"): "todo",
        }
        expected = {"执行编号": run_id, "用例号": case_no, "执行状态": "todo"}
        if args.dry_run:
            report.write(f"run/{run_id}", "<create>", case_no, "skipped", error="dry-run：未写")
            continue
        detail = client.write_verified("create", "run", run_id, values, expected)
        report.write(f"run/{run_id}", "<create>", case_no, detail["state"],
                     detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(
                f"创建执行记录 {run_id} 失败：{detail.get('error') or '回读不一致'}",
                state=detail["state"],
            )

    current = ver.relation(args.version, "测试用例")
    merged = sorted(set(current) | set(new_runs))
    report.count(reused_cases=len(case_ids), created_runs=created)
    if merged != list(current):
        report.check("纳入本版", True, f"{len(current)} → {len(merged)} 条")
        if not args.dry_run:
            detail = client.write_verified(
                "update", "ver", args.version,
                {ver.fid("测试用例"): merged}, {"测试用例": merged},
            )
            report.write(f"ver/{args.version}", "测试用例", f"{len(merged)} 条",
                         detail["state"], detail.get("http"), detail.get("error"))
            if detail["state"] != "success":
                raise SkillFailure(
                    f"更新版本用例清单失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
                )
    else:
        report.check("纳入本版", True, "清单已包含全部用例，跳过")

    advance_node(
        client, ver, args.version, NODE, report,
        dry_run=args.dry_run, no_stage=args.no_stage,
    )
    readback_nodes(client.table("ver", refresh=True), args.version, report)
    report.finish("success")


def main(args, report) -> None:
    report.note("role", "软件测试")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)
    repo_root = resolve_repo_root(args.repo_root)

    ver = client.table("ver")
    ver.require(["版本号", "发布状态", NODE, "独立需求管理", "测试用例"])
    require_version(ver, args.version, report)
    require_run_version(args.version)
    ensure_prior_nodes(ver, args.version, NODE, report)

    version_specs = ver.relation(args.version, "独立需求管理")
    wanted = list(dict.fromkeys(args.spec)) or list(version_specs)
    # 纯缺陷/回归版本没有新规格：没有用例可派生，测试设计按空集收口。
    fix_only = not wanted and bool(
        ver.relation(args.version, "Bug管理")
        or ver.relation(args.version, "依赖需求管理")
        or ver.relation(args.version, "测试用例")
    )
    report.check(
        "用例来源已确定",
        bool(wanted) or fix_only,
        f"{len(wanted)} 份：{'、'.join(wanted) or '无'}"
        + ("；纯缺陷/回归版本，无新用例可派生" if fix_only else ""),
    )
    if not wanted and args.reuse_from:
        # 修复/回归版没有新规格：复用的是既有用例，只为本版新建执行记录。
        _reuse_cases(args, report, client, ver)
        return
    if not wanted:
        if not fix_only:
            raise SkillFailure("本版既未关联独立需求，也未用 --spec 指定来源，无处派生用例")
        report.note("fix_only", "纯缺陷/回归版本：无独立需求，测试设计无需派生用例")
        advance_node(
            client,
            ver,
            args.version,
            NODE,
            report,
            dry_run=args.dry_run,
            no_stage=args.no_stage,
        )
        readback_nodes(client.table("ver", refresh=True), args.version, report)
        report.finish("success")
        return

    # 035：交付范围与测试范围解耦——用例来源可以不属于本版交付
    _in_scope, out_of_scope = split_scope(wanted, version_specs)
    report.check(
        "用例来源可跨版本（035）",
        True,
        f"{len(out_of_scope)} 份不属本版交付：{'、'.join(out_of_scope)}；只纳入用例，不计入交付范围"
        if out_of_scope
        else "全部来源都在本版交付范围内",
    )
    report.note("out_of_scope_specs", out_of_scope)

    indep = client.table("indep")
    indep.require(["编号", "条款", "规格目录", "场景数", "验收状态"])
    case_table = client.table("case")
    case_table.require(list(CASE_FIELDS))
    run_table = client.table("run")
    run_table.require(list(RUN_FIELDS))

    unaccepted: dict[str, object] = {}
    # 1) 从真源派生
    derived: list[dict] = []
    by_spec: dict[str, list[str]] = {}
    for spec_id in wanted:
        if not indep.row_exists(spec_id):
            raise SkillFailure(f"规格「{spec_id}」在独立规格需求表中不存在")
        acceptance = indep.value(spec_id, "验收状态", default=None)
        if acceptance != "accepted":
            unaccepted[spec_id] = acceptance
        path = spec_file(repo_root, indep, spec_id)
        stories = parse_spec(path)
        count = scenario_count(stories)
        report.check(
            f"规格 {spec_id} 可派生",
            count > 0,
            f"{len(stories)} 个 User Story / {count} 条 Acceptance Scenario",
        )
        cases = derive_cases(spec_id, path)
        for case in cases:
            case["spec"] = spec_id
        by_spec[spec_id] = [case["id"] for case in cases]
        derived.extend(cases)

    ids = [case["id"] for case in derived]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    report.check("场景号唯一", not duplicates, f"重复：{duplicates}" if duplicates else f"{len(ids)} 条")
    if duplicates:
        raise SkillFailure(f"derived 用例行 id 重复：{duplicates}")
    report.count(derived_cases=len(derived), specs=len(wanted))
    if unaccepted:
        # 035 FR-008：来源能力尚未验收时允许纳入，但必须标注
        report.check(
            "来源能力未验收（已标注）",
            True,
            "、".join(f"{k}={v}" for k, v in unaccepted.items()),
        )
        report.note("unaccepted_specs", unaccepted)

    # 2) 幂等派生 case 行
    created_cases = updated_cases = unchanged_cases = 0
    for case in derived:
        case_id = case["id"]
        spec_id = case["spec"]
        expected = _case_expected(case, spec_id)
        values = _case_values(case_table, case, spec_id)
        if not case_table.row_exists(case_id):
            created_cases += 1
            if args.dry_run:
                report.write(f"case/{case_id}", "<create>", case["name"], "skipped", error="dry-run：未写")
                continue
            detail = client.write_verified("create", "case", case_id, values, expected)
            report.write(
                f"case/{case_id}", "<create>", case["name"], detail["state"],
                detail.get("http"), detail.get("error"),
            )
            report.readback(f"case/{case_id}", detail.get("readback") or {})
            if detail["state"] != "success":
                raise SkillFailure(
                    f"创建用例 {case_id} 失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
                )
            continue

        diffs = {
            name: {"expect": want, "actual": case_table.value(case_id, name)}
            for name, want in expected.items()
            if not same_value(want, case_table.value(case_id, name))
        }
        if not diffs:
            unchanged_cases += 1
            continue
        updated_cases += 1
        if args.dry_run:
            report.write(
                f"case/{case_id}", "<update>", sorted(diffs), "skipped", error="dry-run：未写"
            )
            continue
        patch = {case_table.fid(name): want for name, want in expected.items() if name in diffs}
        detail = client.write_verified(
            "update", "case", case_id, patch, {name: expected[name] for name in diffs}
        )
        report.write(
            f"case/{case_id}", "<update>", sorted(diffs), detail["state"],
            detail.get("http"), detail.get("error"),
        )
        report.readback(f"case/{case_id}", detail.get("readback") or {})
        if detail["state"] != "success":
            raise SkillFailure(
                f"更新用例 {case_id} 失败：{detail.get('error') or '回读不一致'}",
                state=detail["state"],
            )
    report.count(
        created_cases=created_cases,
        updated_cases=updated_cases,
        unchanged_cases=unchanged_cases,
    )

    # 3) 源场景消失 → 报告，不静默删/留
    derived_set = set(ids)
    for case_id in case_table.rows:
        match = re.match(r"^([A-Za-z0-9]{3})-US\d+-AS\d+$", case_id)
        if not match:
            continue
        for spec_id in wanted:
            if spec_id.split("-", 1)[0] == match.group(1) and case_id not in derived_set:
                report.data["orphans"].append(
                    {"case": case_id, "spec": spec_id, "reason": "源场景已不存在"}
                )
    report.check(
        "源场景无孤儿",
        not report.data["orphans"],
        f"{len(report.data['orphans'])} 条待人工处理" if report.data["orphans"] else "0",
    )

    # 4) 纳入版本：run 行 + ver.runs（两步写入）
    case_view = client.table("case", refresh=not args.dry_run)
    missing_cases = [case_id for case_id in ids if not case_view.row_exists(case_id)]
    if missing_cases and not args.dry_run:
        raise SkillFailure(f"派生后仍缺用例行：{missing_cases}")
    if args.dry_run:
        report.check(
            "用例落库可读",
            True,
            f"dry-run：已存在 {len(ids) - len(missing_cases)} 条，预计新建 {len(missing_cases)} 条（未写）",
        )
    else:
        report.check(
            "用例落库可读",
            not missing_cases,
            f"{len(ids)} 条可读" if not missing_cases else f"缺 {missing_cases}",
        )

    created_runs = reused_runs = 0
    run_ids: list[str] = []
    for case in derived:
        case_id = case["id"]
        run_id = f"{args.version}--{case_id}"
        run_ids.append(run_id)
        expected = {"执行编号": run_id, "用例号": case_id, "用例": [case_id], "执行状态": "todo"}
        if not run_table.row_exists(run_id):
            created_runs += 1
            values = {
                run_table.fid("执行编号"): run_id,
                run_table.fid("用例号"): case_id,
                run_table.fid("用例"): [case_id],
                run_table.fid("执行状态"): "todo",
            }
            if args.dry_run:
                report.write(f"run/{run_id}", "<create>", case_id, "skipped", error="dry-run：未写")
                continue
            detail = client.write_verified("create", "run", run_id, values, expected)
            report.write(
                f"run/{run_id}", "<create>", case_id, detail["state"],
                detail.get("http"), detail.get("error"),
            )
            report.readback(f"run/{run_id}", detail.get("readback") or {})
            if detail["state"] != "success":
                raise SkillFailure(
                    f"创建执行记录 {run_id} 失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
                )
            continue

        reused_runs += 1
        state = run_table.value(run_id, "执行状态")
        link = run_table.relation(run_id, "用例")
        case_no = run_table.value(run_id, "用例号")
        ok = case_no == case_id and link == [case_id] and state in ("todo", "done")
        report.check(
            f"执行记录 {run_id} 可复用",
            ok,
            f"用例号={case_no} 用例={link} 执行状态={state}",
        )
        if not ok:
            raise SkillFailure(
                f"执行记录 {run_id} 与用例 {case_id} 不一致（用例号={case_no}，用例={link}，state={state}）"
            )
    report.count(created_runs=created_runs, reused_runs=reused_runs)

    current = ver.relation(args.version, "测试用例")
    missing_links = [run_id for run_id in run_ids if run_id not in current]
    if missing_links:
        merged = current + missing_links
        if args.dry_run:
            report.write(
                f"ver/{args.version}", "测试用例", missing_links, "skipped", error="dry-run：未写"
            )
        else:
            detail = client.write_verified(
                "update",
                "ver",
                args.version,
                {ver.fid("测试用例"): merged},
                {"测试用例": merged},
            )
            report.write(
                f"ver/{args.version}", "测试用例", missing_links, detail["state"],
                detail.get("http"), detail.get("error"),
            )
            report.readback(f"ver/{args.version}", detail.get("readback") or {})
            if detail["state"] != "success":
                raise SkillFailure(
                    f"把执行记录挂到版本 {args.version} 失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
                )
    else:
        report.check(
            "版本执行清单已包含全部用例", True, f"{len(run_ids)} 条已在 ver.测试用例 中"
        )

    # 5) 最终读回：执行清单 + run 状态 + 节点
    fresh_ver = client.table("ver", refresh=True)
    fresh_run = client.table("run", refresh=True)
    final_links = set(fresh_ver.relation(args.version, "测试用例"))
    absent = [run_id for run_id in run_ids if run_id not in final_links]
    if args.dry_run:
        report.check(
            "读回版本执行清单",
            True,
            f"dry-run：清单当前 {len(final_links)} 条，预计追加 {len(absent)} 条（未写）",
        )
    else:
        report.check(
            "读回版本执行清单",
            not absent,
            f"{len(run_ids)} 条全部在清单中" if not absent else f"缺 {absent}",
        )
    report.readback(
        f"ver/{args.version}#runs",
        {run_id: {"state": fresh_run.value(run_id, "执行状态")} for run_id in run_ids},
    )
    if absent and not args.dry_run:
        raise SkillFailure(f"版本 {args.version} 的执行清单读回缺少：{absent}")

    advance_node(
        client,
        fresh_ver,
        args.version,
        NODE,
        report,
        dry_run=args.dry_run,
        no_stage=args.no_stage,
    )
    readback_nodes(client.table("ver", refresh=True), args.version, report)
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-test-plan", build_parser(), main))
