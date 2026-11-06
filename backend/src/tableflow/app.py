"""FastAPI 应用：人侧只读接口 + Agent 写接口。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from . import db, repository, write_service
from .config import db_path
from .schemas import ProjectsOut, RowDetailOut, TableOut

app = FastAPI(title="TableFlow", version="0.2.0")


@app.middleware("http")
async def add_no_store(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.Error)
async def handle_db_error(request: Request, exc: sqlite3.Error):
    return JSONResponse(status_code=503, content={"detail": "数据存储不可用"})


def get_conn() -> Iterator[sqlite3.Connection]:
    """人侧读连接（只读）。"""
    try:
        conn = db.connect_readonly(db_path())
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise _unavailable() from exc
    try:
        yield conn
    finally:
        conn.close()


def get_write_conn() -> Iterator[sqlite3.Connection]:
    """Agent 写连接。"""
    try:
        conn = db.connect_write(db_path())
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise _unavailable() from exc
    try:
        yield conn
    finally:
        conn.close()


def _unavailable() -> Any:
    from fastapi import HTTPException

    return HTTPException(status_code=503, detail="数据存储不可用")


# ---------- 人侧只读 ----------

@app.get("/api/health")
def health(conn: sqlite3.Connection = Depends(get_conn)):
    conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/projects", response_model=ProjectsOut)
def get_projects(conn: sqlite3.Connection = Depends(get_conn)):
    return ProjectsOut(projects=repository.list_projects(conn))


@app.get("/api/projects/{project_id}/tables")
def get_tables(project_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    tables = repository.list_tables(conn, project_id)
    if tables is None:
        return JSONResponse(status_code=404, content={"detail": "项目不存在"})
    return {"tables": [table.model_dump() for table in tables]}


@app.get("/api/tables/{table_id}/table", response_model=TableOut)
def get_table(table_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    table = repository.get_table(conn, table_id)
    if table is None:
        return JSONResponse(status_code=404, content={"detail": "表格不存在"})
    return table


@app.get("/api/tables/{table_id}/rows/{row_id}", response_model=RowDetailOut)
def get_row(table_id: str, row_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    detail = repository.get_row_detail(conn, table_id, row_id)
    if detail is None:
        return JSONResponse(status_code=404, content={"detail": "行不存在"})
    return detail


# ---------- Agent 写侧 ----------

def _handle(conn: sqlite3.Connection, agent_id: str | None, action: str, target: str,
            body: dict[str, Any] | None, operation) -> Any:
    try:
        result = write_service.run_write(
            conn,
            agent_id=agent_id or "",
            action=action,
            target=target,
            payload=write_service._payload_text(body),
            operation=operation,
        )
    except write_service.WriteError as exc:
        status = 503 if exc.unknown else 400
        kind = "unknown" if exc.unknown else "failed"
        return JSONResponse(status_code=status, content={"result": kind, "error": str(exc)})
    return {"result": "success", "id": result}


@app.post("/api/agent/projects/{project_id}/tables")
def agent_create_table(
    project_id: str,
    body: dict[str, Any] = Body(default={}),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "table.create", project_id, body,
                   lambda: write_service.create_table(conn, project_id, body))


@app.patch("/api/agent/tables/{table_id}")
def agent_update_table(
    table_id: str,
    body: dict[str, Any] = Body(default={}),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "table.update", table_id, body,
                   lambda: write_service.update_table(conn, table_id, body))


@app.delete("/api/agent/tables/{table_id}")
def agent_delete_table(
    table_id: str,
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "table.delete", table_id, None,
                   lambda: write_service.delete_table(conn, table_id))


@app.post("/api/agent/tables/{table_id}/fields")
def agent_create_field(
    table_id: str,
    body: dict[str, Any] = Body(default={}),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "field.create", table_id, body,
                   lambda: write_service.create_field(conn, table_id, body))


@app.patch("/api/agent/fields/{field_id}")
def agent_update_field(
    field_id: str,
    body: dict[str, Any] = Body(default={}),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "field.update", field_id, body,
                   lambda: write_service.update_field(conn, field_id, body))


@app.delete("/api/agent/fields/{field_id}")
def agent_delete_field(
    field_id: str,
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "field.delete", field_id, None,
                   lambda: write_service.delete_field(conn, field_id))


@app.post("/api/agent/tables/{table_id}/rows")
def agent_create_row(
    table_id: str,
    body: dict[str, Any] = Body(default={}),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "row.create", table_id, body,
                   lambda: write_service.create_row(conn, table_id, body))


@app.patch("/api/agent/rows/{row_id}")
def agent_update_row(
    row_id: str,
    body: dict[str, Any] = Body(default={}),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "row.update", row_id, body,
                   lambda: write_service.update_row(conn, row_id, body))


@app.delete("/api/agent/rows/{row_id}")
def agent_delete_row(
    row_id: str,
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, x_agent_id, "row.delete", row_id, None,
                   lambda: write_service.delete_row(conn, row_id))
