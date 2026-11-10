#!/usr/bin/env bash
# 把 tableflow 部署到远端主机（docker compose，单端口，前后端同容器）。
#
# 用法：
#   HOST=user@your-host bash deploy/deploy.sh          # 只更新代码，不动数据（默认）
#   HOST=user@your-host bash deploy/deploy.sh --seed   # 同时重建数据（seed.sh 会先备份旧库）
#
# 也可以把 HOST 写进 deploy/.env（不入库，已 gitignore），脚本会自动读取。
# 默认不 seed：线上可能有通过 Agent 写入的项目，重建会把它们清掉。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  . "$SCRIPT_DIR/.env"
fi

HOST="${HOST:?请设置 HOST（环境变量或 deploy/.env），例如 HOST=user@your-host}"
DEST="${DEST:-/srv/tableflow}"
PORT="${PORT:-8090}"
SSH_OPTS=(-F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no)

SEED=0
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "未知参数：$arg（可用：--seed）" >&2; exit 2 ;;
  esac
done

echo "== 1/4 rsync → $HOST:$DEST"
rsync -az --delete \
  --exclude '.git' --exclude '.agent-teams' \
  --exclude 'backend/.venv' --exclude 'backend/**/__pycache__' --exclude 'backend/.pytest_cache' \
  --exclude 'frontend/node_modules' --exclude 'data/*.db*' --exclude '/dist' \
  --exclude '.tmp-shots' --exclude 'deploy/.env' \
  -e "ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no" \
  ./ "$HOST:$DEST/"

echo "== 2/4 构建并启动"
ssh "${SSH_OPTS[@]}" "$HOST" "cd $DEST && docker compose -f deploy/docker-compose.yml up -d --build"

echo "== 2.5/4 等待服务就绪"
ssh "${SSH_OPTS[@]}" "$HOST" "for i in \$(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:$PORT/api/health && break; sleep 1; done; curl -sS -o /dev/null -w \"ready=%{http_code}\\n\" http://127.0.0.1:$PORT/api/health"

if [ "$SEED" = "1" ]; then
  echo "== 3/4 重建数据（--seed，seed.sh 内部会先备份旧库）"
  ssh "${SSH_OPTS[@]}" "$HOST" "docker exec tableflow sh /app/seed.sh"
else
  echo "== 3/4 跳过数据初始化（默认不动数据；需要重建请加 --seed）"
fi

echo "== 4/4 验证"
ssh "${SSH_OPTS[@]}" "$HOST" "curl -sS -o /dev/null -w 'api=%{http_code}\\n' http://127.0.0.1:$PORT/api/projects; curl -sS -o /dev/null -w 'ui=%{http_code}\\n' http://127.0.0.1:$PORT/; curl -sS http://127.0.0.1:$PORT/api/projects"
echo
echo "部署完成：http://${HOST#*@}:$PORT/"
