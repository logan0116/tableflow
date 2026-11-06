"""样例数据：校验、全量写入、规模数据生成。

v0 不迁移存量数据，本模块只服务于演示与验收（宪法原则 I、VII）。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .db import connect_write, init_schema

KNOWN_TYPES = {"text", "number", "datetime", "enum"}


class SeedError(ValueError):
    """样例数据不合法。"""


def load_seed(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_seed(data: dict[str, Any]) -> None:
    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        raise SeedError("projects 必须是非空数组")

    project_ids: set[str] = set()
    for project in projects:
        pid = project.get("id")
        if not isinstance(pid, str) or not pid:
            raise SeedError("项目缺少 id")
        if pid in project_ids:
            raise SeedError(f"项目 id 重复：{pid}")
        project_ids.add(pid)
        if not isinstance(project.get("name"), str) or not project["name"]:
            raise SeedError(f"项目 {pid} 缺少 name")

        field_ids: set[str] = set()
        for field in project.get("fields", []):
            fid = field.get("id")
            if not isinstance(fid, str) or not fid:
                raise SeedError(f"项目 {pid} 的字段缺少 id")
            if fid in field_ids:
                raise SeedError(f"项目 {pid} 字段 id 重复：{fid}")
            field_ids.add(fid)
            if field.get("type") not in KNOWN_TYPES:
                raise SeedError(f"字段 {fid} 的 type 非法：{field.get('type')}")
            if not isinstance(field.get("order"), int):
                raise SeedError(f"字段 {fid} 的 order 必须是整数")
            if field.get("visible", 1) not in (0, 1):
                raise SeedError(f"字段 {fid} 的 visible 只能是 0 或 1")
            options = field.get("options")
            if options is not None:
                if not isinstance(options, list):
                    raise SeedError(f"字段 {fid} 的 options 必须是数组")
                for option in options:
                    if not isinstance(option, dict) or "value" not in option or "label" not in option:
                        raise SeedError(f"字段 {fid} 的 options 项必须含 value 与 label")

        row_ids: set[str] = set()
        for row in project.get("rows", []):
            rid = row.get("id")
            if not isinstance(rid, str) or not rid:
                raise SeedError(f"项目 {pid} 的行缺少 id")
            if rid in row_ids:
                raise SeedError(f"项目 {pid} 行 id 重复：{rid}")
            row_ids.add(rid)
            values = row.get("values", {})
            if not isinstance(values, dict):
                raise SeedError(f"行 {rid} 的 values 必须是对象")
            unknown = set(values) - field_ids
            if unknown:
                raise SeedError(f"行 {rid} 含未知字段键：{sorted(unknown)}")


def write_seed(db_file: Path, data: dict[str, Any]) -> dict[str, int]:
    """全量替换三张表后写入。先校验，校验失败不落库。"""
    validate_seed(data)
    conn = connect_write(db_file)
    try:
        init_schema(conn)
        conn.execute("DELETE FROM row_records")
        conn.execute("DELETE FROM fields")
        conn.execute("DELETE FROM projects")

        counts = {"projects": 0, "fields": 0, "rows": 0}
        for project in data["projects"]:
            conn.execute(
                "INSERT INTO projects (id, name) VALUES (?, ?)",
                (project["id"], project["name"]),
            )
            counts["projects"] += 1
            for field in project.get("fields", []):
                options = field.get("options")
                conn.execute(
                    'INSERT INTO fields (id, table_id, name, type, options, "order", visible)'
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        field["id"],
                        project["id"],
                        field["name"],
                        field["type"],
                        json.dumps(options, ensure_ascii=False) if options is not None else None,
                        field["order"],
                        field.get("visible", 1),
                    ),
                )
                counts["fields"] += 1
            for row in project.get("rows", []):
                conn.execute(
                    "INSERT INTO row_records (id, table_id, data) VALUES (?, ?, ?)",
                    (
                        row["id"],
                        project["id"],
                        json.dumps(row.get("values", {}), ensure_ascii=False),
                    ),
                )
                counts["rows"] += 1
        conn.commit()
        return counts
    finally:
        conn.close()


def seed_from_file(db_file: Path, seed_file: Path) -> dict[str, int]:
    return write_seed(db_file, load_seed(seed_file))


def build_generated(project_count: int, row_count: int) -> dict[str, Any]:
    """生成规模数据，用于 SC-005（20项目 / 500行）验证。"""
    base = datetime(2026, 11, 6, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    statuses = [
        {"value": "todo", "label": "待办"},
        {"value": "doing", "label": "进行中"},
        {"value": "done", "label": "已完成"},
    ]
    data: dict[str, Any] = {"projects": []}
    for p in range(project_count):
        pid = f"gen-{p:03d}"
        fields = [
            {"id": f"{pid}-f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
            {"id": f"{pid}-f2", "name": "状态", "type": "enum", "options": statuses, "order": 2, "visible": 1},
            {"id": f"{pid}-f3", "name": "进度", "type": "number", "options": None, "order": 3, "visible": 1},
            {"id": f"{pid}-f4", "name": "截止", "type": "datetime", "options": None, "order": 4, "visible": 1},
        ]
        rows = []
        for r in range(row_count):
            due = base + timedelta(days=r % 30, hours=r % 8)
            rows.append(
                {
                    "id": f"{pid}-r{r:04d}",
                    "values": {
                        f"{pid}-f1": f"任务{r:04d}",
                        f"{pid}-f2": statuses[r % len(statuses)]["value"],
                        f"{pid}-f3": r % 100,
                        f"{pid}-f4": due.isoformat(),
                    },
                }
            )
        data["projects"].append({"id": pid, "name": f"生成项目{p:03d}", "fields": fields, "rows": rows})
    return data
