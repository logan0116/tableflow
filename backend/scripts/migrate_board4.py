#!/usr/bin/env python3
"""board@4（019）六表建表与存量迁移：给 board@3 项目补 case/run 两表与版本表字段。

契约唯一来源：`specs/019-test-contract/board@4.yaml`
- tables.case / tables.run（步骤 1-9）；
- tables.ver 新增六个四态节点、`ver.runs` 与三个用例字段（不建 plan 表）。

本脚本只做数据层结构迁移，不实现写接口、计算引擎与门禁（分别归 020/023/025）：

1. 为每个 board@3 项目建 `case` / `run` 两张表；表级 `kind` 落库，`run=detail`、其余
   `board`。已存在同名同 id 的表/字段只核对不覆盖，重复执行不产生重复结构。
2. 给版本表插入六个节点 enum（board@4 顺序）、`ver.runs` relation、`用例总数` /
   `已完成用例数` / `用例是否完成` 三个计算字段（空集语义：0 / 0 / 真）。
   `stage_done` / `gate` 改造归 023/025，本脚本不碰旧「发布条件」字段。
3. 存量版本行按发布状态初始化六节点：`released` → 六节点 `done`；`planned` /
   `dropped` → `todo`。只补「六节点全空」的行，重跑不覆盖人工改过的节点。
4. 迁移前后对 ver/indep/dep/bug 四张老表逐行比对：**迁移前已存在的字段**值必须
   完全一致（新增节点字段不计入，它们就是要新增的值）；indep/dep/bug 的字段定义
   也要求逐项一致，ver 只允许字段顺序随契约重排。任何差异回滚并退出 1。
   比对产物默认写入 `data/backups/board4-migration-<时间戳>.json`。

用法（在仓库根目录或 backend 目录）：
    backend/.venv/bin/python backend/scripts/migrate_board4.py --dry-run
    backend/.venv/bin/python backend/scripts/migrate_board4.py
    backend/.venv/bin/python backend/scripts/migrate_board4.py --db data/tableflow.db
    backend/.venv/bin/python backend/scripts/migrate_board4.py --project tableflow --project demo
    backend/.venv/bin/python backend/scripts/migrate_board4.py --no-backup --artifact /tmp/b4.json

退出码：0=全部成功（含本来就一致）；1=有冲突/比对差异，未提交或已回滚。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:  # 在仓库内运行时是 backend/scripts/x.py 的上两级；单独拷到 /tmp 跑时退化到 cwd
    REPO_ROOT = Path(__file__).resolve().parents[2]
except IndexError:  # pragma: no cover - 仅独立拷贝运行时触发
    REPO_ROOT = Path.cwd()
DEFAULT_DB = Path(os.environ.get("TABLEFLOW_DB") or REPO_ROOT / "data" / "tableflow.db")
TZ = timezone(timedelta(hours=8))
ROLES = ("ver", "indep", "dep", "bug")
STAGE_FIELD_NAMES = (
    "版本需求设计",
    "测试设计",
    "开发",
    "开发验收",
    "测试",
    "测试验收",
)
CASE_DONE_NAMES = ("用例总数", "已完成用例数", "用例是否完成")

# board@4 版本表字段顺序（含 stage_done，便于 023/025 落地后重跑仍能对齐）。
# 旧字段名保留在 ALIAS 里：改名归 019 的另一条迁移动作，本脚本只保证顺序不被打乱。
VER_ORDER = [
    "版本号",
    "发布时间",
    "版本需求设计",
    "测试设计",
    "开发",
    "开发验收",
    "测试",
    "测试验收",
    "六节点是否全部完成",
    "发布条件",
    "发布状态",
    "独立需求管理",
    "独立需求已完成/总数",
    "独立需求是否完成",
    "依赖需求管理",
    "依赖需求已完成/总数",
    "依赖需求是否完成",
    "测试用例",
    "用例总数",
    "已完成用例数",
    "用例是否完成",
    "Bug管理",
    "Bug已修复/总数",
    "Bug是否清空",
    "负责人",
    "变更说明",
]
VER_ORDER_ALIASES = {
    "上一版本Bug已修复/总数": "Bug已修复/总数",
    "上一版本Bug是否清空": "Bug是否清空",
}
POSITION_BY_NAME = {name: index + 1 for index, name in enumerate(VER_ORDER)}
POSITION_BY_NAME.update(
    {
        old: POSITION_BY_NAME[new]
        for old, new in VER_ORDER_ALIASES.items()
    }
)

STAGE_ITEMS = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]
RUN_STATE_ITEMS = [
    {"value": "todo", "label": "待执行", "tone": "neutral"},
    {"value": "done", "label": "已执行", "tone": "success"},
]
RUN_RESULT_ITEMS = [
    {"value": "pass", "label": "通过", "tone": "success"},
    {"value": "fail", "label": "失败", "tone": "danger"},
    {"value": "blocked", "label": "阻塞", "tone": "warning"},
    {"value": "skip", "label": "跳过", "tone": "info"},
]
CASE_PRIORITY_ITEMS = [
    {"value": "P0", "label": "高", "tone": "danger"},
    {"value": "P1", "label": "中", "tone": "warning"},
    {"value": "P2", "label": "低", "tone": "neutral"},
]


class MigrationError(RuntimeError):
    """结构性冲突：重名/重 id 但配置不同，拒绝覆盖。"""


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


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _table_map(conn: sqlite3.Connection, project_id: str) -> dict[str, dict[str, Any]]:
    """角色 → 表行（按 id 后缀识别 ver/indep/dep/bug）。"""
    tables: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        'SELECT id, name, "order", kind FROM tables WHERE project_id = ? ORDER BY "order"',
        (project_id,),
    ):
        for role in ROLES:
            if row["id"].endswith(f"-{role}"):
                tables[role] = dict(row)
                break
    return tables


def _fields(conn: sqlite3.Connection, table_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            'SELECT id, name, type, options, "order", visible FROM fields'
            ' WHERE table_id = ? ORDER BY "order", id',
            (table_id,),
        )
    ]


def _field_prefix(ver_fields: list[dict[str, Any]], ver_table_id: str) -> str:
    """沿用项目既有字段 id 前缀：tf-v-ver→tf-；v-ver→''；demo-cloud-v-ver→demo-cloud-。"""
    for field in ver_fields:
        if field["name"] == "版本号" or field["id"].endswith("v-ver"):
            if field["id"].endswith("v-ver"):
                return field["id"][: -len("v-ver")]
    return ver_table_id[: -len("ver")]


def _is_board3_ver(fields: list[dict[str, Any]]) -> bool:
    names = {field["name"] for field in fields}
    return {"版本号", "发布条件", "发布状态", "Bug管理"} <= names


def _ensure_kind_column(conn: sqlite3.Connection) -> bool:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tables)")}
    if "kind" in columns:
        return False
    conn.execute("ALTER TABLE tables ADD COLUMN kind TEXT NOT NULL DEFAULT 'board'")
    return True


def _backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(db_path.name + f".bak-board4-{stamp}")
    destination = sqlite3.connect(target)
    try:
        conn.backup(destination)
    finally:
        destination.close()
    return target


def _display_field(conn: sqlite3.Connection, table_id: str, fallback: str) -> str:
    """关联弹层第二列：目标表可读文本字段（第 2 个 text，退化到第 1 个）。"""
    texts = [f["id"] for f in _fields(conn, table_id) if f["type"] == "text"]
    if len(texts) >= 2:
        return texts[1]
    if texts:
        return texts[0]
    return fallback


def _status_field(conn: sqlite3.Connection, table_id: str, name: str, fallback: str) -> str:
    for field in _fields(conn, table_id):
        if field["name"] == name and field["type"] == "enum":
            return field["id"]
    return fallback


def _field_by_name(conn: sqlite3.Connection, table_id: str, name: str) -> dict[str, Any] | None:
    for field in _fields(conn, table_id):
        if field["name"] == name:
            return field
    return None


def _case_fields(prefix: str, indep_table: str, indep_clause: str, indep_acceptance: str) -> list[dict[str, Any]]:
    def fid(short: str) -> str:
        return f"{prefix}c-{short}"

    fields: list[dict[str, Any]] = [
        {
            "id": fid("id"), "name": "用例号", "type": "text",
            "options": {"constraints": {"required": True}},
        },
        {
            "id": fid("name"), "name": "用例名", "type": "text",
            "options": {"constraints": {"required": True}},
        },
        {
            "id": fid("indep"), "name": "来源规格", "type": "relation",
            "options": {
                "table_id": indep_table,
                "display_field": indep_clause,
                "status_field": indep_acceptance,
                "constraints": {"required": True, "relation_must_exist": True},
            },
        },
        {"id": fid("precondition"), "name": "前置条件", "type": "text", "options": None},
        {"id": fid("steps"), "name": "操作步骤", "type": "text", "options": None},
        {"id": fid("expect"), "name": "预期结果", "type": "text", "options": None},
        {
            "id": fid("priority"), "name": "优先级", "type": "enum",
            "options": {"items": CASE_PRIORITY_ITEMS},
        },
        {"id": fid("owner"), "name": "负责人", "type": "text", "options": None},
    ]
    for index, field in enumerate(fields, start=1):
        field["order"] = index
    return fields


def _run_fields(prefix: str, case_table: str, case_display: str) -> list[dict[str, Any]]:
    def fid(short: str) -> str:
        return f"{prefix}r-{short}"

    fields: list[dict[str, Any]] = [
        {
            "id": fid("id"), "name": "执行编号", "type": "text",
            "options": {"constraints": {"required": True}},
        },
        {
            "id": fid("case_no"), "name": "用例号", "type": "text",
            "options": {"constraints": {"required": True}},
        },
        {
            "id": fid("case"), "name": "用例", "type": "relation",
            "options": {
                "table_id": case_table,
                "display_field": case_display,
                "constraints": {"required": True, "relation_must_exist": True},
            },
        },
        {
            "id": fid("state"), "name": "执行状态", "type": "enum",
            "options": {"items": RUN_STATE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": fid("result"), "name": "执行结果", "type": "enum",
            "options": {"items": RUN_RESULT_ITEMS},
        },
        {"id": fid("evidence"), "name": "证据", "type": "text", "options": None},
        {
            "id": fid("executed_at"), "name": "执行时间", "type": "datetime",
            "options": {"with_time": True},
        },
        {"id": fid("executor"), "name": "执行人", "type": "text", "options": None},
        {"id": fid("note"), "name": "备注", "type": "text", "options": None},
    ]
    for index, field in enumerate(fields, start=1):
        field["order"] = index
    return fields


def _ver_fields(
    prefix: str,
    run_table: str,
    run_case_no: str,
    run_state: str,
) -> list[dict[str, Any]]:
    def vid(short: str) -> str:
        return f"{prefix}v-{short}"

    fields: list[dict[str, Any]] = [
        {
            "id": vid("stage-plan"), "name": "版本需求设计", "type": "enum",
            "options": {"items": STAGE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": vid("stage-test-design"), "name": "测试设计", "type": "enum",
            "options": {"items": STAGE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": vid("stage-dev"), "name": "开发", "type": "enum",
            "options": {"items": STAGE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": vid("stage-dev-accept"), "name": "开发验收", "type": "enum",
            "options": {"items": STAGE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": vid("stage-test"), "name": "测试", "type": "enum",
            "options": {"items": STAGE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": vid("stage-test-accept"), "name": "测试验收", "type": "enum",
            "options": {"items": STAGE_ITEMS, "constraints": {"required": True}},
        },
        {
            "id": vid("runs"), "name": "测试用例", "type": "relation",
            "options": {
                "table_id": run_table,
                "display_field": run_case_no,
                "status_field": run_state,
                "constraints": {"relation_must_exist": True},
            },
        },
        {
            "id": vid("case-total"), "name": "用例总数", "type": "computed",
            "options": {"kind": "count", "source": vid("runs")},
        },
        {
            "id": vid("case-done-count"), "name": "已完成用例数", "type": "computed",
            "options": {
                "kind": "count",
                "source": vid("runs"),
                "where": {"field_id": run_state, "equals": "done"},
            },
        },
        {
            "id": vid("case-done"), "name": "用例是否完成", "type": "computed",
            "options": {
                "kind": "rollup",
                "source": vid("runs"),
                "field_id": run_state,
                "aggregate": "all",
                "equals": "done",
                "true_label": "是",
                "false_label": "否",
            },
        },
    ]
    for field in fields:
        field["order"] = POSITION_BY_NAME[field["name"]]
    return fields


def _find_field_conflict(
    existing: list[dict[str, Any]], desired: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """返回 (已存在字段, 冲突说明)。冲突说明为 None 表示可安全跳过/新建。"""
    by_id = {field["id"]: field for field in existing}
    by_name = {field["name"]: field for field in existing}
    current = by_id.get(desired["id"])
    if current is not None:
        if current["name"] != desired["name"] or current["type"] != desired["type"]:
            return current, (
                f"字段 id {desired['id']} 已存在但配置不同："
                f"{current['name']}/{current['type']} ≠ {desired['name']}/{desired['type']}"
            )
        return current, None
    same_name = by_name.get(desired["name"])
    if same_name is not None:
        return same_name, (
            f"字段名「{desired['name']}」已存在但 id 不同："
            f"{same_name['id']} ≠ {desired['id']}"
        )
    return None, None


def _ensure_table(
    conn: sqlite3.Connection,
    project_id: str,
    table_id: str,
    name: str,
    order: int,
    kind: str,
    action: dict[str, Any],
) -> None:
    row = conn.execute(
        'SELECT id, name, "order", kind FROM tables WHERE id = ?', (table_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            'INSERT INTO tables (id, project_id, name, "order", kind) VALUES (?, ?, ?, ?, ?)',
            (table_id, project_id, name, order, kind),
        )
        action["tables_created"].append(table_id)
        return
    if row["name"] != name:
        raise MigrationError(
            f"表 id {table_id} 已存在但名称不同：{row['name']!r} ≠ {name!r}；拒绝覆盖"
        )
    if row["kind"] != kind:
        conn.execute("UPDATE tables SET kind = ? WHERE id = ?", (kind, table_id))
        action["kind_updates"].append({"table": table_id, "before": row["kind"], "after": kind})


def _ensure_fields(
    conn: sqlite3.Connection,
    table_id: str,
    desired: list[dict[str, Any]],
    action: dict[str, Any],
    *,
    reorder: bool = False,
) -> None:
    existing = _fields(conn, table_id)
    for field in desired:
        current, problem = _find_field_conflict(existing, field)
        if problem:
            raise MigrationError(f"{table_id}：{problem}")
        if current is not None:
            continue
        conn.execute(
            'INSERT INTO fields (id, table_id, name, type, options, "order", visible)'
            " VALUES (?, ?, ?, ?, ?, ?, 1)",
            (
                field["id"],
                table_id,
                field["name"],
                field["type"],
                _dumps(field["options"]) if field["options"] is not None else None,
                int(field["order"]),
            ),
        )
        action["fields_created"].append(field["id"])

    if not reorder:
        return
    # 版本表按 board@4 顺序重排；未知字段保持原相对顺序排在最后。
    current_fields = _fields(conn, table_id)
    known: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for field in current_fields:
        position = POSITION_BY_NAME.get(field["name"])
        if position is None:
            unknown.append(field)
        else:
            known.append({**field, "_position": position})
    known.sort(key=lambda field: field["_position"])
    ordered = known + unknown
    for index, field in enumerate(ordered, start=1):
        if field["order"] == index:
            continue
        conn.execute('UPDATE fields SET "order" = ? WHERE id = ?', (index, field["id"]))
        action["order_updates"].append(
            {"field": field["id"], "before": field["order"], "after": index}
        )


def _init_stage_nodes(
    conn: sqlite3.Connection,
    ver_table: str,
    release_field: str,
    stage_fields: list[str],
    action: dict[str, Any],
) -> None:
    rows = conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id", (ver_table,)
    ).fetchall()
    for row in rows:
        data = _loads(row["data"]) or {}
        if any(data.get(field) not in (None, "") for field in stage_fields):
            # 六节点已有任一项：视为已初始化/人工维护过，重跑不覆盖。
            continue
        value = "done" if data.get(release_field) == "released" else "todo"
        for field in stage_fields:
            data[field] = value
        conn.execute(
            "UPDATE row_records SET data = ? WHERE table_id = ? AND id = ?",
            (_dumps(data), ver_table, row["id"]),
        )
        action["nodes_initialized"].append({"row": row["id"], "value": value})


def _init_case_computed(
    conn: sqlite3.Connection,
    ver_table: str,
    fields: list[tuple[str, Any]],
    action: dict[str, Any],
) -> None:
    now = _now()
    rows = conn.execute("SELECT id FROM row_records WHERE table_id = ?", (ver_table,)).fetchall()
    for row in rows:
        for field_id, value in fields:
            exists = conn.execute(
                "SELECT 1 FROM computed_values WHERE table_id = ? AND row_id = ? AND field_id = ?",
                (ver_table, row["id"], field_id),
            ).fetchone()
            if exists is not None:
                continue
            conn.execute(
                "INSERT INTO computed_values (table_id, row_id, field_id, value, computed_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (ver_table, row["id"], field_id, _dumps(value), now),
            )
            action["computed_initialized"].append({"row": row["id"], "field": field_id})


def _snapshot(conn: sqlite3.Connection, tables: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role in ROLES:
        table_id = tables[role]["id"]
        fields = _fields(conn, table_id)
        rows = {
            row["id"]: _loads(row["data"]) or {}
            for row in conn.execute(
                "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id", (table_id,)
            )
        }
        computed = {
            (row["row_id"], row["field_id"]): {
                "value": row["value"],
                "override_value": row["override_value"],
                "override_reason": row["override_reason"],
            }
            for row in conn.execute(
                "SELECT row_id, field_id, value, override_value, override_reason"
                " FROM computed_values WHERE table_id = ?",
                (table_id,),
            )
        }
        result[role] = {"fields": fields, "rows": rows, "computed": computed}
    return result


def _compare(
    targets: list[dict[str, Any]],
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    details: dict[str, Any] = {}
    diff_total = 0
    for target in targets:
        project_id = target["project_id"]
        project_detail: dict[str, Any] = {}
        for role in ROLES:
            old = before[project_id][role]
            new = after[project_id][role]
            old_field_ids = {field["id"] for field in old["fields"]}
            old_rows = old["rows"]
            new_rows = new["rows"]
            added_rows = sorted(set(new_rows) - set(old_rows))
            removed_rows = sorted(set(old_rows) - set(new_rows))

            row_diffs = []
            for row_id in sorted(old_rows):
                old_values = {
                    key: value
                    for key, value in old_rows[row_id].items()
                    if key in old_field_ids
                }
                new_values = {
                    key: value
                    for key, value in new_rows[row_id].items()
                    if key in old_field_ids
                }
                if old_values != new_values:
                    changed = sorted(
                        key
                        for key in set(old_values) | set(new_values)
                        if old_values.get(key) != new_values.get(key)
                    )
                    row_diffs.append({"row": row_id, "fields": changed})

            new_fields = {field["id"]: field for field in new["fields"]}
            field_diffs = []
            order_changes = []
            for field in old["fields"]:
                current = new_fields.get(field["id"])
                if current is None:
                    field_diffs.append({"field": field["id"], "problem": "字段被删除"})
                    continue
                for key in ("name", "type", "options", "visible"):
                    if field[key] != current[key]:
                        field_diffs.append(
                            {"field": field["id"], "field_key": key, "before": field[key], "after": current[key]}
                        )
                if field["order"] != current["order"]:
                    change = {
                        "field": field["id"],
                        "before": field["order"],
                        "after": current["order"],
                    }
                    if role == "ver":
                        # 版本表新增字段后按契约重排顺序，属预期；其它表不允许改顺序。
                        order_changes.append(change)
                    else:
                        field_diffs.append({"field": field["id"], "problem": "字段顺序变化", **change})

            computed_diffs = []
            for (row_id, field_id), old_value in old["computed"].items():
                if field_id not in old_field_ids:
                    continue
                new_value = new["computed"].get((row_id, field_id))
                if new_value is None:
                    computed_diffs.append({"row": row_id, "field": field_id, "problem": "计算值被删除"})
                elif old_value["value"] != new_value["value"]:
                    computed_diffs.append(
                        {
                            "row": row_id,
                            "field": field_id,
                            "before": _loads(old_value["value"]),
                            "after": _loads(new_value["value"]),
                        }
                    )
                elif (
                    old_value["override_value"] != new_value["override_value"]
                    or old_value["override_reason"] != new_value["override_reason"]
                ):
                    computed_diffs.append(
                        {"row": row_id, "field": field_id, "problem": "人工覆盖被改动"}
                    )

            diff_count = (
                len(added_rows)
                + len(removed_rows)
                + len(row_diffs)
                + len(field_diffs)
                + len(computed_diffs)
            )
            diff_total += diff_count
            project_detail[role] = {
                "rows_before": len(old_rows),
                "rows_after": len(new_rows),
                "rows_compared": len(old_rows),
                "added_rows": added_rows,
                "removed_rows": removed_rows,
                "row_value_diffs": row_diffs,
                "field_def_diffs": field_diffs,
                "order_changes": order_changes,
                "computed_value_diffs": computed_diffs,
                "diff": diff_count,
            }
        details[project_id] = project_detail
    return details, diff_total


def migrate(
    db_path: str | Path,
    *,
    projects: list[str] | None = None,
    artifact: str | Path | None = None,
    backup: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行 board@4 数据层迁移；返回比对产物（同时写入 artifact）。"""
    db_path = Path(db_path).expanduser().resolve()
    if not db_path.exists():
        raise MigrationError(f"数据库不存在：{db_path}")

    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    backup_path: Path | None = None
    artifact_doc: dict[str, Any]
    try:
        if backup and not dry_run:
            backup_path = _backup(conn, db_path)

        conn.execute("BEGIN IMMEDIATE")
        try:
            kind_column_added = _ensure_kind_column(conn)
            project_rows = conn.execute("SELECT id, name FROM projects ORDER BY id").fetchall()
            targets: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            selected = set(projects or [])
            for project in project_rows:
                project_id = project["id"]
                if selected and project_id not in selected:
                    continue
                tables = _table_map(conn, project_id)
                missing = [role for role in ROLES if role not in tables]
                if missing:
                    skipped.append({"project": project_id, "reason": f"缺表：{missing}"})
                    continue
                ver_fields = _fields(conn, tables["ver"]["id"])
                if not _is_board3_ver(ver_fields):
                    skipped.append(
                        {"project": project_id, "reason": "版本表不是 board@3 口径，跳过"}
                    )
                    continue
                targets.append(
                    {
                        "project_id": project_id,
                        "project_name": project["name"],
                        "tables": tables,
                        "field_prefix": _field_prefix(ver_fields, tables["ver"]["id"]),
                    }
                )
            if selected:
                unknown = sorted(selected - {target["project_id"] for target in targets})
                unknown -= {item["project"] for item in skipped}
                if unknown:
                    raise MigrationError(f"指定的项目不存在：{unknown}")

            before = {
                target["project_id"]: _snapshot(conn, target["tables"]) for target in targets
            }
            actions: list[dict[str, Any]] = []
            for target in targets:
                actions.append(_migrate_project(conn, target))
            after = {
                target["project_id"]: _snapshot(conn, target["tables"]) for target in targets
            }
            comparison, diff_total = _compare(targets, before, after)

            artifact_doc = {
                "generated_at": _now(),
                "db": str(db_path),
                "contract": "specs/019-test-contract/board@4.yaml",
                "scope": "board@3 项目的 case/run 建表与版本表六节点/用例字段迁移",
                "comparison_scope": (
                    "四张老表逐行比对，只比较迁移前已存在的字段；"
                    "新增节点/用例字段的值不计入差异（它们本就必须新增）。"
                ),
                "backup": str(backup_path) if backup_path else None,
                "kind_column_added": kind_column_added,
                "projects": actions,
                "skipped": skipped,
                "comparison": comparison,
                "diff_total": diff_total,
                "dry_run": dry_run,
                "ok": diff_total == 0,
            }
            if diff_total == 0:
                if dry_run:
                    conn.execute("ROLLBACK")
                else:
                    conn.execute("COMMIT")
            else:
                conn.execute("ROLLBACK")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()

    if artifact is None:
        artifact = REPO_ROOT / "data" / "backups" / (
            f"board4-migration-{datetime.now(TZ).strftime('%Y%m%d-%H%M%S')}.json"
        )
    artifact = Path(artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(artifact_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    artifact_doc["artifact_path"] = str(artifact)
    return artifact_doc


def _migrate_project(conn: sqlite3.Connection, target: dict[str, Any]) -> dict[str, Any]:
    project_id = target["project_id"]
    tables = target["tables"]
    prefix = target["field_prefix"]
    action: dict[str, Any] = {
        "project": project_id,
        "project_name": target["project_name"],
        "field_prefix": prefix,
        "tables": {role: tables[role]["id"] for role in ROLES},
        "tables_created": [],
        "kind_updates": [],
        "fields_created": [],
        "order_updates": [],
        "nodes_initialized": [],
        "computed_initialized": [],
    }

    table_prefix = tables["ver"]["id"][: -len("ver")]
    max_order = int(
        conn.execute(
            "SELECT coalesce(max(\"order\"), 0) FROM tables WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    )
    case_table = f"{table_prefix}case"
    run_table = f"{table_prefix}run"
    case_row = conn.execute(
        'SELECT "order" FROM tables WHERE id = ?', (case_table,)
    ).fetchone()
    case_order = int(case_row["order"]) if case_row else max_order + 1
    run_row = conn.execute(
        'SELECT "order" FROM tables WHERE id = ?', (run_table,)
    ).fetchone()
    run_order = int(run_row["order"]) if run_row else case_order + 1
    _ensure_table(conn, project_id, case_table, "测试用例", case_order, "board", action)
    _ensure_table(conn, project_id, run_table, "用例执行情况", run_order, "detail", action)
    action["tables"]["case"] = case_table
    action["tables"]["run"] = run_table

    indep_table = tables["indep"]["id"]
    indep_clause = _display_field(conn, indep_table, f"{prefix}i-clause")
    indep_acceptance = _status_field(conn, indep_table, "验收状态", f"{prefix}i-acceptance")
    _ensure_fields(
        conn,
        case_table,
        _case_fields(prefix, indep_table, indep_clause, indep_acceptance),
        action,
    )
    case_display = _display_field(conn, case_table, f"{prefix}c-name")
    _ensure_fields(conn, run_table, _run_fields(prefix, case_table, case_display), action)

    run_fields = _fields(conn, run_table)
    run_case_no = next(
        (field["id"] for field in run_fields if field["name"] == "用例号"),
        f"{prefix}r-case_no",
    )
    run_state = _status_field(conn, run_table, "执行状态", f"{prefix}r-state")
    _ensure_fields(
        conn,
        tables["ver"]["id"],
        _ver_fields(prefix, run_table, run_case_no, run_state),
        action,
        reorder=True,
    )

    stage_fields = [
        field["id"]
        for field in _fields(conn, tables["ver"]["id"])
        if field["name"] in STAGE_FIELD_NAMES
    ]
    release_field = next(
        (
            field["id"]
            for field in _fields(conn, tables["ver"]["id"])
            if field["name"] == "发布状态"
        ),
        f"{prefix}v-status",
    )
    _init_stage_nodes(conn, tables["ver"]["id"], release_field, stage_fields, action)

    case_fields = {field["name"]: field["id"] for field in _fields(conn, tables["ver"]["id"])}
    computed_specs = [
        (case_fields.get("用例总数"), 0),
        (case_fields.get("已完成用例数"), 0),
        (case_fields.get("用例是否完成"), True),
    ]
    _init_case_computed(
        conn,
        tables["ver"]["id"],
        [(field_id, value) for field_id, value in computed_specs if field_id],
        action,
    )
    return action


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="board@4 六表建表与存量迁移（019）")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 数据库路径")
    parser.add_argument(
        "--project",
        action="append",
        dest="projects",
        help="只迁移指定项目 id（可重复；默认全部 board@3 项目）",
    )
    parser.add_argument("--artifact", help="比对产物 JSON 路径")
    parser.add_argument("--no-backup", action="store_true", help="不生成迁移前备份")
    parser.add_argument("--dry-run", action="store_true", help="执行后回滚，只产出比对产物")
    args = parser.parse_args(argv)

    try:
        result = migrate(
            args.db,
            projects=args.projects,
            artifact=args.artifact,
            backup=not args.no_backup,
            dry_run=args.dry_run,
        )
    except (MigrationError, sqlite3.Error) as exc:
        print(f"[失败] {exc}", file=sys.stderr)
        return 1

    print(f"数据库：{result['db']}")
    print(f"契约：{result['contract']}")
    if result["backup"]:
        print(f"迁移前备份：{result['backup']}")
    for action in result["projects"]:
        print(
            f"  [{action['project']}] 建表 {len(action['tables_created'])}，"
            f"建字段 {len(action['fields_created'])}，"
            f"节点初始化 {len(action['nodes_initialized'])} 行，"
            f"用例字段初始值 {len(action['computed_initialized'])} 项，"
            f"字段重排 {len(action['order_updates'])} 处"
        )
    for skipped in result["skipped"]:
        print(f"  [跳过] {skipped['project']}：{skipped['reason']}")
    print(f"四张老表比对：差异 {result['diff_total']} 处")
    print(f"比对产物：{result['artifact_path']}")
    if result["dry_run"]:
        print("dry-run：已回滚，未写入")
    if not result["ok"]:
        print("迁移未提交：老表存在差异，详见产物", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
