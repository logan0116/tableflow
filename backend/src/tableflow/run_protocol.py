"""执行记录（`run`）写入协议：状态/结果一致性、行 id 形状与执行清单去重（020）。

board@4 把「跑没跑」与「跑得怎么样」拆成两个字段：`run.state` 只管进度，
`run.result` 只管结论。两者一旦不一致，版本表的用例进度就会与结论打架
（例如 `state=todo` 却已有 `result=pass`：版本显示"未执行"，明细显示"通过"）。
本模块把契约 `rules.run_state_result_consistency` 落到写侧，并把另外两条
与"同版本同用例只有一条执行记录"直接相关的口径一起收紧：

1. 状态/结果一致：`state=todo` 时 `result` 必须为空，`state=done` 时 `result` 必须非空；
   `result` 非空而 `state` 未置时同样拒绝（有结论就必须有执行状态）。
2. 执行记录行 id 形状：`<版本号>--<用例号>`（如 `v0.7.0--008-US1-AS1`）；
   `run.case_no` 与行 id 的用例号后缀必须一致——行 id 就是"同版本同用例"的幂等键，
   形状不写死，重复纳入就无法靠行 id 冲突识别。
3. 执行清单不重复：`ver.runs` 这类指向执行记录表的 relation 值里不得出现重复 id，
   且版本行的清单只能收录 `<本行版本号>--<用例号>`（防止把 v0.8.0 的记录挂进 v0.7.0）。

识别方式（不依赖表 id、字段 id/名称、也不依赖表级 `kind`——`kind` 落库属 019 实现范围）：
表内同时存在**值域恰为 `{todo, done}`** 的 enum 字段，与**值域是
`{pass, fail, blocked, skip}` 子集**的 enum 字段。board@4 六表里只有 `run.state`
的值域是 `{todo, done}`、只有 `run.result` 的值域落在这个结论集合内，按值域识别
既不会被 `spec.stage`（含 doing/na）或 `ver.stage.*`（含 doing/failed）误命中，
也不要求迁移脚本把字段 id 起成某个名字。
多义（同值域的候选字段不止一个）时不猜、不启用，与 `write_service._owner_field` 同一纪律。
`run.case_no` 同样不靠固定 id：优先认 id 以 `-case_no` 结尾的文本字段，
退一步认名称恰为「用例号」的文本字段；找不到就不做这项校验（不猜）。

所有校验都在任何落库语句之前完成，失败由 `WriteError` 转 400，整请求零写入
（`write_service.run_write` 负责回滚并记一条失败审计）。信封仍是 protocol@2 的
`{"result":"failed","error":"..."}`，不新增路径、不新增响应字段。
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .errors import WriteError

RUN_STATE_VALUES = frozenset({"todo", "done"})
RUN_RESULT_VALUES = frozenset({"pass", "fail", "blocked", "skip"})
# 用例号字段的兜底识别：迁移脚本若没沿用 `-case_no` 后缀，至少认契约里的名称。
RUN_CASE_NO_FIELD_NAME = "用例号"
# 执行记录行 id：<版本号>--<用例号>。版本号形如 v0.7.0，用例号即场景号（008-US1-AS1）。
RUN_ID_RE = re.compile(r"^v\d+\.\d+\.\d+--[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
VERSION_ID_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def _loads(raw: Any) -> Any:
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
    values = {
        item.get("value")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("value"), str)
    }
    return frozenset(values)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _unique(candidates: list[sqlite3.Row]) -> sqlite3.Row | None:
    return candidates[0] if len(candidates) == 1 else None


def state_result_fields(
    fields: dict[str, sqlite3.Row],
) -> tuple[sqlite3.Row, sqlite3.Row] | None:
    """按枚举值域识别执行记录表，返回 (state 字段, result 字段)；不是执行记录表则 None。"""
    state = _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "enum" and _enum_values(field) == RUN_STATE_VALUES
        ]
    )
    result = _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "enum"
            and bool(_enum_values(field))
            and _enum_values(field) <= RUN_RESULT_VALUES
        ]
    )
    if state is None or result is None:
        return None
    return state, result


def is_run_table(fields: dict[str, sqlite3.Row]) -> bool:
    return state_result_fields(fields) is not None


def _case_no_field(fields: dict[str, sqlite3.Row]) -> sqlite3.Row | None:
    """用例号字段：优先 id 后缀 `-case_no`，退一步认名称「用例号」；多义不猜。"""
    by_id = _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "text" and field["id"].endswith("-case_no")
        ]
    )
    if by_id is not None:
        return by_id
    return _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "text" and field["name"] == RUN_CASE_NO_FIELD_NAME
        ]
    )


def _check_state_result(state_field: sqlite3.Row, result_field: sqlite3.Row, values: dict[str, Any]) -> None:
    state = values.get(state_field["id"])
    result = values.get(result_field["id"])
    if _is_empty(state):
        if not _is_empty(result):
            raise WriteError(
                "执行状态与执行结果不一致：填了执行结果"
                f"（{result_field['name']}={result}）却没有执行状态；"
                "state 必须是 todo 或 done"
            )
        return
    if state == "todo" and not _is_empty(result):
        raise WriteError(
            "执行状态与执行结果不一致：state=todo 时 result 必须为空"
            f"（当前 {result_field['name']}={result}）"
        )
    if state == "done" and _is_empty(result):
        raise WriteError(
            "执行状态与执行结果不一致：state=done 时 result 必须非空"
            f"（{', '.join(sorted(RUN_RESULT_VALUES))}）"
        )


def _check_case_no(row_id: str, values: dict[str, Any], fields: dict[str, sqlite3.Row]) -> None:
    case_no_field = _case_no_field(fields)
    if case_no_field is None:
        return
    case_no = values.get(case_no_field["id"])
    if _is_empty(case_no):
        return
    suffix = row_id.split("--", 1)[1]
    if case_no != suffix:
        raise WriteError(
            f"{case_no_field['name']} 必须与执行记录行 id 的用例号一致："
            f"行 id={row_id}，{case_no_field['name']}={case_no}"
        )


def _check_run_row_id(row_id: str, values: dict[str, Any], fields: dict[str, sqlite3.Row]) -> None:
    if not RUN_ID_RE.match(row_id):
        raise WriteError(
            "执行记录行 id 必须是「<版本号>--<用例号>」（如 v0.7.0--008-US1-AS1）："
            f"{row_id!r}"
        )
    _check_case_no(row_id, values, fields)


def _table_fields(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, name, type, options FROM fields WHERE table_id = ?", (table_id,)
    ).fetchall()
    return {row["id"]: row for row in rows}


def _check_run_list(row_id: str, field: sqlite3.Row, ids: list[Any]) -> None:
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise WriteError(
            f"执行清单不得重复纳入同一执行记录：{duplicates}（字段「{field['name']}」）"
        )
    if not VERSION_ID_RE.match(row_id):
        return
    foreign = [item for item in ids if not str(item).startswith(f"{row_id}--")]
    if foreign:
        raise WriteError(
            f"执行清单只能收录本版本的执行记录（{row_id}--<用例号>）：{foreign}"
        )


def validate_row_write(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    *,
    merged: dict[str, Any],
    submitted: dict[str, Any],
    creating: bool,
) -> None:
    """执行记录表与执行清单的写侧校验；不一致一律 `WriteError`（400，零写入）。

    `merged` 是合并后的整行（新建时即提交值），用于状态/结果校验；
    `submitted` 是本次请求提交的键，关系清单只校验本次提交的字段
    （存量悬空/脏数组不阻断无关字段的编辑，沿用 V060-04 口径）。
    """
    pair = state_result_fields(fields)
    if pair is not None:
        _check_state_result(pair[0], pair[1], merged)
        if creating:
            _check_run_row_id(row_id, merged, fields)
        elif RUN_ID_RE.match(row_id):
            # 存量行可能有不合法 id（协议前写入）：不再用 id 形状卡住编辑，
            # 但 case_no 与 id 后缀的可核对关系仍要求一致。
            _check_case_no(row_id, merged, fields)

    for field_id in sorted(set(submitted) & set(fields)):
        field = fields[field_id]
        if field["type"] != "relation":
            continue
        options = _loads(field["options"])
        target_table = options.get("table_id") if isinstance(options, dict) else None
        if not isinstance(target_table, str):
            continue
        if not is_run_table(_table_fields(conn, target_table)):
            continue
        ids = merged.get(field_id)
        if not isinstance(ids, list):
            continue
        _check_run_list(row_id, field, ids)
