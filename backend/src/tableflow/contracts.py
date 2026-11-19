"""契约文件校验与原子写（V061-03修复）。

契约`board@1`/`board@2`被脚本与skill直接读取：编辑窗口里一旦出现非法YAML或重复键，
读取方（如`create_bug_table.py`）会连带失败。本模块提供三件事：
- `load_contract`：解析 + **重复键检测**（PyYAML默认静默覆盖，这里改为报错）；
- `check_contract`：结构断言（meta/tables/conventions/migrations/row_id/闸门）；
- `write_contract_atomic`：先校验再`临时文件+os.replace`，杜绝半截文件落盘。

用法见`backend/scripts/check_contracts.py`与`backend/tests/test_contracts.py`。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

REQUIRED_CONVENTIONS = ("semantic_key", "field_id", "row_id", "gate_mapping", "status_values_scope")
REQUIRED_MIGRATIONS = ("gate-tag-existing",)


class ContractError(ValueError):
    """契约内容不合法（解析失败、重复键、结构缺失）。"""


class _UniqueKeyLoader(yaml.SafeLoader):
    """映射键重复即报错的SafeLoader。"""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ContractError(f"重复键：{key!r}（第{key_node.start_mark.line + 1}行）")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_contract(path: str | Path) -> dict[str, Any]:
    """解析契约；重复键与语法错误都转成`ContractError`。"""
    text = Path(path).read_text(encoding="utf-8")
    return load_contract_text(text, source=str(path))


def load_contract_text(text: str, *, source: str = "<text>") -> dict[str, Any]:
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except ContractError as exc:
        raise ContractError(f"{source}：{exc}") from exc
    except yaml.YAMLError as exc:
        raise ContractError(f"{source}：YAML解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{source}：顶层必须是映射")
    return data


def check_contract(path: str | Path) -> list[str]:
    """返回问题清单；空列表表示通过。"""
    path = Path(path)
    try:
        data = load_contract(path)
    except (ContractError, OSError) as exc:
        return [str(exc)]
    issues: list[str] = []
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    if not meta.get("id"):
        issues.append("meta.id缺失")
    tables = data.get("tables") if isinstance(data.get("tables"), dict) else {}
    if not tables:
        issues.append("tables为空")
    keys: list[str] = []
    gate_count = 0
    for table_name, table in tables.items():
        if not isinstance(table, dict):
            issues.append(f"tables.{table_name}不是映射")
            continue
        if not table.get("row_id"):
            issues.append(f"tables.{table_name}.row_id缺失")
        fields = table.get("fields")
        if not isinstance(fields, list) or not fields:
            issues.append(f"tables.{table_name}.fields为空")
            continue
        for field in fields:
            if not isinstance(field, dict):
                issues.append(f"tables.{table_name}含非映射字段")
                continue
            for key in ("key", "name", "type"):
                if not field.get(key):
                    issues.append(f"tables.{table_name}.{field.get('key', '?')}缺{key}")
            if field.get("key"):
                keys.append(str(field["key"]))
            if field.get("gate"):
                gate_count += 1
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        issues.append(f"语义键重复：{duplicates}")
    if gate_count == 0:
        issues.append("没有gate:true字段")
    conventions = data.get("conventions") if isinstance(data.get("conventions"), dict) else {}
    for key in REQUIRED_CONVENTIONS:
        if key not in conventions:
            issues.append(f"conventions.{key}缺失")
    migrations = data.get("migrations")
    if not isinstance(migrations, list) or not migrations:
        issues.append("migrations为空")
    else:
        ids = {entry.get("id") for entry in migrations if isinstance(entry, dict)}
        for entry in migrations:
            if not isinstance(entry, dict):
                issues.append("migrations含非映射项")
                continue
            if not entry.get("id") or not entry.get("status"):
                issues.append(f"migrations.{entry.get('id', '?')}缺id或status")
        for required in REQUIRED_MIGRATIONS:
            if required not in ids:
                issues.append(f"migrations缺{required}")
    return issues


def check_contract_pair(path_a: str | Path, path_b: str | Path) -> list[str]:
    """两份契约各自合法，且共有迁移条目逐字一致。"""
    issues = [f"{path_a}：{issue}" for issue in check_contract(path_a)]
    issues += [f"{path_b}：{issue}" for issue in check_contract(path_b)]
    if issues:
        return issues
    data_a, data_b = load_contract(path_a), load_contract(path_b)
    entries_a = {entry["id"]: entry for entry in data_a.get("migrations") or [] if isinstance(entry, dict)}
    entries_b = {entry["id"]: entry for entry in data_b.get("migrations") or [] if isinstance(entry, dict)}
    for migration_id in REQUIRED_MIGRATIONS:
        if entries_a.get(migration_id) != entries_b.get(migration_id):
            issues.append(f"两契约的migrations.{migration_id}不一致")
    return issues


def write_contract_atomic(path: str | Path, text: str) -> None:
    """先校验再原子落盘：非法YAML/重复键不会替换原文件。"""
    target = Path(path)
    load_contract_text(text, source=str(target))
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
