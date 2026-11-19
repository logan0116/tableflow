#!/usr/bin/env python3
"""API key 管理 CLI（013）：签发、吊销、列出、审计查询。

用法（在 backend 目录执行）：
    .venv/bin/python scripts/tf_keys.py issue --label zhang.gong --note "前端"
    .venv/bin/python scripts/tf_keys.py revoke --id k-1a2b3c4d --by captain
    .venv/bin/python scripts/tf_keys.py list
    .venv/bin/python scripts/tf_keys.py audit --limit 20

密钥明文只在 `issue` 时打印一次；库里只留 SHA-256 摘要。签发与吊销都会落
`write_audit`（action=`key.issue` / `key.revoke`），可用 `audit` 倒查。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:  # 已安装（uv run / pip install -e）时直接导入
    from tableflow import auth
    from tableflow.config import db_path
    from tableflow.db import connect_write, init_schema
    from tableflow.errors import WriteError
except ModuleNotFoundError:  # 从仓库 backend 目录直接跑脚本
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from tableflow import auth
    from tableflow.config import db_path
    from tableflow.db import connect_write, init_schema
    from tableflow.errors import WriteError


def _print_keys(keys: list[dict]) -> None:
    if not keys:
        print("（没有 key）")
        return
    print(f"{'key_id':<12} {'状态':<6} {'label':<20} {'签发时间':<20} note")
    for key in keys:
        status = "已吊销" if key["revoked_at"] else "有效"
        print(
            f"{key['id']:<12} {status:<6} {key['label']:<20}"
            f" {key['created_at']:<20} {key['note'] or ''}"
        )


def _print_audit(rows: list[dict]) -> None:
    if not rows:
        print("（没有审计记录）")
        return
    print(f"{'id':<6} {'时间':<20} {'身份':<18} {'key_id':<12} {'action':<16} {'result':<8} target")
    for row in rows:
        print(
            f"{row['id']:<6} {row['created_at']:<20} {row['agent_id']:<18}"
            f" {(row['key_id'] or '-'):<12} {row['action']:<16} {row['result']:<8}"
            f" {row['target']}"
        )
        if row["error"]:
            print(f"       错误：{row['error']}")


def _db_option(parser: argparse.ArgumentParser) -> None:
    """--db 既可放在子命令前，也可放在子命令后（SUPPRESS 避免子命令默认值覆盖前置值）。"""
    parser.add_argument(
        "--db", type=Path, default=argparse.SUPPRESS, help="数据库路径，默认 data/tableflow.db"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="API key 管理（签发/吊销/列出/审计查询）")
    parser.add_argument("--db", type=Path, default=None, help="数据库路径，默认 data/tableflow.db")
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue", help="签发一把 key（明文只打印一次）")
    issue.add_argument("--label", required=True, help="调用者身份，写审计与负责人填充用")
    issue.add_argument("--note", default=None, help="备注（可省略）")
    issue.add_argument("--by", default="cli", help="操作者身份，落审计")
    _db_option(issue)

    revoke = sub.add_parser("revoke", help="吊销一把 key")
    revoke.add_argument("--id", required=True, help="key_id（k-xxxxxxxx）")
    revoke.add_argument("--by", default="cli", help="操作者身份，落审计")
    _db_option(revoke)

    list_cmd = sub.add_parser("list", help="列出全部 key（不含明文）")
    _db_option(list_cmd)

    audit = sub.add_parser("audit", help="查最近的写审计（含 key 标识）")
    audit.add_argument("--limit", type=int, default=20)
    _db_option(audit)

    args = parser.parse_args(argv)
    target = args.db or db_path()
    conn = connect_write(target)
    try:
        init_schema(conn)
        if args.command == "issue":
            record, raw = auth.issue_key(conn, args.label, note=args.note, by=args.by)
            print(f"key_id: {record['id']}")
            print(f"label:  {record['label']}")
            print(f"key:    {raw}")
            print("上面这把 key 只显示这一次，请立刻交给使用者保存。")
        elif args.command == "revoke":
            record = auth.revoke_key(conn, args.id, by=args.by)
            print(f"已吊销：{record['id']}（label={record['label']}，{record['revoked_at']}）")
        elif args.command == "list":
            _print_keys(auth.list_keys(conn))
        elif args.command == "audit":
            _print_audit(auth.list_audit(conn, args.limit))
    except WriteError as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
