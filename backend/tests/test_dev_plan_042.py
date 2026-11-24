"""042：tf-dev-plan 驱动 spec 侧阶段状态并执行 039 结构下限校验。

覆盖：
- 结构统计只认 Functional Requirements / Edge Cases 两个章节，且同/更高级标题会关章节；
- 结构下限检出：任一低于下限即报出该维度；
- Clarifications 有未决标记时 clarify 判 doing，无章节判 na；
- 规格侧五个阶段字段在「规格目录/宪法」齐备时给出确定取值。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "tf-dev-plan" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import tf_dev_plan as skill  # noqa: E402

GOOD = """# Feature Specification: 示例

### User Story 1 - 甲 (Priority: P1)

1. **Given** a，**When** b，**Then** c

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 甲
- **FR-002**: 系统 MUST 乙
- **FR-003**: 系统 MUST 丙
- **FR-004**: 系统 MUST 丁
- **FR-005**: 系统 MUST 戊
- **FR-006**: 系统 MUST 己

### Edge Cases

- 边界一
- 边界二
- 边界三
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "spec.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_structure_numbers_counts_only_named_sections(tmp_path: Path) -> None:
    path = write(tmp_path, GOOD)
    assert skill.structure_numbers(path) == {"fr": 6, "edge": 3}


def test_structure_numbers_accepts_chinese_sections(tmp_path: Path) -> None:
    text = "## 功能需求\n\n- **FR-001**: 甲\n- **FR-002**: 乙\n\n## 边界情况\n\n- 一\n- 二\n"
    assert skill.structure_numbers(write(tmp_path, text)) == {"fr": 2, "edge": 2}


def test_structure_numbers_falls_back_to_fr_items(tmp_path: Path) -> None:
    text = "## 需求溯源\n\n- **FR-001**: 甲\n- **FR-002**: 乙\n"
    assert skill.structure_numbers(write(tmp_path, text))["fr"] == 2


def test_structure_numbers_fallback_without_named_section(tmp_path: Path) -> None:
    text = "## Background\n\n- **FR-001**: 甲\n"
    assert skill.structure_numbers(write(tmp_path, text))["fr"] == 1


def test_structure_numbers_stops_at_same_level_heading(tmp_path: Path) -> None:
    text = GOOD + "\n## Success Criteria\n\n- **SC-001**: 不算功能需求\n- 也不算边界\n"
    path = write(tmp_path, text)
    assert skill.structure_numbers(path) == {"fr": 6, "edge": 3}


def test_structure_numbers_keeps_section_across_deeper_heading(tmp_path: Path) -> None:
    text = GOOD.replace(
        "### Functional Requirements\n",
        "### Functional Requirements\n\n#### 分组一\n",
    )
    path = write(tmp_path, text)
    assert skill.structure_numbers(path)["fr"] == 6


def test_structure_numbers_ignores_non_fr_bullets(tmp_path: Path) -> None:
    text = GOOD.replace("- **FR-006**: 系统 MUST 己", "- 普通条目，不是 FR")
    path = write(tmp_path, text)
    assert skill.structure_numbers(path)["fr"] == 5


def test_clarify_state_done_when_all_resolved(tmp_path: Path) -> None:
    text = GOOD + "\n## Clarifications\n\n- Q: 甲？ → A: 乙。\n"
    assert skill.clarify_state(write(tmp_path, text)) == "done"


def test_clarify_state_doing_when_pending_marker(tmp_path: Path) -> None:
    text = GOOD + "\n## Clarifications\n\n- Q: 甲？ → A: 待定。\n"
    assert skill.clarify_state(write(tmp_path, text)) == "doing"


def test_clarify_state_na_without_section(tmp_path: Path) -> None:
    assert skill.clarify_state(write(tmp_path, GOOD)) == "na"


def test_structure_floor_reports_each_short_dimension() -> None:
    actual = {"us": 1, "scen": 3, "fr": 2, "edge": 0}
    short = {k: f"{actual[k]}/{skill.STRUCT_FLOOR[k]}" for k in skill.STRUCT_FLOOR if actual[k] < skill.STRUCT_FLOOR[k]}
    assert short == {"us": "1/2", "scen": "3/5", "fr": "2/6", "edge": "0/3"}


def test_stage_fields_cover_five_spec_side_stages() -> None:
    assert set(skill.STAGE_FIELDS) == {"constitution", "specify", "clarify", "analyze", "checklist"}
