"""人侧读接口契约测试：项目 / 表格列表 / 表格数据 / 单行明细。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

SAMPLE = {
    "projects": [
        {
            "id": "p",
            "name": "项目",
            "tables": [
                {
                    "id": "t-staff",
                    "name": "人员",
                    "order": 1,
                    "fields": [
                        {"id": "s1", "name": "姓名", "type": "text", "options": None, "order": 1, "visible": 1},
                    ],
                    "rows": [{"id": "sr1", "values": {"s1": "张工"}}],
                },
                {
                    "id": "t-task",
                    "name": "任务",
                    "order": 2,
                    "fields": [
                        {"id": "f2", "name": "负责人", "type": "relation",
                         "options": {"table_id": "t-staff"}, "order": 2, "visible": 1},
                        {"id": "f1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "f3", "name": "隐藏列", "type": "text", "options": None, "order": 3, "visible": 0},
                    ],
                    "rows": [
                        {"id": "r2", "values": {"f1": "乙", "f2": []}},
                        {"id": "r1", "values": {"f1": "甲", "f2": ["sr1"], "f3": "不该出现"}},
                    ],
                },
            ],
        },
        {
            "id": "p-empty",
            "name": "空项目",
            "tables": [
                {
                    "id": "t-empty",
                    "name": "空表",
                    "order": 1,
                    "fields": [{"id": "e1", "name": "任务", "type": "text", "options": None, "order": 1, "visible": 1}],
                    "rows": [],
                }
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


def test_projects_sorted(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert [p["id"] for p in response.json()["projects"]] == ["p", "p-empty"]


def test_tables_sorted_by_order(client):
    payload = client.get("/api/projects/p/tables").json()
    assert [t["id"] for t in payload["tables"]] == ["t-staff", "t-task"]


def test_unknown_project_tables_404(client):
    assert client.get("/api/projects/nope/tables").status_code == 404


def test_table_fields_order_and_visibility(client):
    payload = client.get("/api/tables/t-task/table").json()
    assert payload["table"]["id"] == "t-task"
    assert payload["project"]["id"] == "p"
    assert [field["id"] for field in payload["fields"]] == ["f1", "f2"]
    assert [row["id"] for row in payload["rows"]] == ["r1", "r2"]


def test_hidden_field_values_not_leaked(client):
    payload = client.get("/api/tables/t-task/table").json()
    assert "f3" not in payload["rows"][0]["values"]


def test_relation_value_passthrough(client):
    payload = client.get("/api/tables/t-task/table").json()
    assert payload["rows"][0]["values"]["f2"] == ["sr1"]


def test_empty_table_returns_fields_no_rows(client):
    payload = client.get("/api/tables/t-empty/table").json()
    assert payload["fields"]
    assert payload["rows"] == []


def test_row_detail(client):
    payload = client.get("/api/tables/t-staff/rows/sr1").json()
    assert payload["row"]["id"] == "sr1"
    assert payload["row"]["values"]["s1"] == "张工"


def test_row_detail_404_for_missing_row(client):
    assert client.get("/api/tables/t-staff/rows/nope").status_code == 404


def test_unknown_table_404(client):
    assert client.get("/api/tables/nope/table").status_code == 404


def test_no_store_headers(client):
    for path in ("/api/projects", "/api/projects/p/tables", "/api/tables/t-task/table"):
        assert client.get(path).headers["Cache-Control"] == "no-store"


def test_people_side_has_no_write_methods(client):
    for path in ("/api/projects", "/api/projects/p/tables", "/api/tables/t-task/table"):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(path).status_code == 405, (path, method)
