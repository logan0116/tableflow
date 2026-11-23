"""规格结构分析（039）：章节完整性、结构下限、需求与场景的追溯关系。

本模块不连数据库、不读仓库目录，只对一段 `spec.md` 文本做纯解析，便于单测与
在脚本/技能里复用。

口径（`specs/019-test-contract/board@5.yaml` 与 `specs/039-spec-structure/spec.md`）：

- 章节：`User Scenarios & Testing`、`Functional Requirements`、`Edge Cases` 必备，
  `Success Criteria`、`Key Entities` 建议具备；
- 下限：User Story ≥ 2、验收场景 ≥ 5、功能需求 ≥ 6、边界情况 ≥ 3；
- 追溯：场景可以引用需求（`（FR-001）`），需求也可以列出场景（`（场景：US1-AS1）`）；
  两侧都未建立引用时判为「未建立追溯」；
- 可判定性：User Story 块内的编号项若不是 `1. **Given** ... **When** ... **Then** ...`
  形式，计入 `malformed_scenarios`——它们不会被派生为用例，属于静默丢失。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HEAD_RE = re.compile(r"^(#{1,4})\s+(.*?)\s*$")
STORY_RE = re.compile(r"^###\s+User Story\s+(\d+)\b(.*)$", re.I)
SCENARIO_RE = re.compile(
    r"^\s*(\d+)\.\s+\*\*Given\*\*\s*(.+?)\s*\*\*When\*\*\s*(.+?)\s*\*\*Then\*\*\s*(.+?)\s*$"
)
NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+\S")
FR_RE = re.compile(r"^\s*[-*]\s+\*\*FR-(\d+)\*\*", re.I)
BULLET_RE = re.compile(r"^\s*[-*]\s+\S")
FR_REF_RE = re.compile(r"FR-\d+", re.I)
SCENARIO_REF_RE = re.compile(r"US\d+-AS\d+", re.I)

FLOOR = {"us": 2, "scenarios": 5, "fr": 6, "edge": 3}

# 章节标题 -> 语义键（小写匹配）
SECTION_KEYS = {
    "user scenarios & testing": "user_scenarios",
    "requirements": "requirements",
    "functional requirements": "functional_requirements",
    "edge cases": "edge_cases",
    "success criteria": "success_criteria",
    "key entities": "key_entities",
}

REQUIRED_SECTIONS = ("user_scenarios", "functional_requirements", "edge_cases")
OPTIONAL_SECTIONS = ("success_criteria", "key_entities")


def _section_key(title: str) -> str | None:
    low = title.strip().lower().rstrip("：:")
    for prefix, key in SECTION_KEYS.items():
        if low == prefix or low.startswith(prefix):
            return key
    return None


def analyze(text: str) -> dict[str, Any]:
    """解析一份规格文本，返回结构指标与追溯情况。"""
    lines = text.splitlines()
    sections: dict[str, bool] = {key: False for key in SECTION_KEYS.values()}

    us_count = 0
    scenarios: list[dict[str, Any]] = []
    malformed: list[int] = []          # 编号但非 Given/When/Then 的行号
    fr_ids: list[str] = []
    edge = sc = 0
    fr_linked: set[str] = set()
    scenario_linked = 0
    scenario_refs: set[str] = set()

    section: str | None = None
    section_level = 0
    in_story = False

    for lineno, line in enumerate(lines, start=1):
        head = HEAD_RE.match(line)
        if head:
            level, title = len(head.group(1)), head.group(2)
            if section is not None and level <= section_level:
                section, section_level = None, 0
            key = _section_key(title)
            if key:
                sections[key] = True
                section, section_level = key, level
            story = STORY_RE.match(line)
            in_story = story is not None
            if story:
                us_count += 1
            continue

        if in_story:
            match = SCENARIO_RE.match(line)
            if match:
                scenarios.append(
                    {"seq": int(match.group(1)), "given": match.group(2).strip(),
                     "when": match.group(3).strip(), "then": match.group(4).strip()}
                )
                refs = {ref.upper() for ref in FR_REF_RE.findall(line)}
                if refs:
                    fr_linked |= refs
                    scenario_linked += 1
                scenario_refs |= {ref.upper() for ref in SCENARIO_REF_RE.findall(line)}
                continue
            if NUMBERED_RE.match(line):
                malformed.append(lineno)
                continue

        if section == "functional_requirements" and FR_RE.match(line):
            fr_ids.append(f"FR-{FR_RE.match(line).group(1)}")
            continue
        if section == "edge_cases" and BULLET_RE.match(line):
            edge += 1
            continue
        if section == "success_criteria" and BULLET_RE.match(line):
            sc += 1

    scenario_ids = _scenario_ids(lines)

    counts = {"us": us_count, "scenarios": len(scenarios), "fr": len(fr_ids), "edge": edge}
    short = {key: counts[key] for key in FLOOR if counts[key] < FLOOR[key]}
    missing_sections = [key for key in REQUIRED_SECTIONS if not sections[key]]

    uncovered_fr = sorted(set(fr_ids) - {ref.upper() for ref in fr_linked})
    return {
        "lines": len(lines),
        "counts": counts,
        "success_criteria": sc,
        "sections": sections,
        "missing_sections": missing_sections,
        "below_floor": short,
        "fr_ids": fr_ids,
        "scenario_ids": scenario_ids,
        "malformed_scenarios": malformed,
        "scenarios_referencing_fr": scenario_linked,
        "fr_covered_by_scenario": sorted(fr_linked),
        "uncovered_fr": uncovered_fr,
        "traceability": (
            "linked" if scenario_linked and len(uncovered_fr) < len(fr_ids) else
            ("partial" if scenario_linked else "absent")
        ),
        "ok": not short and not missing_sections and not malformed,
    }


def _scenario_ids(lines: list[str]) -> list[str]:
    """按 User Story 序号生成场景 id。"""
    out: list[str] = []
    current: int | None = None
    for line in lines:
        story = STORY_RE.match(line)
        if story:
            current = int(story.group(1))
            continue
        if line.startswith("### ") and not STORY_RE.match(line):
            current = None
            continue
        if current is None:
            continue
        match = SCENARIO_RE.match(line)
        if match:
            out.append(f"US{current}-AS{int(match.group(1))}")
    return out


def analyze_file(path: Path) -> dict[str, Any]:
    return analyze(path.read_text(encoding="utf-8"))
