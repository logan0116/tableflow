"""独立需求生命周期校验（034）：拆分与放弃。

契约 `specs/019-test-contract/board@5.yaml` 的相关规则：

- `rules.spec_terminal_states` 终态只有 accepted 与 dropped；
- `rules.spec_drop` 放弃须同时给出理由与时间，且必须先摘除版本关联；
- `rules.spec_drop_immutable` dropped 不可回退，已放弃的规格不得新开依赖需求；
- `rules.spec_split` / `rules.spec_split_not_terminal` 拆分只在未 accepted 时允许，
  且不是终态。

识别口径与其它模块一致：不依赖表 id。独立需求表按 `验收状态` 的枚举值域识别
（board@5 前是三元域，迁移未完成的项目仍按三元识别）；版本表按 025 的六节点识别；
依赖需求表按它指向独立需求的关系识别。
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import version_stage
from .errors import WriteError

# board@5 前是三元域，迁移未完成的项目仍按三元识别
ACCEPTANCE_DOMAINS = frozenset({
    frozenset({"pending", "accepted", "rejected", "dropped"}),
    frozenset({"pending", "accepted", "rejected"}),
})

DROP_REASON_NAME = "放弃理由"
DROPPED_AT_NAME = "放弃时间"
SPLIT_LOG_NAME = "拆分记录"


def _loads(raw: Any) -> Any:
    import json

    if raw is None or not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _enum_values(field: sqlite3.Row) -> frozenset[str]:
    options = _loads(field["options"])
    items = options.get("items") if isinstance(options, dict) else options
    if not isinstance(items, list):
        return frozenset()
    return frozenset(
        item.get("value")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("value"), str)
    )


def _table_fields(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        'SELECT id, name, type, options, "order" FROM fields WHERE table_id = ?',
        (table_id,),
    ).fetchall()
    return {row["id"]: row for row in rows}


def _target_table_id(field: sqlite3.Row) -> str | None:
    options = _loads(field["options"])
    target = options.get("table_id") if isinstance(options, dict) else None
    return target if isinstance(target, str) else None


def _acceptance_field(fields: dict[str, sqlite3.Row]) -> sqlite3.Row | None:
    candidates = [
        field
        for field in fields.values()
        if field["type"] == "enum" and _enum_values(field) in ACCEPTANCE_DOMAINS
    ]
    return candidates[0] if len(candidates) == 1 else None


def _by_name(fields: dict[str, sqlite3.Row], name: str) -> sqlite3.Row | None:
    return next((field for field in fields.values() if field["name"] == name), None)


def _version_tables(conn: sqlite3.Connection) -> list[tuple[str, dict[str, sqlite3.Row]]]:
    out: list[tuple[str, dict[str, sqlite3.Row]]] = []
    for row in conn.execute("SELECT id FROM tables").fetchall():
        table_id = row["id"]
        fields = _table_fields(conn, table_id)
        if version_stage.stage_nodes(fields) is not None:
            out.append((table_id, fields))
    return out


def _versions_holding(conn: sqlite3.Connection, spec_id: str) -> list[str]:
    """该独立需求当前被哪些版本持有。"""
    holders: list[str] = []
    for version_table_id, version_fields in _version_tables(conn):
        relation = next(
            (
                field
                for field in version_fields.values()
                if field["type"] == "relation"
                and _target_table_id(field)
                and _acceptance_field(_table_fields(conn, _target_table_id(field) or ""))
                is not None
            ),
            None,
        )
        if relation is None:
            continue
        for row in conn.execute(
            "SELECT id, data FROM row_records WHERE table_id = ?", (version_table_id,)
        ).fetchall():
            values = _loads(row["data"]) or {}
            if spec_id in (values.get(relation["id"]) or []):
                holders.append(row["id"])
    return sorted(set(holders))


def _validate_indep(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    merged: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    acceptance = _acceptance_field(fields)
    if acceptance is None:
        return
    old = previous.get(acceptance["id"])
    new = merged.get(acceptance["id"])

    if old == "dropped" and new != "dropped":
        raise WriteError(
            f"dropped 是终态：独立需求 {row_id} 已放弃，不能改回 {new or '空'}；"
            "要重新做这项能力，请新建独立需求"
        )

    if new == "dropped" and old != "dropped":
        reason_field = _by_name(fields, DROP_REASON_NAME)
        at_field = _by_name(fields, DROPPED_AT_NAME)
        missing: list[str] = []
        if reason_field is None or not str(merged.get(reason_field["id"]) or "").strip():
            missing.append(DROP_REASON_NAME)
        if at_field is None or not merged.get(at_field["id"]):
            missing.append(DROPPED_AT_NAME)
        if missing:
            raise WriteError(
                f"放弃独立需求 {row_id} 必须同时给出{'、'.join(missing)}；"
                "放弃要留下理由与时间，不能只改状态"
            )
        holders = _versions_holding(conn, row_id)
        if holders:
            raise WriteError(
                f"放弃独立需求 {row_id} 前必须先摘除它与版本的关联：仍在 {'、'.join(holders)} 中"
            )

    split_field = _by_name(fields, SPLIT_LOG_NAME)
    if split_field is not None and split_field["id"] in merged:
        new_log = str(merged.get(split_field["id"]) or "")
        old_log = str(previous.get(split_field["id"]) or "")
        if new_log != old_log and new_log.strip():
            if merged.get(acceptance["id"]) == "accepted":
                raise WriteError(
                    f"拆分只在独立需求尚未 accepted 时允许：{row_id} 已验收通过，"
                    "范围变化请开依赖需求，不要拆分"
                )


def _validate_version(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    merged: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    """已放弃的需求不得再挂到版本。"""
    relation = next(
        (
            field
            for field in fields.values()
            if field["type"] == "relation"
            and _target_table_id(field)
            and (target_fields := _table_fields(conn, _target_table_id(field) or ""))
            and _acceptance_field(target_fields) is not None
        ),
        None,
    )
    if relation is None:
        return
    added = [
        item
        for item in (merged.get(relation["id"]) or [])
        if item not in (previous.get(relation["id"]) or [])
    ]
    if not added:
        return
    acceptance = _acceptance_field(_table_fields(conn, _target_table_id(relation) or ""))
    if acceptance is None:
        return
    dropped: list[str] = []
    for spec_id in added:
        row = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?",
            (_target_table_id(relation), spec_id),
        ).fetchone()
        if row is None:
            continue
        if (_loads(row["data"]) or {}).get(acceptance["id"]) == "dropped":
            dropped.append(spec_id)
    if dropped:
        raise WriteError(
            f"已放弃的独立需求不能再挂到版本 {row_id}：{'、'.join(dropped)}；"
            "要重新做这项能力，请新建独立需求"
        )


def _validate_dep(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    merged: dict[str, Any],
) -> None:
    """已放弃的规格不得新开依赖需求（能力未建立，没有可修改的对象）。"""
    relation = next(
        (
            field
            for field in fields.values()
            if field["type"] == "relation"
            and _target_table_id(field)
            and _acceptance_field(_table_fields(conn, _target_table_id(field) or "")) is not None
        ),
        None,
    )
    if relation is None:
        return
    targets = merged.get(relation["id"]) or []
    if not targets:
        return
    acceptance = _acceptance_field(_table_fields(conn, _target_table_id(relation) or ""))
    if acceptance is None:
        return
    dropped: list[str] = []
    for spec_id in targets:
        row = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?",
            (_target_table_id(relation), spec_id),
        ).fetchone()
        if row is None:
            continue
        if (_loads(row["data"]) or {}).get(acceptance["id"]) == "dropped":
            dropped.append(spec_id)
    if dropped:
        raise WriteError(
            f"依赖需求 {row_id} 不能关联已放弃的规格：{'、'.join(dropped)}；"
            "该能力未建立，如要重做请新建独立需求"
        )


def validate_row_write(
    conn: sqlite3.Connection,
    table_id: str,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    *,
    merged: dict[str, Any],
    previous: dict[str, Any],
    submitted: dict[str, Any] | None = None,
) -> None:
    """写侧校验入口。失败抛 WriteError，整请求零写入。"""
    if _acceptance_field(fields) is not None:
        _validate_indep(conn, fields, row_id, merged, previous)
        return
    if version_stage.stage_nodes(fields) is not None:
        _validate_version(conn, fields, row_id, merged, previous)
        return
    _validate_dep(conn, fields, row_id, merged)
