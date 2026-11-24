#!/bin/sh
# 容器内初始化数据：备份旧库 → 建空库 → 用写接口灌 demo / tableflow / 002-004。
# 用法：docker exec tableflow sh /app/seed.sh
set -eu

# 重建前先备份：线上可能有人工/Agent 写入的其它项目，rm 掉就找不回来了。
# WAL 模式下直接 cp 主库会缺最近提交（改动用 -wal），必须用 SQLite Online Backup API
# 取一致性快照，并在备份后做完整性检查。保留最近 5 份，按 mtime 淘汰最旧的。
if [ -f /data/tableflow.db ]; then
  stamp=$(date +%Y%m%d-%H%M%S)
  bak="/data/tableflow.db.bak-$stamp"
  python - "$bak" <<'PY'
import sqlite3, sys

bak = sys.argv[1]
src = sqlite3.connect("file:/data/tableflow.db?mode=ro", uri=True)
dst = sqlite3.connect(bak)
try:
    src.backup(dst)
    dst.execute("PRAGMA journal_mode=DELETE")
    dst.commit()
    check = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if check != "ok":
        raise SystemExit(f"backup integrity_check failed: {check}")
    have = {row[0] for row in dst.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "tables" not in have:
        raise SystemExit("backup missing core table: tables")
    print(f"backup ok: tables={len(have)}")
finally:
    dst.close()
    src.close()
PY
  ls -1t /data/tableflow.db.bak-* 2>/dev/null | tail -n +6 | while read -r old; do
    rm -f "$old"
  done
  echo "backup: $bak"
fi

rm -f /data/tableflow.db /data/tableflow.db-wal /data/tableflow.db-shm

python - <<'PY'
from pathlib import Path
from tableflow.db import connect_write, init_schema

init_schema(connect_write(Path("/data/tableflow.db")))
print("schema ready")
PY

export TABLEFLOW_API_BASE=http://127.0.0.1:8090
python /app/data/load_demo_project.py
python /app/data/load_tableflow.py
python /app/data/load_specs.py
echo "seed done"
