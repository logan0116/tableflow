"""034 US1：拆分动作的留痕格式与前置。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "tf-lifecycle" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import tf_lifecycle  # noqa: E402

AT = "2026-11-23T20:00:00+08:00"


def test_split_log_records_time_clauses_and_target() -> None:
    line = tf_lifecycle.build_split_log("", AT, "US3、US4", "044-AR")
    assert line == f"{AT} 移交 US3、US4 -> 044-AR"


def test_split_log_appends_without_losing_history() -> None:
    first = tf_lifecycle.build_split_log("", AT, "US3", "044-AR")
    second = tf_lifecycle.build_split_log(first, AT, "US4", "045-AR")
    assert second.splitlines() == [
        f"{AT} 移交 US3 -> 044-AR",
        f"{AT} 移交 US4 -> 045-AR",
    ]


def test_split_log_is_parseable_by_lifecycle_report() -> None:
    """写进去的格式必须能被追溯接口解析回来。"""
    src = (REPO_ROOT / "backend" / "src" / "tableflow" / "spec_lifecycle.py").read_text(encoding="utf-8")
    assert "SPLIT_LINE_RE" in src
    line = tf_lifecycle.build_split_log("", AT, "US3", "044-AR")
    import re
    match = re.match(r"^(\S+)\s+移交\s+(.+?)\s*->\s*(\S+)\s*$", line)
    assert match and match.group(3) == "044-AR"


def test_split_keeps_origin_alive() -> None:
    """拆分不是终态：原需求继续存在，记录里只有移交清单与承接方。"""
    line = tf_lifecycle.build_split_log("", AT, "US3", "044-AR")
    assert "dropped" not in line
    assert "-> 044-AR" in line
