"""阶段证据校验（038）：阶段置 done 必须留下可定位的证据。

引擎在容器里看不到仓库文件，所以「产物是否存在」由技能校验（`tf-dev-plan` 校验
spec 结构与阶段产物、`tf-dev-implement` 校验 plan/tasks/回链与单测）。引擎能严格管的
是另一半：**状态从非 done 变为 done 的那一刻，必须有一条非空的证据行**。

契约口径（`specs/019-test-contract/board@5.yaml`）：

- `rules.stage_done_needs_evidence` 置 done 须有 `<阶段>=...>` 行；
- `rules.stage_unprovable` 历史缺证据视为「无法证明」，不回改；
- `rules.stage_backfill` 补做须记时间与操作者；
- `rules.stage_reuse` 复用须写来源路径与版本。

证据格式（`spec.stage_evidence` 字段，每行一条）：

    constitution=reused:.specify/memory/constitution.md@v1
    specify=specs/042-implement-full-flow/spec.md（US4/场景13/FR11/边界5）
    plan=specs/042-implement-full-flow/plan.md（回链 13 条场景）
    implement=pytest 218 passed（补做 2026-11-23 agent-tf-role）

只校验状态**发生变化**的那一次写入：重放同一值不改条件，避免历史缺证据的行
在改无关字段时被卡住（与 025 的节点闸门同一纪律）。
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .errors import WriteError

STAGE_VALUES = frozenset({"todo", "doing", "done", "na"})
STAGE_NAME_RE = re.compile(r"^speckit-([a-z_]+)状态$", re.I)
EVIDENCE_FIELD_NAME = "阶段证据"
CONSTITUTION_VERSION_NAME = "宪法版本"
REUSE_PREFIX = "reused:"
REUSE_VERSION_RE = re.compile(r"@([^\s（）()，,；;]+)")
CONFIRM_MARKERS = ("重新确认", "仍适用", "已确认")
EVIDENCE_LINE_RE = re.compile(r"^\s*([a-z_]+)\s*=\s*(.+?)\s*$", re.I)


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


def stage_key(field: sqlite3.Row) -> str | None:
    """阶段键：从契约名称 `speckit-<key>状态` 取中段。"""
    match = STAGE_NAME_RE.match(str(field["name"]))
    return match.group(1).lower() if match else None


def parse_evidence(text: Any) -> dict[str, str]:
    """把 `阶段证据` 解析成 {阶段键: 证据}；同一键多次出现以最后一行为准。"""
    out: dict[str, str] = {}
    if not isinstance(text, str):
        return out
    for line in text.splitlines():
        match = EVIDENCE_LINE_RE.match(line)
        if match:
            out[match.group(1).lower()] = match.group(2).strip()
    return out


def _stage_fields(fields: dict[str, sqlite3.Row]) -> dict[str, sqlite3.Row]:
    out: dict[str, sqlite3.Row] = {}
    for field in fields.values():
        if field["type"] != "enum" or _enum_values(field) != STAGE_VALUES:
            continue
        key = stage_key(field)
        if key:
            out[key] = field
    return out


def _evidence_field(fields: dict[str, sqlite3.Row]) -> sqlite3.Row | None:
    return next(
        (field for field in fields.values() if field["name"] == EVIDENCE_FIELD_NAME),
        None,
    )


def _check_reuse(
    fields: dict[str, sqlite3.Row],
    merged: dict[str, Any],
    evidence: dict[str, str],
) -> None:
    """S2：复用产物的来源版本与当前宪法版本不一致时，必须写明已重新确认。"""
    version_field = next(
        (field for field in fields.values() if field["name"] == CONSTITUTION_VERSION_NAME),
        None,
    )
    if version_field is None:
        return
    current = str(merged.get(version_field["id"]) or "").strip()
    if not current:
        return
    stale: list[str] = []
    for key, value in evidence.items():
        if not value.startswith(REUSE_PREFIX):
            continue
        match = REUSE_VERSION_RE.search(value)
        if match is None:
            stale.append(f"{key}=复用了 {value}，但没写来源版本")
            continue
        reused = match.group(1).strip()
        if reused != current and not any(mark in value for mark in CONFIRM_MARKERS):
            stale.append(
                f"{key}=复用 {reused}，当前宪法版本是 {current}"
            )
    if stale:
        raise WriteError(
            "S2：复用产物的来源版本与当前版本不一致时，必须在证据行里写明「已重新确认仍适用」；"
            "未确认的复用不算有效证据：" + "；".join(stale)
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
    """阶段置 done 的证据校验。失败抛 WriteError，整请求零写入。"""
    stages = _stage_fields(fields)
    if not stages:
        return
    evidence_field = _evidence_field(fields)
    if evidence_field is None:
        return  # 未迁移的项目没有证据字段：不猜，也不阻断
    evidence = parse_evidence(merged.get(evidence_field["id"]))
    _check_reuse(fields, merged, evidence)

    missing: list[str] = []
    for key, field in stages.items():
        new_value = merged.get(field["id"])
        if new_value != "done":
            continue
        if previous.get(field["id"]) == "done":
            continue  # 只在"到达 done"的那一刻校验
        if not evidence.get(key):
            missing.append(f"{key}（字段「{field['name']}」）")
    if missing:
        raise WriteError(
            "S1：阶段置 done 必须留下证据：在「阶段证据」里补上 "
            + "、".join(
                f"{item.split('（')[0]}=<产物路径或命令结论>" for item in missing
            )
            + "；缺证据的阶段按「无法证明」处理，不能置 done"
        )


def stage_report(
    conn: sqlite3.Connection, table_id: str, fields: dict[str, sqlite3.Row], values: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """给查询用：每个阶段的取值与证据，缺证据标 unprovable。"""
    stages = _stage_fields(fields)
    evidence_field = _evidence_field(fields)
    evidence = parse_evidence(values.get(evidence_field["id"]) if evidence_field else None)
    report: dict[str, dict[str, Any]] = {}
    for key, field in stages.items():
        value = values.get(field["id"])
        unprovable = value in (None, "") or (value == "done" and not evidence.get(key))
        report[key] = {
            "value": value,
            "evidence": evidence.get(key),
            "unprovable": unprovable,
        }
    return report


ACCEPTANCE_DOMAINS = frozenset({
    frozenset({"pending", "accepted", "rejected", "dropped"}),
    frozenset({"pending", "accepted", "rejected"}),
})


def _acceptance_field(fields: dict[str, sqlite3.Row]) -> sqlite3.Row | None:
    hits = [
        field
        for field in fields.values()
        if field["type"] == "enum" and _enum_values(field) in ACCEPTANCE_DOMAINS
    ]
    return hits[0] if len(hits) == 1 else None


def _fields_of(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        'SELECT id, name, type, options, "order" FROM fields WHERE table_id = ?',
        (table_id,),
    ).fetchall()
    return {row["id"]: row for row in rows}


def project_stage_report(
    conn: sqlite3.Connection, project_id: str, spec_id: str
) -> dict[str, Any] | None:
    """某份独立需求的阶段视图：取值、证据、是否「无法证明」（038 FR-006）。"""
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        return None
    for row in conn.execute(
        'SELECT id FROM tables WHERE project_id = ? ORDER BY "order" ASC, id ASC',
        (project_id,),
    ).fetchall():
        fields = _fields_of(conn, row["id"])
        if _acceptance_field(fields) is None:
            continue
        record = conn.execute(
            "SELECT data FROM row_records WHERE table_id = ? AND id = ?",
            (row["id"], spec_id),
        ).fetchone()
        if record is None:
            continue
        values = _loads(record["data"]) or {}
        stages = stage_report(conn, row["id"], fields, values)
        return {
            "spec": spec_id,
            "table": row["id"],
            "stages": stages,
            "unprovable": sorted(key for key, item in stages.items() if item["unprovable"]),
        }
    return None
