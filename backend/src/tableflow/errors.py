"""共享异常：写服务的业务校验失败。

单独成模块，避免 `write_service` 与 `calculation` 互相 import 造成循环依赖。
`AuthError` 表示调用者凭据不可用（无效/已吊销的 API key），由接口层映射为 401。
"""

from __future__ import annotations


class WriteError(Exception):
    """业务校验或数据库错误；`unknown=True` 表示提交结果未知。"""

    def __init__(self, message: str, *, unknown: bool = False) -> None:
        super().__init__(message)
        self.unknown = unknown


class AuthError(Exception):
    """调用者凭据不可用；接口层返回 401，且不写业务数据。"""
