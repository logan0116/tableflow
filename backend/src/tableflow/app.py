"""FastAPI 应用：只读接口（v0 无写路径）。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import db, repository
from .config import db_path
from .schemas import ProjectsOut, TableOut

app = FastAPI(title="TableFlow", version="0.1.0")


@app.middleware("http")
async def add_no_store(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.Error)
async def handle_db_error(request: Request, exc: sqlite3.Error):
    return JSONResponse(status_code=503, content={"detail": "数据存储不可用"})


def get_conn() -> Iterator[sqlite3.Connection]:
    try:
        conn = db.connect_readonly(db_path())
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="数据存储不可用") from exc
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/health")
def health(conn: sqlite3.Connection = Depends(get_conn)):
    conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/projects", response_model=ProjectsOut)
def get_projects(conn: sqlite3.Connection = Depends(get_conn)):
    return ProjectsOut(projects=repository.list_projects(conn))


@app.get("/api/projects/{project_id}/table", response_model=TableOut)
def get_table(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    table = repository.get_table(conn, project_id)
    if table is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return table
