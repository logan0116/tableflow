"""契约校验与原子写回归（V061-03）：YAML可解析、无重复键、--pre-write失败不写。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tableflow.contracts import (
    ContractError,
    check_contract,
    check_contract_pair,
    load_contract,
    load_contract_text,
    write_contract_atomic,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
BOARD1 = REPO_ROOT / "specs" / "008-board-contract" / "board@1.yaml"
BOARD2 = REPO_ROOT / "specs" / "011-bug-table" / "board@2.yaml"
CLI = BACKEND_DIR / "scripts" / "check_contracts.py"

VALID_TEXT = """\
meta:
  id: test@1
  revision: 1
conventions:
  semantic_key: k
  field_id: f
  row_id: r
  gate_mapping: g
  status_values_scope: s
tables:
  ver:
    id: t-ver
    name: 版本
    row_meaning: 一个版本
    row_id: ver.version
    fields:
      - key: ver.version
        name: 版本号
        type: text
      - key: ver.gate
        name: 发布条件
        type: computed
        gate: true
migrations:
  - id: gate-tag-existing
    status: 已执行
"""


# ---------- 现有两份契约 ----------

def test_default_contracts_pass():
    assert check_contract(BOARD1) == []
    assert check_contract(BOARD2) == []


def test_contract_pair_migration_consistent():
    assert check_contract_pair(BOARD1, BOARD2) == []


def test_contracts_parse_with_gate_and_row_id():
    board1 = load_contract(BOARD1)
    board2 = load_contract(BOARD2)
    assert board1["meta"]["id"] == "board@1"
    assert board2["meta"]["id"] == "board@2"
    assert board2["tables"]["bug"]["row_id"] == "bug.id"
    gates = [f["key"] for t in board2["tables"].values() for f in t["fields"] if f.get("gate")]
    assert gates == ["ver.spec_ready", "ver.change_ready", "ver.bug_ready", "ver.gate"]


# ---------- 重复键与非法YAML ----------

def test_duplicate_key_rejected():
    text = VALID_TEXT + "meta:\n  id: duplicated\n"
    with pytest.raises(ContractError, match="重复键"):
        load_contract_text(text)


def test_invalid_yaml_rejected():
    text = VALID_TEXT.replace("row_meaning: 一个版本\n", "row_meaning: '未闭合\n")
    with pytest.raises(ContractError, match="YAML解析失败|重复键"):
        load_contract_text(text)


def test_missing_structure_reported(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("meta:\n  id: x\ntables: {}\n", encoding="utf-8")
    issues = check_contract(path)
    assert any("tables为空" in issue for issue in issues)
    assert any("migrations为空" in issue for issue in issues)
    assert any("conventions" in issue for issue in issues)


# ---------- 原子写：失败不落盘 ----------

def test_atomic_write_rejects_invalid_and_keeps_original(tmp_path):
    target = tmp_path / "board.yaml"
    target.write_text(VALID_TEXT, encoding="utf-8")
    bad = VALID_TEXT + "meta:\n  id: duplicated\n"
    with pytest.raises(ContractError):
        write_contract_atomic(target, bad)
    assert target.read_text(encoding="utf-8") == VALID_TEXT
    assert [p.name for p in tmp_path.iterdir()] == ["board.yaml"]  # 临时文件已清理


def test_atomic_write_replaces_when_valid(tmp_path):
    target = tmp_path / "board.yaml"
    target.write_text(VALID_TEXT, encoding="utf-8")
    updated = VALID_TEXT.replace("revision: 1", "revision: 2")
    write_contract_atomic(target, updated)
    assert "revision: 2" in target.read_text(encoding="utf-8")


# ---------- CLI：团队提交前自查入口 ----------

def test_cli_checks_default_contracts():
    result = subprocess.run(
        [sys.executable, str(CLI)], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert "契约校验通过" in result.stdout


def test_cli_pre_write_rejects_invalid(tmp_path):
    target = tmp_path / "board.yaml"
    target.write_text(VALID_TEXT, encoding="utf-8")
    bad = VALID_TEXT + "meta:\n  id: duplicated\n"
    result = subprocess.run(
        [sys.executable, str(CLI), "--pre-write", str(target)],
        cwd=str(REPO_ROOT), input=bad, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 1
    assert "拒绝写入" in result.stderr
    assert target.read_text(encoding="utf-8") == VALID_TEXT
