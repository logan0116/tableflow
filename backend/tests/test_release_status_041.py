"""041 US2：发布就绪报告的判定口径（board@5）。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "tf-release-status" / "scripts"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import tf_release_status  # noqa: E402

ALL_DONE = {
    "版本需求设计": "done", "测试设计": "done", "开发": "done",
    "开发验收": "done", "测试": "done", "测试验收": "done",
}
BLOCKED = {**ALL_DONE, "开发": "todo", "开发验收": "todo",
           "测试": "todo", "测试验收": "todo"}


def test_all_nodes_done_reports_releasable() -> None:
    verdict, reason = tf_release_status.verdict("planned", ALL_DONE)
    assert verdict == "可发布"
    assert "六节点全部 done" in reason


def test_blocked_version_lists_unfinished_nodes() -> None:
    verdict, reason = tf_release_status.verdict("planned", BLOCKED)
    assert verdict == "不可发布"
    for name in ("开发", "开发验收", "测试", "测试验收"):
        assert f"{name}=todo" in reason


def test_dropped_version_reports_terminated() -> None:
    verdict, reason = tf_release_status.verdict("dropped", BLOCKED)
    assert verdict == "已终止"
    assert "不发布" in reason


def test_every_check_carries_its_basis() -> None:
    """结论里的每个未完成节点都带实际取值，不是只说「未完成」。"""
    _verdict, reason = tf_release_status.verdict("planned", BLOCKED)
    assert reason.count("=") >= 4
