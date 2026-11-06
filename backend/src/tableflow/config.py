"""运行期配置。"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def db_path() -> Path:
    """数据库路径：环境变量 TABLEFLOW_DB 优先，默认仓库根目录 data/tableflow.db。"""
    raw = os.environ.get("TABLEFLOW_DB")
    if raw:
        return Path(raw).expanduser().resolve()
    return REPO_ROOT / "data" / "tableflow.db"
