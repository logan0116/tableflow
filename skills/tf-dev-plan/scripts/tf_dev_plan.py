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

ALLOWED = ("ver", "indep", "dep", "bug")
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
EVIDENCE_FIELD = "阶段证据"
EVIDENCE_LINE_RE = re.compile(r"^\s*([a-z_]+)\s*=\s*(.+?)\s*$", re.I)


def merge_evidence(existing: object, updates: dict[str, str]) -> str:
    """把新证据并入既有「阶段证据」文本；同键覆盖，输出按键排序。"""
    lines: dict[str, str] = {}
    if isinstance(existing, str):
        for line in existing.splitlines():
            match = EVIDENCE_LINE_RE.match(line)
            if match:
                lines[match.group(1).lower()] = line.strip()
    for key, value in updates.items():
        lines[key] = f"{key}={value}"
    return "\n".join(lines[key] for key in sorted(lines))
FR_RE = re.compile(r"^\s*[-*]\s+\*\*FR-\d+", re.I)
BULLET_RE = re.compile(r"^\s*[-*]\s+\S")
FR_SECTION_TITLES = ("functional requirements", "功能需求", "需求")
EDGE_SECTION_TITLES = ("edge cases", "边界情况", "边界")


def structure_numbers(path: Path) -> dict:
    """统计规格的结构条数：功能需求与边界情况。

    章节名兼容中英文（本仓 001–013 用中文标题）；段名认不出或段内计 0 时，
    功能需求按 ``FR-\\d+`` 条目直接计数，避免"有内容但判定 0"。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    fr = edge = 0
    section_level = None   # 当前计数的章节级别：None=不在计数章节
    section = None
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            if section_level is not None and level <= section_level:
                section_level, section = None, None
            low = title.lower()
            if any(low.startswith(item) for item in FR_SECTION_TITLES):
                section, section_level = "fr", level
            elif any(low.startswith(item) for item in EDGE_SECTION_TITLES):
                section, section_level = "edge", level
            continue
        if section == "fr" and FR_RE.match(line):
            fr += 1
        elif section == "edge" and BULLET_RE.match(line):
            edge += 1
    if fr == 0:
        fr = sum(1 for line in lines if FR_RE.match(line))
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
    bugs = ver.relation(args.version, "Bug管理")
    runs = ver.relation(args.version, "测试用例")
    report.count(specs=len(specs), changes=len(changes), bugs=len(bugs), runs=len(runs))
    report.check(
        "版本范围已确定",
        bool(specs or changes or bugs or runs),
        f"规格 {len(specs)} 条 / 变更单 {len(changes)} 条 / 缺陷 {len(bugs)} 条 / 用例 {len(runs)} 条",
    )
    if not (specs or changes or bugs or runs):
        raise SkillFailure(
            "本版未挂任何需求、变更单、缺陷或用例，版本范围未确定，不能推进「版本需求设计」"
        )

    # 035/034：修复版与回归版没有新规格，范围由缺陷或已收录用例界定。
    if not (specs or changes):
        if bugs:
            bug_table = client.table("bug")
            bug_table.require(["编号", "状态", "证据"])
            no_evidence = [
                bug_id for bug_id in bugs
                if not str(bug_table.value(bug_id, "证据", default="") or "").strip()
            ]
            report.check(
                "本版缺陷有复现证据",
                not no_evidence,
                f"{len(bugs)} 条均有证据"
                if not no_evidence
                else f"缺证据：{'、'.join(no_evidence)}",
            )
            if no_evidence:
                raise SkillFailure(
                    "缺陷没有复现证据，范围无法确认："
                    + "、".join(no_evidence)
                    + "；先补证据（复现测试或现象记录）"
                )
        report.check(
            "修复/回归版范围",
            True,
            f"缺陷 {len(bugs)} 条 / 用例 {len(runs)} 条，无新规格交付",
        )
        advance_node(
            client, ver, args.version, NODE, report,
            dry_run=args.dry_run, no_stage=args.no_stage,
        )
        readback_nodes(client.table("ver", refresh=True), args.version, report)
        report.finish("success")
        return

    indep = client.table("indep")
    dep = client.table("dep")
    indep.require(["编号", "条款", "规格目录", "场景数", "验收状态", "宪法版本",
                   *STAGE_FIELDS.values()])
    dep.require(["编号", "条款", "关联的独立规格需求", "回归状态"])

    constant_version = indep.value(specs[0], "宪法版本") if specs else None
    stage_plan: dict[str, dict[str, str]] = {}
    stage_evidence: dict[str, dict[str, str]] = {}

    for spec_id in specs:
        if not indep.row_exists(spec_id):
            raise SkillFailure(f"版本关联的规格「{spec_id}」在独立规格需求表中不存在")
        path = spec_file(repo_root, indep, spec_id)
        # 证据行要写的相对路径取自实际读到的文件，不另起一套推导（038）。
        spec_rel = path.parent.relative_to(repo_root).as_posix()
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

        # 038：置 done 的阶段必须留下可定位证据
        stage_evidence[spec_id] = {
            "specify": f"{spec_rel}/spec.md（US{len(stories)}/场景{count}/FR{numbers['fr']}/边界{numbers['edge']}）",
        }
        constitution_state = stage_plan[spec_id][STAGE_FIELDS["constitution"]]
        if constitution_state == "done":
            stage_evidence[spec_id]["constitution"] = (
                f"reused:.specify/memory/constitution.md@{constant_version or '未记录版本'}"
            )
        if stage_plan[spec_id][STAGE_FIELDS["clarify"]] == "done":
            stage_evidence[spec_id]["clarify"] = f"{spec_rel}/spec.md#Clarifications（无未决项）"

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
    evidence_fid = indep.fid(EVIDENCE_FIELD, required=False)
    if evidence_fid:
        for spec_id, entries in stage_evidence.items():
            if not entries:
                continue
            merged = merge_evidence(indep.value(spec_id, EVIDENCE_FIELD, default=None), entries)
            if indep.value(spec_id, EVIDENCE_FIELD, default=None) == merged:
                continue
            if args.dry_run:
                report.write(f"indep/{spec_id}", EVIDENCE_FIELD, f"{len(entries)} 条", "skipped", error="dry-run：未写")
                continue
            detail = client.write_verified(
                "update", "indep", spec_id, {evidence_fid: merged}, {EVIDENCE_FIELD: merged}
            )
            report.write(f"indep/{spec_id}", EVIDENCE_FIELD, f"{len(entries)} 条",
                         detail["state"], detail.get("http"), detail.get("error"))
            if detail["state"] != "success":
                raise SkillFailure(
                    f"写规格 {spec_id} 的阶段证据失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
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
