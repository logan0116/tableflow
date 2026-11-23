"""依赖需求变更流校验（037）：回归置 passed 前必须走完整变更。

契约口径（`specs/019-test-contract/board@5.yaml`）：

- `rules.change_flow_full` 依赖需求是一次完整变更，缺项不得置 passed；
- `rules.change_regress_precondition` 置 passed 时受影响条款、一致性检查、
  集成验收三项都必须非空；
- `rules.change_revision_not_needed` 规格修订取 not_needed 时必须有判定依据。

只校验状态**发生变化**的那一次写入：历史依赖需求缺字段不回改、也不阻断无关编辑
（与 025 的节点闸门、038 的阶段证据同一纪律）。

**新建行不校验**：历史导入与重建会把已经 passed 的依赖需求整行写回，那不是"推进"
而是还原事实；要求导入方补齐当时就不存在的检查结论，只会让历史无法重建。规则约束的
是从 todo/doing 走到 passed 的那一步。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .errors import WriteError

REGRESS_VALUES = frozenset({"todo", "doing", "passed", "failed"})
REVISION_VALUES = frozenset({"not_needed", "pending", "done"})

AFFECTED_NAME = "受影响条款"
CONSISTENCY_NAME = "一致性检查"
INTEGRATION_NAME = "集成验收"
EVIDENCE_NAME = "证据"
REVISION_NAME = "规格修订"


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


def _by_name(fields: dict[str, sqlite3.Row], name: str) -> sqlite3.Row | None:
    return next((field for field in fields.values() if field["name"] == name), None)


def _regress_field(fields: dict[str, sqlite3.Row]) -> sqlite3.Row | None:
    hits = [
        field
        for field in fields.values()
        if field["type"] == "enum" and _enum_values(field) == REGRESS_VALUES
    ]
    return hits[0] if len(hits) == 1 else None


def _text(values: dict[str, Any], field: sqlite3.Row | None) -> str:
    if field is None:
        return ""
    return str(values.get(field["id"]) or "").strip()


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
    """依赖需求变更流校验。失败抛 WriteError，整请求零写入。"""
    regress = _regress_field(fields)
    if regress is None:
        return

    if not previous:
        return  # 新建行：导入既有状态，不是推进

    # 未迁移的项目没有这三个字段：不猜、不阻断（与 038 阶段证据同一口径）
    flow_fields = {name: _by_name(fields, name) for name in (AFFECTED_NAME, CONSISTENCY_NAME, INTEGRATION_NAME)}
    if any(field is None for field in flow_fields.values()):
        return

    old_state = previous.get(regress["id"])
    new_state = merged.get(regress["id"])

    if new_state == "passed" and old_state != "passed":
        missing: list[str] = []
        for name in (AFFECTED_NAME, CONSISTENCY_NAME, INTEGRATION_NAME):
            if not _text(merged, _by_name(fields, name)):
                missing.append(name)
        if missing:
            raise WriteError(
                "依赖需求置 passed 前必须完成完整变更，缺少："
                + "、".join(missing)
                + "。补丁不因规模小免除流程；跨规格变更还要逐份给出一致性检查结论"
            )

    revision = _by_name(fields, REVISION_NAME)
    if revision is not None and revision["id"] in merged:
        new_revision = merged.get(revision["id"])
        old_revision = previous.get(revision["id"])
        if new_revision == "not_needed" and old_revision != "not_needed":
            if not _text(merged, _by_name(fields, EVIDENCE_NAME)):
                raise WriteError(
                    "规格修订取 not_needed 时必须写明判定依据："
                    "在「证据」里说明为什么本次改动不产生规格内容变化"
                )
