"""独立需求生命周期校验（034）：拆分与放弃。

契约 `specs/019-test-contract/board@5.yaml` 的相关规则：

- `rules.spec_terminal_states` 终态只有 accepted 与 dropped；
- `rules.spec_drop` 放弃须同时给出理由与时间，且必须先摘除版本关联；
- `rules.spec_drop_immutable` dropped 不可回退，已放弃的规格不得新开依赖需求；
- `rules.spec_split` / `rules.spec_split_not_terminal` 拆分只在未 accepted 时允许，
  且不是终态。

识别口径与其它模块一致：不依赖表 id。独立需求表按 `验收状态` 的枚举值域识别
（board@5 前是三元域，迁移未完成的项目仍按三元识别）；版本表按 025 的六节点识别；
依赖需求表按「回归状态」枚举值域识别（与 board_rules 同口径），不按表 id。
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from . import version_stage
from .errors import WriteError

# board@5 前是三元域，迁移未完成的项目仍按三元识别
ACCEPTANCE_DOMAINS = frozenset({
    frozenset({"pending", "accepted", "rejected", "dropped"}),
    frozenset({"pending", "accepted", "rejected"}),
})

# 依赖需求表的识别口径与 board_rules 一致：按「回归状态」枚举值域，不按表 id。
REGRESS_VALUES = frozenset({"todo", "doing", "passed", "failed"})

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


def _project_of(conn: sqlite3.Connection, table_id: str) -> str | None:
    row = conn.execute("SELECT project_id FROM tables WHERE id = ?", (table_id,)).fetchone()
    return row["project_id"] if row else None


def _version_tables(
    conn: sqlite3.Connection, project_id: str | None = None
) -> list[tuple[str, dict[str, sqlite3.Row]]]:
    """版本表清单；给定项目时只看该项目——跨项目同编号需求不得互相干扰。"""
    out: list[tuple[str, dict[str, sqlite3.Row]]] = []
    if project_id:
        rows = conn.execute("SELECT id FROM tables WHERE project_id = ?", (project_id,)).fetchall()
    else:
        rows = conn.execute("SELECT id FROM tables").fetchall()
    for row in rows:
        table_id = row["id"]
        fields = _table_fields(conn, table_id)
        if version_stage.stage_nodes(fields) is not None:
            out.append((table_id, fields))
    return out


def _versions_holding(
    conn: sqlite3.Connection, spec_id: str, project_id: str | None = None
) -> list[str]:
    """该独立需求当前被哪些版本持有（限定本项目）。"""
    holders: list[str] = []
    for version_table_id, version_fields in _version_tables(conn, project_id):
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
    table_id: str,
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
            f"L1：dropped 是终态：独立需求 {row_id} 已放弃，不能改回 {new or '空'}；"
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
                f"L2：放弃独立需求 {row_id} 必须同时给出{'、'.join(missing)}；"
                "放弃要留下理由与时间，不能只改状态"
            )
        holders = _versions_holding(conn, row_id, _project_of(conn, table_id))
        if holders:
            raise WriteError(
                f"L3：放弃独立需求 {row_id} 前必须先摘除它与版本的关联：仍在 {'、'.join(holders)} 中"
            )

    split_field = _by_name(fields, SPLIT_LOG_NAME)
    if split_field is not None and split_field["id"] in merged:
        new_log = str(merged.get(split_field["id"]) or "")
        old_log = str(previous.get(split_field["id"]) or "")
        if new_log != old_log and new_log.strip():
            if merged.get(acceptance["id"]) == "accepted":
                raise WriteError(
                    f"L6：拆分只在独立需求尚未 accepted 时允许：{row_id} 已验收通过，"
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
            f"L4：已放弃的独立需求不能再挂到版本 {row_id}：{'、'.join(dropped)}；"
            "要重新做这项能力，请新建独立需求"
        )


def _is_dep_table(fields: dict[str, sqlite3.Row]) -> bool:
    """只有依赖需求表才有「回归状态」；用例等表不适用 C4/L5。"""
    return any(
        field["type"] == "enum" and _enum_values(field) == REGRESS_VALUES
        for field in fields.values()
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
    unaccepted: list[str] = []
    for spec_id in targets:
        row = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?",
            (_target_table_id(relation), spec_id),
        ).fetchone()
        if row is None:
            continue
        state = (_loads(row["data"]) or {}).get(acceptance["id"])
        if state == "dropped":
            dropped.append(spec_id)
        elif state != "accepted":
            unaccepted.append(f"{spec_id}={state}")
    if dropped:
        raise WriteError(
            f"L5：依赖需求 {row_id} 不能关联已放弃的规格：{'、'.join(dropped)}；"
            "该能力未建立，如要重做请新建独立需求"
        )
    if unaccepted:
        raise WriteError(
            f"C4：依赖需求 {row_id} 只能关联已验收的规格；以下尚未 accepted："
            + "、".join(unaccepted)
            + "。规格未验收时按 in_place 直接改规格，不开依赖需求"
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
        _validate_indep(conn, table_id, fields, row_id, merged, previous)
        return
    if version_stage.stage_nodes(fields) is not None:
        _validate_version(conn, fields, row_id, merged, previous)
        return
    if not _is_dep_table(fields):
        return
    _validate_dep(conn, fields, row_id, merged)


SPLIT_LINE_RE = re.compile(r"^(\S+)\s+移交\s+(.+?)\s*->\s*(\S+)\s*$")
SPLIT_LOG_NAME = "拆分记录"
ABANDON_REASON_NAME = "放弃理由"
ABANDONED_AT_NAME = "放弃时间"


def _indep_table_of(
    conn: sqlite3.Connection, project_id: str
) -> tuple[str, dict[str, sqlite3.Row]] | None:
    for row in conn.execute(
        'SELECT id FROM tables WHERE project_id = ? ORDER BY "order" ASC, id ASC',
        (project_id,),
    ).fetchall():
        fields = _table_fields(conn, row["id"])
        if _acceptance_field(fields) is not None:
            return row["id"], fields
    return None


def _parse_split_log(text: Any) -> list[dict[str, str]]:
    if not isinstance(text, str):
        return []
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        match = SPLIT_LINE_RE.match(line.strip())
        if match:
            out.append({"at": match.group(1), "clauses": match.group(2), "to": match.group(3)})
    return out


def lifecycle_report(
    conn: sqlite3.Connection, project_id: str, spec_id: str
) -> dict[str, Any] | None:
    """独立需求的生命周期视图：终态、放弃留痕、拆分链（034 T003）。

    拆分链双向可追：``split_out`` 是从本需求拆出去的，``split_in`` 是哪些需求拆到了本需求，
    ``chain`` 沿 ``split_out`` 继续向下展开（深度上限 10，防环）。
    """
    located = _indep_table_of(conn, project_id)
    if located is None:
        return None
    table_id, fields = located
    acceptance = _acceptance_field(fields)
    reason_field = _by_name(fields, ABANDON_REASON_NAME)
    at_field = _by_name(fields, ABANDONED_AT_NAME)
    log_field = _by_name(fields, SPLIT_LOG_NAME)

    def load(cid: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table_id, cid)
        ).fetchone()
        return None if row is None else (_loads(row["data"]) or {})

    values = load(spec_id)
    if values is None:
        return None

    split_out = _parse_split_log(values.get(log_field["id"])) if log_field else []
    split_in: list[dict[str, str]] = []
    if log_field is not None:
        for row in conn.execute(
            "SELECT id, data FROM row_records WHERE table_id = ?", (table_id,)
        ).fetchall():
            if row["id"] == spec_id:
                continue
            for entry in _parse_split_log((_loads(row["data"]) or {}).get(log_field["id"])):
                if entry["to"] == spec_id:
                    split_in.append({"from": row["id"], **entry})

    chain: list[dict[str, Any]] = []
    seen = {spec_id}
    frontier = [entry["to"] for entry in split_out]
    depth = 0
    while frontier and depth < 10:
        depth += 1
        nxt: list[str] = []
        for cid in frontier:
            if cid in seen:
                continue
            seen.add(cid)
            target = load(cid)
            entry: dict[str, Any] = {"spec": cid, "exists": target is not None}
            if target is not None:
                entry["acceptance"] = (
                    target.get(acceptance["id"]) if acceptance else None
                )
                out = _parse_split_log(target.get(log_field["id"])) if log_field else []
                entry["split_out"] = out
                nxt.extend(item["to"] for item in out)
            chain.append(entry)
        frontier = nxt

    return {
        "spec": spec_id,
        "acceptance": values.get(acceptance["id"]) if acceptance else None,
        "abandon_reason": values.get(reason_field["id"]) if reason_field else None,
        "abandoned_at": values.get(at_field["id"]) if at_field else None,
        "split_out": split_out,
        "split_in": split_in,
        "chain": chain,
    }
