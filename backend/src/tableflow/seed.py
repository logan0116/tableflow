"""样例数据：校验、全量写入、规模数据生成。

v0 不迁移存量数据，本模块只服务于演示与验收（宪法原则 I、VII）。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .db import connect_write, init_schema

KNOWN_TYPES = {"text", "number", "datetime", "enum", "relation", "computed"}
TONES = {"neutral", "info", "success", "warning", "danger"}


class SeedError(ValueError):
    """样例数据不合法。"""


def load_seed(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_seed(data: dict[str, Any]) -> None:
    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        raise SeedError("projects 必须是非空数组")

    seen: set[str] = set()
    for project in projects:
        pid = project.get("id")
        if not isinstance(pid, str) or not pid:
            raise SeedError("项目缺少 id")
        if pid in seen:
            raise SeedError(f"id 重复：{pid}")
        seen.add(pid)
        if not isinstance(project.get("name"), str) or not project["name"]:
            raise SeedError(f"项目 {pid} 缺少 name")

        tables = project.get("tables", [])
        if not isinstance(tables, list) or not tables:
            raise SeedError(f"项目 {pid} 至少要有一张表格")
        table_ids = {table.get("id") for table in tables}

        for table in tables:
            tid = table.get("id")
            if not isinstance(tid, str) or not tid:
                raise SeedError(f"项目 {pid} 的表格缺少 id")
            if tid in seen:
                raise SeedError(f"id 重复：{tid}")
            seen.add(tid)
            if not isinstance(table.get("name"), str) or not table["name"]:
                raise SeedError(f"表格 {tid} 缺少 name")
            if not isinstance(table.get("order", 0), int):
                raise SeedError(f"表格 {tid} 的 order 必须是整数")

            field_ids: set[str] = set()
            for field in table.get("fields", []):
                fid = field.get("id")
                if not isinstance(fid, str) or not fid:
                    raise SeedError(f"表格 {tid} 的字段缺少 id")
                if fid in seen:
                    raise SeedError(f"id 重复：{fid}")
                seen.add(fid)
                field_ids.add(fid)
                if field.get("type") not in KNOWN_TYPES:
                    raise SeedError(f"字段 {fid} 的 type 非法：{field.get('type')}")
                if not isinstance(field.get("order"), int):
                    raise SeedError(f"字段 {fid} 的 order 必须是整数")
                if field.get("visible", 1) not in (0, 1):
                    raise SeedError(f"字段 {fid} 的 visible 只能是 0 或 1")
                options = field.get("options")
                if field.get("type") == "enum":
                    if isinstance(options, dict):
                        items = options.get("items")
                    else:
                        items = options
                    if not isinstance(items, list) or not items:
                        raise SeedError(f"字段 {fid} 的 enum options 必须是非空数组")
                    seen_values: set[str] = set()
                    for option in items:
                        if not isinstance(option, dict) or "value" not in option or "label" not in option:
                            raise SeedError(f"字段 {fid} 的 options 项必须含 value 与 label")
                        if not isinstance(option["value"], str) or not option["value"]:
                            raise SeedError(f"字段 {fid} 的 options.value 必须是非空字符串")
                        if option["value"] in seen_values:
                            raise SeedError(f"字段 {fid} 的 options.value 重复：{option['value']}")
                        seen_values.add(option["value"])
                        if option.get("tone") not in TONES:
                            raise SeedError(f"字段 {fid} 的 options 项必须含合法 tone")
                if field.get("type") == "relation":
                    if not isinstance(options, dict) or not isinstance(options.get("table_id"), str):
                        raise SeedError(f"字段 {fid} 的 relation options 必须含 table_id")
                    if options["table_id"] not in table_ids:
                        raise SeedError(f"字段 {fid} 的关联目标不在同项目内：{options['table_id']}")

            row_ids: set[str] = set()
            relation_ids = {
                field["id"] for field in table.get("fields", []) if field.get("type") == "relation"
            }
            for row in table.get("rows", []):
                rid = row.get("id")
                if not isinstance(rid, str) or not rid:
                    raise SeedError(f"表格 {tid} 的行缺少 id")
                if rid in seen:
                    raise SeedError(f"id 重复：{rid}")
                seen.add(rid)
                row_ids.add(rid)
                values = row.get("values", {})
                if not isinstance(values, dict):
                    raise SeedError(f"行 {rid} 的 values 必须是对象")
                unknown = set(values) - field_ids
                if unknown:
                    raise SeedError(f"行 {rid} 含未知字段键：{sorted(unknown)}")
                for key in relation_ids & set(values):
                    value = values[key]
                    if value is None:
                        continue
                    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                        raise SeedError(f"行 {rid} 的关联字段 {key} 必须是字符串数组")


def write_seed(db_file: Path, data: dict[str, Any]) -> dict[str, int]:
    """全量替换业务四张表后写入。先校验，校验失败不落库。"""
    validate_seed(data)
    conn = connect_write(db_file)
    try:
        init_schema(conn)
        conn.execute("DELETE FROM computed_values")
        conn.execute("DELETE FROM business_changes")
        conn.execute("DELETE FROM row_records")
        conn.execute("DELETE FROM fields")
        conn.execute("DELETE FROM tables")
        conn.execute("DELETE FROM projects")

        counts = {"projects": 0, "tables": 0, "fields": 0, "rows": 0}
        for project in data["projects"]:
            conn.execute(
                "INSERT INTO projects (id, name) VALUES (?, ?)",
                (project["id"], project["name"]),
            )
            counts["projects"] += 1
            for table in project.get("tables", []):
                conn.execute(
                    'INSERT INTO tables (id, project_id, name, "order") VALUES (?, ?, ?, ?)',
                    (table["id"], project["id"], table["name"], table.get("order", 0)),
                )
                counts["tables"] += 1
                for field in table.get("fields", []):
                    options = field.get("options")
                    conn.execute(
                        'INSERT INTO fields (id, table_id, name, type, options, "order", visible)'
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            field["id"],
                            table["id"],
                            field["name"],
                            field["type"],
                            json.dumps(options, ensure_ascii=False) if options is not None else None,
                            field["order"],
                            field.get("visible", 1),
                        ),
                    )
                    counts["fields"] += 1
                for row in table.get("rows", []):
                    conn.execute(
                        "INSERT INTO row_records (id, table_id, data) VALUES (?, ?, ?)",
                        (
                            row["id"],
                            table["id"],
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


def build_generated(project_count: int, tables_per_project: int, row_count: int) -> dict[str, Any]:
    """生成规模数据，用于 SC-006（20项目 / 每项目10表 / 单表500行）验证。"""
    base = datetime(2026, 11, 6, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    statuses = [
        {"value": "todo", "label": "待办", "tone": "neutral"},
        {"value": "doing", "label": "进行中", "tone": "info"},
        {"value": "done", "label": "已完成", "tone": "success"},
    ]
    data: dict[str, Any] = {"projects": []}
    for p in range(project_count):
        pid = f"gen-{p:03d}"
        tables = []
        for t in range(tables_per_project):
            tid = f"{pid}-t{t:02d}"
            fields = [
                {"id": f"{tid}-f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                {"id": f"{tid}-f2", "name": "状态", "type": "enum", "options": statuses, "order": 2, "visible": 1},
                {"id": f"{tid}-f3", "name": "进度", "type": "number", "options": None, "order": 3, "visible": 1},
                {"id": f"{tid}-f4", "name": "截止", "type": "datetime", "options": None, "order": 4, "visible": 1},
            ]
            rows = []
            for r in range(row_count):
                due = base + timedelta(days=r % 30, hours=r % 8)
                rows.append(
                    {
                        "id": f"{tid}-r{r:04d}",
                        "values": {
                            f"{tid}-f1": f"任务{r:04d}",
                            f"{tid}-f2": statuses[r % len(statuses)]["value"],
                            f"{tid}-f3": r % 100,
                            f"{tid}-f4": due.isoformat(),
                        },
                    }
                )
            tables.append(
                {"id": tid, "name": f"表{t:02d}", "order": t, "fields": fields, "rows": rows}
            )
        data["projects"].append({"id": pid, "name": f"生成项目{p:03d}", "tables": tables})
    return data
