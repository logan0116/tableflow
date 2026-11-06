#!/usr/bin/env python3
"""样例数据写入 CLI（v0 唯一入数路径）。

用法：
    uv run python scripts/seed_data.py --seed ../data/seed.example.json
    uv run python scripts/seed_data.py --projects 20 --rows 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tableflow.config import db_path
from tableflow.seed import SeedError, build_generated, seed_from_file, write_seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="写入样例数据（全量替换三张表）")
    parser.add_argument("--seed", type=Path, help="样例 JSON 文件")
    parser.add_argument("--projects", type=int, help="生成项目数（规模数据）")
    parser.add_argument("--tables", type=int, default=1, help="每个项目的表格数（规模数据）")
    parser.add_argument("--rows", type=int, help="每张表的行数（规模数据）")
    parser.add_argument("--db", type=Path, default=None, help="数据库路径，默认 data/tableflow.db")
    args = parser.parse_args(argv)

    if (args.projects is None) != (args.rows is None):
        parser.error("--projects 与 --rows 必须同时给出")
    if args.seed is None and args.projects is None:
        parser.error("必须给出 --seed 或 --projects/--rows")

    target = args.db or db_path()

    try:
        if args.projects is not None:
            counts = write_seed(target, build_generated(args.projects, args.tables, args.rows))
        else:
            counts = seed_from_file(target, args.seed)
    except (SeedError, FileNotFoundError) as exc:
        print(f"写入失败：{exc}", file=sys.stderr)
        return 1

    print(f"数据库：{target}")
    print(f"写入：项目 {counts['projects']} / 表格 {counts['tables']} / 字段 {counts['fields']} / 行 {counts['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
