"""版本表六节点（`ver.stage.*`）写侧校验：串行推进与节点闸门一致性（025）。

board@4 把版本进度拆成六个四态 enum 节点（契约 `status_definitions.version_stage`）：

    ver.stage.plan → ver.stage.test_design → ver.stage.dev
        → ver.stage.dev_accept → ver.stage.test → ver.stage.test_accept

人工可以填这六个字段，但"填"必须受两条约束（契约 `rules.version_stage_serial` /
`rules.version_stage_gate_consistency`），否则发布条件能被一路手改成全绿：

1. **串行推进**：节点到达 `done` 时，它左边的节点必须全部 `done`；任一前序节点是
   `failed` 时，该节点不得向前推进（`doing`/`done` 都不行，返工改回 `doing` 才能再走）。
   反向移动（例如把后序节点改回 `todo`）不拦，也**不会自动回退下游节点**。
2. **节点闸门一致性**：三个关键节点到达 `done` 时，还要有数据支撑：
   - `开发验收`（dev_accept）：本版规格（`ver.specs`）全部 `spec.acceptance == accepted`；
   - `测试`（test）：本版用例（`ver.runs`）全部 `run.state == done`；
   - `测试验收`（test_accept）：本版缺陷（`ver.bugs`）全部 `bug.status == closed`，
     且本版变更单（`ver.changes`）全部 `change.regress == passed`。

**为什么直接读源数据、不读 `case_done`/`bug_clear`/`change_done`/`spec_done` 计算值**：
`update_row` 里的校验发生在重算之前，同一请求既追加 `runs` 又置 `stage.test=done` 时
计算值还是旧的。这里按与 010 相同的空集/悬空口径自行判定（空集为真、目标行缺失按
未就绪），与计算字段等价且不受重算时机影响。

识别方式（不依赖表 id、字段 id 或表级 `kind`，与 020 的 `run_protocol` 同一纪律）：
表内**恰好六个**枚举值域为 `{todo,doing,done,failed}` 的 enum 字段即六节点。
顺序优先按节点语义键（字段 id 里的 `stage-*` 段，退一步按契约名称）解析后取契约顺序；
解析不全时退回字段 `order`（019 门禁保证六节点按契约顺序落库），此时仅跳过无法定位的
闸门项而不是猜。节点闸门依赖的 relation 按**目标表值域**识别（run / bug / dep / indep），
认不出时该项校验不启用（由 019 门禁保证字段存在），不阻断其它校验。

所有校验都在任何落库语句之前完成，失败由 `WriteError` 转 400，整请求零写入
（`write_service.run_write` 回滚并记失败审计）。信封不变（protocol@2）。
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from . import run_protocol
from .errors import WriteError

STAGE_VALUES = frozenset({"todo", "doing", "done", "failed"})
STAGE_KEYS = ("plan", "test_design", "dev", "dev_accept", "test", "test_accept")
STAGE_LABELS = {
    "plan": "版本需求设计",
    "test_design": "测试设计",
    "dev": "开发",
    "dev_accept": "开发验收",
    "test": "测试",
    "test_accept": "测试验收",
}
NAME_TO_KEY = {label: key for key, label in STAGE_LABELS.items()}

# 目标表（版本表关联进来的"证据来源"）识别：按目标表的判据枚举值域。
BUG_STATUS_VALUES = frozenset({"open", "fixing", "verifying", "closed"})
RUN_RESULT_VALUES = frozenset({"pass", "fail", "blocked", "skip"})
WAIVER_VALUES = frozenset({"none", "waived"})
WAIVER_BY_NAME = "放行批准人"
WAIVER_REASON_NAME = "放行理由"
REGRESS_VALUES = frozenset({"todo", "doing", "passed", "failed"})
ACCEPTANCE_VALUES = frozenset({"pending", "accepted", "rejected", "dropped"})
# board@5 前是三元域；迁移未完成的项目仍按三元识别，两种都认
ACCEPTANCE_DOMAINS = frozenset({
    ACCEPTANCE_VALUES,
    frozenset({"pending", "accepted", "rejected"}),
})

# 节点钥匙 → (来源角色, 判据字段取值, 人读说明)。
NODE_REQUIREMENTS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "dev_accept": (("indep", "accepted", "本版规格必须全部 accepted"),),
    "test": (("run", "done", "本版用例必须全部执行"),),
    "test_accept": (
        ("run", "done", "本版用例必须全部执行"),
        ("bug", "closed", "本版缺陷必须全部 closed"),
        ("dep", "passed", "本版变更单必须全部 passed（回归通过）"),
    ),
}

_FORWARD_VALUES = frozenset({"doing", "done"})


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
    return frozenset(
        item.get("value")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("value"), str)
    )


def _table_fields(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, name, type, options, \"order\" FROM fields WHERE table_id = ?",
        (table_id,),
    ).fetchall()
    return {row["id"]: row for row in rows}


def _unique(items: list) -> Any | None:
    return items[0] if len(items) == 1 else None


def _node_key(field: sqlite3.Row) -> str | None:
    """节点语义键：先认字段 id 里的 `stage-*` 段（迁移脚本写法），再认契约名称。"""
    match = re.search(r"stage[-_]?(.+)$", str(field["id"]).lower())
    if match:
        tail = match.group(1).strip("-_").replace("-", "_")
        if tail in STAGE_KEYS:
            return tail
    return NAME_TO_KEY.get(field["name"])


def stage_nodes(
    fields: dict[str, sqlite3.Row],
) -> list[tuple[sqlite3.Row, str | None]] | None:
    """识别六节点；不是版本表的六节点结构（不是恰好六个四态 enum）返回 None。

    返回按推进顺序排好的 [(字段, 语义键或 None)]。语义键全部解析成功时按契约顺序排，
    否则退回字段 `order`（不猜节点身份，闸门项按已解析的键启用）。
    """
    nodes = [
        field
        for field in fields.values()
        if field["type"] == "enum" and _enum_values(field) == STAGE_VALUES
    ]
    if len(nodes) != 6:
        return None
    nodes.sort(key=lambda field: (int(field["order"]), str(field["id"])))
    keys = [_node_key(field) for field in nodes]
    if all(key is not None for key in keys) and len(set(keys)) == 6:
        ordered = sorted(zip(keys, nodes), key=lambda pair: STAGE_KEYS.index(pair[0]))  # type: ignore[arg-type]
        return [(field, key) for key, field in ordered]  # type: ignore[misc]
    return [(field, key) for field, key in zip(nodes, keys)]


def _completion_field(fields: dict[str, sqlite3.Row], role: str) -> sqlite3.Row | None:
    """目标表的判据字段：run → state，bug → status，dep → regress，indep → acceptance。"""
    if role == "run":
        pair = run_protocol.state_result_fields(fields)
        return pair[0] if pair is not None else None
    domains = {
        "bug": frozenset({BUG_STATUS_VALUES}),
        "dep": frozenset({REGRESS_VALUES}),
        "indep": ACCEPTANCE_DOMAINS,
    }[role]
    return _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "enum" and _enum_values(field) in domains
        ]
    )


def _target_role(fields: dict[str, sqlite3.Row]) -> str | None:
    if run_protocol.is_run_table(fields):
        return "run"
    domains = {
        _enum_values(field)
        for field in fields.values()
        if field["type"] == "enum"
    }
    for role, domain_set in (
        ("bug", frozenset({BUG_STATUS_VALUES})),
        ("dep", frozenset({REGRESS_VALUES})),
        ("indep", ACCEPTANCE_DOMAINS),
    ):
        if domain_set & domains:
            return role
    return None


def _relation_sources(
    conn: sqlite3.Connection, fields: dict[str, sqlite3.Row]
) -> dict[str, tuple[sqlite3.Row, str, sqlite3.Row]]:
    """版本表里指向"证据来源"的 relation：角色 → (relation 字段, 目标表 id, 判据字段)。

    同一角色有多个 relation 时不猜（该角色不启用）。
    """
    candidates: dict[str, list[tuple[sqlite3.Row, str, sqlite3.Row]]] = {}
    for field in fields.values():
        if field["type"] != "relation":
            continue
        options = _loads(field["options"])
        target_id = options.get("table_id") if isinstance(options, dict) else None
        if not isinstance(target_id, str):
            continue
        target_fields = _table_fields(conn, target_id)
        role = _target_role(target_fields)
        if role is None:
            continue
        completion = _completion_field(target_fields, role)
        if completion is None:
            continue
        candidates.setdefault(role, []).append((field, target_id, completion))
    return {
        role: entries[0]
        for role, entries in candidates.items()
        if len(entries) == 1
    }


def _fetch_values(
    conn: sqlite3.Connection, table_id: str, ids: list[str]
) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, data FROM row_records WHERE table_id = ? AND id IN ({placeholders})",
        (table_id, *ids),
    ).fetchall()
    return {row["id"]: _loads(row["data"]) or {} for row in rows}


def _unsatisfied(
    conn: sqlite3.Connection,
    table_id: str,
    relation_field: sqlite3.Row,
    completion_field: sqlite3.Row,
    expected: str,
    values: dict[str, Any],
) -> list[str]:
    ids = values.get(relation_field["id"])
    if not isinstance(ids, list) or not ids:
        return []  # 空集为真（board@4 empty_set）
    rows = _fetch_values(conn, table_id, [str(item) for item in ids])
    problems: list[str] = []
    for row_id in ids:
        data = rows.get(str(row_id))
        if data is None:
            problems.append(f"{row_id}=<行不存在>")
            continue
        actual = data.get(completion_field["id"])
        if actual != expected:
            problems.append(f"{row_id}={actual}")
    return problems


def _run_quality_fields(
    fields: dict[str, sqlite3.Row],
) -> tuple[sqlite3.Row | None, sqlite3.Row | None, sqlite3.Row | None, sqlite3.Row | None]:
    """执行记录的质量判据：执行结果、放行标记、批准人、理由。认不出返回 None（不猜）。"""
    if run_protocol.state_result_fields(fields) is None:
        return None, None, None, None
    result = _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "enum" and _enum_values(field) == RUN_RESULT_VALUES
        ]
    )
    waived = _unique(
        [
            field
            for field in fields.values()
            if field["type"] == "enum" and _enum_values(field) == WAIVER_VALUES
        ]
    )
    by_name = {
        field["name"]: field for field in fields.values() if field["type"] == "text"
    }
    return result, waived, by_name.get(WAIVER_BY_NAME), by_name.get(WAIVER_REASON_NAME)


def _owned_run_ids(
    conn: sqlite3.Connection, run_table_id: str, version_id: str
) -> list[str]:
    """本版本在执行记录表里实际存在的行：id 以 ``<版本号>--`` 开头。

    020 规定执行记录行 id 是 ``<版本号>--<用例号>``，版本号取版本行 id 本身，
    所以前缀就是归属关系，不依赖 ``ver.runs`` 这条可被改写的关联。
    """
    prefix = f"{version_id}--"
    rows = conn.execute(
        "SELECT id FROM row_records WHERE table_id = ?", (run_table_id,)
    ).fetchall()
    return sorted(str(row["id"]) for row in rows if str(row["id"]).startswith(prefix))


def _run_result_problems(
    conn: sqlite3.Connection,
    target_id: str,
    relation_field: sqlite3.Row,
    values: dict[str, Any],
    version_id: str,
) -> list[str]:
    """036：执行结果必须 pass，或带有效放行标记（批准人与理由都不为空）。

    判定对象是「本版本实际持有的执行行」，与本次提交的清单取并集：
    把失败行从 ``ver.runs`` 里摘掉、或把清单清空，都不能减少被判定的行。
    """
    submitted = values.get(relation_field["id"])
    ids = [str(item) for item in submitted] if isinstance(submitted, list) else []
    ids = sorted(set(ids) | set(_owned_run_ids(conn, target_id, version_id)))
    if not ids:
        return []  # 空集为真：新版本尚无执行记录时不拦（与 computed 的 and 同口径）
    fields = _table_fields(conn, target_id)
    result, waived, by_field, reason_field = _run_quality_fields(fields)
    if result is None:
        return []  # 认不出质量字段：不猜
    rows = _fetch_values(conn, target_id, [str(item) for item in ids])
    problems: list[str] = []
    for row_id in ids:
        data = rows.get(str(row_id))
        if data is None:
            continue  # 行不存在由 _unsatisfied 报
        outcome = data.get(result["id"])
        if outcome == "pass":
            continue
        if (
            waived is not None
            and by_field is not None
            and reason_field is not None
            and data.get(waived["id"]) == "waived"
            and (data.get(by_field["id"]) or "").strip()
            and (data.get(reason_field["id"]) or "").strip()
        ):
            continue
        problems.append(f"{row_id}={outcome if outcome not in (None, '') else '空'}")
    return problems


def _check_serial(
    nodes: list[tuple[sqlite3.Row, str | None]],
    merged: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    for index, (field, _key) in enumerate(nodes):
        new_value = merged.get(field["id"])
        if new_value == previous.get(field["id"]):
            continue
        if new_value not in _FORWARD_VALUES:
            continue  # 反向移动（含改回 todo）不拦
        failed = [
            previous_field
            for previous_field, _previous_key in nodes[:index]
            if merged.get(previous_field["id"]) == "failed"
        ]
        if failed:
            names = "、".join(f"「{item['name']}」" for item in failed)
            raise WriteError(
                "版本进度必须串行推进：前序节点"
                f"{names}为 failed，「{field['name']}」不得推进；"
                "请先把失败节点返工改回 doing，再逐节点推进"
            )
        if new_value != "done":
            continue
        unfinished = [
            (previous_field, merged.get(previous_field["id"]))
            for previous_field, _previous_key in nodes[:index]
            if merged.get(previous_field["id"]) != "done"
        ]
        if unfinished:
            detail = "、".join(
                f"「{item['name']}」={value if value not in (None, '') else '未填'}"
                for item, value in unfinished
            )
            raise WriteError(
                f"版本进度必须串行推进：「{field['name']}」置 done 前，"
                f"前序节点必须全部 done；未完成：{detail}"
            )


def _check_gate(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    nodes: list[tuple[sqlite3.Row, str | None]],
    merged: dict[str, Any],
    previous: dict[str, Any],
    sources: dict[str, tuple[sqlite3.Row, str, sqlite3.Row]],
    row_id: str,
) -> None:
    for field, key in nodes:
        if key is None or key not in NODE_REQUIREMENTS:
            continue
        if merged.get(field["id"]) != "done" or previous.get(field["id"]) == "done":
            continue  # 只在"到达 done"的那一刻校验；重放 done 不改条件
        for role, expected, description in NODE_REQUIREMENTS[key]:
            source = sources.get(role)
            if source is None:
                continue  # 依赖来源认不出：不猜，由 019 门禁保证字段存在
            relation_field, target_id, completion = source
            problems = _unsatisfied(
                conn, target_id, relation_field, completion, expected, merged
            )
            if problems:
                detail = "、".join(problems)
                raise WriteError(
                    f"「{field['name']}」置 done 前，{description}：{detail}"
                    f"（字段「{relation_field['name']}」）"
                )
        if key != "test_accept":
            continue
        source = sources.get("run")
        if source is None:
            continue
        quality = _run_result_problems(conn, source[1], source[0], merged, row_id)
        if quality:
            raise WriteError(
                "「测试验收」置 done 前，本版执行结果必须全部 pass，"
                "或带有效放行标记（放行批准人与放行理由都不为空）：" + "、".join(quality)
            )


def validate_row_write(
    conn: sqlite3.Connection,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    *,
    merged: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    """版本表六节点的写侧校验；违反串行或闸门一致性一律 `WriteError`（400，零写入）。

    `merged` 是合并后的整行（新建时即提交值），`previous` 是写前的整行（新建时为空）。
    只校验"值发生变化"的节点：重放同一个值不改条件，避免修无关字段时被历史数据卡住；
    但同时把节点从 done 改成 done 不会重新验闸门，这是契约允许的（见规格边界）。
    """
    nodes = stage_nodes(fields)
    if nodes is None:
        return
    _check_serial(nodes, merged, previous)
    _check_gate(conn, fields, nodes, merged, previous, _relation_sources(conn, fields), row_id)
