"""交付唯一性与先后校验（033，board@5 的 C1/C2/C3）。

契约 `specs/019-test-contract/board@5.yaml` 的三条写入期规则：

- **C1** 同一独立需求在所有版本的「独立需求管理」中出现次数不超过 1；
- **C2** 同一依赖需求在所有版本的「依赖需求管理」中出现次数不超过 1；
- **C3** 依赖需求所在版本不得早于其关联的任一独立需求所在版本，允许同版本；
  关联多份规格时以其中最晚交付者作为比较基准。

实现口径：

1. **只校验新增**。判定对象是本次写入相对原值新加入的 id，不是写入后的全集——
   否则存量违规数据会让任何无关编辑都被拦下（与 013 对存量悬空引用的处理同一思路）。
2. **表识别不依赖表 id**：表内恰好六个四态 enum 字段即版本表（复用 025 的
   `version_stage.stage_nodes`）；关系角色按目标表的判据枚举值域识别 indep / dep。
3. **C3 在两条路径上都校验**：把依赖需求挂到版本时（版本表写入），以及修改依赖需求
   关联的规格时（dep 表写入）；后者先反查该依赖需求当前由哪个版本持有。
4. **语义序比较**：版本号按 `v<主>.<次>.<修>` 比较；任一侧无法解析时 C3 不启用（不猜）。

规则判定只有这一份实现：技能侧不复制判定逻辑，只转述引擎返回的规则号与说明。
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from . import version_stage
from .errors import WriteError

ACCEPTANCE_VALUES = frozenset({"pending", "accepted", "rejected", "dropped"})
# board@5 前是三元域；迁移未完成的项目仍按三元识别，两种都认
ACCEPTANCE_DOMAINS = frozenset({
    ACCEPTANCE_VALUES,
    frozenset({"pending", "accepted", "rejected"}),
})
REGRESS_VALUES = frozenset({"todo", "doing", "passed", "failed"})

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


# ---------- 基础工具 ----------


def _loads(raw: Any) -> Any:
    if raw is None or not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _semver(value: Any) -> tuple[int, int, int] | None:
    match = SEMVER_RE.match(str(value or "").strip())
    return tuple(int(x) for x in match.groups()) if match else None


def _fmt(key: tuple[int, int, int]) -> str:
    return f"v{key[0]}.{key[1]}.{key[2]}"


def _table_fields(conn: sqlite3.Connection, table_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        'SELECT id, name, type, options, "order" FROM fields WHERE table_id = ?',
        (table_id,),
    ).fetchall()
    return {row["id"]: row for row in rows}


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


def _target_table_id(field: sqlite3.Row) -> str | None:
    options = _loads(field["options"])
    target = options.get("table_id") if isinstance(options, dict) else None
    return target if isinstance(target, str) else None


def _target_role(conn: sqlite3.Connection, field: sqlite3.Row) -> str | None:
    """按目标表的判据枚举值域判定关系角色：indep / dep / 其他。"""
    target_id = _target_table_id(field)
    if not target_id:
        return None
    domains = {
        _enum_values(item)
        for item in _table_fields(conn, target_id).values()
        if item["type"] == "enum"
    }
    if ACCEPTANCE_DOMAINS & domains:
        return "indep"
    if REGRESS_VALUES in domains:
        return "dep"
    return None


def _relation_fields(
    conn: sqlite3.Connection, fields: dict[str, sqlite3.Row]
) -> dict[str, sqlite3.Row]:
    """表内指向 indep / dep 的关系字段；同角色多个时不猜（该角色不启用）。"""
    found: dict[str, list[sqlite3.Row]] = {}
    for field in fields.values():
        if field["type"] != "relation":
            continue
        role = _target_role(conn, field)
        if role:
            found.setdefault(role, []).append(field)
    return {role: items[0] for role, items in found.items() if len(items) == 1}


def _version_rows(
    conn: sqlite3.Connection, table_id: str
) -> list[tuple[str, dict[str, Any]]]:
    rows = conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ?", (table_id,)
    ).fetchall()
    return [(row["id"], _loads(row["data"]) or {}) for row in rows]


def _row_values(
    conn: sqlite3.Connection, table_id: str, row_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT data FROM row_records WHERE table_id = ? AND id = ?", (table_id, row_id)
    ).fetchone()
    return None if row is None else (_loads(row["data"]) or {})


def _version_tables(conn: sqlite3.Connection) -> list[tuple[str, dict[str, sqlite3.Row]]]:
    out: list[tuple[str, dict[str, sqlite3.Row]]] = []
    for row in conn.execute("SELECT id FROM tables").fetchall():
        table_id = row["id"]
        fields = _table_fields(conn, table_id)
        if version_stage.stage_nodes(fields) is not None:
            out.append((table_id, fields))
    return out


# ---------- 持有者索引 ----------


def _holders(
    conn: sqlite3.Connection, table_id: str, field_id: str, *, exclude: str | None = None
) -> dict[str, str]:
    """某关联字段里各 id 被哪些版本持有：id → 版本号（语义序最大者）。"""
    holders: dict[str, str] = {}
    for version_id, data in _version_rows(conn, table_id):
        if version_id == exclude:
            continue
        for item in _as_list(data.get(field_id)):
            current = holders.get(item)
            if current is None:
                holders[item] = version_id
                continue
            if _semver(version_id) and _semver(current) and _semver(version_id) > _semver(current):
                holders[item] = version_id
    return holders


def _check_once(
    rule: str, added: list[str], holders: dict[str, str], version_id: str, label: str
) -> None:
    clashes = [(item, holders[item]) for item in added if item in holders]
    if clashes:
        detail = "、".join(f"{item}（已属 {version}）" for item, version in clashes)
        advice = (
            "复测历史能力请把用例纳入本版本（ver.测试用例），不要重复挂载需求"
            if rule == "C1"
            else "一次增量只属于一个版本；要再改请新建依赖需求，不要重复挂载"
        )
        raise WriteError(
            f"{rule}：同一{label}在所有版本中只能出现一次；{version_id} 重复挂载 {detail}。{advice}"
        )


# ---------- C3 ----------


def _dep_spec_field(
    conn: sqlite3.Connection, fields: dict[str, sqlite3.Row]
) -> sqlite3.Row | None:
    candidates = [
        field
        for field in fields.values()
        if field["type"] == "relation" and _target_role(conn, field) == "indep"
    ]
    return candidates[0] if len(candidates) == 1 else None


def _check_dep_after_spec(
    conn: sqlite3.Connection,
    version_table_id: str,
    indep_field_id: str,
    dep_specs: dict[str, list[str]],
    version_id: str,
    own_specs: list[str] = (),
) -> None:
    """C3：依赖需求所在版本不得早于其关联独立需求所在版本。

    ``own_specs`` 是本次同一请求里加入本版本的规格：它们尚未落库，但语义上已属本版本，
    必须按 ``version_id`` 计入，否则"同一行既挂需求又挂变更单"会被误判为未交付。
    """
    version_key = _semver(version_id)
    if version_key is None:
        return
    spec_versions = _holders(conn, version_table_id, indep_field_id)
    own = set(own_specs)
    for dep_id, specs in dep_specs.items():
        if not specs:
            continue
        latest: tuple[int, int, int] | None = None
        undelivered: list[str] = []
        for spec_id in specs:
            holder = version_id if spec_id in own else spec_versions.get(spec_id)
            if holder is None:
                undelivered.append(spec_id)
                continue
            key = _semver(holder)
            if key is not None and (latest is None or key > latest):
                latest = key
        if undelivered:
            raise WriteError(
                f"C3：依赖需求 {dep_id} 关联的规格尚未交付，不能挂到 {version_id}："
                + "、".join(undelivered)
                + "。请先交付该规格，或把它从依赖需求的关联中移除"
            )
        if latest is not None and version_key < latest:
            raise WriteError(
                f"C3：依赖需求 {dep_id} 关联的规格最晚交付于 {_fmt(latest)}，"
                f"不能挂到更早的版本 {version_id}。请把该依赖需求挂到不早于 {_fmt(latest)} 的版本"
            )


# ---------- 两条写入路径 ----------


def _validate_version_row(
    conn: sqlite3.Connection,
    table_id: str,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    merged: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    relations = _relation_fields(conn, fields)
    indep_field = relations.get("indep")
    dep_field = relations.get("dep")

    if indep_field is not None:
        added = [
            item
            for item in _as_list(merged.get(indep_field["id"]))
            if item not in _as_list(previous.get(indep_field["id"]))
        ]
        if added:
            _check_once(
                "C1", added,
                _holders(conn, table_id, indep_field["id"], exclude=row_id),
                row_id, "独立需求",
            )

    if dep_field is None:
        return
    added = [
        item
        for item in _as_list(merged.get(dep_field["id"]))
        if item not in _as_list(previous.get(dep_field["id"]))
    ]
    if not added:
        return
    _check_once(
        "C2", added,
        _holders(conn, table_id, dep_field["id"], exclude=row_id),
        row_id, "依赖需求",
    )
    if indep_field is None:
        return
    dep_table_id = _target_table_id(dep_field)
    if dep_table_id is None:
        return
    spec_field = _dep_spec_field(conn, _table_fields(conn, dep_table_id))
    if spec_field is None:
        return
    dep_specs = {}
    for dep_id in added:
        values = _row_values(conn, dep_table_id, dep_id)
        if values is not None:
            dep_specs[dep_id] = _as_list(values.get(spec_field["id"]))
    _check_dep_after_spec(
        conn, table_id, indep_field["id"], dep_specs, row_id,
        own_specs=_as_list(merged.get(indep_field["id"])),
    )


def _validate_dep_row(
    conn: sqlite3.Connection,
    table_id: str,
    fields: dict[str, sqlite3.Row],
    row_id: str,
    merged: dict[str, Any],
    submitted: dict[str, Any],
) -> None:
    """修改依赖需求关联的规格时，按它当前所属版本复核 C3。"""
    spec_field = _dep_spec_field(conn, fields)
    if spec_field is None or spec_field["id"] not in submitted:
        return
    specs = _as_list(merged.get(spec_field["id"]))
    if not specs:
        return
    for version_table_id, version_fields in _version_tables(conn):
        relations = _relation_fields(conn, version_fields)
        dep_field = relations.get("dep")
        indep_field = relations.get("indep")
        if dep_field is None or indep_field is None:
            continue
        if _target_table_id(dep_field) != table_id:
            continue
        for version_id, data in _version_rows(conn, version_table_id):
            if row_id not in _as_list(data.get(dep_field["id"])):
                continue
            _check_dep_after_spec(
                conn, version_table_id, indep_field["id"], {row_id: specs}, version_id
            )
            return


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
    if version_stage.stage_nodes(fields) is not None:
        _validate_version_row(conn, table_id, fields, row_id, merged, previous)
        return
    _validate_dep_row(
        conn, table_id, fields, row_id, merged,
        submitted if submitted is not None else merged,
    )


# ---------- 交付记录查询（033 T001 / FR-006） ----------

SPEC_REVISION_NAME = "规格修订"


def _version_table_of(
    conn: sqlite3.Connection, project_id: str
) -> tuple[str, dict[str, sqlite3.Row]] | None:
    rows = conn.execute(
        'SELECT id FROM tables WHERE project_id = ? ORDER BY "order" ASC, id ASC',
        (project_id,),
    ).fetchall()
    for row in rows:
        fields = _table_fields(conn, row["id"])
        if version_stage.stage_nodes(fields) is not None:
            return row["id"], fields
    return None


def _dep_meta_fields(
    conn: sqlite3.Connection, dep_table_id: str
) -> tuple[sqlite3.Row | None, sqlite3.Row | None, sqlite3.Row | None]:
    """依赖需求表的：关联规格、回归状态、规格修订。"""
    fields = _table_fields(conn, dep_table_id)
    spec_field = _dep_spec_field(conn, fields)
    regress = next(
        (
            field
            for field in fields.values()
            if field["type"] == "enum" and _enum_values(field) == REGRESS_VALUES
        ),
        None,
    )
    revision = next(
        (field for field in fields.values() if field["name"] == SPEC_REVISION_NAME),
        None,
    )
    return spec_field, regress, revision


def spec_delivery(
    conn: sqlite3.Connection, project_id: str, spec_id: str
) -> dict[str, Any] | None:
    """某份规格的交付记录与当前生效修订。

    返回 ``None`` 表示项目不存在或没有版本表（无法判定）。
    """
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        return None
    located = _version_table_of(conn, project_id)
    if located is None:
        return None
    version_table_id, version_fields = located
    relations = _relation_fields(conn, version_fields)
    indep_field = relations.get("indep")
    dep_field = relations.get("dep")

    versions = _version_rows(conn, version_table_id)
    delivered_in: str | None = None
    if indep_field is not None:
        for version_id, data in versions:
            if spec_id not in _as_list(data.get(indep_field["id"])):
                continue
            if delivered_in is None or (
                _semver(version_id) and _semver(delivered_in)
                and _semver(version_id) > _semver(delivered_in)
            ):
                delivered_in = version_id

    revisions: list[dict[str, Any]] = []
    if dep_field is not None:
        dep_table_id = _target_table_id(dep_field)
        if dep_table_id is not None:
            spec_field, regress, revision = _dep_meta_fields(conn, dep_table_id)
            if spec_field is not None:
                for version_id, data in versions:
                    for dep_id in _as_list(data.get(dep_field["id"])):
                        values = _row_values(conn, dep_table_id, dep_id)
                        if values is None:
                            continue
                        if spec_id not in _as_list(values.get(spec_field["id"])):
                            continue
                        revisions.append(
                            {
                                "dep": dep_id,
                                "version": version_id,
                                "regress": values.get(regress["id"]) if regress else None,
                                "spec_revision": values.get(revision["id"]) if revision else None,
                            }
                        )
    revisions.sort(key=lambda item: (_semver(item["version"]) or (0, 0, 0), item["dep"]))

    effective = [
        item for item in revisions
        if item["regress"] == "passed" and item["spec_revision"] == "done"
    ]
    current = (
        {"source": "change", **effective[-1]}
        if effective
        else {"source": "initial", "dep": None, "version": delivered_in, "regress": None,
              "spec_revision": None}
    )
    return {
        "spec": spec_id,
        "delivered_in": delivered_in,
        "current_revision": current,
        "effective_revisions": effective,
        "all_changes": revisions,
    }


def resolve_spec_by_dir(
    conn: sqlite3.Connection, project_id: str, directory: str
) -> str | None:
    """按规格目录找规格编号（033 US1 AS1：给 ``specs/026-ver-columns/`` 能查到交付记录）。"""
    located = _version_table_of(conn, project_id)
    if located is None:
        return None
    _version_table_id, version_fields = located
    indep_field = _relation_fields(conn, version_fields).get("indep")
    if indep_field is None:
        return None
    indep_table_id = _target_table_id(indep_field)
    if indep_table_id is None:
        return None
    wanted = directory.strip().strip("/")
    for row in conn.execute(
        "SELECT id, data FROM row_records WHERE table_id = ?", (indep_table_id,)
    ).fetchall():
        values = _loads(row["data"]) or {}
        for name, value in values.items():
            if name.endswith("dir") and isinstance(value, str):
                if value.strip().strip("/") == wanted:
                    return row["id"]
    return None
