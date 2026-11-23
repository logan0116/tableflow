"""039：规格结构分析——章节完整性、结构下限、场景可判定性与追溯。

覆盖 `spec_structure.analyze` 的解析口径：
- 三个必备章节与两个建议章节的识别；
- 下限判定（US≥2/场景≥5/FR≥6/边界≥3）；
- 缺 **When** 的编号项计入 malformed，不进场景数（这类场景会被静默丢用例）；
- 场景引用 FR 时计入追踪，两侧都没引用判为 absent。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tableflow.spec_structure import FLOOR, analyze  # noqa: E402

GOOD = """# Feature Specification: 示例

## User Scenarios & Testing

### User Story 1 - 甲 (Priority: P1)

1. **Given** a，**When** b，**Then** c（FR-001）
2. **Given** d，**When** e，**Then** f（FR-002）

### User Story 2 - 乙 (Priority: P1)

1. **Given** g，**When** h，**Then** i（FR-003）
2. **Given** j，**When** k，**Then** l（FR-004）
3. **Given** m，**When** n，**Then** o（FR-005）

## Requirements

### Functional Requirements

- **FR-001**: 甲
- **FR-002**: 乙
- **FR-003**: 丙
- **FR-004**: 丁
- **FR-005**: 戊
- **FR-006**: 己

### Edge Cases

- 边界一
- 边界二
- 边界三

## Success Criteria

- **SC-001**: 一条
## Key Entities

- 实体一
"""


def test_good_spec_passes_all_gates() -> None:
    report = analyze(GOOD)
    assert report["counts"] == {"us": 2, "scenarios": 5, "fr": 6, "edge": 3}
    assert report["missing_sections"] == []
    assert report["below_floor"] == {}
    assert report["malformed_scenarios"] == []
    assert report["ok"] is True


def test_missing_functional_requirements_is_flagged() -> None:
    text = GOOD.replace("### Functional Requirements", "### 其它要求")
    report = analyze(text)
    assert "functional_requirements" in report["missing_sections"]
    assert report["ok"] is False


def test_missing_edge_cases_is_flagged() -> None:
    text = GOOD.replace("### Edge Cases", "### 其它")
    report = analyze(text)
    assert "edge_cases" in report["missing_sections"]


def test_below_floor_reports_each_dimension() -> None:
    text = GOOD.replace("1. **Given** a，**When** b，**Then** c（FR-001）", "")
    text = text.replace("2. **Given** d，**When** e，**Then** f（FR-002）", "")
    report = analyze(text)
    assert report["counts"]["scenarios"] == 3
    assert report["below_floor"] == {"scenarios": 3}
    assert FLOOR["scenarios"] == 5


def test_scenario_without_when_is_malformed_not_counted() -> None:
    text = GOOD.replace(
        "1. **Given** a，**When** b，**Then** c（FR-001）",
        "1. **Given** a，**Then** c（FR-001）",
    )
    report = analyze(text)
    assert report["counts"]["scenarios"] == 4
    assert len(report["malformed_scenarios"]) == 1
    assert report["ok"] is False


def test_traceability_linked_when_scenarios_reference_fr() -> None:
    report = analyze(GOOD)
    assert report["scenarios_referencing_fr"] == 5
    assert report["uncovered_fr"] == ["FR-006"]
    assert report["traceability"] in ("linked", "partial")


def test_traceability_absent_without_references() -> None:
    text = GOOD.replace("（FR-001）", "").replace("（FR-002）", "") \
                .replace("（FR-003）", "").replace("（FR-004）", "") \
                .replace("（FR-005）", "")
    report = analyze(text)
    assert report["scenarios_referencing_fr"] == 0
    assert report["traceability"] == "absent"
    assert report["uncovered_fr"] == report["fr_ids"]


def test_scenario_ids_follow_user_story_numbering() -> None:
    report = analyze(GOOD)
    assert report["scenario_ids"] == [
        "US1-AS1", "US1-AS2", "US2-AS1", "US2-AS2", "US2-AS3",
    ]


def test_deeper_heading_keeps_section_open() -> None:
    text = GOOD.replace("### Functional Requirements\n", "### Functional Requirements\n\n#### 分组\n")
    report = analyze(text)
    assert report["counts"]["fr"] == 6
