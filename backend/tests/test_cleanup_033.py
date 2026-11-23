"""033 US3：跨版本重复挂载的清理计划。

对应 033 的删除规则——同一独立需求只保留首次出现的版本，其余摘除；
并要求 036 已生效才允许清理（否则摘除需求会让旧版本误转绿）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "tf-lifecycle" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import tf_lifecycle  # noqa: E402


def test_plan_keeps_first_occurrence() -> None:
    plan = tf_lifecycle.plan_cleanup({
        "026-AR": ["v0.7.1", "v0.7.3", "v0.7.4"],
        "027-AR": ["v0.7.1"],
    })
    assert plan == {"026-AR": ("v0.7.1", ["v0.7.3", "v0.7.4"])}


def test_plan_handles_semver_order() -> None:
    """保留的是语义序最小的版本，不是字符串最小的。"""
    plan = tf_lifecycle.plan_cleanup({"007-AR": ["v0.5.10", "v0.5.2"]})
    assert plan["007-AR"] == ("v0.5.2", ["v0.5.10"])


def test_plan_ignores_unique_entries() -> None:
    assert tf_lifecycle.plan_cleanup({"033-AR": ["v0.8.0"], "034-AR": []}) == {}


def test_cleanup_leaves_runs_and_changes_untouched() -> None:
    """清理只动「独立需求管理」；计划里只有需求编号，不涉及用例与变更单。"""
    plan = tf_lifecycle.plan_cleanup({"026-AR": ["v0.7.1", "v0.7.3"]})
    removals: dict[str, list[str]] = {}
    for spec_id, (_keep, drop) in plan.items():
        for version_id in drop:
            removals.setdefault(version_id, []).append(spec_id)
    assert removals == {"v0.7.3": ["026-AR"]}
    assert all("-" in spec for spec in removals["v0.7.3"])


def test_cleanup_requires_036_effective() -> None:
    """036 未生效（执行记录表没有放行标记字段）时拒绝清理。"""

    class NoWaiverTable:
        def fid(self, name: str, *, required: bool = True):
            return None

    class StubClient:
        def table(self, key: str, refresh: bool = False):
            return NoWaiverTable()

    assert tf_lifecycle.supports_cleanup(StubClient()) is False


def test_cleanup_allowed_after_036() -> None:
    class WithWaiverTable:
        def fid(self, name: str, *, required: bool = True):
            return "r-waived"

    class StubClient:
        def table(self, key: str, refresh: bool = False):
            return WithWaiverTable()

    assert tf_lifecycle.supports_cleanup(StubClient()) is True
