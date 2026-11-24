# 前端构建阶段：按锁文件安装，产物可复现
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 运行阶段：后端依赖按 uv.lock 安装，非 root 运行
FROM python:3.12-slim

RUN pip install --no-cache-dir uv \
    && apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

RUN useradd --create-home --uid 10001 tableflow
COPY backend/src ./backend/src
COPY --from=frontend /build/dist ./frontend/dist
COPY data ./data
COPY deploy/seed.sh ./seed.sh
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && chown -R tableflow:tableflow /app

ENV PYTHONPATH=/app/backend/src \
    TABLEFLOW_DB=/data/tableflow.db \
    TABLEFLOW_STATIC_DIR=/app/frontend/dist \
    TABLEFLOW_AUTH_MODE=enforced

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "tableflow.app:app", "--host", "0.0.0.0", "--port", "8090"]
