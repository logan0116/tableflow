#!/usr/bin/env python3
"""tf-dev-implement：推进版本第 3 节点「开发」（软件开发角色）。

校验版本内规格的任务清单已全部勾选、spec 有验收场景，然后把
``indep.speckit-implement状态=done`` 与 ``ver.开发=done`` 落库并回读。

表作用域：读/写 ``ver``/``indep``。不跑构建、不改代码；代码与单测由 speckit-implement
流程完成，本技能只做「完成判据 + 节点推进」。
"""

from __future__ import annotations

from _tf_common import (
    SkillFailure,
    advance_node,
    base_parser,
    ensure_prior_nodes,
    entry,
    make_client,
    parse_spec,
    parse_tasks,
    readback_nodes,
    require_version,
    resolve_repo_root,
    scenario_count,
    spec_file,
    tasks_file,
)

ALLOWED = ("ver", "indep")
NODE = "开发"
IMPLEMENT_FIELD = "speckit-implement状态"


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    parser = base_parser(
        "推进版本第 3 节点「开发」：校验任务清单与实现状态，写 indep.speckit-implement状态 与 ver.开发=done"
    )
    parser.add_argument(
        "--spec",
        action="append",
        default=[],
        metavar="SPEC_ID",
        help="只处理这些规格（如 017-AR）；默认版本内全部规格。可重复。",
    )
    return parser


def main(args, report) -> None:
    report.note("role", "软件开发")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)
    repo_root = resolve_repo_root(args.repo_root)

    ver = client.table("ver")
    ver.require(["版本号", "发布状态", NODE, "独立需求管理"])
    require_version(ver, args.version, report)
    ensure_prior_nodes(ver, args.version, NODE, report)

    version_specs = ver.relation(args.version, "独立需求管理")
    wanted = list(dict.fromkeys(args.spec)) or list(version_specs)
    report.check("版本已关联规格", bool(wanted), f"{len(wanted)} 份：{'、'.join(wanted) or '无'}")
    if not wanted:
        raise SkillFailure("版本未关联任何独立规格需求，没有可推进的开发工作")
    for spec_id in wanted:
        attached = spec_id in version_specs
        report.check(f"规格 {spec_id} 已挂到版本", attached, "在 ver.独立需求管理 中")
        if not attached:
            raise SkillFailure(f"规格 {spec_id} 未挂到版本 {args.version}，不能推进其开发状态")

    indep = client.table("indep")
    indep.require(["编号", "条款", "规格目录", IMPLEMENT_FIELD, "验收状态"])

    blocked: list[str] = []
    for spec_id in wanted:
        if not indep.row_exists(spec_id):
            raise SkillFailure(f"规格「{spec_id}」在独立规格需求表中不存在")
        spec_path = spec_file(repo_root, indep, spec_id)
        stories = parse_spec(spec_path)
        count = scenario_count(stories)
        report.check(
            f"规格 {spec_id} 有验收场景",
            count > 0,
            f"{len(stories)} 个 User Story / {count} 条 Acceptance Scenario",
        )
        if count == 0:
            raise SkillFailure(f"规格 {spec_id} 没有 Acceptance Scenario：{spec_path}")

        task_path = tasks_file(repo_root, indep, spec_id)
        if task_path is None:
            blocked.append(f"{spec_id} 缺少 tasks.md")
            report.check(f"规格 {spec_id} 任务清单", False, "tasks.md 不存在")
            continue
        tasks = parse_tasks(task_path)
        report.check(
            f"规格 {spec_id} 任务全部完成",
            not tasks["unchecked"] and tasks["checked"] > 0,
            f"已勾选 {tasks['checked']} 条，未勾选 {len(tasks['unchecked'])} 条",
        )
        if tasks["unchecked"]:
            blocked.append(f"{spec_id} 有 {len(tasks['unchecked'])} 条未完成任务")
        if tasks["checked"] == 0:
            blocked.append(f"{spec_id} 的 tasks.md 没有已完成任务")

    if blocked:
        raise SkillFailure("开发节点未满足：" + "；".join(blocked))

    # 先写 indep（每个规格的 implement 状态），再推进版本节点。
    for spec_id in wanted:
        expected = {IMPLEMENT_FIELD: "done"}
        if indep.value(spec_id, IMPLEMENT_FIELD) == "done":
            report.check(f"规格 {spec_id} implement 状态", True, "已是 done，跳过写入")
            continue
        if args.dry_run:
            report.write(f"indep/{spec_id}", IMPLEMENT_FIELD, "done", "skipped", error="dry-run：未写")
            continue
        detail = client.write_verified(
            "update", "indep", spec_id, {indep.fid(IMPLEMENT_FIELD): "done"}, expected
        )
        report.write(
            f"indep/{spec_id}", IMPLEMENT_FIELD, "done", detail["state"],
            detail.get("http"), detail.get("error"),
        )
        report.readback(f"indep/{spec_id}", detail.get("readback") or {})
        if detail["state"] != "success":
            raise SkillFailure(
                f"写规格 {spec_id} 的 implement 状态失败：{detail.get('error') or '回读不一致'}",
                state=detail["state"],
            )

    fresh_indep = client.table("indep", refresh=True)
    implement_states = {spec_id: fresh_indep.value(spec_id, IMPLEMENT_FIELD) for spec_id in wanted}
    pending = [spec_id for spec_id, state in implement_states.items() if state != "done"]
    if args.dry_run:
        report.check(
            "读回 implement 状态",
            True,
            f"dry-run：当前未 done {len(pending)} 份，本次预计写入 {len(pending)} 份（未写）",
        )
    else:
        report.check(
            "读回 implement 状态",
            not pending,
            f"{len(wanted)} 份全部 done" if not pending else f"未 done：{pending}",
        )
    report.readback(f"indep#implement/{args.version}", implement_states)
    if pending and not args.dry_run:
        raise SkillFailure(f"读回后仍有规格 implement 不为 done：{pending}")

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
    raise SystemExit(entry("tf-dev-implement", build_parser(), main))
