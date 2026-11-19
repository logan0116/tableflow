#!/usr/bin/env python3
"""契约校验与原子写（V061-03修复）。

用法（在仓库根目录或backend目录执行）：
    python3 backend/scripts/check_contracts.py                 # 校验board@1与board@2
    python3 backend/scripts/check_contracts.py --pre-write specs/011-bug-table/board@2.yaml \\
        < board@2.yaml.new                                    # 校验通过才原子替换

退出码：0=通过；1=有解析/重复键/结构问题（且未写文件）。
编辑契约的规矩：先写临时文件，再用`--pre-write`落盘，或手改后立刻跑本脚本。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR / "src"))

from tableflow.contracts import (  # noqa: E402
    ContractError,
    check_contract_pair,
    write_contract_atomic,
)

DEFAULT_CONTRACTS = (
    REPO_ROOT / "specs" / "008-board-contract" / "board@1.yaml",
    REPO_ROOT / "specs" / "011-bug-table" / "board@2.yaml",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验契约YAML（解析/重复键/结构），可选原子写")
    parser.add_argument("--contracts", nargs="+", default=[str(p) for p in DEFAULT_CONTRACTS],
                        help="要校验的契约路径（默认board@1与board@2）")
    parser.add_argument("--pre-write", metavar="TARGET",
                        help="从stdin读新内容，校验通过后原子替换TARGET；失败不写")
    args = parser.parse_args(argv)

    if args.pre_write:
        text = sys.stdin.read()
        try:
            write_contract_atomic(args.pre_write, text)
        except ContractError as exc:
            print(f"拒绝写入：{exc}", file=sys.stderr)
            return 1
        print(f"已原子写入：{args.pre_write}（校验通过）")
        return 0

    paths = [Path(p) for p in args.contracts]
    issues: list[str] = []
    if len(paths) == 2 and paths == list(DEFAULT_CONTRACTS):
        issues = check_contract_pair(paths[0], paths[1])
    else:
        from tableflow.contracts import check_contract

        for path in paths:
            issues += [f"{path}：{issue}" for issue in check_contract(path)]
    if issues:
        for issue in issues:
            print(f"[问题] {issue}", file=sys.stderr)
        return 1
    for path in paths:
        print(f"[OK] {path}")
    print("契约校验通过：YAML可解析、无重复键、结构完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
