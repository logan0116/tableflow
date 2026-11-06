#!/usr/bin/env python3
"""兼容入口：v0.3.0 的数据迁移采用「重建」策略。

governance 的 002 spec 结论：v0.3.0 不保留 001 的随机行 id 与双向关联字段，
旧库不自动转换；迁移 = 备份 → 删库 → 按新模板重灌（见 data/rebuild_v030.py）。

用法：
    backend/.venv/bin/python data/migrate_v030.py [--api-base http://127.0.0.1:8000]
"""

from __future__ import annotations

import sys

from rebuild_v030 import main

if __name__ == "__main__":
    sys.exit(main())
