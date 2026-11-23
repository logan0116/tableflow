#!/usr/bin/env python3
"""tf-release-status：这个版本能不能发？（只读）

board@5 口径下的发布就绪报告。取代已废弃的 `tf-status`。

- 判定口径：`发布条件 = and(六节点全部 done)`（board@5 `rules.release_gate`）；
  三布尔（独立需求是否完成 / 依赖需求是否完成 / Bug 是否清空）自 board@4 起降为
  展示字段，**不参与**发布条件，这里只作对照列出来。
- 只读硬承诺：全程只发 GET，不写任何字段。
- 每条判定都给出复算口径与数据来源（041 FR-006）。

用法：

    python3 skills/tf-release-status/scripts/tf_release_status.py --version v0.8.0
"""

from __future__ import annotations

from _tf_common import (
    SkillFailure,
    base_parser,
    entry,
    make_client,
    node_snapshot,
    stage_done,
)

ALLOWED = ("ver", "indep", "dep", "bug", "run", "case")
NODE = "发布就绪"


def verdict(status: str, nodes: dict[str, object]) -> tuple[str, str]:
    """根据发布状态与六节点给出（结论, 理由）。"""
    if status == "dropped":
        return "已终止", "发布状态=dropped：本版决定不发布，红灯与证据保留"
    unfinished = [(name, state) for name, state in nodes.items() if state != "done"]
    if not unfinished:
        return "可发布", "六节点全部 done，发布条件成立"
    return "不可发布", "六节点未齐：" + "、".join(f"{k}={v}" for k, v in unfinished)


def build_parser():
    return base_parser("只读报告某版本能否发布：按 board@5 口径复算六节点与发布条件")


def main(args, report) -> None:
    report.note("role", "系统工程")
    report.note("node", NODE)
    client = make_client(args, ALLOWED)
    ver = client.table("ver")
    ver.require(["版本号", "发布状态", "独立需求管理", "依赖需求管理", "Bug管理", "测试用例"])
    # 报告要覆盖 released/dropped，不能复用 require_version（那个只放行 planned）
    if not ver.row_exists(args.version):
        report.check("版本存在", False, args.version)
        raise SkillFailure(f"版本 {args.version} 不存在")
    report.check("版本存在", True, args.version)

    status = ver.value(args.version, "发布状态")
    report.check("版本状态", status in ("planned", "released", "dropped"), f"发布状态={status}")

    nodes = node_snapshot(ver, args.version)
    report.readback(f"ver/{args.version}#nodes", nodes)
    done = stage_done(nodes)
    report.check(
        "六节点全部完成",
        done,
        "六个节点均 done"
        if done
        else "未完成：" + "、".join(f"{name}={state}" for name, state in nodes.items() if state != "done"),
    )

    board_gate = ver.value(args.version, "发布条件", default=None)
    report.check(
        "看板发布条件与复算一致",
        board_gate is None or bool(board_gate) == done,
        f"看板={board_gate}，复算={done}（口径：发布条件 = and(六节点全部 done)）",
    )

    # 三布尔只作对照，不参与判定
    for name in ("独立需求是否完成", "依赖需求是否完成", "Bug是否清空"):
        value = ver.value(args.version, name, default=None)
        report.note("display_only", {**(report.data.get("display_only") or {}), name: value})

    # 交付范围与测试范围的量化事实
    specs = ver.relation(args.version, "独立需求管理")
    changes = ver.relation(args.version, "依赖需求管理")
    runs = ver.relation(args.version, "测试用例")
    bugs = ver.relation(args.version, "Bug管理")
    run_table = client.table("run")
    results = {}
    for run_id in runs:
        try:
            results[run_id] = run_table.value(run_id, "执行结果")
        except Exception:  # noqa: BLE001 - 字段缺失时不阻断报告
            results[run_id] = None
    passed = sum(1 for value in results.values() if value == "pass")
    report.count(specs=len(specs), changes=len(changes), runs=len(runs), bugs=len(bugs),
                 passed=passed)
    report.note(
        "facts",
        {
            "交付范围": f"独立需求 {len(specs)} 条、依赖需求 {len(changes)} 条",
            "测试范围": f"用例 {len(runs)} 条，其中结果 pass {passed} 条",
            "数据来源": f"版本行 {args.version} 及其四个关系目标表",
        },
    )

    result, reason = verdict(str(status), nodes)
    report.note("verdict", result)
    report.note("reason", reason)
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-release-status", build_parser(), main))
