#!/usr/bin/env python3
"""tf-dev-implement：推进版本第 3 节点「开发」（软件开发角色），驱动 speckit 实现侧全流程。

单次执行依次处理 plan → tasks → implement 三个阶段（需求 042-AR）：

1. **plan**：``plan.md`` 不存在则按 ``spec.md`` 的 User Story 生成骨架，每条实现项
   回链场景号；``speckit-plan状态=done``。
2. **tasks**：``tasks.md`` 不存在则按实现项生成可勾选任务，每条任务回链场景号；
   ``speckit-task状态=done``。
3. **implement**：要求 ``tasks.md`` 全部勾选且单测通过，两者同时成立才置
   ``speckit-implement状态=done`` 并推进 ``ver.开发``。

产物生成与校验由本技能负责；代码本身由开发按 ``plan.md``/``tasks.md`` 落地，技能以
单测结果作为实现完成的证据，不代替写业务代码。

表作用域：读/写 ``ver``/``indep``；本地读 ``specs/<dir>/`` 下的 spec/plan/tasks，
写 ``plan.md`` 与 ``tasks.md``（已存在时不覆盖，除非显式 ``--force-plan``/``--force-tasks``）。
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
from pathlib import Path

from _tf_common import (
    SkillFailure,
    advance_node,
    base_parser,
    case_id_for,
    ensure_prior_nodes,
    entry,
    make_client,
    parse_spec,
    parse_tasks,
    readback_nodes,
    require_version,
    resolve_repo_root,
    scenario_count,
    spec_dir_of,
    spec_file,
    tasks_file,
)

ALLOWED = ("ver", "indep", "dep", "bug")
NODE = "开发"
PLAN_FIELD = "speckit-plan状态"
TASK_FIELD = "speckit-task状态"
IMPLEMENT_FIELD = "speckit-implement状态"

# 生成产物里每条实现项必带的回链标记
COVER = "覆盖场景"

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


def build_parser():
    parser = base_parser(
        "推进版本第 3 节点「开发」：驱动 plan → tasks → implement 三阶段，"
        "生成并校验 plan.md/tasks.md，单测通过后写 implement 状态与 ver.开发=done"
    )
    parser.add_argument(
        "--spec",
        action="append",
        default=[],
        metavar="SPEC_ID",
        help="只处理这些规格（如 042-AR）；默认版本内全部规格。可重复。",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="只生成并校验 plan.md/tasks.md，写这两个阶段状态，不推进版本节点",
    )
    parser.add_argument(
        "--force-plan", action="store_true", help="plan.md 已存在时也重新生成（会覆盖人工补充内容）"
    )
    parser.add_argument(
        "--force-tasks", action="store_true", help="tasks.md 已存在时也重新生成（会覆盖勾选进度）"
    )
    parser.add_argument(
        "--test-cmd",
        default=None,
        help="实现阶段的单测命令；默认自动探测（backend/.venv 存在则用其 pytest）",
    )
    parser.add_argument(
        "--test-timeout", type=int, default=900, help="单测命令超时秒数，默认 900"
    )
    return parser


def spec_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            for prefix in ("Feature Specification:", "Feature Specification：", "规格：", "规格:"):
                if title.startswith(prefix):
                    title = title[len(prefix):].strip()
            return title
    return path.parent.name


def scenario_ids(spec_id: str, stories: list[dict]) -> list[str]:
    ids: list[str] = []
    for story in stories:
        for scene in story["scenarios"]:
            ids.append(case_id_for(spec_id, story["number"], scene["seq"]))
    return ids


def render_plan(spec_id: str, spec_rel: str, title: str, stories: list[dict], today: str) -> str:
    lines = [
        f"# 实现计划：{title}",
        "",
        f"- **需求**：{spec_id}",
        f"- **规格**：`{spec_rel}/spec.md`",
        f"- **生成时间**：{today}",
        "- **基线修订**：首次",
        "- **生成者**：tf-dev-implement",
        "",
        "## 实现项",
        "",
    ]
    for story in stories:
        ids = [case_id_for(spec_id, story["number"], s["seq"]) for s in story["scenarios"]]
        lines += [
            f"### US{story['number']} {story['title']}（{story['priority']}）",
            "",
            f"- {COVER}：{'、'.join(ids)}",
            "- 实现要点：（待补）",
            "- 影响面：（待补）",
            "- 验证方式：（待补）",
            "",
        ]
    lines += [
        "## 验证",
        "",
        "- 单测范围：（待补）",
        "- 验证命令：`backend/.venv/bin/python -m pytest -q`",
        "- 结论：（待补）",
        "",
    ]
    return "\n".join(lines)


def render_tasks(spec_id: str, spec_rel: str, title: str, stories: list[dict], today: str) -> str:
    lines = [
        f"# 任务清单：{title}",
        "",
        f"- **需求**：{spec_id}",
        f"- **规格**：`{spec_rel}/spec.md`",
        f"- **计划**：`{spec_rel}/plan.md`",
        f"- **生成时间**：{today}",
        "- **生成者**：tf-dev-implement",
        "",
    ]
    seq = 0
    for story in stories:
        seq += 1
        ids = [case_id_for(spec_id, story["number"], s["seq"]) for s in story["scenarios"]]
        lines.append(
            f"- [ ] T{seq:03d} 实现 US{story['number']} {story['title']}（{COVER}：{'、'.join(ids)}）"
        )
    lines += [
        f"- [ ] T{seq + 1:03d} 补齐单元测试（覆盖上述全部实现项）",
        f"- [ ] T{seq + 2:03d} 更新文档与契约引用（如涉及）",
        f"- [ ] T{seq + 3:03d} 跑通全量测试并记录结果",
        "",
    ]
    return "\n".join(lines)


def write_artifact(path: Path, content: str, rel: str, report, dry_run: bool) -> None:
    if dry_run:
        report.write(f"file/{rel}", "<create>", f"{len(content)} 字符", "skipped", error="dry-run：未写")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    report.write(f"file/{rel}", "<create>", f"{len(content)} 字符", "success")


def coverage_missing(path: Path, ids: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [i for i in ids if i not in text]


def detect_test_cmd(repo_root: Path) -> tuple[str, Path]:
    backend = repo_root / "backend"
    if (backend / ".venv" / "bin" / "python").exists():
        return ".venv/bin/python -m pytest -q", backend
    if (repo_root / ".venv" / "bin" / "python").exists():
        return ".venv/bin/python -m pytest -q", repo_root
    return "python3 -m pytest -q", repo_root


def run_tests(repo_root: Path, cmd: str | None, timeout: int) -> tuple[bool, str, str]:
    command, cwd = (cmd, repo_root) if cmd else detect_test_cmd(repo_root)
    # 单测必须自包含：清掉调用者带来的 TF_*（TF_API_KEY/TF_BASE/TF_PROJECT），
    # 否则 e2e/rebuild 测试会继承真实看板配置并连到外部服务。
    env = {key: value for key, value in os.environ.items() if not key.startswith("TF_")}
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, command, f"超时（>{timeout}s）"
    except OSError as exc:
        return False, command, f"无法执行：{exc}"
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    tail = output[-1200:] if len(output) > 1200 else output
    return proc.returncode == 0, command, tail


def _close_fix_version(
    args, report, client, ver, repo_root, bug_ids, dep_ids, run_ids
) -> None:
    """缺陷修复/变更/纯回归版本没有独立需求时的开发收口。

    判据：本版缺陷全部脱离 open（fixing/verifying/closed），或本版已有执行记录
    （纯回归版本），且单测通过——"修好了"由机器可验证的两件事支撑：状态真的动了、
    单测真的过了。
    """
    report.check(
        "版本已关联缺陷、变更单或既有用例",
        bool(bug_ids or dep_ids or run_ids),
        f"缺陷 {len(bug_ids)} 条 / 变更单 {len(dep_ids)} 条 / 执行记录 {len(run_ids)} 条",
    )
    if not (bug_ids or dep_ids or run_ids):
        raise SkillFailure(
            "版本未关联任何独立规格需求、缺陷、变更单或既有用例，没有可推进的开发工作"
        )

    if bug_ids:
        bug = client.table("bug")
        bug.require(["编号", "状态"])
        pending = [
            bug_id for bug_id in bug_ids
            if bug.value(bug_id, "状态") not in ("fixing", "verifying", "closed")
        ]
        report.check(
            "本版缺陷已进入修复",
            not pending,
            f"{len(bug_ids)} 条已全部脱离 open"
            if not pending
            else f"仍待修 {len(pending)} 条：{'、'.join(pending)}",
        )
        if pending:
            raise SkillFailure(
                "缺陷还没有进入修复状态，开发节点不能收口："
                + "、".join(pending)
                + "；先改到 fixing（或 verifying），并留下修复证据"
            )

    if args.plan_only:
        report.check("缺陷修复范围", True, "已确认本版工作项，未推进版本节点（--plan-only）")
        report.finish("success")
        return

    ok, command, output = run_tests(repo_root, args.test_cmd, args.test_timeout)
    report.check("单测通过", ok, f"`{command}` -> {'通过' if ok else '失败'}")
    report.note("test_output_tail", output[-800:])
    if not ok:
        raise SkillFailure(f"单测未通过，不能置开发完成：`{command}`")

    advance_node(
        client, ver, args.version, NODE, report,
        dry_run=args.dry_run, no_stage=args.no_stage,
    )
    readback_nodes(client.table("ver", refresh=True), args.version, report)
    report.finish("success")


def main(args, report) -> None:
    report.note("role", "软件开发")
    report.note("node", NODE)
    report.note("mode", "plan-only" if args.plan_only else "apply")
    client = make_client(args, ALLOWED)
    repo_root = resolve_repo_root(args.repo_root)
    today = datetime.date.today().isoformat()

    ver = client.table("ver")
    ver.require(["版本号", "发布状态", NODE, "独立需求管理"])
    require_version(ver, args.version, report)
    ensure_prior_nodes(ver, args.version, NODE, report)

    version_specs = ver.relation(args.version, "独立需求管理")
    wanted = list(dict.fromkeys(args.spec)) or list(version_specs)
    version_bugs = ver.relation(args.version, "Bug管理")
    version_deps = ver.relation(args.version, "依赖需求管理")
    version_runs = ver.relation(args.version, "测试用例")
    # FR-010：单份（或部分）规格完成不得代替版本完成，子集模式下只写各规格状态、不推进版本节点
    full_scope = set(wanted) == set(version_specs)
    report.check("版本已关联规格", bool(wanted), f"{len(wanted)} 份：{'、'.join(wanted) or '无'}")
    if not wanted:
        # 没有独立需求时，本版是缺陷修复/变更版本：修 bug 本身就是开发工作（034/037）。
        _close_fix_version(
            args, report, client, ver, repo_root, version_bugs, version_deps, version_runs
        )
        return
    for spec_id in wanted:
        attached = spec_id in version_specs
        report.check(f"规格 {spec_id} 已挂到版本", attached, "在 ver.独立需求管理 中")
        if not attached:
            raise SkillFailure(f"规格 {spec_id} 未挂到版本 {args.version}，不能推进其开发状态")

    indep = client.table("indep")
    indep.require(["编号", "条款", "规格目录", PLAN_FIELD, TASK_FIELD, IMPLEMENT_FIELD, "验收状态"])

    stage_updates: dict[str, dict[str, str]] = {}
    implement_blocked: list[str] = []
    counts = {"plans_created": 0, "tasks_created": 0}

    for spec_id in wanted:
        if not indep.row_exists(spec_id):
            raise SkillFailure(f"规格「{spec_id}」在独立规格需求表中不存在")
        spec_path = spec_file(repo_root, indep, spec_id)
        stories = parse_spec(spec_path)
        total = scenario_count(stories)
        report.check(
            f"规格 {spec_id} 有验收场景",
            total > 0,
            f"{len(stories)} 个 User Story / {total} 条 Acceptance Scenario",
        )
        if total == 0:
            raise SkillFailure(f"规格 {spec_id} 没有 Acceptance Scenario：{spec_path}")

        spec_rel = spec_dir_of(indep, spec_id).rstrip("/")
        title = spec_title(spec_path)
        ids = scenario_ids(spec_id, stories)

        # ---- 阶段 1：plan ----
        plan_path = repo_root / spec_rel / "plan.md"
        if not plan_path.exists():
            write_artifact(
                plan_path, render_plan(spec_id, spec_rel, title, stories, today), f"{spec_rel}/plan.md",
                report, args.dry_run,
            )
            if plan_path.exists() or args.dry_run:
                counts["plans_created"] += 0 if args.dry_run else 1
            report.check(f"规格 {spec_id} plan.md", True, "不存在，已生成骨架" if not args.dry_run else "不存在，dry-run 未写")
        elif args.force_plan:
            write_artifact(
                plan_path, render_plan(spec_id, spec_rel, title, stories, today), f"{spec_rel}/plan.md",
                report, args.dry_run,
            )
            report.check(f"规格 {spec_id} plan.md", True, "--force-plan 重新生成")
        else:
            report.check(f"规格 {spec_id} plan.md", True, "已存在，沿用")

        if plan_path.exists():
            text = plan_path.read_text(encoding="utf-8")
            missing = coverage_missing(plan_path, ids)
            placeholders = text.count("（待补）")
            report.check(
                f"规格 {spec_id} plan 回链场景",
                not missing,
                f"{len(ids)} 条场景全覆盖" if not missing else f"缺 {len(missing)} 条：{missing[:5]}",
            )
            report.check(
                f"规格 {spec_id} plan 已填写",
                not placeholders,
                "无占位符" if not placeholders else f"仍有 {placeholders} 处「（待补）」",
            )
            plan_ok = not missing and not placeholders
        else:
            # 本轮刚生成骨架：不是完成的设计，停下等补全（042：先完成计划，再确认任务）。
            plan_ok = False
            report.check(
                f"规格 {spec_id} plan 已生成",
                False,
                "已生成骨架，补全实现要点后重跑；本轮不推进 plan 阶段",
            )
        if plan_ok:
            stage_updates.setdefault(spec_id, {})[PLAN_FIELD] = "done"

        # ---- 阶段 2：tasks ----
        task_path = tasks_file(repo_root, indep, spec_id)
        if task_path is None:
            target = repo_root / spec_rel / "tasks.md"
            write_artifact(
                target, render_tasks(spec_id, spec_rel, title, stories, today), f"{spec_rel}/tasks.md",
                report, args.dry_run,
            )
            if target.exists() and not args.dry_run:
                counts["tasks_created"] += 1
            task_path = target
            report.check(
                f"规格 {spec_id} tasks.md", True,
                "不存在，已生成骨架" if not args.dry_run else "不存在，dry-run 未写",
            )
        elif args.force_tasks:
            write_artifact(
                task_path, render_tasks(spec_id, spec_rel, title, stories, today), f"{spec_rel}/tasks.md",
                report, args.dry_run,
            )
            report.check(f"规格 {spec_id} tasks.md", True, "--force-tasks 重新生成")
        else:
            report.check(f"规格 {spec_id} tasks.md", True, "已存在，沿用")

        if task_path.exists():
            missing = coverage_missing(task_path, ids)
            report.check(
                f"规格 {spec_id} tasks 回链场景",
                not missing,
                f"{len(ids)} 条场景全覆盖" if not missing else f"缺 {len(missing)} 条：{missing[:5]}",
            )
            tasks_ok = not missing
        else:
            tasks_ok = args.dry_run
        if tasks_ok:
            stage_updates.setdefault(spec_id, {})[TASK_FIELD] = "done"

        # ---- 阶段 3：implement（plan-only 不跑） ----
        if args.plan_only:
            continue
        if not (plan_ok and tasks_ok):
            implement_blocked.append(f"{spec_id} 计划或任务未就绪")
            continue
        tasks = parse_tasks(task_path)
        report.check(
            f"规格 {spec_id} 任务全部完成",
            not tasks["unchecked"] and tasks["checked"] > 0,
            f"已勾选 {tasks['checked']} 条，未勾选 {len(tasks['unchecked'])} 条",
        )
        if tasks["unchecked"] or tasks["checked"] == 0:
            implement_blocked.append(
                f"{spec_id} 任务未完成（已勾选 {tasks['checked']}，未勾选 {len(tasks['unchecked'])}）"
            )
            continue
        stage_updates.setdefault(spec_id, {})[IMPLEMENT_FIELD] = "pending-test"

    # ---- 038：先写阶段证据，再改状态（置 done 必须有证据行） ----
    evidence_fid = indep.fid(EVIDENCE_FIELD, required=False)
    check_counts = {
        spec_id: parse_tasks(repo_root / spec_dir_of(indep, spec_id) / "tasks.md")
        for spec_id in wanted
        if (repo_root / spec_dir_of(indep, spec_id) / "tasks.md").exists()
    }
    for spec_id, updates in stage_updates.items():
        if evidence_fid is None:
            break
        entries: dict[str, str] = {}
        rel = spec_dir_of(indep, spec_id).rstrip("/")
        if updates.get(PLAN_FIELD) == "done":
            entries["plan"] = f"{rel}/plan.md（回链 {len(scenario_ids(spec_id, parse_spec(spec_file(repo_root, indep, spec_id))))} 条场景）"
        if updates.get(TASK_FIELD) == "done" and spec_id in check_counts:
            counts = check_counts[spec_id]
            entries["task"] = f"{rel}/tasks.md（已勾选 {counts['checked']} 条，未勾选 {len(counts['unchecked'])} 条）"
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

    # ---- 写阶段状态（plan/tasks 先落库，implement 待单测结论） ----
    for spec_id, updates in stage_updates.items():
        for field, value in updates.items():
            if value == "pending-test":
                continue
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

    report.count(**counts)

    if args.plan_only:
        report.check("plan/tasks 阶段", True, "计划与任务已就绪，未推进版本节点（--plan-only）")
        report.finish("success")
        return

    if implement_blocked:
        raise SkillFailure("开发节点未满足：" + "；".join(implement_blocked))

    # ---- 单测：implement 阶段的证据 ----
    ok, command, output = run_tests(repo_root, args.test_cmd, args.test_timeout)
    report.check("单测通过", ok, f"`{command}` -> {'通过' if ok else '失败'}")
    report.note("test_output_tail", output[-800:])
    if not ok:
        raise SkillFailure(f"单测未通过，不能置 implement 完成：`{command}`")

    if evidence_fid:
        # 重读整表：plan/task 证据刚写进去，缓存里的旧行会把它们覆盖掉（BUG-083-11）。
        indep = client.table("indep", refresh=True)
        implement_entries = {
            spec_id: merge_evidence(
                indep.value(spec_id, EVIDENCE_FIELD, default=None),
                {"implement": f"单测通过（{command}）"},
            )
            for spec_id in wanted
            if indep.value(spec_id, IMPLEMENT_FIELD) != "done"
        }
        for spec_id, merged_text in implement_entries.items():
            if args.dry_run:
                report.write(f"indep/{spec_id}", EVIDENCE_FIELD, "implement", "skipped", error="dry-run：未写")
                continue
            detail = client.write_verified(
                "update", "indep", spec_id, {evidence_fid: merged_text}, {EVIDENCE_FIELD: merged_text}
            )
            report.write(f"indep/{spec_id}", EVIDENCE_FIELD, "implement",
                         detail["state"], detail.get("http"), detail.get("error"))
            if detail["state"] != "success":
                raise SkillFailure(
                    f"写规格 {spec_id} 的 implement 证据失败：{detail.get('error') or '回读不一致'}",
                    state=detail["state"],
                )

    for spec_id in wanted:
        if indep.value(spec_id, IMPLEMENT_FIELD) == "done":
            report.check(f"规格 {spec_id} implement 状态", True, "已是 done，跳过写入")
            continue
        if args.dry_run:
            report.write(f"indep/{spec_id}", IMPLEMENT_FIELD, "done", "skipped", error="dry-run：未写")
            continue
        detail = client.write_verified(
            "update", "indep", spec_id,
            {indep.fid(IMPLEMENT_FIELD): "done"}, {IMPLEMENT_FIELD: "done"},
        )
        report.write(
            f"indep/{spec_id}", IMPLEMENT_FIELD, "done", detail["state"],
            detail.get("http"), detail.get("error"),
        )
        if detail["state"] != "success":
            raise SkillFailure(
                f"写规格 {spec_id} 的 implement 状态失败：{detail.get('error') or '回读不一致'}",
                state=detail["state"],
            )

    fresh = client.table("indep", refresh=True)
    states = {s: fresh.value(s, IMPLEMENT_FIELD) for s in wanted}
    pending = [s for s, v in states.items() if v != "done"]
    report.check(
        "读回 implement 状态",
        args.dry_run or not pending,
        f"dry-run：{len(pending)} 份待写（未写）" if args.dry_run else (
            f"{len(wanted)} 份全部 done" if not pending else f"未 done：{pending}"
        ),
    )
    report.readback(f"indep#implement/{args.version}", states)
    if pending and not args.dry_run:
        raise SkillFailure(f"读回后仍有规格 implement 不为 done：{pending}")

    if not full_scope:
        report.check(
            "版本节点推进",
            True,
            f"本次只处理 {len(wanted)}/{len(version_specs)} 份规格（--spec 子集），"
            "按 FR-010 不推进版本节点",
        )
        report.finish("success")
        return

    advance_node(
        client, ver, args.version, NODE, report,
        dry_run=args.dry_run, no_stage=args.no_stage,
    )
    readback_nodes(client.table("ver", refresh=True), args.version, report)
    report.finish("success")


if __name__ == "__main__":
    raise SystemExit(entry("tf-dev-implement", build_parser(), main))
