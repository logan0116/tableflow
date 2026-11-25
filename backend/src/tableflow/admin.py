"""设置页管理口令（045）。

管理接口（列出/签发/吊销 API key）不走 API key 身份，而是用部署侧口令
`TABLEFLOW_ADMIN_TOKEN` 校验。口令不落库、不进界面，只由运维在部署时给定。

安全约束：未配置口令时管理接口一律 503（fail-closed），不得降级为
「无口令放行」；口令比较用常量时间，错误响应不回显任何正确口令片段。
"""

from __future__ import annotations

import os
import secrets

ADMIN_TOKEN_ENV = "TABLEFLOW_ADMIN_TOKEN"
MIN_TOKEN_LEN = 8


class AdminDisabled(Exception):
    """未配置管理口令：设置页不可用（503）。"""


class AdminError(Exception):
    """口令缺失或不匹配：拒绝（401）。"""


def admin_token() -> str | None:
    """部署侧管理口令；未配置或过短都视为未启用。"""
    raw = (os.environ.get(ADMIN_TOKEN_ENV) or "").strip()
    if len(raw) < MIN_TOKEN_LEN:
        return None
    return raw


def admin_enabled() -> bool:
    return admin_token() is not None


def verify_admin(token: str | None) -> None:
    """校验口令：未配置 → `AdminDisabled`；不匹配 → `AdminError`。"""
    expected = admin_token()
    if expected is None:
        raise AdminDisabled(
            f"管理口令未配置（{ADMIN_TOKEN_ENV} 至少 {MIN_TOKEN_LEN} 位），设置页不可用"
        )
    provided = (token or "").strip()
    if not provided or not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise AdminError("管理口令错误")
