"""共享异常：写服务的业务校验失败。

单独成模块，避免 `write_service` 与 `calculation` 互相 import 造成循环依赖。
"""

from __future__ import annotations


class WriteError(Exception):
    """业务校验或数据库错误；`unknown=True` 表示提交结果未知。"""

    def __init__(self, message: str, *, unknown: bool = False) -> None:
        super().__init__(message)
        self.unknown = unknown
