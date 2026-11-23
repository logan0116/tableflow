"""v0.8.0 验收映射自检：场景↔测试双向对得上。

- 每份规格里的每条验收场景，都必须在 `acceptance_manifest.COVERED` 里有条目；
- 映射里引用的每个 `文件::函数` 都必须真实存在；
- 不允许映射到已删除的技能测试。

这份检查让「用例通过」有据可查：`tf-test-implement` 记录某条用例 pass 时，
证据就是这里映射到的测试。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / "backend" / "tests"
SRC = REPO_ROOT / "backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tableflow.spec_structure import analyze_file  # noqa: E402

from acceptance_manifest import COVERED  # noqa: E402

SPEC_NUMS = tuple(f"{n:03d}" for n in range(33, 43))


def _scenario_ids() -> dict[str, str]:
    """性况场景号 -> 来源规格目录名。"""
    out: dict[str, str] = {}
    for num in SPEC_NUMS:
        matches = sorted((REPO_ROOT / "specs").glob(f"{num}-*/spec.md"))
        assert matches, f"找不到规格 {num}"
        for path in matches:
            for sid in analyze_file(path)["scenario_ids"]:
                out[f"{num}-{sid}"] = path.parent.name
    return out


def _defined_tests() -> dict[str, set[str]]:
    """文件名 -> 该文件里的测试函数名集合。"""
    out: dict[str, set[str]] = {}
    for path in TESTS.glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out[path.name] = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }
    return out


def test_every_scenario_has_a_mapping() -> None:
    scenarios = _scenario_ids()
    missing = sorted(set(scenarios) - set(COVERED))
    assert missing == [], f"以下场景没有映射到测试：{missing}"


def test_no_mapping_without_scenario() -> None:
    scenarios = _scenario_ids()
    extra = sorted(set(COVERED) - set(scenarios))
    assert extra == [], f"映射里有规格中不存在的场景：{extra}"


def test_every_mapped_test_exists() -> None:
    defined = _defined_tests()
    problems: list[str] = []
    for case_id, refs in COVERED.items():
        if not refs:
            problems.append(f"{case_id} 没有引用任何测试")
            continue
        for ref in refs:
            file_name, _, func = ref.partition("::")
            if file_name not in defined:
                problems.append(f"{case_id} -> {file_name} 不存在")
            elif func not in defined[file_name]:
                problems.append(f"{case_id} -> {file_name}::{func} 不存在")
    assert problems == [], "映射指向了不存在的测试：" + "；".join(problems)


def test_mapping_covers_all_ten_specs() -> None:
    per_spec = {num: 0 for num in SPEC_NUMS}
    for case_id in COVERED:
        per_spec[case_id[:3]] += 1
    empty = [num for num, count in per_spec.items() if count == 0]
    assert empty == [], f"这些规格没有任何映射：{empty}"
