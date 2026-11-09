#!/bin/sh
# 容器内初始化数据：备份旧库 → 建空库 → 用写接口灌 fd_system / tableflow / 002-004。
# 用法：docker exec tableflow sh /app/seed.sh
set -eu

# 重建前先备份：线上可能有人工/Agent 写入的其它项目，rm 掉就找不回来了。
# 保留最近 5 份，文件名带时间戳，按 mtime 淘汰最旧的。
if [ -f /data/tableflow.db ]; then
  stamp=$(date +%Y%m%d-%H%M%S)
  cp /data/tableflow.db "/data/tableflow.db.bak-$stamp"
  ls -1t /data/tableflow.db.bak-* 2>/dev/null | tail -n +6 | while read -r old; do
    rm -f "$old"
  done
  echo "backup: /data/tableflow.db.bak-$stamp"
fi

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
