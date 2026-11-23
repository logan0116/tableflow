"""040：规则清单的可枚举性、与实现的一致性、与文档的同步。

覆盖：
- 每条规则四个要素齐全、规则号唯一；
- 每个规则号都能在某个校验模块里找到（规则不是只写在文档里）；
- 文档 `specs/019-test-contract/rules.md` 与规则清单逐字一致（防止手改漂移）；
- 只读接口 `/api/rules` 支持前缀过滤。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "backend" / "src"
for path in (SRC, REPO_ROOT / "backend" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tableflow.app import app  # noqa: E402
from tableflow.rules import RULES, as_dicts, get  # noqa: E402

import render_rules  # noqa: E402

VALIDATOR_SOURCES = (
    "tableflow/board_rules.py",
    "tableflow/spec_lifecycle.py",
    "tableflow/stage_evidence.py",
    "tableflow/change_flow.py",
)


def test_every_rule_has_all_fields() -> None:
    for rule in RULES:
        assert rule.id and rule.title and rule.meaning
        assert rule.expr and rule.impl and rule.counterexample
        assert rule.enforced in ("engine", "skill")
        assert rule.since


def test_rule_ids_are_unique_and_lookup_works() -> None:
    ids = [rule.id for rule in RULES]
    assert len(ids) == len(set(ids))
    for rule_id in ids:
        assert get(rule_id).id == rule_id
    assert get("不存在") is None


def test_every_rule_id_appears_in_a_validator() -> None:
    source = "\n".join(
        (SRC / name).read_text(encoding="utf-8") for name in VALIDATOR_SOURCES
    )
    # 规则号可能直接写在消息里（`f"C3：..."`），也可能作为参数传入
    # （`_check_once("C1", ...)`），两种都算"在实现里出现过"。
    missing = [rule.id for rule in RULES if rule.id not in source]
    assert missing == [], f"规则号未出现在任何校验模块里：{missing}"


def test_rule_doc_is_in_sync() -> None:
    target = REPO_ROOT / "specs" / "019-test-contract" / "rules.md"
    assert target.exists(), "规则文档未生成，请运行 backend/scripts/render_rules.py"
    assert target.read_text(encoding="utf-8") == render_rules.render(), (
        "规则文档与规则清单不一致，请重新生成"
    )


def test_prefix_filter() -> None:
    c_rules = as_dicts("C")
    assert {item["id"] for item in c_rules} == {"C1", "C2", "C3", "C4"}
    assert as_dicts("L") and as_dicts("S") and as_dicts("D")


def test_api_lists_rules() -> None:
    with TestClient(app) as client:
        body = client.get("/api/rules").json()
        assert body["total"] == len(RULES)
        assert {item["id"] for item in body["rules"]} == {rule.id for rule in RULES}

        filtered = client.get("/api/rules", params={"prefix": "L"}).json()
        assert filtered["total"] == len(as_dicts("L"))
        assert all(item["id"].startswith("L") for item in filtered["rules"])


@pytest.mark.parametrize("rule_id", [rule.id for rule in RULES])
def test_rule_has_readable_counterexample(rule_id: str) -> None:
    rule = get(rule_id)
    assert len(rule.counterexample) >= 8
    assert len(rule.meaning) >= 8
