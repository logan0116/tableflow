"""020：新表（`run` 执行记录）写入协议。

对应 `specs/020-protocol-test/spec.md` 的四条交付：
1. 状态/结果一致性：`state=todo` 时 `result` 必须为空、`state=done` 时必须非空，
   不一致 400 且零写入（新建与合并更新两条路径）；
2. 两步写入（建 run 行 → 追加到 ver.runs）第二步失败时，第一次写入必须可被回读发现；
3. 同版本同用例重复纳入：400（服务端行为写死），不产生第二条执行记录；
4. 执行记录行 id 形状（`<版本号>--<用例号>`）与执行清单去重/不跨版本。

信封沿用 protocol@2：400 + `{"result":"failed","error":"..."}`。
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tableflow.app import app
from tableflow.seed import write_seed

HEADERS = {"X-Agent-Id": "agent-test"}

RUN_ID = "v0.7.0--008-US1-AS1"
CASE_ID = "008-US1-AS1"

TODO_VALUES = {
    "tf-r-case_no": CASE_ID,
    "tf-r-case": [CASE_ID],
    "tf-r-state": "todo",
    "tf-r-result": None,
}

BASE = {
    "projects": [
        {
            "id": "p",
            "name": "项目",
            "tables": [
                {
                    "id": "t-ver",
                    "name": "版本管理",
                    "order": 1,
                    "fields": [
                        {"id": "tf-v-version", "name": "版本号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {
                            "id": "tf-v-runs",
                            "name": "测试用例",
                            "type": "relation",
                            "options": {
                                "table_id": "t-run",
                                "constraints": {"relation_must_exist": True},
                            },
                            "order": 2,
                            "visible": 1,
                        },
                    ],
                    "rows": [
                        {"id": "v0.7.0", "values": {"tf-v-version": "v0.7.0", "tf-v-runs": []}},
                        {"id": "v0.8.0", "values": {"tf-v-version": "v0.8.0", "tf-v-runs": []}},
                        {"id": "4.0.0_001", "values": {"tf-v-version": "4.0.0_001", "tf-v-runs": []}},
                    ],
                },
                {
                    "id": "t-case",
                    "name": "测试用例",
                    "order": 2,
                    "fields": [
                        {"id": "tf-c-id", "name": "用例号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "tf-c-name", "name": "用例名", "type": "text", "options": None, "order": 2, "visible": 1},
                    ],
                    "rows": [
                        {"id": CASE_ID, "values": {"tf-c-id": CASE_ID, "tf-c-name": "纳入后读回版本行"}},
                    ],
                },
                {
                    "id": "t-run",
                    "name": "用例执行情况",
                    "order": 3,
                    "fields": [
                        {"id": "tf-r-id", "name": "执行编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "tf-r-case_no", "name": "用例号", "type": "text", "options": None, "order": 2, "visible": 1},
                        {
                            "id": "tf-r-case",
                            "name": "用例",
                            "type": "relation",
                            "options": {"table_id": "t-case"},
                            "order": 3,
                            "visible": 1,
                        },
                        {
                            "id": "tf-r-state",
                            "name": "执行状态",
                            "type": "enum",
                            "options": [
                                {"value": "todo", "label": "未执行", "tone": "neutral"},
                                {"value": "done", "label": "已执行", "tone": "success"},
                            ],
                            "order": 4,
                            "visible": 1,
                        },
                        {
                            "id": "tf-r-result",
                            "name": "执行结果",
                            "type": "enum",
                            "options": [
                                {"value": "pass", "label": "通过", "tone": "success"},
                                {"value": "fail", "label": "失败", "tone": "danger"},
                                {"value": "blocked", "label": "阻塞", "tone": "warning"},
                                {"value": "skip", "label": "跳过", "tone": "info"},
                            ],
                            "order": 5,
                            "visible": 1,
                        },
                        {"id": "tf-r-note", "name": "备注", "type": "text", "options": None, "order": 6, "visible": 1},
                    ],
                    "rows": [],
                },
                {
                    "id": "t-run-odd",
                    "name": "用例执行情况（非惯例字段 id）",
                    "order": 5,
                    "fields": [
                        {"id": "r2-id", "name": "执行编号", "type": "text", "options": None, "order": 1, "visible": 1},
                        {"id": "r2-caseid", "name": "用例号", "type": "text", "options": None, "order": 2, "visible": 1},
                        {
                            "id": "r2-progress",
                            "name": "执行状态",
                            "type": "enum",
                            "options": [
                                {"value": "todo", "label": "未执行", "tone": "neutral"},
                                {"value": "done", "label": "已执行", "tone": "success"},
                            ],
                            "order": 3,
                            "visible": 1,
                        },
                        {
                            "id": "r2-outcome",
                            "name": "执行结果",
                            "type": "enum",
                            "options": [
                                {"value": "pass", "label": "通过", "tone": "success"},
                                {"value": "fail", "label": "失败", "tone": "danger"},
                            ],
                            "order": 4,
                            "visible": 1,
                        },
                    ],
                    "rows": [],
                },
                {
                    "id": "t-other",
                    "name": "其它表",
                    "order": 4,
                    "fields": [
                        {
                            "id": "x-state",
                            "name": "外部状态",
                            "type": "enum",
                            "options": [
                                {"value": "open", "label": "打开", "tone": "warning"},
                                {"value": "closed", "label": "关闭", "tone": "success"},
                            ],
                            "order": 1,
                            "visible": 1,
                        },
                        {
                            "id": "x-result",
                            "name": "外部结论",
                            "type": "enum",
                            "options": [
                                {"value": "pass", "label": "通过", "tone": "success"},
                                {"value": "fail", "label": "失败", "tone": "danger"},
                            ],
                            "order": 2,
                            "visible": 1,
                        },
                    ],
                    "rows": [],
                },
            ],
        }
    ]
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "run_protocol.db"
    write_seed(db, BASE)
    monkeypatch.setenv("TABLEFLOW_DB", str(db))
    with TestClient(app) as client:
        yield client, db


def _rows(db, table: str) -> dict[str, dict]:
    conn = sqlite3.connect(db)
    try:
        return {
            row[0]: json.loads(row[1])
            for row in conn.execute(
                "SELECT id, data FROM row_records WHERE table_id = ?", (table,)
            ).fetchall()
        }
    finally:
        conn.close()


def _changes(db, table: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT count(*) FROM business_changes WHERE table_id = ?", (table,)
        ).fetchone()[0]
    finally:
        conn.close()


def _last_audit(db) -> tuple[str, str | None]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT result, error FROM write_audit ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()


def _create_run(client, row_id: str = RUN_ID, **overrides) -> object:
    values = {**TODO_VALUES, **overrides}
    return client.post(f"/api/agent/tables/t-run/rows/{row_id}", json={"values": values}, headers=HEADERS)


def _patch_run(client, row_id: str = RUN_ID, values: dict | None = None) -> object:
    return client.patch(f"/api/agent/tables/t-run/rows/{row_id}", json={"values": values or {}}, headers=HEADERS)


def _patch_runs(client, version: str, runs: list[str]) -> object:
    return client.patch(
        f"/api/agent/tables/t-ver/rows/{version}",
        json={"values": {"tf-v-runs": runs}},
        headers=HEADERS,
    )


# ---------- 一、状态与结果一致性（新建） ----------

def test_create_todo_with_result_rejected_zero_write(env):
    """US1-AS2：新建执行记录 state=todo 却带 result → 400，run 表零写入、版本清单不变。"""
    client, db = env
    resp = _create_run(client, **{"tf-r-result": "pass"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["result"] == "failed"
    assert "不一致" in body["error"]
    assert _rows(db, "t-run") == {}
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == []
    assert _changes(db, "t-run") == 0
    # 失败仍留审计，但无业务数据（P-043 口径）。
    audit_result, error = _last_audit(db)
    assert audit_result == "failed"
    assert "不一致" in error


def test_create_done_without_result_rejected_zero_write(env):
    """US1-AS3：新建 state=done 但 result 为空 → 400，零写入。"""
    client, db = env
    resp = _create_run(client, **{"tf-r-state": "done"})

    assert resp.status_code == 400
    assert "不一致" in resp.json()["error"]
    assert _rows(db, "t-run") == {}


def test_create_todo_without_result_ok(env):
    """US1-AS1：新建 state=todo、result 为空 → 200，落库。"""
    client, db = env
    resp = _create_run(client)

    assert resp.status_code == 200
    assert resp.json() == {"result": "success", "id": RUN_ID}
    values = _rows(db, "t-run")[RUN_ID]
    assert values["tf-r-state"] == "todo"
    assert values.get("tf-r-result") in (None, "")


def test_create_result_without_state_rejected(env):
    """US1-AS4：有结论却未置执行状态（state 缺省为空）→ 400，零写入。"""
    client, db = env
    values = {"tf-r-case_no": CASE_ID, "tf-r-case": [CASE_ID], "tf-r-result": "pass"}
    resp = client.post(f"/api/agent/tables/t-run/rows/{RUN_ID}", json={"values": values}, headers=HEADERS)

    assert resp.status_code == 400
    assert "不一致" in resp.json()["error"]
    assert _rows(db, "t-run") == {}


# ---------- 一、状态与结果一致性（合并更新） ----------

def test_patch_result_without_state_rejected(env):
    """019 US3-AS4：已存在的 todo 记录直接写 result=pass 而不改 state → 400，两字段读回不变。"""
    client, db = env
    assert _create_run(client).status_code == 200
    changes_before = _changes(db, "t-run")

    resp = _patch_run(client, values={"tf-r-result": "pass"})

    assert resp.status_code == 400
    assert "不一致" in resp.json()["error"]
    values = _rows(db, "t-run")[RUN_ID]
    assert values["tf-r-state"] == "todo"
    assert values.get("tf-r-result") in (None, "")
    assert _changes(db, "t-run") == changes_before  # 失败不新增业务变更


def test_patch_state_done_without_result_rejected(env):
    """US1-AS5：只把 state 改成 done（result 仍空）→ 400，整行不变。"""
    client, db = env
    assert _create_run(client).status_code == 200
    before = _rows(db, "t-run")[RUN_ID]

    resp = _patch_run(client, values={"tf-r-state": "done"})

    assert resp.status_code == 400
    assert "不一致" in resp.json()["error"]
    assert _rows(db, "t-run")[RUN_ID] == before


def test_patch_state_done_with_result_ok(env):
    """US1-AS6：state=done 与 result 同时提交 → 200，回读一致。"""
    client, db = env
    assert _create_run(client).status_code == 200

    resp = _patch_run(client, values={"tf-r-state": "done", "tf-r-result": "pass"})

    assert resp.status_code == 200
    values = _rows(db, "t-run")[RUN_ID]
    assert values["tf-r-state"] == "done"
    assert values["tf-r-result"] == "pass"


def test_patch_fix_inconsistent_legacy_row_in_one_request(env):
    """边界：存量不一致行（直接落库的脏数据）必须一次 PATCH 内同时修正，否则仍 400。"""
    client, db = env
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO row_records (id, table_id, data) VALUES (?, 't-run', ?)",
            (RUN_ID, json.dumps({**TODO_VALUES, "tf-r-result": "pass"})),
        )
        conn.commit()
    finally:
        conn.close()

    assert _patch_run(client, values={"tf-r-note": "顺手改备注"}).status_code == 400
    resp = _patch_run(client, values={"tf-r-state": "done", "tf-r-result": "pass"})
    assert resp.status_code == 200
    assert _rows(db, "t-run")[RUN_ID]["tf-r-state"] == "done"


# ---------- 二、两步写入的失败语义 ----------

def test_two_step_write_second_failure_keeps_first_write_readable(env):
    """US2：第一步建 run 行成功、第二步追加 ver.runs 失败 → 第一次写入必须能回读发现。"""
    client, db = env
    first = _create_run(client)
    assert first.status_code == 200

    # 第二步写坏引用（执行记录不存在）→ 400，版本行零写入。
    second = _patch_runs(client, "v0.7.0", ["v0.7.0--999-US1-AS9"])
    assert second.status_code == 400
    assert second.json()["result"] == "failed"
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == []

    # 第一次写入可被回读发现：run 行仍在且状态可读（悬空行不是"没写进去"）。
    detail = client.get(f"/api/tables/t-run/rows/{RUN_ID}")
    assert detail.status_code == 200
    assert detail.json()["row"]["values"]["tf-r-state"] == "todo"
    assert _rows(db, "t-run")[RUN_ID]["tf-r-state"] == "todo"

    # 修好第二步后可继续，最终版本行能看到这条执行记录。
    third = _patch_runs(client, "v0.7.0", [RUN_ID])
    assert third.status_code == 200
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == [RUN_ID]


# ---------- 三、同版本同用例重复纳入 ----------

def test_duplicate_inclusion_second_post_is_400_and_single_row(env):
    """US3-AS1：同版本同用例重复纳入 → 400，只有一条执行记录，版本清单不变。"""
    client, db = env
    assert _create_run(client).status_code == 200

    resp = _create_run(client)

    assert resp.status_code == 400
    assert "已纳入本版本" in resp.json()["error"]
    assert list(_rows(db, "t-run")) == [RUN_ID]
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == []


def test_duplicate_after_inclusion_is_400(env):
    """US3-AS2：已纳入后重放第一步 → 仍 400（幂等靠回读，不靠重复建行）。"""
    client, db = env
    assert _create_run(client).status_code == 200
    assert _patch_runs(client, "v0.7.0", [RUN_ID]).status_code == 200

    resp = _create_run(client)

    assert resp.status_code == 400
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == [RUN_ID]
    assert list(_rows(db, "t-run")) == [RUN_ID]


def test_run_list_rejects_duplicate_ids(env):
    """US3-AS3：把同一条执行记录在同一版本里登记两次 → 400，版本行零写入。"""
    client, db = env
    assert _create_run(client).status_code == 200

    resp = _patch_runs(client, "v0.7.0", [RUN_ID, RUN_ID])

    assert resp.status_code == 400
    assert "重复纳入" in resp.json()["error"]
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == []


def test_run_list_rejects_other_version_record(env):
    """US3-AS4：把别的版本的执行记录挂进本版清单 → 400，版本行零写入。"""
    client, db = env
    other = "v0.8.0--008-US1-AS1"
    assert _create_run(client, other).status_code == 200

    resp = _patch_runs(client, "v0.7.0", [other])

    assert resp.status_code == 400
    assert "只能收录本版本" in resp.json()["error"]
    assert _rows(db, "t-ver")["v0.7.0"]["tf-v-runs"] == []


# ---------- 四、行 id 形状 ----------

def test_run_id_must_encode_version_and_case(env):
    """US4-AS1：行 id 不是 `<版本号>--<用例号>` → 400，零写入。"""
    client, db = env
    resp = _create_run(client, "RUN-01")

    assert resp.status_code == 400
    assert "执行记录行 id" in resp.json()["error"]
    assert _rows(db, "t-run") == {}


def test_case_no_must_match_run_id_suffix(env):
    """US4-AS2：run.case_no 与行 id 的用例号不一致 → 400（同一事实两个值一律拒绝）。"""
    client, db = env
    resp = _create_run(client, **{"tf-r-case_no": "008-US1-AS2"})

    assert resp.status_code == 400
    assert "用例号一致" in resp.json()["error"]
    assert _rows(db, "t-run") == {}


def test_non_run_table_with_state_result_names_is_untouched(env):
    """US4-AS3：字段形状不匹配执行记录表的表不套用该协议（不误伤既有表）。"""
    client, db = env
    resp = client.post(
        "/api/agent/tables/t-other/rows/X-01",
        json={"values": {"x-state": "open", "x-result": "pass"}},
        headers=HEADERS,
    )

    assert resp.status_code == 200
    assert _rows(db, "t-other")["X-01"]["x-state"] == "open"


def test_run_table_detected_by_value_domain_not_field_id(env):
    """US4-AS4：字段 id 起成 `r2-progress`/`r2-outcome` 也按值域识别，一致性照样校验。"""
    client, db = env
    resp = client.post(
        f"/api/agent/tables/t-run-odd/rows/{RUN_ID}",
        json={"values": {"r2-caseid": CASE_ID, "r2-progress": "todo", "r2-outcome": "pass"}},
        headers=HEADERS,
    )

    assert resp.status_code == 400
    assert "不一致" in resp.json()["error"]
    assert _rows(db, "t-run-odd") == {}


def test_run_table_detected_by_value_domain_still_enforces_row_id(env):
    """US4-AS5：非惯例字段 id 的执行记录表同样要求行 id 形状。"""
    client, db = env
    resp = client.post(
        "/api/agent/tables/t-run-odd/rows/RUN-1",
        json={"values": {"r2-caseid": CASE_ID, "r2-progress": "todo"}},
        headers=HEADERS,
    )

    assert resp.status_code == 400
    assert "执行记录行 id" in resp.json()["error"]
    assert _rows(db, "t-run-odd") == {}


def test_case_no_fallback_by_field_name(env):
    """US4-AS6：字段 id 不是 `-case_no` 时按名称「用例号」兜底，仍校验一致性。"""
    client, db = env
    resp = client.post(
        f"/api/agent/tables/t-run-odd/rows/{RUN_ID}",
        json={"values": {"r2-caseid": "008-US1-AS2", "r2-progress": "todo"}},
        headers=HEADERS,
    )

    assert resp.status_code == 400
    assert "用例号一致" in resp.json()["error"]
    assert _rows(db, "t-run-odd") == {}


def test_run_id_uses_version_row_id_not_hardcoded_semver(env):
    """版本行 id 不是 v<主>.<次>.<修>（如 4.0.0_001）时，执行记录 id 仍按 <版本号>--<用例号>。"""
    client, db = env
    run_id = "4.0.0_001--008-US1-AS1"
    resp = _create_run(client, run_id)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"result": "success", "id": run_id}
    assert run_id in _rows(db, "t-run")


def test_run_list_foreign_check_applies_to_non_semver_version(env):
    """执行清单的「只能收录本版本」不因版本号不是 semver 而失效。"""
    client, db = env
    resp = _patch_runs(client, "4.0.0_001", ["v0.7.0--008-US1-AS1"])

    assert resp.status_code == 400, resp.text
    assert "本版本" in resp.json()["error"]
