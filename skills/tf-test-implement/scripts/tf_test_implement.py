#!/usr/bin/env python3
"""tf-test-implement：推进版本第 5 节点「测试」（软件测试角色）。

把指定用例在目标版本里的 ``run`` 行写成 ``执行状态=done`` + ``执行结果`` + 证据/时间/执行人；
本版全部 ``run`` 都 ``done`` 后，把 ``ver.测试`` 置 done。重跑就地更新同一行，不新建。

表作用域：读 ``ver``/``run``/``case``；写 ``run``/``ver``。
"""

from __future__ import annotations

from _tf_common import (
    RUN_RESULT_VALUES,
    SkillFailure,
    advance_node,
    base_parser,
    ensure_prior_nodes,
    entry,
    make_client,
    now_iso,
    readback_nodes,
    require_version,
    require_run_version,
)

ALLOWED = ("ver", "run", "case")
NODE = "测试"


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    parser = base_parser(
        "推进版本第 5 节点「测试」：写 run 执行状态/结果/证据，全部执行后写 ver.测试=done"
    )
    parser.add_argument("--case", action="append", default=[], metavar="CASE_OR_RUN_ID",
                        help="要执行的用例号或执行记录 id；可重复")
    parser.add_argument("--all-pending", action="store_true", help="执行本版所有 state!=done 的执行记录")
    parser.add_argument("--result", choices=sorted(RUN_RESULT_VALUES), help="执行结果")
    parser.add_argument("--evidence", default=None, help="证据：截图目录/日志路径/提交号")
    parser.add_argument("--executor", default=None, help="执行人，默认 TF_AGENT")
    parser.add_argument("--note", default=None, help="备注（失败或阻塞原因）")
    parser.add_argument("--at", default=None, help="执行时间，默认当前时间（ISO 8601）")
    return parser


def _run_id(version: str, raw: str) -> str:
    return raw if raw.startswith(f"{version}--") else f"{version}--{raw}"


def main(args, report) -> None:
    report.note("role", "软件测试")
    report.note("node", NODE)
    if args.case and args.all_pending:
        raise SkillFailure("--case 与 --all-pending 只能二选一，避免执行范围歧义")
    if not args.case and not args.all_pending:
        raise SkillFailure("必须指定 --case <用例号> 或 --all-pending")
    if not args.result:
        raise SkillFailure("必须指定 --result（pass/fail/blocked/skip）")
    if args.result == "pass" and not args.evidence:
        raise SkillFailure("执行结果 pass 必须提供 --evidence（截图/日志/提交号）")

    client = make_client(args, ALLOWED)
    require_run_version(args.version)
    ver = client.table("ver")
    ver.require(["版本号", "发布状态", NODE, "测试用例"])
    require_version(ver, args.version, report)
    ensure_prior_nodes(ver, args.version, NODE, report)

    version_runs = ver.relation(args.version, "测试用例")
    report.check("版本已纳入用例", bool(version_runs), f"{len(version_runs)} 条执行记录")
    if not version_runs:
        raise SkillFailure(f"版本 {args.version} 未纳入任何用例，测试节点无对象")

    run_table = client.table("run")
    run_table.require(["执行编号", "用例号", "用例", "执行状态", "执行结果", "证据", "执行时间", "执行人", "备注"])
    case_table = client.table("case")
    case_table.require(["用例号"])

    if args.case:
        targets = []
        for raw in dict.fromkeys(args.case):
            run_id = _run_id(args.version, raw)
            if run_id not in version_runs:
                raise SkillFailure(f"执行记录 {run_id} 不在版本 {args.version} 的执行清单中")
            if not run_table.row_exists(run_id):
                raise SkillFailure(f"版本清单引用的执行记录 {run_id} 在表中不存在")
            targets.append(run_id)
    else:
        targets = [
            run_id for run_id in version_runs if run_table.value(run_id, "执行状态") != "done"
        ]
        if not targets:
            report.check("待执行记录", True, "本版用例已全部执行，只推进节点")

    executor = args.executor or args.agent
    executed_at = args.at or now_iso()
    executed = 0
    for run_id in targets:
        if not run_table.row_exists(run_id):
            raise SkillFailure(f"执行记录 {run_id} 不存在")
        case_id = run_table.value(run_id, "用例号")
        link = run_table.relation(run_id, "用例")
        if not case_id or link != [case_id]:
            raise SkillFailure(
                f"执行记录 {run_id} 的用例号/用例关系不一致（用例号={case_id}，用例={link}）"
            )
        if not case_table.row_exists(case_id):
            raise SkillFailure(f"执行记录 {run_id} 指向的用例 {case_id} 不存在")

        # 客户端先按 020 校验状态/结果一致性：done 必须有结果。
        if not args.result:
            raise SkillFailure("state=done 时执行结果不能为空")
        values = {
            run_table.fid("执行状态"): "done",
            run_table.fid("执行结果"): args.result,
            run_table.fid("执行时间"): executed_at,
            run_table.fid("执行人"): executor,
        }
        expected = {
            "执行状态": "done",
            "执行结果": args.result,
            "执行时间": executed_at,
            "执行人": executor,
        }
        if args.evidence:
            values[run_table.fid("证据")] = args.evidence
            expected["证据"] = args.evidence
        if args.note:
            values[run_table.fid("备注")] = args.note
            expected["备注"] = args.note

        executed += 1
        if args.dry_run:
            report.write(
                f"run/{run_id}", "执行状态/执行结果", f"done/{args.result}",
                "skipped", error="dry-run：未写",
            )
            continue
        detail = client.write_verified("update", "run", run_id, values, expected)
        report.write(
            f"run/{run_id}", "执行状态/执行结果", f"done/{args.result}", detail["state"],
            detail.get("http"), detail.get("error"),
        )
        report.readback(f"run/{run_id}", detail.get("readback") or {})
        if detail["state"] != "success":
            raise SkillFailure(
                f"写执行记录 {run_id} 失败：{detail.get('error') or '回读不一致'}",
                state=detail["state"],
            )

    fresh_run = client.table("run", refresh=not args.dry_run)
    states = {run_id: fresh_run.value(run_id, "执行状态") for run_id in version_runs}
    pending = [run_id for run_id, state in states.items() if state != "done"]
    report.readback(f"run#state/{args.version}", states)
    report.count(executed=executed, pending=len(pending), runs=len(version_runs))
    if args.dry_run:
        report.check(
            "全部用例已执行",
            True,
            f"dry-run：当前待执行 {len(pending)} 条，本次预计执行 {executed} 条（未写）",
        )
    else:
        report.check(
            "全部用例已执行",
            not pending,
            f"{len(version_runs)} 条全部 done" if not pending else f"仍待执行 {pending}",
        )

    if pending:
        report.note("stage_advanced", False)
        report.note("blocker", f"仍有 {len(pending)} 条执行记录未执行，测试节点未推进")
    else:
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


if __name__ == "__main__":
    raise SystemExit(entry("tf-test-implement", build_parser(), main))
