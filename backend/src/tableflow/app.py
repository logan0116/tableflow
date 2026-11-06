"""FastAPI 应用：只读接口（v0 无写路径）。"""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import db
from .config import db_path

app = FastAPI(title="TableFlow", version="0.1.0")


@app.middleware("http")
async def add_no_store(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.Error)
async def handle_db_error(request: Request, exc: sqlite3.Error):
    return JSONResponse(status_code=503, content={"detail": "数据存储不可用"})


def _connect() -> sqlite3.Connection:
    return db.connect_readonly(db_path())


@app.get("/api/health")
def health():
    try:
        conn = _connect()
    except (sqlite3.Error, OSError, RuntimeError):
        return JSONResponse(status_code=503, content={"detail": "数据存储不可用"})
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()
    return {"status": "ok"}
