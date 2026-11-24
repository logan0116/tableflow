"""043：关系弹层的执行结果列。

契约侧只验证声明存在——渲染由前端类型检查与浏览器实测保证。
"""

from __future__ import annotations

from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[2] / "specs/019-test-contract/board@5.yaml"


def _ver_runs_block() -> str:
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if "key: ver.runs" in line)
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("- key: "))
    return "\n".join(lines[start:end])


def test_ver_runs_declares_result_field() -> None:
    """US1-AS1：ver.runs 必须声明 result_field，弹层才有结果列可渲染。"""
    block = _ver_runs_block()
    assert "result_field: run.result" in block, block
    assert "status_field: run.state" in block, "状态列不能被结果列替代"


def test_display_of_run_mentions_fourth_column() -> None:
    """US2-AS2：弹层说明要写清四列与「未配置不渲染」。"""
    text = CONTRACT.read_text(encoding="utf-8")
    assert "第四列 result_field" in text
    assert "未配置 result_field 时不渲染该列" in text
