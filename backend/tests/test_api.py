"""接口骨架测试：health、只读方法限制、缓存头。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import build_generated, write_seed


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    write_seed(db, build_generated(2, 3))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as test_client:
        yield test_client


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_no_store_header(client):
    response = client.get("/api/health")
    assert response.headers["Cache-Control"] == "no-store"


def test_write_methods_not_allowed(client):
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/health")
        assert response.status_code == 405, method


def test_health_503_when_db_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("TABLEFLOW_DB", str(tmp_path / "missing.db"))
    with TestClient(app) as test_client:
        response = test_client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "数据存储不可用"}
