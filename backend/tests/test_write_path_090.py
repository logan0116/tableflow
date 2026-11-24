"""090 写路径回归：类型校验、三态 unknown、删除冻结、drop 留痕与重算、迁移脚本返回。

对应 v0.10.1 的 BUG-090-04/11/16/17/18。
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.db import connect_write
from tableflow.errors import WriteError
from tableflow.seed import write_seed
from tableflow.write_service import run_write

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY = {"X-Agent-Id": "agent-test"}
STAGE = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]

BASE = {
    "projects": [
        {
            "id": "p90w",
            "name": "090 写路径",
            "tables": [
                {
                    "id": "t-indep",
                    "name": "独立需求",
                    "order": 1,
                    "fields": [
                        {"id": "i-id", "name": "编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "i-clause", "name": "条款", "type": "text", "options": None, "order": 2, "visible": 1},
                        {"id": "i-acceptance", "name": "验收状态", "type": "enum", "options": [
                            {"value": "pending", "label": "待验收", "tone": "warning"},
                            {"value": "accepted", "label": "已验收", "tone": "success"},
                            {"value": "rejected", "label": "未通过", "tone": "danger"},
                            {"value": "dropped", "label": "已放弃", "tone": "danger"},
                        ], "order": 3, "visible": 1},
                        {"id": "i-drop-reason", "name": "放弃理由", "type": "text", "options": None, "order": 4, "visible": 1},
                        {"id": "i-dropped-at", "name": "放弃时间", "type": "datetime", "options": None, "order": 5, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-ver",
                    "name": "版本",
                    "order": 2,
                    "fields": [
                        {"id": "v-ver", "name": "版本号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "v-status", "name": "发布状态", "type": "enum", "options": [
                            {"value": "planned", "label": "计划", "tone": "neutral"},
                            {"value": "released", "label": "已发布", "tone": "success"},
                            {"value": "dropped", "label": "已终止", "tone": "danger"},
                        ], "order": 2, "visible": 1},
                        {"id": "v-indep", "name": "独立需求管理", "type": "relation", "options": {
                            "table_id": "t-indep", "display_field": "i-clause", "status_field": "i-acceptance",
                        }, "order": 3, "visible": 1},
                        {"id": "v-ratio", "name": "独立需求已完成/总数", "type": "computed", "options": {
                            "kind": "ratio", "source": "v-indep",
                            "where": {"field_id": "i-acceptance", "equals": "accepted"},
                        }, "order": 4, "visible": 1},
                        {"id": "v-note", "name": "说明", "type": "text", "options": None, "order": 12, "visible": 1},
                        {"id": "v-stage-plan", "name": "版本需求设计", "type": "enum", "options": STAGE, "order": 6, "visible": 1},
                        {"id": "v-stage-test-design", "name": "测试设计", "type": "enum", "options": STAGE, "order": 7, "visible": 1},
                        {"id": "v-stage-dev", "name": "开发", "type": "enum", "options": STAGE, "order": 8, "visible": 1},
                        {"id": "v-stage-dev-accept", "name": "开发验收", "type": "enum", "options": STAGE, "order": 9, "visible": 1},
                        {"id": "v-stage-test", "name": "测试", "type": "enum", "options": STAGE, "order": 10, "visible": 1},
                        {"id": "v-stage-test-accept", "name": "测试验收", "type": "enum", "options": STAGE, "order": 11, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-note",
                    "name": "类型校验",
                    "order": 3,
                    "fields": [
                        {"id": "n-text", "name": "文本", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "n-num", "name": "数字", "type": "number", "options": None, "order": 2, "visible": 1},
                        {"id": "n-when", "name": "时间", "type": "datetime", "options": None, "order": 3, "visible": 1},
                    ],
                    "rows": [],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "write-path-090.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    monkeypatch.delenv("TABLEFLOW_AUTH_MODE", raising=False)
    with TestClient(app) as client:
        yield client, db


def _post(client, table, row, values):
    return client.post(f"/api/agent/tables/{table}/rows/{row}", json={"values": values}, headers=LEGACY)


def _get(client, table, row):
    payload = client.get(f"/api/tables/{table}/rows/{row}")
    assert payload.status_code == 200, payload.text
    return payload.json()["row"]["values"]


def _changes(db, table_id, row_id=None):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        if row_id is None:
            return conn.execute(
                "SELECT field_name, old_value, new_value FROM business_changes WHERE table_id = ?",
                (table_id,),
            ).fetchall()
        return conn.execute(
            "SELECT field_name, old_value, new_value FROM business_changes"
            " WHERE table_id = ? AND row_id = ? ORDER BY id",
            (table_id, row_id),
        ).fetchall()
    finally:
        conn.close()


# ---------- BUG-090-17 值类型 ----------

def test_text_field_rejects_non_string(env):
    client, _ = env
    response = _post(client, "t-note", "n1", {"n-text": ["not-text"]})
    assert response.status_code == 400
    assert "文本" in response.json()["error"]


def test_number_field_rejects_string(env):
    client, _ = env
    response = _post(client, "t-note", "n2", {"n-num": "not-a-number"})
    assert response.status_code == 400
    assert "数字" in response.json()["error"]


def test_number_field_rejects_bool(env):
    client, _ = env
    response = _post(client, "t-note", "n3", {"n-num": True})
    assert response.status_code == 400


def test_datetime_field_rejects_object(env):
    client, _ = env
    response = _post(client, "t-note", "n4", {"n-when": {"not": "a-date"}})
    assert response.status_code == 400
    assert "时间" in response.json()["error"]


def test_datetime_field_rejects_non_iso(env):
    client, _ = env
    response = _post(client, "t-note", "n5", {"n-when": "not-a-date"})
    assert response.status_code == 400


def test_valid_scalars_accepted(env):
    client, _ = env
    response = _post(
        client, "t-note", "n6",
        {"n-text": "ok", "n-num": 3, "n-when": "2026-11-24T10:00:00+08:00"},
    )
    assert response.status_code == 200
    assert response.json()["result"] == "success"


# ---------- BUG-090-18 三态 unknown ----------

class _FlakyCommit:
    """除 commit 外全部代理到真连接：模拟提交阶段磁盘/IO 失败。"""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def commit(self):
        raise sqlite3.OperationalError("disk I/O error")


def test_commit_failure_reports_unknown(tmp_path):
    db = tmp_path / "flaky.db"
    write_seed(db, BASE)
    conn = connect_write(db)
    try:
        with pytest.raises(WriteError) as excinfo:
            run_write(
                _FlakyCommit(conn),
                agent_id="agent-test",
                action="row.create",
                target="t-note/n9",
                payload=None,
                operation=lambda: "t-note/n9",
            )
        assert excinfo.value.unknown is True
        assert "未知" in str(excinfo.value)
    finally:
        conn.close()


# ---------- BUG-090-16 删除冻结与审计保留 ----------

def test_delete_released_version_rejected(env):
    client, _ = env
    assert _post(client, "t-ver", "v1", {"v-ver": "v1", "v-status": "released"}).status_code == 200
    response = client.delete("/api/agent/tables/t-ver/rows/v1", headers=LEGACY)
    assert response.status_code == 400
    assert "已发布" in response.json()["error"]
    assert _get(client, "t-ver", "v1")["v-status"] == "released"


def test_delete_planned_version_allowed(env):
    client, _ = env
    assert _post(client, "t-ver", "v2", {"v-ver": "v2", "v-status": "planned"}).status_code == 200
    response = client.delete("/api/agent/tables/t-ver/rows/v2", headers=LEGACY)
    assert response.status_code == 200


def test_delete_table_keeps_business_changes(env):
    client, db = env
    assert _post(client, "t-note", "n7", {"n-text": "keep-me"}).status_code == 200
    before = _changes(db, "t-note", "n7")
    assert any(row["field_name"] == "文本" for row in before)

    response = client.delete("/api/agent/tables/t-note", headers=LEGACY)
    assert response.status_code == 200
    after = _changes(db, "t-note", "n7")
    assert any(
        row["field_name"] == "文本" and "keep-me" in (row["new_value"] or "")
        for row in after
    )


# ---------- BUG-090-04 drop 留痕与重算 ----------

def test_drop_records_changes_and_recomputes(env):
    client, db = env
    assert _post(client, "t-indep", "034-AR", {
        "i-id": "034-AR", "i-clause": "放弃测试", "i-acceptance": "pending",
    }).status_code == 200
    assert _post(client, "t-ver", "v3", {
        "v-ver": "v3", "v-status": "planned", "v-indep": ["034-AR"],
    }).status_code == 200
    assert _get(client, "t-ver", "v3")["v-ratio"] == "0/1"

    response = client.post(
        "/api/agent/tables/t-indep/rows/034-AR/drop",
        json={"reason": "范围收缩", "at": "2026-11-24T20:00:00+08:00"},
        headers=LEGACY,
    )
    assert response.status_code == 200, response.text

    assert _get(client, "t-indep", "034-AR")["i-acceptance"] == "dropped"
    assert _get(client, "t-ver", "v3")["v-indep"] == []
    # 重算：版本的需求比从 0/1 变成 0/0
    assert _get(client, "t-ver", "v3")["v-ratio"] == "0/0"
    fields = {row["field_name"] for row in _changes(db, "t-ver", "v3")}
    assert "独立需求管理" in fields
    assert {"验收状态", "放弃理由", "放弃时间"} <= {row["field_name"] for row in _changes(db, "t-indep", "034-AR")}


# ---------- BUG-090-11 迁移脚本返回列表 ----------

def test_extend_acceptance_returns_list():
    sys.path.insert(0, str(REPO_ROOT / "backend" / "scripts"))
    try:
        import migrate_board5
    finally:
        sys.path.pop(0)
    field = {
        "id": "x-i-acceptance",
        "name": "验收状态",
        "type": "enum",
        "options": [{"value": "pending", "label": "待验收"}],
    }
    assert migrate_board5.extend_acceptance(field, apply=False, planned=[]) == []
    field_with_dropped = {
        **field,
        "options": [{"value": "pending"}, {"value": "dropped"}],
    }
    assert migrate_board5.extend_acceptance(field_with_dropped, apply=True, planned=[]) == []
