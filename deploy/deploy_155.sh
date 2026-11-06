#!/usr/bin/env bash
# 把 tableflow 部署到 155（docker compose，单端口 8090，前后端同容器）。
# 用法：bash deploy/deploy_155.sh
set -euo pipefail

HOST="${HOST:-root@192.168.1.155}"
DEST="${DEST:-/srv/tableflow}"
SSH_OPTS=(-F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no)

echo "== 1/4 rsync → $HOST:$DEST"
rsync -az --delete \
  --exclude '.git' --exclude '.agent-teams' \
  --exclude 'backend/.venv' --exclude 'backend/**/__pycache__' --exclude 'backend/.pytest_cache' \
  --exclude 'frontend/node_modules' --exclude 'data/*.db*' --exclude '/dist' \
  -e "ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no" \
  ./ "$HOST:$DEST/"

echo "== 2/4 构建并启动"
ssh "${SSH_OPTS[@]}" "$HOST" "cd $DEST && docker compose -f deploy/docker-compose.yml up -d --build"

echo "== 2.5/4 等待服务就绪"
ssh "${SSH_OPTS[@]}" "$HOST" 'for i in $(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:8090/api/health && break; sleep 1; done; curl -sS -o /dev/null -w "ready=%{http_code}\n" http://127.0.0.1:8090/api/health'

echo "== 3/4 初始化数据"
ssh "${SSH_OPTS[@]}" "$HOST" "docker exec tableflow sh /app/seed.sh"

echo "== 4/4 验证"
ssh "${SSH_OPTS[@]}" "$HOST" "curl -sS -o /dev/null -w 'api=%{http_code}\n' http://127.0.0.1:8090/api/projects; curl -sS -o /dev/null -w 'ui=%{http_code}\n' http://127.0.0.1:8090/; curl -sS http://127.0.0.1:8090/api/projects"
echo
echo "部署完成：http://192.168.1.155:8090/"
