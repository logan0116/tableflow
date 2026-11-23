#!/usr/bin/env python3
"""tf-dev-check：推进版本第 4 节点「开发验收」（软件开发角色）。

判据是客观的、不含人的判断：**本版每份规格的实现完成且单测通过**。本技能据此
把 ``indep.验收状态`` 写成 ``accepted``，再推进 ``ver.开发验收``。

两层分工（不叠加、不互相复核）：

- 开发节点（``tf-dev-implement``）：跑单测、校验 ``plan.md``/``tasks.md`` 回链，
  成立才写 ``speckit-implement状态=done``——它是「实现+单测成立」的唯一证据点；
- 开发验收节点（本技能）：认这个结论，把它翻译成「验收通过」，并推进节点。

所以本技能**不重跑单测**：单测是开发节点的证据，重跑等于给同一件事加第二套判据。

表作用域：读/写 ``ver``/``indep``。
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

ALLOWED = ("ver", "indep")
NODE = "开发验收"
IMPLEMENT_FIELD = "speckit-implement状态"
ACCEPT_FIELD = "验收状态"


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    return base_parser(
        "推进版本第 4 节点「开发验收」：按「实现完成+单测通过」写 indep.验收状态=accepted，"
        "再写 ver.开发验收=done"
    )


def main(args, report) -> None:
    report.note("role", "软件开发")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)

    ver = client.table("ver")
    ver.require(["版本号", "发布状态", NODE, "独立需求管理"])
    require_version(ver, args.version, report)
    ensure_prior_nodes(ver, args.version, NODE, report)

    indep = client.table("indep")
    indep.require(["编号", IMPLEMENT_FIELD, ACCEPT_FIELD])
    specs = ver.relation(args.version, "独立需求管理")
    report.check("版本已关联规格", True, f"{len(specs)} 份：{'、'.join(specs) or '无（空集语义）'}")

    blockers: list[str] = []
    statuses: dict[str, dict] = {}
    to_accept: list[str] = []
    for spec_id in specs:
        if not indep.row_exists(spec_id):
            blockers.append(f"{spec_id} 不在独立规格需求表中")
            statuses[spec_id] = {"存在": False}
            continue
        implement = indep.value(spec_id, IMPLEMENT_FIELD)
        acceptance = indep.value(spec_id, ACCEPT_FIELD)
        statuses[spec_id] = {IMPLEMENT_FIELD: implement, ACCEPT_FIELD: acceptance}
        report.check(
            f"规格 {spec_id} 实现完成且单测通过",
            implement == "done",
            f"{IMPLEMENT_FIELD}={implement}",
        )
        if implement != "done":
            blockers.append(f"{spec_id} 实现未完成（{IMPLEMENT_FIELD}={implement}）")
            continue
        if acceptance != "accepted":
            to_accept.append(spec_id)

    report.readback(f"indep#status/{args.version}", statuses)
    if blockers:
        raise SkillFailure("开发验收未满足：" + "；".join(blockers))

    report.note("accept_criteria", "实现完成 + 单测通过（由开发节点采集），无需人工判断")

    # 按客观判据写验收状态；已是 accepted 的跳过
    for spec_id in to_accept:
        if args.dry_run:
            report.write(f"indep/{spec_id}", ACCEPT_FIELD, "accepted", "skipped", error="dry-run：未写")
            continue
        detail = client.write_verified(
            "update", "indep", spec_id,
            {indep.fid(ACCEPT_FIELD): "accepted"}, {ACCEPT_FIELD: "accepted"},
        )
        report.write(f"indep/{spec_id}", ACCEPT_FIELD, "accepted",
                     detail["state"], detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(
                f"写规格 {spec_id} 的验收状态失败：{detail.get('error') or '回读不一致'}",
                state=detail["state"],
            )

    fresh = client.table("indep", refresh=True)
    pending = [s for s in specs if fresh.value(s, ACCEPT_FIELD) != "accepted"]
    report.check(
        "全部规格已验收",
        args.dry_run or not pending,
        f"dry-run：{len(to_accept)} 份待写（未写）"
        if args.dry_run
        else (f"{len(specs)} 份全部 accepted" if not pending else f"未验收：{pending}"),
    )
    if pending and not args.dry_run:
        raise SkillFailure(f"读回后仍有规格未验收：{pending}")

    advance_node(
        client,
        ver,
        args.version,
        NODE,
        report,
        dry_run=args.dry_run,
        no_stage=args.no_stage,
    )
    snapshot = readback_nodes(client.table("ver", refresh=True), args.version, report)
    report.note("stage_done", stage_done(snapshot))
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-dev-check", build_parser(), main))
