#!/usr/bin/env python3
"""board@4（019）闸门数据迁移：字段改名 + stage_done + gate 改口径 + 去掉三布尔闸门标记。

契约唯一来源：`specs/019-test-contract/board@4.yaml`。本脚本只做**数据层**收尾，
写侧串行/节点一致性校验仍归 025（T7），这里不新增任何写接口拒绝路径。

做四件事（全部幂等，重跑不重复建字段、不覆盖已有行）：
1. `rename-bug-fields`：`上一版本Bug已修复/总数 → Bug已修复/总数`、
   `上一版本Bug是否清空 → Bug是否清空`（只改名，options/语义键不变）。
2. 版本表补 `六节点是否全部完成` 计算字段（id `<前缀>v-stage-done`）：
   `and(六个节点 == done)`，打 gate:true，按契约排到第 9 位。
3. `发布条件` 改为 `and(六节点是否全部完成 == true)`，仍打 gate:true。
4. 三个展示布尔（独立需求是否完成 / 依赖需求是否完成 / Bug是否清空）摘掉 gate:true；
   board@4 起闸门从 4 个降到 2 个。
随后整表重算，并验证：released 版本 gate/stage_done 为真；planned/dropped 为假。

用法：
    backend/.venv/bin/python backend/scripts/migrate_board4_gate.py --dry-run
    backend/.venv/bin/python backend/scripts/migrate_board4_gate.py
    backend/.venv/bin/python backend/scripts/migrate_board4_gate.py --db data/tableflow.db
    # 线上容器内：docker cp 后在容器里用 PYTHONPATH=/app/backend/src 跑，保证用同一份 calculation

退出码：0=成功（含本来就一致）；1=冲突/重算或验证失败（回滚）。
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

try:
    REPO_ROOT = Path(__file__).resolve().parents[2]
except IndexError:  # pragma: no cover - 独立拷贝到 /tmp 运行时
    REPO_ROOT = Path.cwd()
BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tableflow import calculation  # noqa: E402

DEFAULT_DB = Path(os.environ.get("TABLEFLOW_DB") or REPO_ROOT / "data" / "tableflow.db")
TZ = timezone(timedelta(hours=8))
ROLES = ("ver", "indep", "dep", "bug")

RENAMES = {
    "上一版本Bug已修复/总数": "Bug已修复/总数",
    "上一版本Bug是否清空": "Bug是否清空",
}
STAGE_NAMES = (
    "版本需求设计",
    "测试设计",
    "开发",
    "开发验收",
    "测试",
    "测试验收",
)
STAGE_DONE_NAME = "六节点是否全部完成"
GATE_NAME = "发布条件"
ALLOWED_GATE_NAMES = {STAGE_DONE_NAME, GATE_NAME}

# board@4 版本表字段顺序（26）。stage_done 在第 9 位，gate 第 10 位。
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
POSITION_BY_NAME = {name: index + 1 for index, name in enumerate(VER_ORDER)}


class MigrationError(RuntimeError):
    """结构性冲突或迁移后验证失败。"""


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
    for field in ver_fields:
        if field["name"] == "版本号" or field["id"].endswith("v-ver"):
            if field["id"].endswith("v-ver"):
                return field["id"][: -len("v-ver")]
    return ver_table_id[: -len("ver")]


def _backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(db_path.name + f".bak-board4-gate-{stamp}")
    destination = sqlite3.connect(target)
    try:
        conn.backup(destination)
    finally:
        destination.close()
    return target


def _rows(conn: sqlite3.Connection, table_id: str) -> dict[str, dict]:
    return {
        row["id"]: _loads(row["data"]) or {}
        for row in conn.execute(
            "SELECT id, data FROM row_records WHERE table_id = ? ORDER BY id", (table_id,)
        )
    }


def _snapshot_rows(conn: sqlite3.Connection, tables: dict[str, dict]) -> dict[str, dict]:
    return {role: _rows(conn, tables[role]["id"]) for role in ROLES}


def _computed(conn: sqlite3.Connection, table_id: str) -> dict[tuple[str, str], Any]:
    return {
        (row["row_id"], row["field_id"]): _loads(row["value"])
        for row in conn.execute(
            "SELECT row_id, field_id, value FROM computed_values WHERE table_id = ?",
            (table_id,),
        )
    }


def _migrate_project(conn: sqlite3.Connection, target: dict[str, Any]) -> dict[str, Any]:
    project_id = target["project_id"]
    ver_table = target["tables"]["ver"]["id"]
    prefix = target["field_prefix"]
    action: dict[str, Any] = {
        "project": project_id,
        "ver_table": ver_table,
        "field_prefix": prefix,
        "renamed_fields": [],
        "fields_added": [],
        "gate_marks_removed": [],
        "gate_options_updated": [],
        "order_updates": [],
        "recompute": {},
        "gate_checks": [],
    }

    existing = {field["name"]: field for field in _fields(conn, ver_table)}

    # 1) 两个 Bug 字段改名（只改 name，不动 id/options/语义键）。
    for old_name, new_name in RENAMES.items():
        old_field = existing.get(old_name)
        new_field = existing.get(new_name)
        if old_field is not None and new_field is not None:
            raise MigrationError(
                f"{project_id}：字段改名冲突，「{old_name}」与「{new_name}」同时存在"
            )
        if old_field is not None:
            conn.execute(
                "UPDATE fields SET name = ? WHERE id = ?", (new_name, old_field["id"])
            )
            action["renamed_fields"].append(
                {"field": old_field["id"], "before": old_name, "after": new_name}
            )

    # 重新读取（改名后按 name 建索引）。
    fields = _fields(conn, ver_table)
    by_name = {field["name"]: field for field in fields}
    stage_fields = []
    for name in STAGE_NAMES:
        if name not in by_name:
            raise MigrationError(f"{project_id}：六节点字段缺失「{name}」，先跑 T1 迁移")
        stage_fields.append(by_name[name])

    # 2) 六节点汇总字段 stage_done。
    stage_done = by_name.get(STAGE_DONE_NAME)
    stage_done_options = {
        "kind": "and",
        "conditions": [
            {"field_id": field["id"], "equals": "done"} for field in stage_fields
        ],
        "gate": True,
        "true_label": "是",
        "false_label": "否",
    }
    if stage_done is None:
        stage_done_id = f"{prefix}v-stage-done"
        if any(field["id"] == stage_done_id for field in fields):
            raise MigrationError(f"{project_id}：字段 id {stage_done_id} 已被其他字段占用")
        conn.execute(
            'INSERT INTO fields (id, table_id, name, type, options, "order", visible)'
            " VALUES (?, ?, ?, 'computed', ?, ?, 1)",
            (
                stage_done_id,
                ver_table,
                STAGE_DONE_NAME,
                _dumps(stage_done_options),
                POSITION_BY_NAME[STAGE_DONE_NAME],
            ),
        )
        action["fields_added"].append(stage_done_id)
        stage_done_id_value = stage_done_id
    else:
        stage_done_id_value = stage_done["id"]
        if stage_done["type"] != "computed":
            raise MigrationError(f"{project_id}：{STAGE_DONE_NAME} 已存在但不是计算字段")
        if _needs_update(stage_done.get("options"), stage_done_options):
            conn.execute(
                "UPDATE fields SET options = ? WHERE id = ?",
                (_dumps(stage_done_options), stage_done_id_value),
            )
            action["gate_options_updated"].append(
                {"field": stage_done_id_value, "what": "stage_done 规则"}
            )

    # 3) 发布条件改为 and(stage_done == true)。
    gate_field = by_name.get(GATE_NAME)
    if gate_field is None:
        raise MigrationError(f"{project_id}：版本表没有「{GATE_NAME}」字段")
    if gate_field["type"] != "computed":
        raise MigrationError(f"{project_id}：「{GATE_NAME}」不是计算字段")
    old_gate_options = _loads(gate_field.get("options"))
    gate_options = dict(old_gate_options) if isinstance(old_gate_options, dict) else {}
    gate_options.update(
        {
            "kind": "and",
            "conditions": [{"field_id": stage_done_id_value, "equals": True}],
            "gate": True,
            "true_label": gate_options.get("true_label", "是"),
            "false_label": gate_options.get("false_label", "否"),
        }
    )
    if _needs_update(gate_field.get("options"), gate_options):
        conn.execute(
            "UPDATE fields SET options = ? WHERE id = ?",
            (_dumps(gate_options), gate_field["id"]),
        )
        action["gate_options_updated"].append(
            {"field": gate_field["id"], "what": "发布条件规则"}
        )

    # 4) board@4 只保留两个闸门；其余计算字段摘掉 gate:true。
    for field in _fields(conn, ver_table):
        if field["type"] != "computed" or field["name"] in ALLOWED_GATE_NAMES:
            continue
        options = _loads(field.get("options"))
        if not isinstance(options, dict) or not options.get("gate"):
            continue
        options = dict(options)
        options.pop("gate", None)
        conn.execute(
            "UPDATE fields SET options = ? WHERE id = ?",
            (_dumps(options), field["id"]),
        )
        action["gate_marks_removed"].append(field["id"])

    # 5) 版本表按契约顺序重排（stage_done 第 9、gate 第 10）。
    current = _fields(conn, ver_table)
    known = [
        (POSITION_BY_NAME[field["name"]], field)
        for field in current
        if field["name"] in POSITION_BY_NAME
    ]
    unknown = [field for field in current if field["name"] not in POSITION_BY_NAME]
    ordered = [field for _, field in sorted(known, key=lambda item: item[0])] + unknown
    for index, field in enumerate(ordered, start=1):
        if field["order"] == index:
            continue
        conn.execute('UPDATE fields SET "order" = ? WHERE id = ?', (index, field["id"]))
        action["order_updates"].append(
            {"field": field["id"], "before": field["order"], "after": index}
        )

    # 6) 整表重算：stage_done / gate 及各比例、用例字段。
    action["recompute"] = calculation.recompute_table(
        conn, ver_table, actor="agent-board4-gate", origin="human-request"
    )

    # 7) 验证：released → stage_done/gate 真；planned/dropped → 假。
    status_field = by_name.get("发布状态")
    if status_field is None:
        raise MigrationError(f"{project_id}：版本表没有「发布状态」字段")
    gate_id = gate_field["id"]
    computed = _computed(conn, ver_table)
    rows = _rows(conn, ver_table)
    seen = 0
    for row_id, values in rows.items():
        status_value = values.get(status_field["id"])
        expected = status_value == "released"
        gate_value = computed.get((row_id, gate_id))
        stage_value = computed.get((row_id, stage_done_id_value))
        ok = gate_value is expected and stage_value is expected
        action["gate_checks"].append(
            {
                "row": row_id,
                "release_status": status_value,
                "gate": gate_value,
                "stage_done": stage_value,
                "expected": expected,
                "ok": ok,
            }
        )
        seen += 1
        if not ok:
            raise MigrationError(
                f"{project_id}/{row_id}：gate/stage_done 与发布状态不一致（"
                f"release_status={status_value!r}, gate={gate_value!r}, "
                f"stage_done={stage_value!r}, expected={expected}）"
            )
    if seen == 0:
        action["gate_checks"] = []
    return action


def _needs_update(old_raw: Any, new_options: dict) -> bool:
    old = _loads(old_raw)
    return not isinstance(old, dict) or old != new_options


def migrate(
    db_path: str | Path,
    *,
    projects: list[str] | None = None,
    artifact: str | Path | None = None,
    backup: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
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
            selected = set(projects or [])
            targets: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            for project in conn.execute("SELECT id, name FROM projects ORDER BY id"):
                project_id = project["id"]
                if selected and project_id not in selected:
                    continue
                tables = _table_map(conn, project_id)
                missing = [role for role in ROLES if role not in tables]
                if missing:
                    skipped.append({"project": project_id, "reason": f"缺表：{missing}"})
                    continue
                ver_fields = _fields(conn, tables["ver"]["id"])
                targets.append(
                    {
                        "project_id": project_id,
                        "tables": tables,
                        "field_prefix": _field_prefix(ver_fields, tables["ver"]["id"]),
                    }
                )
            if selected:
                known = {target["project_id"] for target in targets} | {
                    item["project"] for item in skipped
                }
                unknown = sorted(selected - known)
                if unknown:
                    raise MigrationError(f"指定的项目不存在：{unknown}")

            before_rows = {
                target["project_id"]: _snapshot_rows(conn, target["tables"])
                for target in targets
            }
            actions = [_migrate_project(conn, target) for target in targets]
            after_rows = {
                target["project_id"]: _snapshot_rows(conn, target["tables"])
                for target in targets
            }
            row_diffs: dict[str, dict[str, int]] = {}
            diff_total = 0
            for target in targets:
                project_id = target["project_id"]
                row_diffs[project_id] = {}
                for role in ROLES:
                    old = before_rows[project_id][role]
                    new = after_rows[project_id][role]
                    changed = sorted(
                        row_id for row_id in old if old[row_id] != new.get(row_id)
                    )
                    added = sorted(set(new) - set(old))
                    removed = sorted(set(old) - set(new))
                    count = len(changed) + len(added) + len(removed)
                    diff_total += count
                    row_diffs[project_id][role] = {
                        "rows_before": len(old),
                        "rows_after": len(new),
                        "changed_rows": changed,
                        "added_rows": added,
                        "removed_rows": removed,
                    }
            artifact_doc = {
                "generated_at": _now(),
                "db": str(db_path),
                "contract": "specs/019-test-contract/board@4.yaml",
                "scope": "board@4 闸门数据迁移：Bug 字段改名、stage_done、gate 改口径、三布尔摘闸门、重算",
                "backup": str(backup_path) if backup_path else None,
                "projects": actions,
                "skipped": skipped,
                "row_diffs": row_diffs,
                "row_diff_total": diff_total,
                "dry_run": dry_run,
                "ok": diff_total == 0,
            }
            if diff_total != 0:
                conn.execute("ROLLBACK")
            elif dry_run:
                conn.execute("ROLLBACK")
            else:
                conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()

    if artifact is None:
        artifact = REPO_ROOT / "data" / "backups" / (
            f"board4-gate-migration-{datetime.now(TZ).strftime('%Y%m%d-%H%M%S')}.json"
        )
    artifact = Path(artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(artifact_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    artifact_doc["artifact_path"] = str(artifact)
    return artifact_doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="board@4 闸门数据迁移（019 收尾）")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 数据库路径")
    parser.add_argument(
        "--project",
        action="append",
        dest="projects",
        help="只迁移指定项目 id（可重复；默认全部 board@3/4 项目）",
    )
    parser.add_argument("--artifact", help="产物 JSON 路径")
    parser.add_argument("--no-backup", action="store_true", help="不生成迁移前备份")
    parser.add_argument("--dry-run", action="store_true", help="执行后回滚，只产出产物")
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
    if result["backup"]:
        print(f"迁移前备份：{result['backup']}")
    for action in result["projects"]:
        checks = action["gate_checks"]
        passed = sum(1 for item in checks if item["ok"])
        print(
            f"  [{action['project']}] 改名 {len(action['renamed_fields'])}，"
            f"新增字段 {len(action['fields_added'])}，"
            f"摘闸门 {len(action['gate_marks_removed'])}，"
            f"规则更新 {len(action['gate_options_updated'])}，"
            f"重排 {len(action['order_updates'])}，"
            f"gate 校验 {passed}/{len(checks)}"
        )
    for skipped in result["skipped"]:
        print(f"  [跳过] {skipped['project']}：{skipped['reason']}")
    print(f"老表行数据差异：{result['row_diff_total']} 处")
    print(f"产物：{result['artifact_path']}")
    if result["dry_run"]:
        print("dry-run：已回滚，未写入")
    if not result["ok"]:
        print("迁移未提交：行数据存在差异，详见产物", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
