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
SSH_OPTS=(-F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

SEED=0
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知参数：$arg（可用：--seed）" >&2; exit 2 ;;
  esac
done

# 远端命令里拼接的路径/端口先转义，避免 .env 里的值被当成 shell 语法执行。
QDEST=$(printf %q "$DEST")
QPORT=$(printf %q "$PORT")
# 镜像 tag 由 git tag 驱动（单一真源）；无 tag 时回退当前版本号。
VERSION="${TABLEFLOW_VERSION:-$(git describe --tags --abbrev=0 2>/dev/null || echo v0.10.5)}"
VERSION="${VERSION#v}"
QVERSION=$(printf %q "$VERSION")

health() {
  ssh "${SSH_OPTS[@]}" "$HOST" \
    "curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:${QPORT}/api/health" 2>/dev/null || echo "000"
}

echo "== 1/4 rsync → $HOST:$DEST"
rsync -az --delete \
  --exclude '.git' --exclude '.agent-teams' \
  --exclude 'backend/.venv' --exclude 'backend/**/__pycache__' --exclude 'backend/.pytest_cache' \
  --exclude 'frontend/node_modules' --exclude 'data/*.db*' --exclude 'data/backups' --exclude 'deploy/data' --exclude '/dist' \
  --exclude '.tmp-shots' --exclude 'deploy/.env' --exclude '.tmp-uv-cache' --exclude '.tmp-npm-cache' \
  -e "ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
  ./ "$HOST:$DEST/"

echo "== 2/4 构建并启动"
ssh "${SSH_OPTS[@]}" "$HOST" "cd ${QDEST} && TABLEFLOW_VERSION=${QVERSION} docker compose -f deploy/docker-compose.yml up -d --build"

echo "== 2.5/4 等待服务就绪"
code="000"
for _ in $(seq 1 30); do
  code=$(health)
  [ "$code" = "200" ] && break
  sleep 1
done
if [ "$code" = "200" ]; then
  echo "ready=200"
elif [ "$SEED" = "1" ]; then
  echo "ready=$code（enforced 下尚未签发 key；seed 后复验）"
else
  echo "健康检查失败（$code）：enforced 模式下需先对库签发 API key（backend/scripts/tf_keys.py issue）" >&2
  exit 1
fi

if [ "$SEED" = "1" ]; then
  echo "== 3/4 重建数据（--seed，seed.sh 内部会先备份旧库）"
  ssh "${SSH_OPTS[@]}" "$HOST" "docker exec tableflow sh /app/seed.sh"
  echo 'seed key 位于容器 /data/seed-key.txt；技能侧：export TF_API_KEY=$(docker exec tableflow cat /data/seed-key.txt)'
  code=$(health)
  if [ "$code" != "200" ]; then
    echo "seed 后健康检查仍失败（$code）" >&2
    exit 1
  fi
  echo "ready=200（seed 后复验）"
else
  echo "== 3/4 跳过数据初始化（默认不动数据；需要重建请加 --seed）"
fi

echo "== 4/4 验证"
ssh "${SSH_OPTS[@]}" "$HOST" "curl -sS -o /dev/null -w 'api=%{http_code}\n' http://127.0.0.1:${QPORT}/api/projects; curl -sS -o /dev/null -w 'ui=%{http_code}\n' http://127.0.0.1:${QPORT}/; curl -sS http://127.0.0.1:${QPORT}/api/projects"
echo
echo "部署完成：http://${HOST#*@}:$PORT/"
