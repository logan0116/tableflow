#!/bin/sh
# 容器内初始化数据：建空库 → 用写接口灌 fd_system / tableflow / 002-004。
# 用法：docker exec tableflow sh /app/seed.sh
set -eu

rm -f /data/tableflow.db /data/tableflow.db-wal /data/tableflow.db-shm

python - <<'PY'
from pathlib import Path
from tableflow.db import connect_write, init_schema

init_schema(connect_write(Path("/data/tableflow.db")))
print("schema ready")
PY

export TABLEFLOW_API_BASE=http://127.0.0.1:8090
python /app/data/load_fd_system.py
python /app/data/load_tableflow.py
python /app/data/load_specs.py
echo "seed done"
