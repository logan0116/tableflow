"""035：交付范围与测试范围解耦。

对应 `specs/035-scope-decouple/spec.md` 与 board@5
`rules.case_scope_independent` / `rules.delivery_scope_only`：

- 版本内的用例可以来自未挂在本版本的独立需求；
- 「独立需求管理」只记录本版交付工作，不因复测而追加；
- 来源能力未验收时允许纳入并在报告中标注。

本文件只验证技能的纯决策函数（`split_scope`）；端到端行为在
v0.8.0 的 `--spec 019-AR --dry-run` 上做过只读验证。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "tf-test-plan" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import tf_test_plan as skill  # noqa: E402


def test_split_scope_keeps_all_when_in_delivery_scope() -> None:
    in_scope, out_of_scope = skill.split_scope(["033-AR", "034-AR"], ["033-AR", "034-AR"])
    assert in_scope == ["033-AR", "034-AR"]
    assert out_of_scope == []


def test_split_scope_separates_historical_capability() -> None:
    in_scope, out_of_scope = skill.split_scope(
        ["033-AR", "019-AR"], ["033-AR", "034-AR"]
    )
    assert in_scope == ["033-AR"]
    assert out_of_scope == ["019-AR"]


def test_split_scope_handles_pure_regression_version() -> None:
    """纯回归版本：交付范围为空，来源全部在交付范围外。"""
    in_scope, out_of_scope = skill.split_scope(["019-AR", "020-AR"], [])
    assert in_scope == []
    assert out_of_scope == ["019-AR", "020-AR"]


def test_split_scope_preserves_order_and_duplicates() -> None:
    """不在本函数里做去重：调用方已用 dict.fromkeys 处理。"""
    in_scope, out_of_scope = skill.split_scope(["019-AR", "019-AR"], [])
    assert in_scope == []
    assert out_of_scope == ["019-AR", "019-AR"]
