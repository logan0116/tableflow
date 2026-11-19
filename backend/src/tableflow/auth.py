"""调用者身份与 API key（013，兼容期）。

兼容期规则：
- 带 `X-API-Key`：按 key 识别调用者（label 即调用者身份）；key 无效或已吊销 → 401 拒写。
- 不带 key：回退 `X-Agent-Id`，旧 skill/脚本的调用方式与写入结果都不变。
- 两者都不带：400 拒写，错误信息保留 `X-Agent-Id` 字样（旧客户端据此提示）。

安全约束：`api_keys` 只存 SHA-256 摘要与标识，明文只在签发时返回一次；
签发/吊销本身也落 `write_audit`（action=`key.issue` / `key.revoke`），审计可倒查。
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .errors import AuthError, WriteError

TZ = timezone(timedelta(hours=8))
KEY_PREFIX = "tfk_"
KEY_ID_PREFIX = "k-"
KEY_LABEL_MAX = 64
NOTE_MAX = 200


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Caller:
    """一次写请求解析出的调用者。"""

    actor: str
    key_id: str | None
    auth_mode: str  # "key" | "agent-id"


def hash_key(raw: str) -> str:
    """key 明文 → 存储摘要；不存明文。"""
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def _new_key_id(conn: sqlite3.Connection) -> str:
    while True:
        candidate = KEY_ID_PREFIX + secrets.token_hex(4)
        exists = conn.execute(
            "SELECT 1 FROM api_keys WHERE id = ?", (candidate,)
        ).fetchone()
        if exists is None:
            return candidate


def _audit_key_event(
    conn: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    target: str,
    result: str,
    error: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO write_audit"
        " (agent_id, key_id, origin, action, target, payload, result, error, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (actor, None, "agent", action, target, None, result, error, _now()),
    )


def _key_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "note": row["note"],
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"],
        "revoked_by": row["revoked_by"],
    }


def issue_key(
    conn: sqlite3.Connection,
    label: str,
    *,
    note: str | None = None,
    by: str = "cli",
) -> tuple[dict[str, Any], str]:
    """签发一把 key：返回（不含明文的记录, 明文）。明文只此一次。"""
    if not isinstance(label, str) or not label.strip():
        raise WriteError("key 的 label（调用者身份）必须是非空字符串")
    label = label.strip()
    if len(label) > KEY_LABEL_MAX:
        raise WriteError(f"key 的 label 长度不能超过 {KEY_LABEL_MAX}")
    if note is not None and (not isinstance(note, str) or len(note) > NOTE_MAX):
        raise WriteError(f"key 的 note 必须是不超过 {NOTE_MAX} 字的字符串")
    raw = KEY_PREFIX + secrets.token_urlsafe(24)
    key_id = _new_key_id(conn)
    created_at = _now()
    conn.execute(
        "INSERT INTO api_keys (id, key_hash, label, note, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (key_id, hash_key(raw), label, note, created_at),
    )
    _audit_key_event(
        conn, actor=by, action="key.issue", target=key_id, result="success"
    )
    conn.commit()
    return (
        {
            "id": key_id,
            "label": label,
            "note": note,
            "created_at": created_at,
            "revoked_at": None,
            "revoked_by": None,
        },
        raw,
    )


def revoke_key(conn: sqlite3.Connection, key_id: str, *, by: str = "cli") -> dict[str, Any]:
    """吊销一把 key；已吊销或不存在都失败（幂等由调用方判断）。"""
    row = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
    if row is None:
        raise WriteError(f"API key 不存在：{key_id}")
    if row["revoked_at"] is not None:
        raise WriteError(f"API key 已吊销：{key_id}（{row['revoked_at']}）")
    revoked_at = _now()
    conn.execute(
        "UPDATE api_keys SET revoked_at = ?, revoked_by = ? WHERE id = ?",
        (revoked_at, by, key_id),
    )
    _audit_key_event(
        conn, actor=by, action="key.revoke", target=key_id, result="success"
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
    return _key_record(updated)


def list_keys(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """列出全部 key（不含摘要与明文），按签发时间排序。"""
    rows = conn.execute(
        "SELECT id, label, note, created_at, revoked_at, revoked_by"
        " FROM api_keys ORDER BY created_at, id"
    ).fetchall()
    return [dict(row) for row in rows]


def list_audit(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    """最近的写审计（含 key 标识），供 CLI 审计查询。"""
    rows = conn.execute(
        "SELECT id, created_at, agent_id, key_id, origin, action, target, result, error"
        " FROM write_audit ORDER BY id DESC LIMIT ?",
        (max(1, int(limit)),),
    ).fetchall()
    return [dict(row) for row in rows]


def resolve_caller(
    conn: sqlite3.Connection,
    *,
    api_key: str | None = None,
    agent_id: str | None = None,
) -> Caller:
    """解析调用者：key 优先；缺 key 回退 X-Agent-Id（兼容期）。"""
    raw = (api_key or "").strip()
    if raw:
        row = conn.execute(
            "SELECT id, label, revoked_at FROM api_keys WHERE key_hash = ?",
            (hash_key(raw),),
        ).fetchone()
        if row is None:
            raise AuthError("无效的 API key")
        if row["revoked_at"] is not None:
            raise AuthError(f"API key 已吊销：{row['id']}")
        return Caller(actor=row["label"], key_id=row["id"], auth_mode="key")
    legacy = (agent_id or "").strip()
    if legacy:
        return Caller(actor=legacy, key_id=None, auth_mode="agent-id")
    raise WriteError("缺少调用者身份：X-API-Key 或 X-Agent-Id 至少给一个")
