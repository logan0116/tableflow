FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "httpx>=0.27"

COPY backend/src /app/backend/src
COPY frontend/dist /app/frontend/dist
COPY data /app/data
COPY deploy/seed.sh /app/seed.sh

ENV PYTHONPATH=/app/backend/src \
    TABLEFLOW_DB=/data/tableflow.db \
    TABLEFLOW_STATIC_DIR=/app/frontend/dist

EXPOSE 8090

CMD ["uvicorn", "tableflow.app:app", "--host", "0.0.0.0", "--port", "8090"]
