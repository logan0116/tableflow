#!/usr/bin/env python3
"""tf-dev-check：推进版本第 4 节点「开发验收」（软件开发角色）。

开发验收的明细口径是 ``indep.验收状态``：本版全部规格 ``accepted`` 才允许把
``ver.开发验收`` 置 done。技能不代替需求方给 accepted，只读并列出未验收项。

表作用域：读 ``ver``/``indep``；写 ``ver``。
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


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    return base_parser(
        "推进版本第 4 节点「开发验收」：校验本版规格全部 accepted，写 ver.开发验收=done"
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
    indep.require(["编号", "验收状态", "speckit-implement状态"])
    specs = ver.relation(args.version, "独立需求管理")
    report.check("版本已关联规格", True, f"{len(specs)} 份：{'、'.join(specs) or '无（空集语义）'}")

    blockers: list[str] = []
    statuses: dict[str, dict] = {}
    for spec_id in specs:
        if not indep.row_exists(spec_id):
            blockers.append(f"{spec_id} 不在独立规格需求表中")
            statuses[spec_id] = {"存在": False}
            continue
        acceptance = indep.value(spec_id, "验收状态")
        implement = indep.value(spec_id, "speckit-implement状态")
        statuses[spec_id] = {"验收状态": acceptance, "speckit-implement状态": implement}
        report.check(
            f"规格 {spec_id} 已验收",
            acceptance == "accepted",
            f"验收状态={acceptance}",
        )
        report.check(
            f"规格 {spec_id} 实现完成",
            implement == "done",
            f"speckit-implement状态={implement}",
        )
        if acceptance != "accepted":
            blockers.append(f"{spec_id} 验收状态={acceptance}")
        if implement != "done":
            blockers.append(f"{spec_id} 实现状态={implement}")

    report.readback(f"indep#acceptance/{args.version}", statuses)
    if blockers:
        raise SkillFailure("开发验收未满足：" + "；".join(blockers))

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
