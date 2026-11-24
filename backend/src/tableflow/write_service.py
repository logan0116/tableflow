"""Agent 写服务：表 / 字段 / 行的 CRUD + 审计 + 三态 + 业务变更记录。

每次写入（成功、失败、未知）都在同一或后续事务里落一条 `write_audit`；
行数据的字段级变化另落 `business_changes`（业务留痕），两者同事务、互不替代。

v0.3.0（002）：
- 字段 options 结构化校验：enum tone、number 格式、datetime with_time、relation 同项目/单向、constraints。
- 行 id 为业务编号（`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`），表内唯一、创建后不可变。
- 字段级约束在落库前校验；失败不落库，只留失败审计。

v0.3.0（003）：
- 新增 `type=computed`：配置在字段创建/更新时校验，值由 `calculation` 在写事务内重算并落库。
- 计算字段不接受直接写入；行 PATCH 支持 `overrides`（人工覆盖，带原因、可清除）。

v0.6.2（013）：
- 写请求的调用者身份由 `auth` 解析，`run_write` 把 `key_id` 落进 `write_audit`；
  无 key 的旧调用（`X-Agent-Id`）行为不变。
- 新建行时，负责人字段缺省由调用者身份填充（仅 key 鉴权的调用者；
  旧调用不改写数据，避免把工具名写进"负责人"）。

v0.6.0 缺陷修复（t9）：
- V060-04：更新行只校验本次提交的关系字段“目标行必须存在”；
  存量悬空引用不再锁死无关字段的编辑，显式提交悬空值仍 400。

v0.7.0（020）：
- 执行记录表（`run`）的写侧协议由 `run_protocol` 校验：`state`/`result` 必须一致
  （`todo`→result 空、`done`→result 非空），行 id 必须是 `<版本号>--<用例号>`，
  执行清单不得重复或跨版本收录；不一致一律 400 且零写入，信封不变（protocol@2）。

v0.7.0（025）：
- 版本表六节点（`ver.stage.*`）的串行推进与节点闸门一致性由 `version_stage` 校验：
  前序未 done（或有 failed）时后序不得推进；「开发验收/测试/测试验收」置 done 还要求
  本版规格 accepted、用例全部执行、缺陷清零与变更回归通过；违反即 400 且零写入。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import (
    board_rules,
    calculation,
    change_flow,
    run_protocol,
    spec_lifecycle,
    stage_evidence,
    version_stage,
)
from .errors import WriteError

TZ = timezone(timedelta(hours=8))
FIELD_TYPES = {"text", "number", "datetime", "enum", "relation", "computed"}
TONES = {"neutral", "info", "success", "warning", "danger"}
ORIGINS = {"agent", "human-request", "seed"}
CONSTRAINT_KEYS = {"required", "min", "max", "enum_strict", "relation_must_exist"}
ROW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ORDER_MAX = 100000
# 负责人字段识别：字段 id 以 -owner 结尾（契约字段 id 规则 <前缀>-<v|i|d>-<短名>），
# 退一步认名称恰为"负责人"的文本字段。多义时不猜，交人工填。
OWNER_FIELD_SUFFIX = "-owner"
OWNER_FIELD_NAME = "负责人"


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _audit_row(
    conn: sqlite3.Connection,
    agent_id: str,
    origin: str,
    action: str,
    target: str,
    payload: str | None,
    result: str,
    error: str | None = None,
    *,
    key_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO write_audit"
        " (agent_id, key_id, origin, action, target, payload, result, error, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            agent_id,
            key_id,
            origin,
            action,
            target,
            payload[:4000] if payload else None,
            result,
            error,
            _now(),
        ),
    )


def record_auth_failure(
    conn: sqlite3.Connection,
    *,
    agent_id: str,
    origin: str,
    action: str,
    target: str,
    payload: str | None,
    error: str,
) -> None:
    """鉴权失败也留痕：key 无效/缺失时写一条 failed 审计（无 key 标识可记）。"""
    _audit_row(
        conn,
        agent_id or "-",
        origin if origin in ORIGINS else "agent",
        action,
        target,
        payload,
        "failed",
        error,
    )
    conn.commit()


def _commit_quietly(conn: sqlite3.Connection) -> None:
    """失败审计的提交：审计写不进去不能掩盖原始错误。"""
    try:
        conn.commit()
    except sqlite3.Error:
        pass


def run_write(
    conn: sqlite3.Connection,
    *,
    agent_id: str,
    action: str,
    target: str,
    payload: str | None,
    operation: Callable[[], Any],
    origin: str = "agent",
    key_id: str | None = None,
) -> Any:
    """执行一次写入并保证留下审计记录；`key_id` 标识本次请求由哪把 key 发起。"""
    if not agent_id:
        _audit_row(conn, "-", "agent", action, target, payload, "failed", "缺少 X-Agent-Id")
        conn.commit()
        raise WriteError("缺少 X-Agent-Id")

    if origin not in ORIGINS:
        _audit_row(
            conn,
            agent_id,
            "agent",
            action,
            target,
            payload,
            "failed",
            f"X-Origin 必须是 {sorted(ORIGINS)} 之一",
            key_id=key_id,
        )
        conn.commit()
        raise WriteError(f"X-Origin 必须是 {sorted(ORIGINS)} 之一")

    try:
        result = operation()
        _audit_row(conn, agent_id, origin, action, target, payload, "success", key_id=key_id)
    except WriteError as exc:
        conn.rollback()
        _audit_row(conn, agent_id, origin, action, target, payload, "failed", str(exc), key_id=key_id)
        _commit_quietly(conn)
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        _audit_row(
            conn, agent_id, origin, action, target, payload, "failed", f"数据库错误：{exc}", key_id=key_id
        )
        _commit_quietly(conn)
        raise WriteError(f"数据库错误：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 - 兜底，保证审计
        conn.rollback()
        _audit_row(
            conn, agent_id, origin, action, target, payload, "failed", f"未预期错误：{exc}", key_id=key_id
        )
        _commit_quietly(conn)
        raise WriteError(f"未预期错误：{exc}") from exc
    try:
        conn.commit()
    except sqlite3.Error as exc:
        # 提交阶段失败无法断言"未落库"：可能已提交、也可能只落了一半。
        # 按 failed 让调用方重试会重复写入，必须返回 unknown。
        raise WriteError(f"提交结果未知，请先回读确认：{exc}", unknown=True) from exc
    return result


def _payload_text(body: dict[str, Any] | None) -> str | None:
    return json.dumps(body, ensure_ascii=False) if body is not None else None


# 请求体允许的顶层键（protocol@2，012-AR 的 P-019 由“忽略多余键”改为“拒绝”）：
# 写错形状静默 success 比报错危险得多——2026-11-19 一次 PATCH 把字段名放在顶层、
# 返回 success 却一字未写，读回才发现（BUG-03 同期发现）。
BODY_KEYS: dict[str, frozenset[str]] = {
    "project.create": frozenset({"id", "name"}),
    "table.create": frozenset({"id", "name", "order", "kind"}),
    "table.update": frozenset({"name", "order", "kind"}),
    "field.create": frozenset({"id", "name", "type", "options", "order", "visible"}),
    "field.update": frozenset({"name", "type", "options", "order", "visible"}),
    "row.create": frozenset({"id", "values"}),
    "row.update": frozenset({"values", "overrides"}),
}


def _reject_unknown_keys(action: str, body: dict[str, Any]) -> None:
    """拒绝请求体里不认识的顶层键；整请求失败，不做部分写入。"""
    allowed = BODY_KEYS[action]
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise WriteError(
            f"请求体含未知顶层键：{unknown}；{action} 只接受 {sorted(allowed)}"
        )


def _require_name(body: dict[str, Any]) -> str:
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WriteError("name 必须是非空字符串")
    return name.strip()


def _require_int(value: Any, label: str, *, minimum: int = 0, maximum: int = ORDER_MAX) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WriteError(f"{label} 必须是整数")
    if value < minimum or value > maximum:
        raise WriteError(f"{label} 必须在 {minimum}–{maximum} 之间")
    return value


def _require_table_kind(value: Any) -> str:
    """board@4 表级分类：board 进导航，detail 不进导航。"""
    if value not in ("board", "detail"):
        raise WriteError("kind 只能是 board 或 detail")
    return value


def _require_visible(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, int) or value not in (0, 1):
        raise WriteError("visible 只能是 0 或 1")
    return value


def _next_order(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) + 1


def _loads(raw: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


# ---------- 字段 options 校验 ----------

def _enum_items(options: Any) -> list[dict[str, Any]]:
    if isinstance(options, dict):
        items = options.get("items")
    else:
        items = options
    return items if isinstance(items, list) else []


def _validate_color(color: Any, field_label: str) -> None:
    if not isinstance(color, dict):
        raise WriteError(f"{field_label} 的 color 必须是 {{bg,fg}} 对象")
    for key in ("bg", "fg"):
        value = color.get(key)
        if not isinstance(value, str) or not value.strip():
            raise WriteError(f"{field_label} 的 color.{key} 必须是非空字符串")


def _validate_enum_options(options: Any) -> Any:
    if options is None:
        raise WriteError("enum 字段必须提供 options")
    if isinstance(options, dict):
        if not isinstance(options.get("items"), list):
            raise WriteError("enum 的 options.items 必须是数组")
        items = options["items"]
    elif isinstance(options, list):
        items = options
    else:
        raise WriteError("enum 的 options 必须是数组或 {items:[...]} 对象")
    if not items:
        raise WriteError("enum 的 options 不能为空")
    seen: set[str] = set()
    for option in items:
        if not isinstance(option, dict):
            raise WriteError("enum 的 options 项必须是对象")
        value = option.get("value")
        label = option.get("label")
        if not isinstance(value, str) or not value.strip():
            raise WriteError("enum 的 options 项必须含非空 value")
        if not isinstance(label, str) or not label.strip():
            raise WriteError(f"enum 选项 {value} 必须含非空 label")
        tone = option.get("tone")
        if tone is None:
            raise WriteError(f"enum 选项 {value} 必须含 tone")
        if tone not in TONES:
            raise WriteError(f"enum 选项 {value} 的 tone 必须是 {sorted(TONES)} 之一")
        if value in seen:
            raise WriteError(f"enum 的 options 出现重复 value：{value}")
        seen.add(value)
        if "color" in option and option["color"] is not None:
            _validate_color(option["color"], f"enum 选项 {value}")
    return options


def _validate_constraints_spec(options: Any, field_type: str) -> None:
    if not isinstance(options, dict):
        return
    constraints = options.get("constraints")
    if constraints is None:
        return
    if not isinstance(constraints, dict):
        raise WriteError("options.constraints 必须是对象")
    for key in ("required", "enum_strict", "relation_must_exist"):
        if key in constraints and not isinstance(constraints[key], bool):
            raise WriteError(f"constraints.{key} 必须是布尔值")
    for key in ("min", "max"):
        if key in constraints:
            value = constraints[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise WriteError(f"constraints.{key} 必须是数字")
    if "min" in constraints and "max" in constraints:
        if constraints["min"] > constraints["max"]:
            raise WriteError("constraints.min 不能大于 constraints.max")
    if field_type != "number" and ("min" in constraints or "max" in constraints):
        raise WriteError("constraints.min/max 仅适用于 number 字段")
    # 未知键忽略（为 003 的 human_request / allow_override 预留），不阻断写入。


def _validate_number_options(options: Any) -> Any:
    if options is None:
        return None
    if not isinstance(options, dict):
        raise WriteError("number 的 options 必须是对象")
    if "decimals" in options:
        decimals = options["decimals"]
        if isinstance(decimals, bool) or not isinstance(decimals, int):
            raise WriteError("number.decimals 必须是 0–6 的整数")
        if not 0 <= decimals <= 6:
            raise WriteError("number.decimals 必须在 0–6 之间")
    if "percent" in options and not isinstance(options["percent"], bool):
        raise WriteError("number.percent 必须是布尔值")
    if "unit" in options:
        unit = options["unit"]
        if not isinstance(unit, str) or len(unit) > 8:
            raise WriteError("number.unit 必须是长度 ≤8 的字符串")
    return options


def _validate_datetime_options(options: Any) -> Any:
    if options is None:
        return None
    if not isinstance(options, dict):
        raise WriteError("datetime 的 options 必须是对象")
    if "with_time" in options and not isinstance(options["with_time"], bool):
        raise WriteError("datetime.with_time 必须是布尔值")
    return options


def _reverse_relation_exists(
    conn: sqlite3.Connection, table_id: str, target_table_id: str, exclude_field_id: str | None
) -> bool:
    if target_table_id == table_id:
        return False
    project = conn.execute(
        "SELECT project_id FROM tables WHERE id = ?", (table_id,)
    ).fetchone()
    if project is None:
        return False
    rows = conn.execute(
        """
        SELECT f.id, f.table_id, f.options
        FROM fields f JOIN tables t ON t.id = f.table_id
        WHERE t.project_id = ? AND f.type = 'relation'
        """,
        (project["project_id"],),
    ).fetchall()
    for row in rows:
        if exclude_field_id is not None and row["id"] == exclude_field_id:
            continue
        options = _loads(row["options"])
        if not isinstance(options, dict):
            continue
        if row["table_id"] == target_table_id and options.get("table_id") == table_id:
            return True
    return False


def _validate_options(
    conn: sqlite3.Connection,
    table_id: str,
    field_type: str,
    options: Any,
    *,
    field_id: str | None = None,
) -> Any:
    if field_type == "enum":
        options = _validate_enum_options(options)
        _validate_constraints_spec(options, field_type)
        return options

    if field_type == "computed":
        return calculation.validate_computed_options(
            conn, table_id, options, field_id=field_id
        )

    if field_type == "relation":
        if not isinstance(options, dict) or not isinstance(options.get("table_id"), str):
            raise WriteError('relation 的 options 必须形如 {"table_id": "..."}')
        target = options["table_id"]
        target_row = conn.execute(
            "SELECT project_id FROM tables WHERE id = ?", (target,)
        ).fetchone()
        if target_row is None:
            raise WriteError(f"relation 的目标表不存在：{target}")
        current = conn.execute(
            "SELECT project_id FROM tables WHERE id = ?", (table_id,)
        ).fetchone()
        if current is None or target_row["project_id"] != current["project_id"]:
            raise WriteError("relation 的目标表必须与当前表同属一个项目")
        if _reverse_relation_exists(conn, table_id, target, field_id):
            raise WriteError("禁止双向关联：目标表已存在指向当前表的 relation 字段")
        _validate_constraints_spec(options, field_type)
        return options

    if field_type == "number":
        options = _validate_number_options(options)
        _validate_constraints_spec(options, field_type)
        return options

    if field_type == "datetime":
        options = _validate_datetime_options(options)
        _validate_constraints_spec(options, field_type)
        return options

    if options is not None and not isinstance(options, dict):
        raise WriteError("text 的 options 必须是对象或 null")
    _validate_constraints_spec(options, field_type)
    return options


# ---------- 项目 ----------

def create_project(conn: sqlite3.Connection, body: dict[str, Any]) -> str:
    _reject_unknown_keys("project.create", body)
    name = _require_name(body)
    project_id = body.get("id") or f"p-{uuid.uuid4().hex[:8]}"
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise WriteError(f"项目 id 已存在：{project_id}")
    conn.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (project_id, name))
    return project_id


def delete_project(conn: sqlite3.Connection, project_id: str) -> str:
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        raise WriteError("项目不存在")
    table_ids = [
        row["id"]
        for row in conn.execute("SELECT id FROM tables WHERE project_id = ?", (project_id,)).fetchall()
    ]
    for table_id in table_ids:
        calculation.delete_values_for_table(conn, table_id)
        # business_changes 是追加式审计：删项目不擦除字段级追溯链（090-16）。
        conn.execute("DELETE FROM row_records WHERE table_id = ?", (table_id,))
        conn.execute("DELETE FROM fields WHERE table_id = ?", (table_id,))
    conn.execute("DELETE FROM tables WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return project_id


# ---------- 表格 ----------

def create_table(conn: sqlite3.Connection, project_id: str, body: dict[str, Any]) -> str:
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        raise WriteError("项目不存在")
    _reject_unknown_keys("table.create", body)
    name = _require_name(body)
    table_id = body.get("id") or f"t-{uuid.uuid4().hex[:8]}"
    order = body.get("order")
    if order is None:
        order = _next_order(
            conn, 'SELECT max("order") FROM tables WHERE project_id = ?', (project_id,)
        )
    else:
        order = _require_int(order, "order")
    kind = _require_table_kind(body.get("kind", "board"))
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone():
        raise WriteError(f"表格 id 已存在：{table_id}")
    conn.execute(
        'INSERT INTO tables (id, project_id, name, "order", kind) VALUES (?, ?, ?, ?, ?)',
        (table_id, project_id, name, int(order), kind),
    )
    return table_id


def update_table(conn: sqlite3.Connection, table_id: str, body: dict[str, Any]) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    _reject_unknown_keys("table.update", body)
    if "name" in body:
        conn.execute("UPDATE tables SET name = ? WHERE id = ?", (_require_name(body), table_id))
    if "order" in body:
        conn.execute(
            'UPDATE tables SET "order" = ? WHERE id = ?',
            (_require_int(body["order"], "order"), table_id),
        )
    if "kind" in body:
        conn.execute(
            "UPDATE tables SET kind = ? WHERE id = ?",
            (_require_table_kind(body["kind"]), table_id),
        )
    return table_id


def delete_table(conn: sqlite3.Connection, table_id: str) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    references = calculation.relations_to_table(conn, table_id)
    if references:
        names = "、".join(f"{ref['table_id']}.{ref['name']}" for ref in references)
        raise WriteError(f"表格仍被 relation 字段引用，请先删除：{names}")
    fields = _fields_map(conn, table_id)
    if run_protocol.is_run_table(fields) and conn.execute(
        "SELECT 1 FROM row_records WHERE table_id = ? LIMIT 1", (table_id,)
    ).fetchone():
        raise WriteError("执行记录表是验收证据，非空时不可整表删除")
    calculation.delete_values_for_table(conn, table_id)
    # 保留 business_changes：删表不擦审计（090-16）。
    conn.execute("DELETE FROM row_records WHERE table_id = ?", (table_id,))
    conn.execute("DELETE FROM fields WHERE table_id = ?", (table_id,))
    conn.execute("DELETE FROM tables WHERE id = ?", (table_id,))
    return table_id


# ---------- 字段 ----------

def create_field(
    conn: sqlite3.Connection,
    table_id: str,
    body: dict[str, Any],
    *,
    actor: str = "-",
    origin: str = "agent",
) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    _reject_unknown_keys("field.create", body)
    name = _require_name(body)
    field_type = body.get("type")
    if field_type not in FIELD_TYPES:
        raise WriteError(f"type 必须是 {sorted(FIELD_TYPES)} 之一")
    field_id = body.get("id") or f"f-{uuid.uuid4().hex[:8]}"
    options = _validate_options(
        conn, table_id, field_type, body.get("options"), field_id=field_id
    )
    order = body.get("order")
    if order is None:
        order = _next_order(
            conn, 'SELECT max("order") FROM fields WHERE table_id = ?', (table_id,)
        )
    else:
        order = _require_int(order, "order")
    visible = _require_visible(body.get("visible", 1))
    if conn.execute("SELECT 1 FROM fields WHERE id = ?", (field_id,)).fetchone():
        raise WriteError(f"字段 id 已存在：{field_id}")
    conn.execute(
        'INSERT INTO fields (id, table_id, name, type, options, "order", visible)'
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            field_id,
            table_id,
            name,
            field_type,
            json.dumps(options, ensure_ascii=False) if options is not None else None,
            int(order),
            visible,
        ),
    )
    if field_type == "computed":
        calculation.recompute_table(conn, table_id, actor=actor, origin=origin)
    return field_id


def update_field(
    conn: sqlite3.Connection,
    field_id: str,
    body: dict[str, Any],
    *,
    actor: str = "-",
    origin: str = "agent",
) -> str:
    field = conn.execute(
        "SELECT table_id, type, options FROM fields WHERE id = ?", (field_id,)
    ).fetchone()
    if field is None:
        raise WriteError("字段不存在")
    _reject_unknown_keys("field.update", body)

    if "type" in body or "options" in body:
        field_type = body.get("type", field["type"])
        if field_type not in FIELD_TYPES:
            raise WriteError(f"type 必须是 {sorted(FIELD_TYPES)} 之一")
        if field["type"] == "computed" and field_type != "computed":
            references = calculation.references_to_field(conn, field_id)
            if references:
                names = "、".join(ref["name"] for ref in references)
                raise WriteError(f"字段仍被计算字段引用，不能改为非计算字段：{names}")
            calculation.delete_values_for_field(conn, field_id)
        options = body["options"] if "options" in body else _loads(field["options"])
        options = _validate_options(
            conn, field["table_id"], field_type, options, field_id=field_id
        )
        conn.execute(
            'UPDATE fields SET type = ?, options = ? WHERE id = ?',
            (
                field_type,
                json.dumps(options, ensure_ascii=False) if options is not None else None,
                field_id,
            ),
        )

    if "name" in body:
        conn.execute("UPDATE fields SET name = ? WHERE id = ?", (_require_name(body), field_id))
    if "order" in body:
        conn.execute(
            'UPDATE fields SET "order" = ? WHERE id = ?',
            (_require_int(body["order"], "order"), field_id),
        )
    if "visible" in body:
        conn.execute(
            "UPDATE fields SET visible = ? WHERE id = ?",
            (_require_visible(body["visible"]), field_id),
        )
    # 被引用字段的类型/options 变化后，重新校验引用它的计算字段配置。
    for reference in calculation.references_to_field(conn, field_id):
        computed_field = conn.execute(
            "SELECT table_id, options FROM fields WHERE id = ?", (reference["field_id"],)
        ).fetchone()
        if computed_field is None:
            continue
        calculation.validate_computed_options(
            conn,
            computed_field["table_id"],
            _loads(computed_field["options"]),
            field_id=reference["field_id"],
        )
    calculation.recompute_for_write(
        conn, field["table_id"], actor=actor, origin=origin
    )
    return field_id


def delete_field(
    conn: sqlite3.Connection,
    field_id: str,
    *,
    actor: str = "-",
    origin: str = "agent",
) -> str:
    field = conn.execute(
        "SELECT table_id, name FROM fields WHERE id = ?", (field_id,)
    ).fetchone()
    if field is None:
        raise WriteError("字段不存在")
    references = calculation.references_to_field(conn, field_id)
    if references:
        names = "、".join(ref["name"] for ref in references)
        raise WriteError(f"字段仍被计算字段引用，不能删除：{names}")
    calculation.delete_values_for_field(conn, field_id)
    conn.execute("DELETE FROM fields WHERE id = ?", (field_id,))
    calculation.recompute_for_write(
        conn, field["table_id"], actor=actor, origin=origin
    )
    return field_id


# ---------- 业务变更记录 ----------

def _encode_value(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


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
            _encode_value(old_value),
            _encode_value(new_value),
            change_kind,
            reason,
        ),
    )


# ---------- 数据行 ----------

def _fields_map(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    # `order` 供 025 的六节点识别兜底排序用（字段 id 解析不出语义键时按契约顺序判定串行）。
    rows = conn.execute(
        'SELECT id, name, type, options, "order" FROM fields WHERE table_id = ?', (table_id,)
    ).fetchall()
    return {row["id"]: row for row in rows}


def _owner_field(fields: dict[str, sqlite3.Row]) -> sqlite3.Row | None:
    """识别本表的负责人字段；多义时不猜（返回 None），交人工填。"""
    by_id = [
        field
        for field in fields.values()
        if field["type"] == "text" and field["id"].endswith(OWNER_FIELD_SUFFIX)
    ]
    candidates = by_id or [
        field
        for field in fields.values()
        if field["type"] == "text" and field["name"] == OWNER_FIELD_NAME
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def _fill_owner(fields: dict[str, sqlite3.Row], values: dict[str, Any], caller: str) -> dict[str, Any]:
    """新建行时负责人缺省由调用者身份填充；已有值/显式值优先。"""
    owner = _owner_field(fields)
    if owner is None or not _is_empty(values.get(owner["id"])):
        return values
    return {**values, owner["id"]: caller}


def _validate_row_id(row_id: Any) -> str:
    if not isinstance(row_id, str) or not ROW_ID_RE.match(row_id):
        raise WriteError("行 id 必须是业务编号，匹配 ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    return row_id


def _validate_scalar_type(field: sqlite3.Row, value: Any) -> None:
    """text/number/datetime 的运行时类型：非字符串文本、非数字数字、非 ISO 时间一律拒收。

    历史脏数据不受影响（只校验本次提交的 values，不校验合并后的整行）。
    """
    if _is_empty(value):
        return
    kind = field["type"]
    name = field["name"]
    if kind == "text":
        if not isinstance(value, str):
            raise WriteError(f"字段「{name}」必须是文本，收到 {type(value).__name__}")
        return
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WriteError(f"字段「{name}」必须是数字，收到 {value!r}")
        if not math.isfinite(value):
            raise WriteError(f"字段「{name}」必须是有限数字，收到 {value!r}")
        return
    if kind == "datetime":
        if not isinstance(value, str):
            raise WriteError(f"字段「{name}」必须是 ISO 时间字符串，收到 {type(value).__name__}")
        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise WriteError(f"字段「{name}」不是合法 ISO 时间：{value!r}") from None


def _validate_values(
    conn: sqlite3.Connection, table_id: str, fields: dict[str, sqlite3.Row], values: dict[str, Any]
) -> None:
    if not isinstance(values, dict):
        raise WriteError("values 必须是对象")
    unknown = set(values) - set(fields)
    if unknown:
        raise WriteError(f"未知字段键：{sorted(unknown)}")
    computed_keys = [key for key, field in fields.items() if field["type"] == "computed" and key in values]
    if computed_keys:
        raise WriteError(f"计算字段不能直接写入：{sorted(computed_keys)}")
    for key, value in values.items():
        field = fields[key]
        _validate_scalar_type(field, value)
        if field["type"] == "enum" and not _is_empty(value):
            items = _enum_items(_loads(field["options"]))
            allowed = [item.get("value") for item in items if isinstance(item, dict)]
            if allowed and value not in allowed:
                raise WriteError(
                    f"字段「{field['name']}」的值不在枚举范围内：{value!r}；合法取值：{allowed}"
                )
        if field["type"] != "relation":
            continue
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise WriteError(f"relation 字段 {key} 的值必须是字符串数组")


def _validate_row_constraints(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    values: dict[str, Any],
    *,
    relation_field_ids: set[str] | None = None,
) -> None:
    """校验行值约束。

    `relation_field_ids` 非空时只校验这些字段的“关联目标必须存在”：
    更新行只校验本次提交的关系字段，存量悬空引用不阻断无关字段的编辑（V060-04）。
    必填/min/max/enum 仍按合并后的整行校验，保证行始终合法。
    """
    for field_id, field in fields.items():
        options = _loads(field["options"])
        if not isinstance(options, dict):
            continue
        constraints = options.get("constraints")
        if not isinstance(constraints, dict):
            continue
        value = values.get(field_id)
        if constraints.get("required") and _is_empty(value):
            raise WriteError(f"字段「{field['name']}」必填")
        if field["type"] == "number" and not _is_empty(value):
            # 非数字值不参与 min/max 比较（历史脏数据不阻断写入）。
            if not isinstance(value, bool) and isinstance(value, (int, float)):
                if "min" in constraints and value < constraints["min"]:
                    raise WriteError(f"字段「{field['name']}」不能小于 {constraints['min']}")
                if "max" in constraints and value > constraints["max"]:
                    raise WriteError(f"字段「{field['name']}」不能大于 {constraints['max']}")
        if field["type"] == "enum" and constraints.get("enum_strict") and not _is_empty(value):
            allowed = {item.get("value") for item in _enum_items(options) if isinstance(item, dict)}
            if value not in allowed:
                raise WriteError(f"字段「{field['name']}」的值不在枚举范围内：{value}")
        if field["type"] == "relation" and constraints.get("relation_must_exist") and not _is_empty(value):
            if relation_field_ids is not None and field_id not in relation_field_ids:
                continue
            target = options.get("table_id")
            for target_id in value:
                exists = conn.execute(
                    "SELECT 1 FROM row_records WHERE table_id = ? AND id = ?",
                    (target, target_id),
                ).fetchone()
                if exists is None:
                    raise WriteError(f"关联目标行不存在：{target}/{target_id}")


def _changes_for_create(
    conn: sqlite3.Connection,
    *,
    actor: str,
    origin: str,
    table_id: str,
    row_id: str,
    fields: dict[str, sqlite3.Row],
    values: dict[str, Any],
) -> None:
    for field_id, value in values.items():
        if _is_empty(value):
            continue
        _record_change(
            conn,
            actor=actor,
            origin=origin,
            table_id=table_id,
            row_id=row_id,
            field_id=field_id,
            field_name=fields[field_id]["name"],
            old_value=None,
            new_value=value,
            change_kind="create",
        )


def drop_spec_row(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    body: dict[str, Any],
    *,
    actor: str,
    origin: str,
) -> dict[str, Any]:
    """原子放弃独立需求：摘关系 + 置 dropped + 字段级留痕 + 重算（034 原子性，090-04）。"""
    result = spec_lifecycle.drop_spec(
        conn, table_id, row_id, reason=body.get("reason"), at=body.get("at")
    )
    changes = result.pop("changes", [])
    reason = str(body.get("reason") or "").strip() or None
    for change in changes:
        _record_change(
            conn,
            actor=actor,
            origin=origin,
            table_id=change["table_id"],
            row_id=change["row_id"],
            field_id=change["field_id"],
            field_name=change["field_name"],
            old_value=change["old"],
            new_value=change["new"],
            change_kind="update",
            reason=reason,
        )
    for table in {table_id, *[change["table_id"] for change in changes]}:
        calculation.recompute_for_write(conn, table, actor=actor, origin=origin)
    return {"result": "success", "id": row_id, **result}


def split_spec_row(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    body: dict[str, Any],
    *,
    actor: str,
    origin: str,
) -> dict[str, Any]:
    """原子拆分：新建承接需求 + 原需求留痕，一次事务完成（090-07）。"""
    result = spec_lifecycle.split_spec(
        conn,
        table_id,
        row_id,
        target=body.get("to"),
        clauses=body.get("clauses"),
        at=body.get("at"),
    )
    changes = result.pop("changes", [])
    for change in changes:
        _record_change(
            conn,
            actor=actor,
            origin=origin,
            table_id=change["table_id"],
            row_id=change["row_id"],
            field_id=change["field_id"],
            field_name=change["field_name"],
            old_value=change["old"],
            new_value=change["new"],
            change_kind=change["kind"],
        )
    calculation.recompute_for_write(conn, table_id, actor=actor, origin=origin)
    return {"result": "success", "id": row_id, **result}


def create_row(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    body: dict[str, Any],
    *,
    actor: str = "-",
    origin: str = "agent",
    autofill_owner_by: str | None = None,
) -> str:
    if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
        raise WriteError("表格不存在")
    _validate_row_id(row_id)
    _reject_unknown_keys("row.create", body)
    body_id = body.get("id")
    if body_id is not None and body_id != row_id:
        raise WriteError("body.id 与路径 row_id 不一致")
    values = body.get("values") or {}
    if not isinstance(values, dict):
        raise WriteError("values 必须是对象")
    fields = _fields_map(conn, table_id)
    if autofill_owner_by:
        # 兼容期只有 key 鉴权的调用者填充负责人；旧 X-Agent-Id 调用保持原样。
        values = _fill_owner(fields, values, autofill_owner_by)
    _validate_values(conn, table_id, fields, values)
    run_protocol.validate_row_write(
        conn, fields, row_id, merged=values, submitted=values, creating=True
    )
    version_stage.validate_row_write(conn, fields, row_id, merged=values, previous={})
    board_rules.validate_row_write(
        conn, table_id, fields, row_id, merged=values, previous={}, submitted=values
    )
    spec_lifecycle.validate_row_write(
        conn, table_id, fields, row_id, merged=values, previous={}, submitted=values
    )
    stage_evidence.validate_row_write(
        conn, table_id, fields, row_id, merged=values, previous={}, submitted=values
    )
    change_flow.validate_row_write(
        conn, table_id, fields, row_id, merged=values, previous={}, submitted=values
    )
    _validate_row_constraints(conn, fields, values)
    if conn.execute(
        "SELECT 1 FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id)
    ).fetchone():
        if run_protocol.is_run_table(fields):
            # 行 id 已是 <版本号>--<用例号>：同版本同用例重复纳入必然撞到同一行。
            raise WriteError(
                f"该用例已纳入本版本（执行记录已存在）：{row_id}；"
                "请回读该行后继续，不新建第二条记录"
            )
        raise WriteError(f"行 id 已存在：{row_id}")
    conn.execute(
        "INSERT INTO row_records (id, table_id, data) VALUES (?, ?, ?)",
        (row_id, table_id, json.dumps(values, ensure_ascii=False)),
    )
    _changes_for_create(
        conn,
        actor=actor,
        origin=origin,
        table_id=table_id,
        row_id=row_id,
        fields=fields,
        values=values,
    )
    calculation.recompute_for_write(conn, table_id, actor=actor, origin=origin)
    return row_id


def update_row(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    body: dict[str, Any],
    *,
    actor: str = "-",
    origin: str = "agent",
) -> str:
    if "id" in body:
        raise WriteError("行 id 不可变")
    _reject_unknown_keys("row.update", body)
    row = conn.execute(
        "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id)
    ).fetchone()
    if row is None:
        raise WriteError("行不存在")
    values = body.get("values") or {}
    if not isinstance(values, dict):
        raise WriteError("values 必须是对象")
    fields = _fields_map(conn, table_id)
    _validate_values(conn, table_id, fields, values)
    old_values = _loads(row["data"]) or {}
    merged = {**old_values, **values}
    run_protocol.validate_row_write(
        conn, fields, row_id, merged=merged, submitted=values, creating=False
    )
    version_stage.validate_row_write(conn, fields, row_id, merged=merged, previous=old_values)
    board_rules.validate_row_write(
        conn, table_id, fields, row_id,
        merged=merged, previous=old_values, submitted=values,
    )
    spec_lifecycle.validate_row_write(
        conn, table_id, fields, row_id,
        merged=merged, previous=old_values, submitted=values,
    )
    stage_evidence.validate_row_write(
        conn, table_id, fields, row_id,
        merged=merged, previous=old_values, submitted=values,
    )
    change_flow.validate_row_write(
        conn, table_id, fields, row_id,
        merged=merged, previous=old_values, submitted=values,
    )
    # 只对本次提交的关系字段校验“目标行必须存在”；存量悬空引用不阻断无关字段的编辑（V060-04）。
    _validate_row_constraints(conn, fields, merged, relation_field_ids=set(values))

    for field_id, new_value in values.items():
        old_value = old_values.get(field_id)
        if old_value == new_value:
            continue
        _record_change(
            conn,
            actor=actor,
            origin=origin,
            table_id=table_id,
            row_id=row_id,
            field_id=field_id,
            field_name=fields[field_id]["name"],
            old_value=old_value,
            new_value=new_value,
            change_kind="update",
        )
    conn.execute(
        "UPDATE row_records SET data = ? WHERE table_id = ? AND id = ?",
        (json.dumps(merged, ensure_ascii=False), table_id, row_id),
    )
    calculation.recompute_for_write(conn, table_id, actor=actor, origin=origin)
    if "overrides" in body:
        calculation.apply_overrides(
            conn,
            table_id,
            row_id,
            body["overrides"],
            fields,
            actor=actor,
            origin=origin,
        )
    return row_id


def _reject_delete_of_released_version(
    fields: dict[str, sqlite3.Row], row_id: str, values: dict[str, Any]
) -> None:
    """删除同样受发布冻结约束：已发布版本不可物理删除（090-16）。"""
    status = next((field for field in fields.values() if field["name"] == "发布状态"), None)
    if status is not None and values.get(status["id"]) == "released":
        raise WriteError(f"L7：版本 {row_id} 已发布，不可删除；发布历史不可回写")


def delete_row(
    conn: sqlite3.Connection,
    table_id: str,
    row_id: str,
    *,
    actor: str = "-",
    origin: str = "agent",
) -> str:
    row = conn.execute(
        "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id)
    ).fetchone()
    if row is None:
        raise WriteError("行不存在")
    fields = _fields_map(conn, table_id)
    old_values = _loads(row["data"]) or {}
    _reject_delete_of_released_version(fields, row_id, old_values)
    if run_protocol.is_run_table(fields):
        raise WriteError(
            "执行记录是验收证据，不可物理删除；重跑请 PATCH 状态/结果，"
            "移除用例请改版本清单并说明（036：不得通过删除用例绕过失败项）"
        )
    for field_id, old_value in old_values.items():
        if _is_empty(old_value) or field_id not in fields:
            continue
        _record_change(
            conn,
            actor=actor,
            origin=origin,
            table_id=table_id,
            row_id=row_id,
            field_id=field_id,
            field_name=fields[field_id]["name"],
            old_value=old_value,
            new_value=None,
            change_kind="delete",
        )
    calculation.delete_values_for_row(conn, table_id, row_id)
    conn.execute("DELETE FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id))
    calculation.recompute_for_write(conn, table_id, actor=actor, origin=origin)
    return row_id
