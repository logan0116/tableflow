#!/usr/bin/env python3
"""tableflow v0.3.0 重建脚本（002 迁移路径：重建而非原地迁移）。

流程（可重复执行、失败即停）：
1. 备份现有 data/tableflow.db 到 data/tableflow.db.bak-20261106（已有备份则保留第一份）；
2. 删除 data/tableflow.db / -wal / -shm；
3. 用新 schema 建库（row_records 复合主键 + business_changes + write_audit.origin）；
4. 依次执行三个加载脚本：load_fd_system → load_tableflow → load_specs；
5. 打印两个项目三张表的行数。

用法：
    backend/.venv/bin/python data/rebuild_v030.py
    backend/.venv/bin/python data/rebuild_v030.py --api-base http://127.0.0.1:8001

注意：加载脚本走 HTTP 写接口，运行前需确保目标后端已加载 v0.3.0 代码。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent
BACKEND_SRC = REPO_ROOT / "backend" / "src"

for path in (str(DATA_DIR), str(BACKEND_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

import httpx  # noqa: E402

import load_fd_system  # noqa: E402
import load_specs  # noqa: E402
import load_tableflow  # noqa: E402
from tableflow.db import connect_write, init_schema  # noqa: E402

DEFAULT_DB = REPO_ROOT / "data" / "tableflow.db"
DEFAULT_API_BASE = os.environ.get("TABLEFLOW_API_BASE", "http://127.0.0.1:8000")

LOADERS = [
    ("load_fd_system", load_fd_system.run),
    ("load_tableflow", load_tableflow.run),
    ("load_specs", load_specs.run),
]


def backup_db(db_file: Path, backup_file: Path | None = None) -> Path | None:
    """用 SQLite 在线备份 API 复制数据库；已有备份不覆盖（保留迁移前第一份）。"""
    if not db_file.exists():
        return None
    target = Path(backup_file) if backup_file else Path(str(db_file) + ".bak-20261106")
    if target.exists():
        print(f"备份已存在，保留：{target}")
        return target
    src = sqlite3.connect(db_file)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    print(f"已备份：{db_file} → {target}")
    return target


def remove_db(db_file: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(db_file) + suffix).unlink(missing_ok=True)


def init_db(db_file: Path) -> None:
    conn = connect_write(db_file)
    try:
        init_schema(conn)
    finally:
        conn.close()


def row_counts(db_file: Path) -> dict[str, dict[str, int]]:
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        tables = conn.execute(
            'SELECT id, project_id FROM tables ORDER BY project_id, "order", id'
        ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for table in tables:
            count = conn.execute(
                "SELECT count(*) FROM row_records WHERE table_id = ?", (table["id"],)
            ).fetchone()[0]
            result.setdefault(table["project_id"], {})[table["id"]] = count
        return result
    finally:
        conn.close()


def rebuild(
    db_file: Path,
    client: httpx.Client,
    *,
    backup: bool = True,
    backup_file: Path | None = None,
) -> dict[str, dict[str, int]]:
    """删库 → 建 schema → 三个加载脚本。重复执行得到一致结果。"""
    db_file = Path(db_file)
    if backup:
        backup_db(db_file, backup_file)
    remove_db(db_file)
    init_db(db_file)
    for name, run in LOADERS:
        print(f"→ {name}")
        run(client, strict=True)
    return row_counts(db_file)


def _print_counts(counts: dict[str, dict[str, int]]) -> None:
    total = 0
    for project_id, tables in counts.items():
        parts = [f"{table_id}={count}" for table_id, count in tables.items()]
        total += sum(tables.values())
        print(f"{project_id}: " + "  ".join(parts))
    print(f"合计 {total} 行")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="重建 tableflow v0.3.0 数据库")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="数据库路径")
    parser.add_argument(
        "--backup", type=Path, default=None,
        help="备份文件路径（缺省为 <db>.bak-20261106）",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="后端地址")
    parser.add_argument("--no-backup", action="store_true", help="跳过备份（测试用）")
    args = parser.parse_args(argv)

    try:
        with httpx.Client(base_url=args.api_base, timeout=10) as client:
            counts = rebuild(
                args.db, client, backup=not args.no_backup, backup_file=args.backup
            )
    except Exception as exc:  # noqa: BLE001 - 失败即停并给出原因
        print(f"重建失败：{exc}", file=sys.stderr)
        return 1

    print("重建完成，行数：")
    _print_counts(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
