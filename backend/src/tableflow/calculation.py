"""计算字段：配置校验、依赖图、五种 kind、写侧重算与人工覆盖。

硬约束（003 spec / 宪法 v6.0.0）：
- 计算在写事务内完成并落 `computed_values`；读侧只读，不做任何业务计算。
- kind 封闭为 count / percent / sum / rollup / and；不做用户表达式、跨表任意聚合。
- 依赖只来自本表 relation 指向的目标行；`and` 可引用同表计算字段，依赖必须无环。
- 计算异常 / 配置非法 → `WriteError`，由 `run_write` 整体回滚。
- 覆盖值优先于重算结果，带原因、可清除；清除后立即重算。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .errors import WriteError

TZ = timezone(timedelta(hours=8))
KINDS = {"count", "percent", "sum", "rollup", "and"}
AGGREGATES = {"all", "any", "none", "min", "max", "count_distinct"}
BOOLEAN_AGGREGATES = {"all", "any", "none"}


# ---------- 基础工具 ----------

def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _loads(raw: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _decode(raw: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def _round_half_up(value: float, decimals: int) -> float:
    quant = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def _field_rows(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, name, type, options FROM fields WHERE table_id = ?", (table_id,)
    ).fetchall()
    return {row["id"]: row for row in rows}


def _table_exists(conn: sqlite3.Connection, table_id: str) -> bool:
    return conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is not None


def _relation_target(options: Any) -> str | None:
    if not isinstance(options, dict):
        return None
    target = options.get("table_id")
    return target if isinstance(target, str) else None


def _all_rows(conn: sqlite3.Connection, table_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ?", (table_id,)
    ).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        values = _loads(row["data"]) or {}
        result[row["id"]] = values if isinstance(values, dict) else {}
    return result


def _stored_values(
    conn: sqlite3.Connection, table_id: str
) -> dict[tuple[str, str], sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM computed_values WHERE table_id = ?", (table_id,)
    ).fetchall()
    return {(row["row_id"], row["field_id"]): row for row in rows}


def _target_rows(
    conn: sqlite3.Connection, table_id: str, cache: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, dict[str, Any]]:
    if table_id not in cache:
        cache[table_id] = _all_rows(conn, table_id)
    return cache[table_id]


# ---------- 配置校验 ----------

def _computed_options_map(
    conn: sqlite3.Connection,
    table_id: str,
    proposed_id: str | None = None,
    proposed_options: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, options FROM fields WHERE table_id = ? AND type = 'computed'",
        (table_id,),
    ).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if proposed_id is not None and row["id"] == proposed_id:
            continue
        options = _loads(row["options"])
        result[row["id"]] = options if isinstance(options, dict) else {}
    if proposed_id is not None:
        result[proposed_id] = proposed_options or {}
    return result


def _topological_order(computed: dict[str, dict[str, Any]]) -> list[str]:
    """按依赖拓扑排序；`and` 引用同表计算字段时被引用者先算。"""
    graph: dict[str, set[str]] = {field_id: set() for field_id in computed}
    for field_id, options in computed.items():
        if options.get("kind") != "and":
            continue
        for condition in options.get("conditions") or []:
            if not isinstance(condition, dict):
                continue
            dependency = condition.get("field_id")
            if isinstance(dependency, str) and dependency in computed:
                graph[field_id].add(dependency)

    order: list[str] = []
    state: dict[str, int] = {}

    def visit(field_id: str) -> None:
        current = state.get(field_id, 0)
        if current == 1:
            raise WriteError("计算字段依赖成环")
        if current == 2:
            return
        state[field_id] = 1
        for dependency in graph[field_id]:
            visit(dependency)
        state[field_id] = 2
        order.append(field_id)

    for field_id in graph:
        visit(field_id)
    return order


def _has_cycle(computed: dict[str, dict[str, Any]]) -> bool:
    try:
        _topological_order(computed)
    except WriteError:
        return True
    return False


def _validate_where(conn: sqlite3.Connection, target_fields: dict[str, sqlite3.Row], where: Any) -> None:
    if not isinstance(where, dict):
        raise WriteError("计算字段的 where 必须是对象")
    field_id = where.get("field_id")
    if not isinstance(field_id, str) or field_id not in target_fields:
        raise WriteError(f"where.field_id 必须是目标表字段：{field_id}")
    if target_fields[field_id]["type"] == "computed":
        raise WriteError("where.field_id 不能引用计算字段")
    if "equals" not in where or where["equals"] is None:
        raise WriteError("where.equals 不能为空")


def _validate_decimals_unit(options: dict[str, Any], *, maximum: int = 6) -> None:
    if "decimals" in options:
        decimals = options["decimals"]
        if isinstance(decimals, bool) or not isinstance(decimals, int):
            raise WriteError("decimals 必须是整数")
        if not 0 <= decimals <= maximum:
            raise WriteError(f"decimals 必须在 0–{maximum} 之间")
    if "unit" in options:
        unit = options["unit"]
        if not isinstance(unit, str) or len(unit) > 8:
            raise WriteError("unit 必须是长度 ≤8 的字符串")


def validate_computed_options(
    conn: sqlite3.Connection,
    table_id: str,
    options: Any,
    *,
    field_id: str | None = None,
) -> dict[str, Any]:
    """创建/更新计算字段时的完整配置校验；返回原 options。"""
    if not isinstance(options, dict):
        raise WriteError("computed 字段必须提供 options 对象")
    kind = options.get("kind")
    if kind not in KINDS:
        raise WriteError(f"computed.kind 必须是 {sorted(KINDS)} 之一")
    if "allow_override" in options and not isinstance(options["allow_override"], bool):
        raise WriteError("allow_override 必须是布尔值")

    fields = _field_rows(conn, table_id)

    if kind == "and":
        conditions = options.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            raise WriteError("and.conditions 必须是非空数组")
        for condition in conditions:
            if not isinstance(condition, dict):
                raise WriteError("and.conditions 项必须是对象")
            condition_field = condition.get("field_id")
            if not isinstance(condition_field, str) or condition_field not in fields:
                raise WriteError(f"and.conditions 引用的字段不存在：{condition_field}")
            if "equals" not in condition or condition["equals"] is None:
                raise WriteError("and.conditions.equals 不能为空")
        for key in ("true_label", "false_label"):
            if key in options and not isinstance(options[key], str):
                raise WriteError(f"{key} 必须是字符串")
        computed = _computed_options_map(conn, table_id, field_id, options)
        if _has_cycle(computed):
            raise WriteError("计算字段依赖成环")
        return options

    source = options.get("source")
    if not isinstance(source, str) or source not in fields:
        raise WriteError(f"source 必须是本表字段：{source}")
    source_field = fields[source]
    if source_field["type"] != "relation":
        raise WriteError("source 必须是本表 relation 字段")
    target_table = _relation_target(_loads(source_field["options"]))
    if target_table is None:
        raise WriteError("source relation 缺少目标表")
    target_fields = _field_rows(conn, target_table)

    where = options.get("where")
    if where is not None:
        _validate_where(conn, target_fields, where)

    if kind == "percent":
        decimals = options.get("decimals", 1)
        if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 1:
            raise WriteError("percent.decimals 必须是 0 或 1")

    if kind == "sum":
        target_field = options.get("field_id")
        if not isinstance(target_field, str) or target_field not in target_fields:
            raise WriteError(f"sum.field_id 必须是目标表字段：{target_field}")
        if target_fields[target_field]["type"] != "number":
            raise WriteError("sum.field_id 必须是 number 字段")
        _validate_decimals_unit(options)

    if kind == "rollup":
        target_field = options.get("field_id")
        if not isinstance(target_field, str) or target_field not in target_fields:
            raise WriteError(f"rollup.field_id 必须是目标表字段：{target_field}")
        if target_fields[target_field]["type"] == "computed":
            raise WriteError("rollup.field_id 不能引用计算字段")
        aggregate = options.get("aggregate")
        if aggregate not in AGGREGATES:
            raise WriteError(f"rollup.aggregate 必须是 {sorted(AGGREGATES)} 之一")
        if aggregate in BOOLEAN_AGGREGATES and (
            "equals" not in options or options["equals"] is None
        ):
            raise WriteError("rollup all/any/none 必须提供 equals")
        if aggregate in {"min", "max"} and target_fields[target_field]["type"] not in {
            "number",
            "datetime",
        }:
            raise WriteError("rollup min/max 的源字段必须是 number 或 datetime")
        require = options.get("require")
        if require is not None:
            if not isinstance(require, list) or not require:
                raise WriteError("rollup.require 必须是非空数组")
            for cond in require:
                if not isinstance(cond, dict) or not isinstance(cond.get("field_id"), str):
                    raise WriteError("rollup.require 每项必须含 field_id")
                if cond["field_id"] not in target_fields:
                    raise WriteError(f"rollup.require 字段不属于目标表：{cond['field_id']}")
                if target_fields[cond["field_id"]]["type"] == "computed":
                    raise WriteError("rollup.require 不能引用计算字段")
                if "equals" not in cond:
                    raise WriteError("rollup.require 每项必须含 equals")

    return options


# ---------- 依赖与影响范围 ----------

def affected_tables(conn: sqlite3.Connection, table_id: str) -> set[str]:
    """表 T 的数据变化会影响哪些表：T 本身 + 以 relation 指向 T 的计算字段所在表。"""
    result = {table_id}
    computed = conn.execute(
        "SELECT table_id, options FROM fields WHERE type = 'computed'"
    ).fetchall()
    source_owners: dict[str, set[str]] = {}
    for row in computed:
        options = _loads(row["options"])
        if not isinstance(options, dict):
            continue
        source = options.get("source")
        if isinstance(source, str):
            source_owners.setdefault(source, set()).add(row["table_id"])
    if not source_owners:
        return result
    relations = conn.execute(
        "SELECT id, options FROM fields WHERE type = 'relation'"
    ).fetchall()
    for relation in relations:
        options = _loads(relation["options"])
        if not isinstance(options, dict):
            continue
        if options.get("table_id") == table_id and relation["id"] in source_owners:
            result |= source_owners[relation["id"]]
    return result


def references_to_field(conn: sqlite3.Connection, field_id: str) -> list[dict[str, str]]:
    """列出引用某字段的计算字段（source / where / field_id / and.conditions）。"""
    references: list[dict[str, str]] = []
    rows = conn.execute(
        "SELECT id, table_id, name, options FROM fields WHERE type = 'computed'"
    ).fetchall()
    for row in rows:
        options = _loads(row["options"])
        if not isinstance(options, dict):
            continue
        hit = options.get("source") == field_id
        where = options.get("where")
        if isinstance(where, dict) and where.get("field_id") == field_id:
            hit = True
        if options.get("field_id") == field_id:
            hit = True
        for condition in options.get("conditions") or []:
            if isinstance(condition, dict) and condition.get("field_id") == field_id:
                hit = True
        if hit:
            references.append(
                {"table_id": row["table_id"], "field_id": row["id"], "name": row["name"]}
            )
    return references


def relations_to_table(conn: sqlite3.Connection, table_id: str) -> list[dict[str, str]]:
    """列出其他表指向某表的 relation 字段（删除表前的保护检查）。"""
    references: list[dict[str, str]] = []
    rows = conn.execute(
        "SELECT id, table_id, name, options FROM fields WHERE type = 'relation'"
    ).fetchall()
    for row in rows:
        options = _loads(row["options"])
        if not isinstance(options, dict):
            continue
        if options.get("table_id") == table_id and row["table_id"] != table_id:
            references.append(
                {"table_id": row["table_id"], "field_id": row["id"], "name": row["name"]}
            )
    return references


# ---------- 五种计算 ----------

def _effective_value(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    field_id: str,
    fields: dict[str, sqlite3.Row],
    row_values: dict[str, Any],
    cache: dict[str, Any],
    stored: dict[tuple[str, str], sqlite3.Row],
) -> Any:
    """取字段有效值：计算字段 override 优先，其次本次重算缓存，最后落库值。"""
    field = fields.get(field_id)
    if field is None:
        raise WriteError(f"计算字段引用的字段不存在：{field_id}")
    if field["type"] != "computed":
        return row_values.get(field_id)
    stored_row = stored.get((row_id, field_id))
    if stored_row is not None and stored_row["override_value"] is not None:
        return _decode(stored_row["override_value"])
    if field_id in cache:
        return cache[field_id]
    return _decode(stored_row["value"]) if stored_row is not None else None


def _selected_target_rows(
    conn: sqlite3.Connection,
    source: str,
    row_values: dict[str, Any],
    target_table: str,
    rows_cache: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    ids = row_values.get(source)
    if not isinstance(ids, list):
        return []
    target = _target_rows(conn, target_table, rows_cache)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for target_id in ids:
        if not isinstance(target_id, str) or target_id in seen:
            continue
        seen.add(target_id)
        if target_id in target:
            selected.append(target[target_id])
    return selected


def _compute_relation_kind(
    conn: sqlite3.Connection,
    field: sqlite3.Row,
    options: dict[str, Any],
    fields: dict[str, sqlite3.Row],
    row_values: dict[str, Any],
    rows_cache: dict[str, dict[str, dict[str, Any]]],
) -> Any:
    kind = options["kind"]
    source = options["source"]
    source_field = fields[source]
    target_table = _relation_target(_loads(source_field["options"]))
    if target_table is None:
        raise WriteError("source relation 缺少目标表")
    selected = _selected_target_rows(conn, source, row_values, target_table, rows_cache)
    where = options.get("where")
    matched = selected
    if isinstance(where, dict):
        matched = [
            values
            for values in selected
            if values.get(where["field_id"]) == where["equals"]
        ]

    if kind == "count":
        return len(matched)

    if kind == "percent":
        total = len(selected)
        if total == 0:
            return None
        decimals = options.get("decimals", 1)
        return _round_half_up(len(matched) / total * 100.0, decimals)

    if kind == "sum":
        target_field = options["field_id"]
        numbers = [
            values.get(target_field)
            for values in selected
            if isinstance(values.get(target_field), (int, float))
            and not isinstance(values.get(target_field), bool)
        ]
        value: Any = sum(numbers)
        if "decimals" in options:
            value = _round_half_up(float(value), options["decimals"])
        return value

    if kind == "rollup":
        target_field = options["field_id"]
        values = [values_.get(target_field) for values_ in selected]
        aggregate = options["aggregate"]
        if aggregate in BOOLEAN_AGGREGATES:
            equals = options["equals"]
            require = options.get("require") or []

            def _matches(values_: dict[str, Any]) -> bool:
                return all(values_.get(cond["field_id"]) == cond["equals"] for cond in require)

            results = [
                _matches(values_) and values_.get(target_field) == equals
                for values_ in selected
            ]
            if aggregate == "all":
                return all(results)
            if aggregate == "any":
                return any(results)
            return not any(results)
        if aggregate == "count_distinct":
            distinct = {
                json.dumps(value, ensure_ascii=False, sort_keys=True)
                for value in values
                if value is not None
            }
            return len(distinct)
        # min / max
        target_fields = _field_rows(conn, target_table)
        target_type = target_fields[target_field]["type"] if target_field in target_fields else None
        candidates: list[tuple[Any, Any]] = []
        for value in values:
            if value is None:
                continue
            if target_type == "number":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                candidates.append((value, value))
            elif target_type == "datetime":
                if not isinstance(value, str):
                    continue
                try:
                    candidates.append((datetime.fromisoformat(value), value))
                except ValueError:
                    continue
            else:
                candidates.append((value, value))
        if not candidates:
            return None
        return (
            min(candidates, key=lambda item: item[0])[1]
            if aggregate == "min"
            else max(candidates, key=lambda item: item[0])[1]
        )

    raise WriteError(f"未知计算类型：{kind}")


def _compute_and(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    options: dict[str, Any],
    fields: dict[str, sqlite3.Row],
    row_values: dict[str, Any],
    cache: dict[str, Any],
    stored: dict[tuple[str, str], sqlite3.Row],
) -> bool:
    for condition in options["conditions"]:
        value = _effective_value(
            conn, table_id, row_id, condition["field_id"], fields, row_values, cache, stored
        )
        # null 与任何值都不相等；条件不成立
        if value is None or value != condition["equals"]:
            return False
    return True


def compute_value(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    field: sqlite3.Row,
    options: dict[str, Any],
    row_values: dict[str, Any],
    fields: dict[str, sqlite3.Row],
    cache: dict[str, Any],
    stored: dict[tuple[str, str], sqlite3.Row],
    rows_cache: dict[str, dict[str, dict[str, Any]]],
) -> Any:
    """按配置计算一行一个字段的值；不写库。"""
    kind = options.get("kind")
    if kind == "and":
        return _compute_and(conn, table_id, row_id, options, fields, row_values, cache, stored)
    if kind in {"count", "percent", "sum", "rollup"}:
        return _compute_relation_kind(conn, field, options, fields, row_values, rows_cache)
    raise WriteError(f"未知计算类型：{kind}")


# ---------- 落库与重算 ----------

def _upsert_value(
    conn: sqlite3.Connection, table_id: str, row_id: str, field_id: str, value: Any
) -> None:
    conn.execute(
        """
        INSERT INTO computed_values (table_id, row_id, field_id, value, computed_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(table_id, row_id, field_id)
        DO UPDATE SET value = excluded.value, computed_at = excluded.computed_at
        """,
        (table_id, row_id, field_id, _dumps(value), _now()),
    )


def _record_change(
    conn: sqlite3.Connection,
    *,
    actor: str,
    origin: str,
    table_id: str,
    row_id: str,
    field_id: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    change_kind: str,
    reason: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO business_changes"
        " (occurred_at, actor, origin, table_id, row_id, field_id, field_name,"
        "  old_value, new_value, change_kind, reason)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _now(),
            actor,
            origin,
            table_id,
            row_id,
            field_id,
            field_name,
            _dumps(old_value),
            _dumps(new_value),
            change_kind,
            reason,
        ),
    )


def recompute_table(
    conn: sqlite3.Connection,
    table_id: str,
    *,
    actor: str = "-",
    origin: str = "agent",
    reason: str | None = None,
) -> dict[str, int]:
    """按依赖拓扑重算一张表的全部计算字段；返回 rows/fields/changed。"""
    fields = _field_rows(conn, table_id)
    computed: dict[str, dict[str, Any]] = {}
    for field_id, field in fields.items():
        if field["type"] != "computed":
            continue
        options = _loads(field["options"])
        if not isinstance(options, dict):
            raise WriteError(f"计算字段 {field['name']} 的配置损坏")
        computed[field_id] = options
    if not computed:
        return {"rows": 0, "fields": 0, "changed": 0}

    order = _topological_order(computed)
    rows = _all_rows(conn, table_id)
    stored = _stored_values(conn, table_id)
    rows_cache: dict[str, dict[str, dict[str, Any]]] = {}
    changed = 0

    for row_id, row_values in rows.items():
        cache: dict[str, Any] = {}
        for field_id in order:
            field = fields[field_id]
            options = computed[field_id]
            try:
                value = compute_value(
                    conn,
                    table_id,
                    row_id,
                    field,
                    options,
                    row_values,
                    fields,
                    cache,
                    stored,
                    rows_cache,
                )
            except WriteError:
                raise
            except Exception as exc:  # noqa: BLE001 - 统一转为可回滚的业务失败
                raise WriteError(f"计算失败（{field['name']}）：{exc}") from exc
            cache[field_id] = value
            old_row = stored.get((row_id, field_id))
            old_value = _decode(old_row["value"]) if old_row is not None else None
            if old_row is None:
                _upsert_value(conn, table_id, row_id, field_id, value)
                if value is not None:
                    _record_change(
                        conn,
                        actor=actor,
                        origin=origin,
                        table_id=table_id,
                        row_id=row_id,
                        field_id=field_id,
                        field_name=field["name"],
                        old_value=None,
                        new_value=value,
                        change_kind="recompute",
                        reason=reason,
                    )
                    changed += 1
            elif old_value != value:
                _upsert_value(conn, table_id, row_id, field_id, value)
                _record_change(
                    conn,
                    actor=actor,
                    origin=origin,
                    table_id=table_id,
                    row_id=row_id,
                    field_id=field_id,
                    field_name=field["name"],
                    old_value=old_value,
                    new_value=value,
                    change_kind="recompute",
                    reason=reason,
                )
                changed += 1

    return {"rows": len(rows), "fields": len(order), "changed": changed}


def recompute_for_write(
    conn: sqlite3.Connection, table_id: str, *, actor: str, origin: str
) -> dict[str, int]:
    """写请求内重算：受影响表（本表 + 引用本表的计算字段所在表）全量。"""
    totals = {"rows": 0, "fields": 0, "changed": 0}
    for affected in sorted(affected_tables(conn, table_id)):
        result = recompute_table(conn, affected, actor=actor, origin=origin)
        for key in totals:
            totals[key] += result[key]
    return totals


def recompute_table_and_dependents(
    conn: sqlite3.Connection, table_id: str, *, actor: str, origin: str
) -> dict[str, int]:
    """显式重算接口：表不存在则失败；幂等。"""
    if not _table_exists(conn, table_id):
        raise WriteError("表格不存在")
    return recompute_for_write(conn, table_id, actor=actor, origin=origin)


# ---------- 人工覆盖 ----------

def computed_output_type(options: dict[str, Any]) -> str:
    kind = options.get("kind")
    if kind == "and":
        return "bool"
    if kind == "rollup":
        aggregate = options.get("aggregate")
        if aggregate in BOOLEAN_AGGREGATES:
            return "bool"
        if aggregate in {"min", "max"}:
            return "scalar"
        return "number"
    return "number"


def _validate_override_value(options: dict[str, Any], value: Any) -> None:
    if isinstance(value, (list, dict)):
        raise WriteError("覆盖值必须是标量")
    output_type = computed_output_type(options)
    if output_type == "bool":
        if not isinstance(value, bool):
            raise WriteError("该计算字段的覆盖值必须是布尔值")
        return
    if output_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WriteError("该计算字段的覆盖值必须是数字")
        return
    # scalar（rollup min/max，可能是数字或日期字符串）
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise WriteError("该计算字段的覆盖值必须是数字或字符串")


def _effective_from_stored(stored_row: sqlite3.Row | None) -> Any:
    if stored_row is None:
        return None
    if stored_row["override_value"] is not None:
        return _decode(stored_row["override_value"])
    return _decode(stored_row["value"])


def _ensure_value_row(
    conn: sqlite3.Connection, table_id: str, row_id: str, field_id: str
) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM computed_values WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (table_id, row_id, field_id),
    ).fetchone()
    if row is not None:
        return row
    conn.execute(
        "INSERT INTO computed_values (table_id, row_id, field_id, value, computed_at)"
        " VALUES (?, ?, ?, NULL, ?)",
        (table_id, row_id, field_id, _now()),
    )
    return conn.execute(
        "SELECT * FROM computed_values WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (table_id, row_id, field_id),
    ).fetchone()


def set_override(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    field: sqlite3.Row,
    options: dict[str, Any],
    value: Any,
    reason: str,
    *,
    actor: str,
    origin: str,
) -> None:
    if not options.get("allow_override"):
        raise WriteError(f"计算字段「{field['name']}」不允许人工覆盖")
    if not isinstance(reason, str) or not reason.strip():
        raise WriteError("覆盖必须填写原因")
    _validate_override_value(options, value)
    stored_row = _ensure_value_row(conn, table_id, row_id, field["id"])
    old_value = _effective_from_stored(stored_row)
    conn.execute(
        "UPDATE computed_values SET override_value = ?, override_reason = ?,"
        " override_by = ?, override_at = ?"
        " WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (_dumps(value), reason.strip(), actor, _now(), table_id, row_id, field["id"]),
    )
    _record_change(
        conn,
        actor=actor,
        origin=origin,
        table_id=table_id,
        row_id=row_id,
        field_id=field["id"],
        field_name=field["name"],
        old_value=old_value,
        new_value=value,
        change_kind="override",
        reason=reason.strip(),
    )


def _compute_single_field(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    field: sqlite3.Row,
    options: dict[str, Any],
) -> Any:
    fields = _field_rows(conn, table_id)
    rows = _all_rows(conn, table_id)
    if row_id not in rows:
        raise WriteError("行不存在")
    stored = _stored_values(conn, table_id)
    cache: dict[str, Any] = {}
    return compute_value(
        conn,
        table_id,
        row_id,
        field,
        options,
        rows[row_id],
        fields,
        cache,
        stored,
        {},
    )


def clear_override(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    field: sqlite3.Row,
    options: dict[str, Any],
    *,
    actor: str,
    origin: str,
    reason: str | None = None,
) -> None:
    stored_row = conn.execute(
        "SELECT * FROM computed_values WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (table_id, row_id, field["id"]),
    ).fetchone()
    if stored_row is None or stored_row["override_value"] is None:
        raise WriteError(f"计算字段「{field['name']}」没有可清除的覆盖")
    old_value = _decode(stored_row["override_value"])
    conn.execute(
        "UPDATE computed_values SET override_value = NULL, override_reason = NULL,"
        " override_by = NULL, override_at = NULL"
        " WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (table_id, row_id, field["id"]),
    )
    value = _compute_single_field(conn, table_id, row_id, field, options)
    conn.execute(
        "UPDATE computed_values SET value = ?, computed_at = ?"
        " WHERE table_id = ? AND row_id = ? AND field_id = ?",
        (_dumps(value), _now(), table_id, row_id, field["id"]),
    )
    _record_change(
        conn,
        actor=actor,
        origin=origin,
        table_id=table_id,
        row_id=row_id,
        field_id=field["id"],
        field_name=field["name"],
        old_value=old_value,
        new_value=value,
        change_kind="override",
        reason=(reason.strip() if isinstance(reason, str) and reason.strip() else "清除覆盖"),
    )


def apply_overrides(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    overrides: Any,
    fields: dict[str, sqlite3.Row],
    *,
    actor: str,
    origin: str,
) -> int:
    if not isinstance(overrides, dict):
        raise WriteError("overrides 必须是对象")
    applied = 0
    for field_id, entry in overrides.items():
        field = fields.get(field_id)
        if field is None:
            raise WriteError(f"覆盖字段不存在：{field_id}")
        if field["type"] != "computed":
            raise WriteError(f"字段「{field['name']}」不是计算字段，不能覆盖")
        options = _loads(field["options"])
        if not isinstance(options, dict):
            raise WriteError(f"计算字段「{field['name']}」配置损坏")
        if not isinstance(entry, dict) or "value" not in entry:
            raise WriteError("overrides 每项必须形如 {value, reason}")
        if entry["value"] is None:
            clear_override(
                conn,
                table_id,
                row_id,
                field,
                options,
                actor=actor,
                origin=origin,
                reason=entry.get("reason"),
            )
        else:
            set_override(
                conn,
                table_id,
                row_id,
                field,
                options,
                entry["value"],
                entry.get("reason", ""),
                actor=actor,
                origin=origin,
            )
        applied += 1
    if applied:
        # 覆盖可能改变同表 and 依赖的有效值，立即按拓扑序重算依赖方。
        recompute_table(conn, table_id, actor=actor, origin=origin)
    return applied


# ---------- 清理 ----------

def delete_values_for_row(conn: sqlite3.Connection, table_id: str, row_id: str) -> None:
    conn.execute(
        "DELETE FROM computed_values WHERE table_id = ? AND row_id = ?", (table_id, row_id)
    )


def delete_values_for_field(conn: sqlite3.Connection, field_id: str) -> None:
    conn.execute("DELETE FROM computed_values WHERE field_id = ?", (field_id,))


def delete_values_for_table(conn: sqlite3.Connection, table_id: str) -> None:
    conn.execute("DELETE FROM computed_values WHERE table_id = ?", (table_id,))
