#!/usr/bin/env python3
"""tf-test-check：推进版本第 6 节点「测试验收」（软件测试角色）。

三条同时成立才允许把 ``ver.测试验收`` 置 done：本版用例全部执行（``run.state``）、
本版 Bug 管理全部 ``closed``、本版变更单全部 ``passed``。判定值在客户端按 board@4
规则重算；看板计算字段只作对照，不作为放行依据。

表作用域：读 ``ver``/``run``/``dep``/``bug``；写 ``ver``。
"""

from __future__ import annotations

from _tf_common import (
    SkillFailure,
    advance_node,
    base_parser,
    ensure_prior_nodes,
    entry,
    make_client,
    readback_nodes,
    require_version,
    stage_done,
)

ALLOWED = ("ver", "run", "dep", "bug")
NODE = "测试验收"


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    return base_parser(
        "推进版本第 6 节点「测试验收」：复算用例完成/Bug清零/变更回归，写 ver.测试验收=done"
    )


def main(args, report) -> None:
    report.note("role", "软件测试")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)

    ver = client.table("ver")
    ver.require(
        ["版本号", "发布状态", NODE, "测试用例", "依赖需求管理", "Bug管理"]
    )
    require_version(ver, args.version, report)
    ensure_prior_nodes(ver, args.version, NODE, report)

    run_table = client.table("run")
    run_table.require(["执行编号", "执行状态", "执行结果"])
    dep_table = client.table("dep")
    dep_table.require(["编号", "回归状态", "证据"])
    bug_table = client.table("bug")
    bug_table.require(["编号", "状态", "证据", "剩余事项"])

    run_ids = ver.relation(args.version, "测试用例")
    change_ids = ver.relation(args.version, "依赖需求管理")
    bug_ids = ver.relation(args.version, "Bug管理")

    run_states = {run_id: run_table.value(run_id, "执行状态") for run_id in run_ids}
    # 036：执行结果为主判据；放行标记三字段在 board@5 才有，缺字段时视为不可放行
    has_waiver = run_table.fid("放行标记", required=False) is not None
    has_waiver_by = run_table.fid("放行批准人", required=False) is not None
    has_waiver_reason = run_table.fid("放行理由", required=False) is not None
    run_results = {run_id: run_table.value(run_id, "执行结果") for run_id in run_ids}
    waiver_flag = {
        run_id: (run_table.value(run_id, "放行标记") if has_waiver else None)
        for run_id in run_ids
    }
    waiver_by = {
        run_id: (run_table.value(run_id, "放行批准人") if has_waiver_by else None)
        for run_id in run_ids
    }
    waiver_reason = {
        run_id: (run_table.value(run_id, "放行理由") if has_waiver_reason else None)
        for run_id in run_ids
    }

    def waiver_ok(run_id: str) -> bool:
        """放行必须三者齐备：标记=waived、批准人非空、理由非空。"""
        return (
            str(waiver_flag.get(run_id)) == "waived"
            and bool(str(waiver_by.get(run_id) or "").strip())
            and bool(str(waiver_reason.get(run_id) or "").strip())
        )
    change_states = {change_id: dep_table.value(change_id, "回归状态") for change_id in change_ids}
    bug_states = {bug_id: bug_table.value(bug_id, "状态") for bug_id in bug_ids}

    pending_runs = [run_id for run_id, state in run_states.items() if state != "done"]
    failed_runs = [
        run_id
        for run_id, state in run_states.items()
        if state == "done" and run_results.get(run_id) != "pass"
    ]
    waived_runs = [run_id for run_id in failed_runs if waiver_ok(run_id)]
    not_passed_runs = [run_id for run_id in failed_runs if run_id not in waived_runs]
    failed_changes = [change_id for change_id, state in change_states.items() if state != "passed"]
    open_bugs = [bug_id for bug_id, state in bug_states.items() if state != "closed"]

    case_done = not pending_runs
    result_ok = not not_passed_runs
    change_done = not failed_changes
    bug_clear = not open_bugs

    report.check(
        "执行结果全部通过",
        result_ok,
        f"{len(run_ids)} 条全部 pass（放行 {len(waived_runs)} 条）"
        if result_ok
        else f"未通过 {not_passed_runs}；其中已放行 {waived_runs}",
    )
    report.check(
        "用例全部执行",
        case_done,
        f"{len(run_ids)} 条全部 done" if case_done else f"未执行 {pending_runs}",
    )
    report.check(
        "变更回归全部通过",
        change_done,
        f"{len(change_ids)} 条全部 passed（空集为真）"
        if change_done
        else f"未通过 {failed_changes}",
    )
    report.check(
        "本版 Bug 全部关闭",
        bug_clear,
        f"{len(bug_ids)} 条全部 closed（空集为真）" if bug_clear else f"未关闭 {open_bugs}",
    )
    report.readback(
        f"run#state/{args.version}",
        {
            run_id: {
                "执行状态": state,
                "执行结果": run_results.get(run_id),
                "放行": waiver_flag.get(run_id) if has_waiver else "（无该字段）",
            }
            for run_id, state in run_states.items()
        },
    )
    report.readback(f"dep#regress/{args.version}", change_states)
    report.readback(f"bug#status/{args.version}", bug_states)

    blockers = []
    if not_passed_runs:
        blockers.append(f"执行结果未通过且未放行：{not_passed_runs}")
    if pending_runs:
        blockers.append(f"用例未全部执行：{pending_runs}")
    if failed_changes:
        blockers.append(f"变更回归未通过：{failed_changes}")
    if open_bugs:
        blockers.append(f"缺陷未关闭：{open_bugs}")
    if blockers:
        raise SkillFailure("测试验收未满足：" + "；".join(blockers))

    # 对照看板计算字段（存在才比，不依赖）。
    board_case_done = ver.value(args.version, "用例是否完成", default=None)
    if board_case_done is not None:
        report.check(
            "看板「用例是否完成」与复算一致",
            bool(board_case_done) == case_done,
            f"看板={board_case_done}，复算={case_done}",
        )
    board_bug_clear = ver.value(args.version, "Bug是否清空", default=None)
    if board_bug_clear is not None:
        report.check(
            "看板「Bug是否清空」与复算一致",
            bool(board_bug_clear) == bug_clear,
            f"看板={board_bug_clear}，复算={bug_clear}",
        )
    board_change_done = ver.value(args.version, "依赖需求是否完成", default=None)
    if board_change_done is not None:
        report.check(
            "看板「依赖需求是否完成」与复算一致",
            bool(board_change_done) == change_done,
            f"看板={board_change_done}，复算={change_done}",
        )

    advance_node(
        client,
        ver,
        args.version,
        NODE,
        report,
        dry_run=args.dry_run,
        no_stage=args.no_stage,
    )
    fresh_ver = client.table("ver", refresh=True)
    snapshot = readback_nodes(fresh_ver, args.version, report)
    computed = stage_done(snapshot)
    report.note(
        "gate",
        {
            "stage_done": computed,
            "board_stage_done": fresh_ver.value(args.version, "六节点是否全部完成", default=None),
            "board_gate": fresh_ver.value(args.version, "发布条件", default=None),
        },
    )
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-test-check", build_parser(), main))
