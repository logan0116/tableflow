"""FastAPI 应用：人侧只读接口 + Agent 写接口。

人侧只有 GET；Agent 写接口用 `X-API-Key` 识别调用者（013），兼容期未带 key 时
回退 `X-Agent-Id`；可选 `X-Origin`（agent / human-request / seed）。
行写接口带 table_id：行 id 为业务编号，复合主键 (table_id, id)。
启动时做一次幂等补表补列（013：`api_keys` 与 `write_audit.key_id`）。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from . import auth, calculation, db, repository, write_service
from .config import db_path
from .schemas import ChangesOut, ProjectsOut, RowDetailOut, TableOut


def _migrate_schema() -> None:
    """启动时幂等补表补列（013：`api_keys`、`write_audit.key_id`）。

    库不存在时跳过，建库仍交给 seed/脚本；迁移失败只告警不阻断读侧。
    """
    path = db_path()
    if not path.exists():
        return
    conn = None
    try:
        conn = db.connect_write(path)
        db.init_schema(conn)
    except (sqlite3.Error, OSError) as exc:  # noqa: BLE001 - 迁移失败不能拖垮只读看板
        print(f"[tableflow] 启动迁移失败：{exc}", file=sys.stderr)
    finally:
        if conn is not None:
            conn.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _migrate_schema()
    yield


app = FastAPI(title="TableFlow", version="0.3.0", lifespan=lifespan)


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


def origin_header(
    x_origin: str | None = Header(default=None, alias="X-Origin"),
) -> str:
    """发起来源：缺省 agent；人经 Agent 写时传 human-request。"""
    return x_origin or "agent"


def caller_headers(
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> tuple[str | None, str | None]:
    """调用者凭据原样收集：key 优先，缺 key 回退 X-Agent-Id（兼容期）。"""
    return x_agent_id, x_api_key


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


@app.get("/api/tables/{table_id}/rows/{row_id}/changes", response_model=ChangesOut)
def get_row_changes(
    table_id: str,
    row_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    conn: sqlite3.Connection = Depends(get_conn),
):
    changes = repository.list_changes(conn, table_id, row_id, limit)
    if changes is None:
        return JSONResponse(status_code=404, content={"detail": "行不存在"})
    return ChangesOut(changes=changes)


# ---------- Agent 写侧 ----------

def _reject(
    conn: sqlite3.Connection,
    *,
    identity: tuple[str | None, str | None],
    origin: str,
    action: str,
    target: str,
    body: dict[str, Any] | None,
    status: int,
    error: str,
) -> JSONResponse:
    """鉴权失败：写一条 failed 审计，不落业务数据。"""
    agent_id, _ = identity
    write_service.record_auth_failure(
        conn,
        agent_id=agent_id or "-",
        origin=origin,
        action=action,
        target=target,
        payload=write_service._payload_text(body),
        error=error,
    )
    return JSONResponse(status_code=status, content={"result": "failed", "error": error})


def _handle(
    conn: sqlite3.Connection,
    identity: tuple[str | None, str | None],
    origin: str,
    action: str,
    target: str,
    body: dict[str, Any] | None,
    operation,
) -> Any:
    try:
        caller = auth.resolve_caller(conn, api_key=identity[1], agent_id=identity[0])
    except auth.AuthError as exc:
        return _reject(
            conn, identity=identity, origin=origin, action=action, target=target,
            body=body, status=401, error=str(exc),
        )
    except write_service.WriteError as exc:
        return _reject(
            conn, identity=identity, origin=origin, action=action, target=target,
            body=body, status=400, error=str(exc),
        )
    try:
        result = write_service.run_write(
            conn,
            agent_id=caller.actor,
            key_id=caller.key_id,
            origin=origin,
            action=action,
            target=target,
            payload=write_service._payload_text(body),
            operation=lambda: operation(caller),
        )
    except write_service.WriteError as exc:
        status = 503 if exc.unknown else 400
        kind = "unknown" if exc.unknown else "failed"
        return JSONResponse(status_code=status, content={"result": kind, "error": str(exc)})
    if isinstance(result, dict):
        return {"result": "success", **result}
    return {"result": "success", "id": result}


@app.post("/api/agent/projects")
def agent_create_project(
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "project.create", "-", body,
                   lambda caller: write_service.create_project(conn, body))


@app.delete("/api/agent/projects/{project_id}")
def agent_delete_project(
    project_id: str,
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "project.delete", project_id, None,
                   lambda caller: write_service.delete_project(conn, project_id))


@app.post("/api/agent/projects/{project_id}/tables")
def agent_create_table(
    project_id: str,
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "table.create", project_id, body,
                   lambda caller: write_service.create_table(conn, project_id, body))


@app.patch("/api/agent/tables/{table_id}")
def agent_update_table(
    table_id: str,
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "table.update", table_id, body,
                   lambda caller: write_service.update_table(conn, table_id, body))


@app.delete("/api/agent/tables/{table_id}")
def agent_delete_table(
    table_id: str,
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "table.delete", table_id, None,
                   lambda caller: write_service.delete_table(conn, table_id))


@app.post("/api/agent/tables/{table_id}/fields")
def agent_create_field(
    table_id: str,
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "field.create", table_id, body,
                   lambda caller: write_service.create_field(
                       conn, table_id, body, actor=caller.actor, origin=origin
                   ))


@app.patch("/api/agent/fields/{field_id}")
def agent_update_field(
    field_id: str,
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "field.update", field_id, body,
                   lambda caller: write_service.update_field(
                       conn, field_id, body, actor=caller.actor, origin=origin
                   ))


@app.delete("/api/agent/fields/{field_id}")
def agent_delete_field(
    field_id: str,
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "field.delete", field_id, None,
                   lambda caller: write_service.delete_field(
                       conn, field_id, actor=caller.actor, origin=origin
                   ))


@app.post("/api/agent/tables/{table_id}/recompute")
def agent_recompute_table(
    table_id: str,
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(
        conn,
        identity,
        origin,
        "table.recompute",
        table_id,
        None,
        lambda caller: calculation.recompute_table_and_dependents(
            conn, table_id, actor=caller.actor, origin=origin
        ),
    )


@app.post("/api/agent/tables/{table_id}/rows/{row_id}")
def agent_create_row(
    table_id: str,
    row_id: str,
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "row.create", f"{table_id}/{row_id}", body,
                   lambda caller: write_service.create_row(
                       conn, table_id, row_id, body, actor=caller.actor, origin=origin,
                       autofill_owner_by=(caller.actor if caller.auth_mode == "key" else None)
                   ))


@app.patch("/api/agent/tables/{table_id}/rows/{row_id}")
def agent_update_row(
    table_id: str,
    row_id: str,
    body: dict[str, Any] = Body(default={}),
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "row.update", f"{table_id}/{row_id}", body,
                   lambda caller: write_service.update_row(
                       conn, table_id, row_id, body, actor=caller.actor, origin=origin
                   ))


@app.delete("/api/agent/tables/{table_id}/rows/{row_id}")
def agent_delete_row(
    table_id: str,
    row_id: str,
    identity: tuple[str | None, str | None] = Depends(caller_headers),
    origin: str = Depends(origin_header),
    conn: sqlite3.Connection = Depends(get_write_conn),
):
    return _handle(conn, identity, origin, "row.delete", f"{table_id}/{row_id}", None,
                   lambda caller: write_service.delete_row(
                       conn, table_id, row_id, actor=caller.actor, origin=origin
                   ))


# 生产部署：前端构建产物挂在根路径，前后端同端口（开发时不设该变量，走 vite）
_static_dir = os.environ.get("TABLEFLOW_STATIC_DIR")
if _static_dir and Path(_static_dir).is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="ui")
