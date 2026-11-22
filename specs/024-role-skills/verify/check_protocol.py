#!/usr/bin/env python3
"""024 共用运行时的协议单元断言：三态分类、空值归一化、场景解析。

不访问网络、不碰数据库；由 run_verify.sh 在技能验证前执行。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "tf-dev-plan" / "scripts"))

import _tf_common as common  # noqa: E402


def main() -> int:
    checks: list[dict] = []

    def check(name: str, fn) -> None:
        try:
            fn()
            checks.append({"name": name, "ok": True})
        except Exception as exc:  # noqa: BLE001 - 断言器要把差异打出来
            checks.append({"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"})

    # 012 P-024 三态判定树
    check("200+success -> success", lambda: _eq(common.classify(200, {"result": "success"}), "success"))
    check("400+failed -> failed", lambda: _eq(common.classify(400, {"result": "failed"}), "failed"))
    check("401 -> failed", lambda: _eq(common.classify(401, {"result": "failed"}), "failed"))
    check("422 detail -> failed", lambda: _eq(common.classify(422, {"detail": []}), "failed"))
    check("503 detail -> unknown", lambda: _eq(common.classify(503, {"detail": "数据存储不可用"}), "unknown"))
    check("503 unknown 信封 -> unknown", lambda: _eq(common.classify(503, {"result": "unknown"}), "unknown"))
    check("连接失败(http=0) -> unknown", lambda: _eq(common.classify(0, None), "unknown"))
    check("200 非 JSON -> unknown", lambda: _eq(common.classify(200, None), "unknown"))
    check("200 无 result -> failed", lambda: _eq(common.classify(200, {}), "failed"))

    # 空值三种形态等价；relation 数组按集合比较
    check("None == '' == []", lambda: _eq(common.same_value(None, ""), True))
    check("'' == []", lambda: _eq(common.same_value("", []), True))
    check("relation 顺序无关", lambda: _eq(common.same_value(["a", "b"], ["b", "a"]), True))
    check("非空文本不等", lambda: _eq(common.same_value("a", "b"), False))

    # 场景解析：三份规格的已知条数
    for directory, expected in [
        ("017-bug-relation", 6),
        ("019-test-contract", 27),
        ("012-protocol", 12),
    ]:
        def _parse(directory=directory, expected=expected):
            stories = common.parse_spec(ROOT / "specs" / directory / "spec.md")
            _eq(common.scenario_count(stories), expected)
            _eq(len(stories) > 0, True)

        check(f"解析 {directory} 场景数={expected}", _parse)

    check("用例行 id = 场景号", lambda: _eq(common.case_id_for("019-AR", 1, 2), "019-US1-AS2"))

    # D-01：--apply 被六个入口共用解析器接受；--dry-run 优先
    def _parser_apply():
        parser = common.base_parser("test")
        args = parser.parse_args(["--version", "v0.7.0", "--apply"])
        _eq(args.apply, True)
        _eq(args.dry_run, False)

    def _parser_dry_wins():
        parser = common.base_parser("test")
        args = parser.parse_args(["--version", "v0.7.0", "--apply", "--dry-run"])
        _eq(args.apply, True)
        _eq(args.dry_run, True)

    def _parser_default_write():
        parser = common.base_parser("test")
        args = parser.parse_args(["--version", "v0.7.0"])
        _eq(args.apply, False)
        _eq(args.dry_run, False)

    check("--apply 被共用解析器接受", _parser_apply)
    check("--dry-run 与 --apply 同给时两者都保留（由技能按 dry-run 优先）", _parser_dry_wins)
    check("不传 --apply 默认仍为写模式", _parser_default_write)
    check(
        "执行结果枚举",
        lambda: _eq(sorted(common.RUN_RESULT_VALUES), ["blocked", "fail", "pass", "skip"]),
    )

    report = {
        "skill": "024-common-protocol",
        "result": "success" if all(item["ok"] for item in checks) else "failed",
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["result"] == "success" else 1


def _eq(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


if __name__ == "__main__":
    raise SystemExit(main())
