#!/usr/bin/env python3
"""tf-dev-plan：推进版本第 1 节点「版本需求设计」（系统工程角色）。

只读校验版本范围与需求挂载，然后写 ``ver.版本需求设计=done`` 并回读。
只接触 ``ver``/``indep``/``dep`` 三张表；写只发生在 ``ver``。
"""

from __future__ import annotations

from _tf_common import (
    base_parser,
    entry,
    ensure_prior_nodes,
    make_client,
    parse_spec,
    readback_nodes,
    require_version,
    resolve_repo_root,
    scenario_count,
    spec_file,
    advance_node,
    SkillFailure,
)

ALLOWED = ("ver", "indep", "dep")
NODE = "版本需求设计"


def build_parser():
    # 统一参数 --dry-run/--apply/--no-stage 由 _tf_common.base_parser 提供。
    return base_parser(
        "推进版本第 1 节点「版本需求设计」：校验版本范围与需求挂载，写 ver.版本需求设计=done"
    )


def main(args, report) -> None:
    report.note("role", "系统工程")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)
    repo_root = resolve_repo_root(args.repo_root)

    ver = client.table("ver")
    ver.require(["版本号", "发布状态", NODE, "独立需求管理", "依赖需求管理"])
    require_version(ver, args.version, report)
    ensure_prior_nodes(ver, args.version, NODE, report)

    specs = ver.relation(args.version, "独立需求管理")
    changes = ver.relation(args.version, "依赖需求管理")
    report.count(specs=len(specs), changes=len(changes))
    report.check(
        "版本范围已确定",
        bool(specs or changes),
        f"规格 {len(specs)} 条 / 变更单 {len(changes)} 条",
    )
    if not (specs or changes):
        raise SkillFailure("本版未挂任何需求或变更单，版本范围未确定，不能推进「版本需求设计」")

    indep = client.table("indep")
    dep = client.table("dep")
    indep.require(["编号", "条款", "规格目录", "场景数", "验收状态"])
    dep.require(["编号", "条款", "关联的独立规格需求", "回归状态"])

    for spec_id in specs:
        if not indep.row_exists(spec_id):
            raise SkillFailure(f"版本关联的规格「{spec_id}」在独立规格需求表中不存在")
        path = spec_file(repo_root, indep, spec_id)
        stories = parse_spec(path)
        count = scenario_count(stories)
        report.check(
            f"规格 {spec_id} 有验收场景",
            count > 0,
            f"{len(stories)} 个 User Story / {count} 条 Acceptance Scenario",
        )
        if count == 0:
            raise SkillFailure(f"规格 {spec_id} 没有 Acceptance Scenario：{path}")
        recorded = indep.value(spec_id, "场景数")
        if isinstance(recorded, (int, float)) and int(recorded) != count:
            report.note(
                "scene_drift",
                {**(report.data.get("scene_drift") or {}), spec_id: {"recorded": recorded, "actual": count}},
            )

    for change_id in changes:
        if not dep.row_exists(change_id):
            raise SkillFailure(f"版本关联的变更单「{change_id}」在依赖需求表中不存在")
        clause = dep.value(change_id, "条款")
        report.check(f"变更单 {change_id} 有条款", bool(clause), "条款非空" if clause else "条款为空")
        if not clause:
            raise SkillFailure(f"变更单「{change_id}」的条款为空，无法确认影响面")
        targets = dep.relation(change_id, "关联的独立规格需求")
        missing = [target for target in targets if not indep.row_exists(target)]
        report.check(
            f"变更单 {change_id} 关联规格存在",
            bool(targets) and not missing,
            f"关联 {targets}" if targets and not missing else f"缺失 {missing or '全部'}",
        )
        if not targets or missing:
            raise SkillFailure(
                f"变更单「{change_id}」关联的独立规格需求为空或不存在：{missing or '空数组'}"
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
    readback_nodes(client.table("ver", refresh=True), args.version, report)
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-dev-plan", build_parser(), main))
