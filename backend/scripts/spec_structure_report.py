#!/usr/bin/env python3
"""规格结构差距报告（039）：逐份核对章节完整性与结构下限。

用法：

    python3 backend/scripts/spec_structure_report.py            # 全部
    python3 backend/scripts/spec_structure_report.py --only 039 # 只看某几份
    python3 backend/scripts/spec_structure_report.py --strict   # 有缺口时退出码 1

输出三层：逐份明细、缺口分类统计、需求与场景的追溯情况。追溯当前只统计不做门禁
（现有规格大多未建立 FR 与场景的互相引用，见 039 的遗留说明）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from tableflow.spec_structure import FLOOR, REQUIRED_SECTIONS, analyze_file  # noqa: E402

SECTION_LABEL = {
    "user_scenarios": "User Scenarios",
    "functional_requirements": "Functional Requirements",
    "edge_cases": "Edge Cases",
    "success_criteria": "Success Criteria",
    "key_entities": "Key Entities",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=[], help="只处理这些编号前缀，如 039")
    parser.add_argument("--strict", action="store_true", help="有结构缺口时返回 1")
    args = parser.parse_args()

    specs = sorted((REPO_ROOT / "specs").glob("*/spec.md"))
    if args.only:
        specs = [p for p in specs if p.parent.name.split("-", 1)[0] in set(args.only)]

    rows = []
    for path in specs:
        report = analyze_file(path)
        rows.append((path.parent.name, report))

    print(f"{'规格':<34}{'行':>5}{'US':>4}{'场景':>5}{'FR':>4}{'边界':>5}  缺口")
    print("-" * 86)
    gaps: dict[str, int] = {}
    for name, report in rows:
        counts = report["counts"]
        problems: list[str] = []
        for key in report["missing_sections"]:
            problems.append(f"缺{SECTION_LABEL.get(key, key)}")
            gaps[f"缺{SECTION_LABEL.get(key, key)}"] = gaps.get(f"缺{SECTION_LABEL.get(key, key)}", 0) + 1
        for key, value in report["below_floor"].items():
            label = f"{key}低于下限({value}/{FLOOR[key]})"
            problems.append(label)
            gaps[label] = gaps.get(label, 0) + 1
        if report["malformed_scenarios"]:
            label = f"有 {len(report['malformed_scenarios'])} 条场景不是 Given/When/Then"
            problems.append(label)
            gaps[label] = gaps.get(label, 0) + 1
        print(
            f"{name:<34}{report['lines']:>5}{counts['us']:>4}{counts['scenarios']:>5}"
            f"{counts['fr']:>4}{counts['edge']:>5}  {'、'.join(problems) or '—'}"
        )

    print()
    print(f"合计 {len(rows)} 份；达标 {sum(1 for _, r in rows if r['ok'])} 份")
    if gaps:
        print("\n缺口分类：")
        for label, count in sorted(gaps.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>3} 份  {label}")

    traced = [name for name, report in rows if report["traceability"] != "absent"]
    print(f"\n需求与场景追溯：{len(traced)}/{len(rows)} 份已建立引用")
    if len(traced) < len(rows):
        print("  （未建立引用的规格只能靠章节存在性判定，无法回答「哪条需求被哪些场景验证」）")

    if args.strict and any(not report["ok"] for _, report in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
