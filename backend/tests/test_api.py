"""接口契约测试：项目列表、表格端点、可见性、排序、空项目、错误码。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import build_generated, write_seed

SAMPLE = {
    "projects": [
        {
            "id": "p-empty",
            "name": "空项目",
            "fields": [
                {"id": "e1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
            ],
            "rows": [],
        },
        {
            "id": "p-main",
            "name": "主项目",
            "fields": [
                {"id": "f2", "name": "状态", "type": "enum",
                 "options": [{"value": "todo", "label": "待办"}], "order": 2, "visible": 1},
                {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                {"id": "f3", "name": "隐藏列", "type": "text", "options": None, "order": 3, "visible": 0},
            ],
            "rows": [
                {"id": "r2", "values": {"f1": "乙", "f2": "todo"}},
                {"id": "r1", "values": {"f1": "甲", "f2": "todo", "f3": "不该出现"}},
            ],
        },
    ]
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    write_seed(db, SAMPLE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as test_client:
        yield test_client


def test_projects_listed_sorted_by_id(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert [p["id"] for p in response.json()["projects"]] == ["p-empty", "p-main"]


def test_table_fields_order_and_visibility(client):
    payload = client.get("/api/projects/p-main/table").json()
    assert [field["id"] for field in payload["fields"]] == ["f1", "f2"]
    assert [row["id"] for row in payload["rows"]] == ["r1", "r2"]


def test_table_hidden_field_values_not_leaked(client):
    payload = client.get("/api/projects/p-main/table").json()
    assert "f3" not in payload["rows"][0]["values"]


def test_empty_project_returns_fields_with_no_rows(client):
    payload = client.get("/api/projects/p-empty/table").json()
    assert payload["fields"]
    assert payload["rows"] == []


def test_unknown_project_404(client):
    response = client.get("/api/projects/nope/table")
    assert response.status_code == 404
    assert response.json() == {"detail": "项目不存在"}


def test_no_store_on_business_endpoints(client):
    assert client.get("/api/projects").headers["Cache-Control"] == "no-store"
    assert client.get("/api/projects/p-main/table").headers["Cache-Control"] == "no-store"


def test_write_methods_rejected_on_project_routes(client):
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/projects").status_code == 405
        assert getattr(client, method)("/api/projects/p-main/table").status_code == 405


def test_scale_generated_data_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "scale.db"
    write_seed(db, build_generated(2, 5))
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as test_client:
        payload = test_client.get("/api/projects/gen-000/table").json()
    assert len(payload["rows"]) == 5
    assert [field["id"] for field in payload["fields"]] == [
        "gen-000-f1", "gen-000-f2", "gen-000-f3", "gen-000-f4",
    ]


def test_field_order_change_reflected(tmp_path, monkeypatch):
    db = tmp_path / "order.db"
    data = {
        "projects": [
            {
                "id": "p",
                "name": "项目",
                "fields": [
                    {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                    {"id": "f2", "name": "状态", "type": "text", "options": None, "order": 2, "visible": 1},
                ],
                "rows": [{"id": "r1", "values": {"f1": "甲", "f2": "乙"}}],
            }
        ]
    }
    write_seed(db, data)

    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute('UPDATE fields SET "order" = 5 WHERE id = ?', ("f1",))
    conn.commit()
    conn.close()

    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as test_client:
        payload = test_client.get("/api/projects/p/table").json()
    assert [field["id"] for field in payload["fields"]] == ["f2", "f1"]


def test_delete_field_removes_column_keeps_rows(tmp_path, monkeypatch):
    db = tmp_path / "del.db"
    data = {
        "projects": [
            {
                "id": "p",
                "name": "项目",
                "fields": [
                    {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                    {"id": "f2", "name": "备注", "type": "text", "options": None, "order": 2, "visible": 1},
                ],
                "rows": [
                    {"id": "r1", "values": {"f1": "甲", "f2": "乙"}},
                    {"id": "r2", "values": {"f1": "丙", "f2": "丁"}},
                ],
            }
        ]
    }
    write_seed(db, data)

    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM fields WHERE id = ?", ("f2",))
    conn.commit()
    conn.close()

    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as test_client:
        payload = test_client.get("/api/projects/p/table").json()

    assert [field["id"] for field in payload["fields"]] == ["f1"]
    assert [row["id"] for row in payload["rows"]] == ["r1", "r2"]
    assert all("f2" not in row["values"] for row in payload["rows"])
