"""042：tf-dev-implement 驱动 plan → tasks 的生成与校验。

覆盖：
- 规格标题剥离 ``Feature Specification:`` 前缀；
- 场景号沿用 ``<前缀>-US<n>-AS<m>``，与用例派生同源；
- plan.md 生成的每条实现项回链全部场景号；
- tasks.md 生成的任务覆盖全部场景号，且初始全部未勾选（因此 implement 阶段必然被拦住）；
- 覆盖率检查能报出缺失的场景号；
- 单测命令探测优先用 backend/.venv。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "tf-dev-implement" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import _tf_common as common  # noqa: E402
import tf_dev_implement as skill  # noqa: E402

SPEC = """# Feature Specification: 示例能力

## User Scenarios & Testing

### User Story 1 - 第一段能力 (Priority: P1)

1. **Given** 条件甲，**When** 动作甲，**Then** 结果甲

2. **Given** 条件乙，**When** 动作乙，**Then** 结果乙

### User Story 2 - 第二段能力 (Priority: P2)

1. **Given** 条件丙，**When** 动作丙，**Then** 结果丙
"""

TODAY = "2026-11-23"
SPEC_REL = "specs/042-example"


@pytest.fixture()
def spec_path(tmp_path: Path) -> Path:
    path = tmp_path / "spec.md"
    path.write_text(SPEC, encoding="utf-8")
    return path


def test_spec_title_strips_feature_prefix(spec_path: Path) -> None:
    assert skill.spec_title(spec_path) == "示例能力"


def test_spec_title_falls_back_to_dir_name(tmp_path: Path) -> None:
    path = tmp_path / "spec.md"
    path.write_text("没有一级标题\n", encoding="utf-8")
    assert skill.spec_title(path) == tmp_path.name


def test_scenario_ids_match_case_scheme(spec_path: Path) -> None:
    stories = common.parse_spec(spec_path)
    assert skill.scenario_ids("042-AR", stories) == [
        "042-US1-AS1",
        "042-US1-AS2",
        "042-US2-AS1",
    ]


def test_render_plan_covers_every_scenario(spec_path: Path) -> None:
    stories = common.parse_spec(spec_path)
    text = skill.render_plan("042-AR", SPEC_REL, "示例能力", stories, TODAY)
    for case_id in skill.scenario_ids("042-AR", stories):
        assert case_id in text
    assert text.startswith("# 实现计划：示例能力")
    assert f"`{SPEC_REL}/spec.md`" in text
    assert "//" not in text.split("- **规格**：")[1].splitlines()[0]


def test_render_tasks_starts_unchecked_and_covers_scenarios(spec_path: Path) -> None:
    stories = common.parse_spec(spec_path)
    text = skill.render_tasks("042-AR", SPEC_REL, "示例能力", stories, TODAY)
    for case_id in skill.scenario_ids("042-AR", stories):
        assert case_id in text

    parsed = {"checked": 0, "unchecked": []}
    for line in text.splitlines():
        if line.startswith("- [ ]"):
            parsed["unchecked"].append(line)
        elif line.startswith("- [x]"):
            parsed["checked"] += 1

    # 每个 User Story 一条，外加三条收口任务
    assert len(parsed["unchecked"]) == len(stories) + 3
    assert parsed["checked"] == 0


def test_rendered_tasks_block_implement(tmp_path: Path, spec_path: Path) -> None:
    stories = common.parse_spec(spec_path)
    tasks = tmp_path / "tasks.md"
    tasks.write_text(
        skill.render_tasks("042-AR", SPEC_REL, "示例能力", stories, TODAY), encoding="utf-8"
    )
    result = common.parse_tasks(tasks)
    assert result["checked"] == 0
    assert len(result["unchecked"]) == len(stories) + 3


def test_coverage_missing_reports_gap(tmp_path: Path, spec_path: Path) -> None:
    stories = common.parse_spec(spec_path)
    ids = skill.scenario_ids("042-AR", stories)

    full = tmp_path / "full.md"
    full.write_text(skill.render_plan("042-AR", SPEC_REL, "示例能力", stories, TODAY), encoding="utf-8")
    assert skill.coverage_missing(full, ids) == []

    partial = tmp_path / "partial.md"
    partial.write_text("只有 042-US1-AS1\n", encoding="utf-8")
    assert skill.coverage_missing(partial, ids) == ["042-US1-AS2", "042-US2-AS1"]


def test_detect_test_cmd_prefers_backend_venv() -> None:
    command, cwd = skill.detect_test_cmd(REPO_ROOT)
    if (REPO_ROOT / "backend" / ".venv" / "bin" / "python").exists():
        assert "pytest" in command
        assert cwd == REPO_ROOT / "backend"
    else:  # pragma: no cover - 本仓库有 venv，此分支仅作环境兜底
        assert cwd == REPO_ROOT
