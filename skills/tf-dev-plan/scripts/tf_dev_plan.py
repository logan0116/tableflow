#!/usr/bin/env python3
"""tf-dev-plan：推进版本第 1 节点「版本需求设计」（系统工程角色）。

只读校验版本范围与需求挂载，然后写 ``ver.版本需求设计=done`` 并回读。
只接触 ``ver``/``indep``/``dep`` 三张表；写只发生在 ``ver``。
"""

from __future__ import annotations

import re
from pathlib import Path

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

# 需求 042-AR：spec 侧五个阶段字段由本节点驱动
STAGE_FIELDS = {
    "constitution": "speckit-constitution状态",
    "specify": "speckit-specify状态",
    "clarify": "speckit-clarify状态",
    "analyze": "speckit-analyze状态",
    "checklist": "speckit-checklist状态",
}

# 需求 039-AR：规格结构下限
STRUCT_FLOOR = {"us": 2, "scen": 5, "fr": 6, "edge": 3}

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*?)\s*$")
FR_RE = re.compile(r"^\s*[-*]\s+\*\*FR-\d+", re.I)
BULLET_RE = re.compile(r"^\s*[-*]\s+\S")


def structure_numbers(path: Path) -> dict:
    """统计规格的结构条数：功能需求与边界情况。"""
    fr = edge = 0
    section_level = None   # 当前计数的章节级别：None=不在计数章节
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            if section_level is not None and level <= section_level:
                section_level, section = None, None
            low = title.lower()
            if low.startswith("functional requirements"):
                section, section_level = "fr", level
            elif low.startswith("edge cases"):
                section, section_level = "edge", level
            continue
        if section == "fr" and FR_RE.match(line):
            fr += 1
        elif section == "edge" and BULLET_RE.match(line):
            edge += 1
    return {"fr": fr, "edge": edge}


def clarify_state(path: Path) -> str:
    """有 Clarifications 章节且无未决标记 -> done；无该章节 -> na；否则 doing。"""
    text = path.read_text(encoding="utf-8")
    if "## Clarifications" not in text:
        return "na"
    body = text.split("## Clarifications", 1)[1]
    for stop in ("\n## ", "\n# "):
        if stop in body:
            body = body.split(stop, 1)[0]
    for marker in ("待定", "待澄清", "TODO", "未决", "TBD"):
        if marker in body:
            return "doing"
    return "done"


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
    indep.require(["编号", "条款", "规格目录", "场景数", "验收状态", "宪法版本",
                   *STAGE_FIELDS.values()])
    dep.require(["编号", "条款", "关联的独立规格需求", "回归状态"])

    constant_version = indep.value(specs[0], "宪法版本") if specs else None
    stage_plan: dict[str, dict[str, str]] = {}

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

        # 需求 039-AR：结构下限校验，specify 阶段据此判定
        numbers = structure_numbers(path)
        actual = {"us": len(stories), "scen": count, **numbers}
        short = {k: f"{actual[k]}/{STRUCT_FLOOR[k]}" for k in STRUCT_FLOOR if actual[k] < STRUCT_FLOOR[k]}
        report.check(
            f"规格 {spec_id} 结构达标",
            not short,
            "US/scen/FR/edge = {us}/{scen}/{fr}/{edge}".format(**actual)
            if not short
            else "低于下限：" + "、".join(f"{k} {v}" for k, v in short.items()),
        )
        if short:
            raise SkillFailure(
                f"规格 {spec_id} 结构未达下限（需求 039）：" + "、".join(f"{k} {v}" for k, v in short.items())
            )

        stage_plan[spec_id] = {
            STAGE_FIELDS["specify"]: "done",
            STAGE_FIELDS["constitution"]: "done" if (constant_version or (repo_root / ".specify" / "memory" / "constitution.md").exists()) else "na",
            STAGE_FIELDS["clarify"]: clarify_state(path),
            STAGE_FIELDS["analyze"]: "na",
            STAGE_FIELDS["checklist"]: "na",
        }

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

    # 需求 042-AR / 038-AR：spec 侧阶段状态必须有写入者，逐字段落库
    if stage_plan:
        report.note(
            "stage_na_reasons",
            {
                STAGE_FIELDS["analyze"]: "本项目未启用 speckit-analyze 跨文档一致性分析",
                STAGE_FIELDS["checklist"]: "本项目未启用 speckit-checklist 检查清单",
            },
        )
    for spec_id, updates in stage_plan.items():
        for field, value in updates.items():
            if indep.value(spec_id, field) == value:
                report.check(f"{spec_id} {field}", True, f"已是 {value}，跳过写入")
                continue
            if args.dry_run:
                report.write(f"indep/{spec_id}", field, value, "skipped", error="dry-run：未写")
                continue
            detail = client.write_verified(
                "update", "indep", spec_id, {indep.fid(field): value}, {field: value}
            )
            report.write(f"indep/{spec_id}", field, value, detail["state"], detail.get("http"), detail.get("error"))
            if detail["state"] != "success":
                raise SkillFailure(
                    f"写规格 {spec_id} 的 {field} 失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
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
