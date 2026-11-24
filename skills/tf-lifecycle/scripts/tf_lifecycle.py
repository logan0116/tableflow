#!/usr/bin/env python3
"""tf-lifecycle：拆分、放弃、历史清理（独立需求生命周期动作）

对应需求 034（拆分/放弃）与 033（历史去重）。前置条件由引擎强制，
本技能只按顺序执行动作并把过程说清楚。

| 动作 | 做什么 | 前置 |
|---|---|---|
| `drop` | 先把该需求从所有版本摘除，再置 dropped 并写理由与时间 | 摘除后引擎才允许（L3） |
| `split` | 新建承接需求行，并在原需求写拆分记录 | 原需求未 accepted（L6） |
| `cleanup` | 同一需求跨版本重复时只保留首次出现，其余摘除 | 036 已生效（执行记录表有放行标记字段） |

用法：

    python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --action drop --spec 043-AR --reason "能力取消"
    python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --action split --spec 043-AR --to 044-AR --clauses "US3、US4"
    python3 skills/tf-lifecycle/scripts/tf_lifecycle.py --action cleanup --dry-run

默认 dry-run，加 `--apply` 才写。
"""

from __future__ import annotations

import datetime
import re

from _tf_common import (
    SkillFailure,
    base_parser,
    entry,
    make_client,
    readback_nodes,
)

ALLOWED = ("ver", "indep", "run")
ACTIONS = ("drop", "split", "cleanup")
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def build_parser():
    parser = base_parser("执行独立需求的生命周期动作：拆分 / 放弃 / 历史清理")
    parser.add_argument("--action", required=True, choices=ACTIONS)
    parser.add_argument("--spec", help="drop / split 的目标独立需求编号")
    parser.add_argument("--reason", help="drop 的放弃理由")
    parser.add_argument("--to", help="split 的承接方编号（新建的独立需求）")
    parser.add_argument("--clauses", help="split 移交的条款或场景号，逗号/顿号分隔")
    return parser


def semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(str(value or ""))
    return tuple(int(x) for x in match.groups()) if match else (999, 999, 999)


def plan_cleanup(occurrences: dict[str, list[str]]) -> dict[str, tuple[str, list[str]]]:
    """跨版本重复的清理计划：同一需求只保留首次出现（语义序最小）的版本。

    返回 ``{需求编号: (保留的版本, 要摘除的版本列表)}``；没有重复的需求不出现。
    """
    plan: dict[str, tuple[str, list[str]]] = {}
    for spec_id, version_ids in occurrences.items():
        if len(version_ids) <= 1:
            continue
        ordered = sorted(version_ids, key=semver)
        plan[spec_id] = (ordered[0], ordered[1:])
    return plan


def build_split_log(existing: str, at: str, clauses: str, target: str) -> str:
    """一行一条拆分记录：``<时间> 移交 <条款清单> -> <承接方>``。"""
    line = f"{at} 移交 {clauses} -> {target}"
    return (existing.rstrip("\n") + "\n" + line).strip() if existing else line


def holders(ver, spec_id: str) -> list[str]:
    """该独立需求当前被哪些版本持有。"""
    out = []
    for version_id in list(ver.rows.keys()):
        if spec_id in (ver.relation(version_id, "独立需求管理") or []):
            out.append(version_id)
    return sorted(out, key=semver)


def supports_cleanup(client) -> bool:
    """036 是否已生效：执行记录表里有「放行标记」字段。"""
    try:
        run_table = client.table("run")
    except SkillFailure:
        return False
    return run_table.fid("放行标记", required=False) is not None


def will_write(args) -> bool:
    """写模式只算一次：``--dry-run`` 优先于 ``--apply``（任务契约，见 Report 初始化）。"""
    return bool(getattr(args, "apply", False)) and not bool(getattr(args, "dry_run", False))


def do_drop(args, report, client, ver, indep) -> None:
    spec_id = args.spec
    if not spec_id or not indep.row_exists(spec_id):
        raise SkillFailure("drop 需要一个存在的 --spec")
    if not args.reason:
        raise SkillFailure("drop 必须给 --reason：放弃要留下理由（L2）")
    state = indep.value(spec_id, "验收状态")
    report.check("当前验收状态", True, f"{spec_id}={state}")

    holding = holders(ver, spec_id)
    report.note("holders", holding)
    for version_id in holding:
        current = ver.relation(version_id, "独立需求管理") or []
        remaining = [item for item in current if item != spec_id]
        report.check(f"从 {version_id} 摘除", True, f"{current} -> {remaining}")
        if not will_write(args):
            report.write(f"ver/{version_id}", "独立需求管理", remaining, "skipped", error="dry-run：未写")
            continue
        detail = client.write_verified(
            "update", "ver", version_id,
            {ver.fid("独立需求管理"): remaining},
            {"独立需求管理": remaining},
        )
        report.write(f"ver/{version_id}", "独立需求管理", remaining, detail["state"], detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(f"摘除 {version_id} 失败：{detail.get('error')}", state=detail["state"])

    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    values = {indep.fid("验收状态"): "dropped"}
    if indep.fid("放弃理由", required=False):
        values[indep.fid("放弃理由")] = args.reason
    if indep.fid("放弃时间", required=False):
        values[indep.fid("放弃时间")] = now
    report.note("plan", f"{spec_id} -> dropped，理由与时间写入")
    if not will_write(args):
        report.write(f"indep/{spec_id}", "验收状态", "dropped", "skipped", error="dry-run：未写")
        report.finish("success")
        return
    detail = client.write_verified(
        "update", "indep", spec_id, values,
        {"验收状态": "dropped"},
    )
    report.write(f"indep/{spec_id}", "验收状态", "dropped", detail["state"], detail.get("http"), detail.get("error"))
    if detail["state"] != "success":
        raise SkillFailure(f"置 dropped 失败：{detail.get('error')}", state=detail["state"])
    report.finish("success")


def do_split(args, report, client, ver, indep) -> None:
    spec_id, target = args.spec, args.to
    if not spec_id or not indep.row_exists(spec_id):
        raise SkillFailure("split 需要一个存在的 --spec")
    if not target:
        raise SkillFailure("split 必须给 --to（承接方编号）")
    if indep.row_exists(target):
        raise SkillFailure(f"承接方 {target} 已存在，拆分不会复用既有行")
    state = indep.value(spec_id, "验收状态")
    report.check("原需求未验收", state != "accepted", f"{spec_id}={state}")
    if state == "accepted":
        raise SkillFailure(
            f"{spec_id} 已验收通过，范围变化请开依赖需求，不要拆分（L6）"
        )
    clauses = (args.clauses or "").strip()
    if not clauses:
        raise SkillFailure("split 必须给 --clauses：移交哪些条款或场景要写清楚")

    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    existing = indep.value(spec_id, "拆分记录", default="") or ""
    merged_log = build_split_log(existing, now, clauses, target)
    log_line = merged_log.splitlines()[-1]

    report.note("plan", f"新建承接方 {target}，并在 {spec_id} 记录：{log_line}")
    if not args.apply:
        report.write(f"indep/{target}", "<create>", "承接需求", "skipped", error="dry-run：未写")
        report.write(f"indep/{spec_id}", "拆分记录", log_line, "skipped", error="dry-run：未写")
        report.finish("success")
        return

    create_values = {
        indep.fid("编号"): target,
        indep.fid("条款"): f"承接 {spec_id} 拆分移交：{clauses}",
    }
    if indep.fid("验收状态", required=False):
        create_values[indep.fid("验收状态")] = "pending"
    created = client.write_verified("create", "indep", target, create_values, {"编号": target})
    report.write(f"indep/{target}", "<create>", "承接需求", created["state"], created.get("http"), created.get("error"))
    if created["state"] != "success":
        raise SkillFailure(f"新建承接方失败：{created.get('error')}", state=created["state"])

    if indep.fid("拆分记录", required=False):
        detail = client.write_verified(
            "update", "indep", spec_id,
            {indep.fid("拆分记录"): merged_log}, {"拆分记录": merged_log},
        )
        report.write(f"indep/{spec_id}", "拆分记录", log_line, detail["state"], detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(f"写拆分记录失败：{detail.get('error')}", state=detail["state"])
    report.note("reminder", "记得从 specs/<dir>/spec.md 移除被移交的条款，并让承接方反向指回原需求")
    report.finish("success")


def do_cleanup(args, report, client, ver) -> None:
    if not supports_cleanup(client):
        raise SkillFailure(
            "历史清理要求 036 已生效（执行记录表应有「放行标记」字段）；"
            "否则摘除需求关联可能让旧版本误转绿。请先部署 board@5 并跑迁移"
        )
    occurrences: dict[str, list[str]] = {}
    for version_id in list(ver.rows.keys()):
        for spec_id in ver.relation(version_id, "独立需求管理") or []:
            occurrences.setdefault(spec_id, []).append(version_id)

    plan = plan_cleanup(occurrences)
    if not plan:
        report.check("跨版本重复", True, "无重复挂载")
        report.finish("success")
        return

    report.note("plan", {spec: {"keep": keep, "drop": drop} for spec, (keep, drop) in plan.items()})
    removals_by_version: dict[str, list[str]] = {}
    for spec_id, (_keep, drop) in plan.items():
        for version_id in drop:
            removals_by_version.setdefault(version_id, []).append(spec_id)

    for version_id, removed in sorted(removals_by_version.items()):
        current = ver.relation(version_id, "独立需求管理") or []
        remaining = [item for item in current if item not in removed]
        report.check(f"{version_id} 摘除", True, f"{removed}")
        if not will_write(args):
            report.write(f"ver/{version_id}", "独立需求管理", remaining, "skipped", error="dry-run：未写")
            continue
        detail = client.write_verified(
            "update", "ver", version_id,
            {ver.fid("独立需求管理"): remaining},
            {"独立需求管理": remaining},
        )
        report.write(f"ver/{version_id}", "独立需求管理", remaining, detail["state"], detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(f"清理 {version_id} 失败：{detail.get('error')}", state=detail["state"])

    report.count(cleaned_specs=len(plan), removed=sum(len(drop) for _keep, drop in plan.values()))
    report.finish("success")


def main(args, report) -> None:
    report.note("role", "系统工程")
    report.note("node", args.action)
    client = make_client(args, ALLOWED)
    ver = client.table("ver")
    ver.require(["版本号", "独立需求管理"])
    indep = client.table("indep")
    indep.require(["编号", "条款", "验收状态"])

    if args.action == "drop":
        do_drop(args, report, client, ver, indep)
    elif args.action == "split":
        do_split(args, report, client, ver, indep)
    else:
        do_cleanup(args, report, client, ver)


if __name__ == "__main__":
    raise SystemExit(entry("tf-lifecycle", build_parser(), main))
