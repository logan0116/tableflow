#!/usr/bin/env python3
"""tf-register：一条需求该落在哪张表？（登记入口）

取代已废弃的 `tf-update`。按契约 `classify.order` 的五种情况自动分派，
发请求前做规则自检（040 的规则清单以引擎为准，这里只预检、不复制判定）：

| 判定 | 条件 | 动作 |
|---|---|---|
| `in_place` | 给了 `--spec` 且该规格尚未 accepted | 不改结构，只更新该独立需求的条款 |
| `change` | 给了 `--spec` 且该规格已 accepted | 在依赖需求表建行 |
| `cross` | 给了多份 `--spec` | 在依赖需求表建一行，关联多份规格 |
| `new_spec` | 没给 `--spec` | 在独立需求表建行 |
| `out_of_board` | 显式 `--kind out_of_board` | 不进看板，只提示记入版本变更说明 |

用法：

    # 先看分派结果（不写）
    python3 skills/tf-register/scripts/tf_register.py --clause "..." --version v0.8.0 \
        --spec 033-AR --dry-run

    # 新规格
    python3 skills/tf-register/scripts/tf_register.py --clause "..." --version v0.8.0 \
        --id 043-AR --dir specs/043-xxx/

    # 变更单（可多份规格）
    python3 skills/tf-register/scripts/tf_register.py --clause "..." --version v0.8.0 \
        --spec 026-AR --spec 027-AR --id DEP-07-BR --impact "..." --affected "..."
"""

from __future__ import annotations

from _tf_common import (
    SkillFailure,
    base_parser,
    entry,
    make_client,
    require_version,
)

ALLOWED = ("ver", "indep", "dep")
NODE = "需求登记"
KINDS = ("in_place", "change", "cross", "new_spec", "out_of_board")


def build_parser():
    parser = base_parser("按 classify 分派一条需求落在哪张表，并完成登记")
    parser.add_argument("--clause", required=True, help="需求原文（归一化后写入条款）")
    parser.add_argument("--spec", action="append", default=[], help="涉及的已有规格编号，可重复")
    parser.add_argument("--id", help="新行编号（new_spec：NNN-AR；change/cross：DEP-NN-BR）")
    parser.add_argument("--dir", help="new_spec 的规格目录，如 specs/043-xxx/")
    parser.add_argument("--impact", help="change/cross 的影响面")
    parser.add_argument("--affected", help="change/cross 的受影响条款（一行一份）")
    parser.add_argument("--kind", choices=KINDS, help="强制指定分派结果（默认自动判定）")
    return parser


def classify(indep, specs: list[str], forced: str | None) -> str:
    """按契约 classify 判定；给不出证据时拒绝登记。"""
    if forced:
        return forced
    if not specs:
        return "new_spec"
    if len(specs) > 1:
        return "cross"
    state = indep.value(specs[0], "验收状态")
    return "change" if state == "accepted" else "in_place"


def main(args, report) -> None:
    report.note("role", "系统工程")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)
    ver = client.table("ver")
    ver.require(["版本号", "发布状态", "独立需求管理", "依赖需求管理"])
    indep = client.table("indep")
    indep.require(["编号", "条款", "验收状态"])
    dep = client.table("dep")

    specs = list(dict.fromkeys(args.spec))
    for spec_id in specs:
        if not indep.row_exists(spec_id):
            raise SkillFailure(f"规格「{spec_id}」不存在，无法作为登记依据")
    kind = classify(indep, specs, args.kind)
    report.note("classify", {"kind": kind, "specs": specs})
    report.check("分派结果", True, f"{kind}（规格 {len(specs)} 份）")

    if kind == "out_of_board":
        report.note("action", "不进看板：把这条记进版本变更说明，不要建行")
        report.finish("success")
        return

    # 规则预检：只报明显冲突，最终判定仍由引擎执行（同源原则）
    if kind in ("change", "cross"):
        for spec_id in specs:
            state = indep.value(spec_id, "验收状态")
            report.check(
                f"规格 {spec_id} 已验收", state == "accepted",
                f"验收状态={state}" + ("" if state == "accepted" else "（未验收时按 in_place 直接改规格）"),
            )
            if state != "accepted":
                raise SkillFailure(
                    f"规格 {spec_id} 尚未验收，不能开依赖需求（C4）；"
                    "规格未验收时按 classify.in_place 直接改规格与其独立需求行"
                )
        if not args.id:
            raise SkillFailure("变更单必须指定 --id（形如 DEP-07-BR）")
        if not args.impact:
            raise SkillFailure("变更单必须指定 --impact（受影响的能力/接口/场景/下游）")

    if kind == "new_spec" and not args.id:
        raise SkillFailure("新规格必须指定 --id（形如 043-AR）")

    require_version(ver, args.version, report)
    version_specs = ver.relation(args.version, "独立需求管理")
    version_changes = ver.relation(args.version, "依赖需求管理")

    if kind == "new_spec":
        if args.id in version_specs:
            raise SkillFailure(f"{args.id} 已在本版交付范围内（C1）")
        values = {indep.fid("编号"): args.id, indep.fid("条款"): args.clause}
        if args.dir:
            values[indep.fid("规格目录")] = args.dir
        if indep.fid("验收状态", required=False):
            values[indep.fid("验收状态")] = "pending"
        report.note("plan", f"新建独立需求 {args.id} 并挂到 {args.version}")
        if args.dry_run:
            report.write(f"indep/{args.id}", "<create>", args.clause[:40], "skipped", error="dry-run：未写")
            report.finish("success")
            return
        detail = client.write_verified("create", "indep", args.id, values, {"条款": args.clause})
        report.write(f"indep/{args.id}", "<create>", args.clause[:40], detail["state"], detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(f"新建独立需求失败：{detail.get('error') or '回读不一致'}", state=detail["state"])
        patch = client.write_verified(
            "update", "ver", args.version,
            {ver.fid("独立需求管理"): version_specs + [args.id]},
            {"独立需求管理": version_specs + [args.id]},
        )
        report.write(f"ver/{args.version}", "独立需求管理", version_specs + [args.id], patch["state"], patch.get("http"), patch.get("error"))
        if patch["state"] != "success":
            raise SkillFailure(f"挂到版本失败：{patch.get('error') or '回读不一致'}", state=patch["state"])
        report.finish("success")
        return

    if kind == "in_place":
        spec_id = specs[0]
        report.note("plan", f"就地更新 {spec_id} 的条款，不新建行")
        if args.dry_run:
            report.write(f"indep/{spec_id}", "条款", args.clause[:40], "skipped", error="dry-run：未写")
            report.finish("success")
            return
        detail = client.write_verified(
            "update", "indep", spec_id,
            {indep.fid("条款"): args.clause}, {"条款": args.clause},
        )
        report.write(f"indep/{spec_id}", "条款", args.clause[:40], detail["state"], detail.get("http"), detail.get("error"))
        if detail["state"] != "success":
            raise SkillFailure(f"更新条款失败：{detail.get('error') or '回读不一致'}", state=detail["state"])
        report.note("reminder", "记得同步修改 specs/<dir>/spec.md 的内容，条款与规格要一致")
        report.finish("success")
        return

    # change / cross
    if args.id in version_changes:
        raise SkillFailure(f"{args.id} 已在本版依赖需求范围内（C2）")
    values = {
        dep.fid("编号"): args.id,
        dep.fid("条款"): args.clause,
        dep.fid("关联的独立规格需求"): specs,
        dep.fid("影响面"): args.impact,
        dep.fid("回归状态"): "todo",
    }
    if args.affected and dep.fid("受影响条款", required=False):
        values[dep.fid("受影响条款")] = args.affected
    report.note("plan", f"新建依赖需求 {args.id}，关联 {len(specs)} 份规格并挂到 {args.version}")
    if args.dry_run:
        report.write(f"dep/{args.id}", "<create>", args.clause[:40], "skipped", error="dry-run：未写")
        report.finish("success")
        return
    detail = client.write_verified("create", "dep", args.id, values, {"条款": args.clause})
    report.write(f"dep/{args.id}", "<create>", args.clause[:40], detail["state"], detail.get("http"), detail.get("error"))
    if detail["state"] != "success":
        raise SkillFailure(f"新建依赖需求失败：{detail.get('error') or '回读不一致'}", state=detail["state"])
    patch = client.write_verified(
        "update", "ver", args.version,
        {ver.fid("依赖需求管理"): version_changes + [args.id]},
        {"依赖需求管理": version_changes + [args.id]},
    )
    report.write(f"ver/{args.version}", "依赖需求管理", version_changes + [args.id], patch["state"], patch.get("http"), patch.get("error"))
    if patch["state"] != "success":
        raise SkillFailure(f"挂到版本失败：{patch.get('error') or '回读不一致'}", state=patch["state"])
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-register", build_parser(), main))
