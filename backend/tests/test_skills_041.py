"""041：看板操作技能重构。

覆盖：
- 五个旧技能已从仓库删除；
- 活跃技能的文档不再指向旧技能（除「取代/已废弃」这类说明）；
- `tf-register.classify` 的五个分派分支与契约 `classify.order` 一致；
- `tf-lifecycle` 的版本序比较。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "skills"

for name in ("tf-register", "tf-lifecycle"):
    path = SKILLS / name / "scripts"
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import tf_register  # noqa: E402
import tf_lifecycle  # noqa: E402

DEPRECATED = ("tf-update", "tf-status", "ms-update", "ms-implement", "ms-summary")
ACTIVE = (
    "tf-dev-plan", "tf-dev-implement", "tf-dev-check",
    "tf-test-plan", "tf-test-implement", "tf-test-check",
    "tf-register", "tf-release-status", "tf-lifecycle",
)


class StubIndep:
    """只提供 value(row_id, name) 的最小替身。"""

    def __init__(self, states: dict[str, str]):
        self.states = states

    def value(self, row_id: str, name: str, default=None):
        return self.states.get(row_id, default)


def test_deprecated_skills_are_gone() -> None:
    remaining = [name for name in DEPRECATED if (SKILLS / name).exists()]
    assert remaining == [], f"旧技能未删除：{remaining}"


def test_active_skills_exist() -> None:
    missing = [name for name in ACTIVE if not (SKILLS / name / "SKILL.md").exists()]
    assert missing == [], f"缺少技能：{missing}"


def test_no_stale_references_in_active_docs() -> None:
    offenders: list[str] = []
    for name in ACTIVE:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if any(old in line for old in DEPRECATED) and "取代" not in line and "已废弃" not in line:
                offenders.append(f"{name}: {line.strip()[:60]}")
    assert offenders == [], "仍有指向旧技能的引用：" + "；".join(offenders)


def test_classify_new_spec_without_spec() -> None:
    assert tf_register.classify(StubIndep({}), [], None) == "new_spec"


def test_classify_cross_with_multiple_specs() -> None:
    indep = StubIndep({"026-AR": "accepted", "027-AR": "accepted"})
    assert tf_register.classify(indep, ["026-AR", "027-AR"], None) == "cross"


def test_classify_change_when_spec_accepted() -> None:
    indep = StubIndep({"026-AR": "accepted"})
    assert tf_register.classify(indep, ["026-AR"], None) == "change"


def test_classify_in_place_when_spec_not_accepted() -> None:
    indep = StubIndep({"034-AR": "pending"})
    assert tf_register.classify(indep, ["034-AR"], None) == "in_place"


def test_classify_forced_kind_wins() -> None:
    indep = StubIndep({"026-AR": "accepted"})
    assert tf_register.classify(indep, ["026-AR"], "out_of_board") == "out_of_board"


def test_semver_orders_numerically() -> None:
    assert tf_lifecycle.semver("v0.7.1") < tf_lifecycle.semver("v0.7.10")
    assert tf_lifecycle.semver("v0.10.0") > tf_lifecycle.semver("v0.9.9")


def test_semver_tolerates_missing_v_prefix() -> None:
    assert tf_lifecycle.semver("7.0.0") == tf_lifecycle.semver("v7.0.0")


def test_semver_puts_unparsable_last() -> None:
    assert tf_lifecycle.semver("garbage") == (999, 999, 999)
    assert tf_lifecycle.semver("v9.9.9") < tf_lifecycle.semver("garbage")
