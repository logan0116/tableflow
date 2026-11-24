#!/usr/bin/env python3
"""登记 DEP-07-BR：tf-test-plan 支持按用例号精确复用，并挂到 v0.8.5。

这是对 035 测试设计规格的增量改动（不是新能力），所以走依赖需求，不新建独立规格。

幂等：存在即跳过。默认 dry-run，``--apply`` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/register_dep_085.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "")
DEP_ID = "DEP-07-BR"
VERSION = "v0.8.5"
TABLES = {"ver": "tf-ver", "dep": "tf-dep"}

VALUES = {
    "tf-d-id": DEP_ID,
    "tf-d-clause": "tf-test-plan 的 --reuse-from 支持 --case 过滤：只复用指定用例号；不传则维持复用全部",
    "tf-d-indep": ["035-AR"],
    "tf-d-impact": "只影响复用路径；派生路径（按 spec 场景生成用例）不变",
    "tf-d-regress": "todo",
    "tf-d-increment": "修复版只需复测与本版缺陷相关的用例，当前 --reuse-from 会把源版本用例全部带入，"
                      "导致修复版挂上无关用例、本版测了什么失真",
    "tf-d-baselines": "035-AR@v0.8.4",
    "tf-d-affected": "035-AR 复用路径（--reuse-from）",
    "tf-d-plan": "tf-test-plan 增加 --case（可重复）；_reuse_cases 内按集合过滤；补一条端到端测试",
    "tf-d-consistency": "与现有 --spec 参数同构：不传即全量，传则取交集；派生路径不受影响",
    "tf-d-integration": "v0.8.5 用 7 条未修缺陷的复现用例验证",
    "tf-d-rest": "待实现",
}


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", os.environ.get("TF_AGENT", "agent-tf-role"))
    req.add_header("X-Origin", "human-request")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"http": resp.status, **json.loads(resp.read().decode() or "{}")}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:  # noqa: BLE001 - 非 JSON 错误体照样回传
            payload = {"error": raw[:300]}
        return {"http": exc.code, **payload}
    except Exception as exc:  # noqa: BLE001 - 网络异常按三态处理
        return {"http": 0, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正写入；默认只预览")
    args = parser.parse_args()
    if not BASE:
        raise SystemExit("[dep] 未设置 TF_BASE")

    mode = "写入" if args.apply else "预览"
    planned: list[str] = []
    failures: list[str] = []

    detail = call("GET", f"/api/tables/{TABLES['dep']}/table")
    if detail.get("http") != 200:
        raise SystemExit(f"[dep] 读取依赖需求表失败：{detail}")
    existing = {row["id"] for row in detail.get("rows") or []}
    if DEP_ID in existing:
        planned.append(f"依赖需求 {DEP_ID} 已存在，跳过")
    else:
        planned.append(f"新建依赖需求 {DEP_ID}：{VALUES['tf-d-clause']}")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['dep']}/rows/{DEP_ID}",
                          {"values": VALUES})
            if result.get("http") not in (200, 201):
                failures.append(f"{DEP_ID}：{result.get('error') or result}")

    ver = call("GET", f"/api/tables/{TABLES['ver']}/table")
    row = next((item for item in (ver.get("rows") or []) if item["id"] == VERSION), None)
    current = (row or {}).get("values", {}).get("tf-v-dep") or []
    merged = sorted(set(list(current) + [DEP_ID]))
    if merged != list(current):
        planned.append(f"{VERSION} 的依赖需求管理 {len(current)} → {len(merged)} 条")
        if args.apply:
            result = call("PATCH", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}",
                          {"values": {"tf-v-dep": merged}})
            if result.get("http") not in (200, 201):
                failures.append(f"{VERSION} 挂载：{result.get('error') or result}")
    else:
        planned.append(f"{VERSION} 的依赖需求管理已包含 {DEP_ID}，跳过")

    print(f"[dep] 共 {len(planned)} 项{mode}")
    for item in planned:
        print("  -", item)
    print(f"\n合计 {len(planned)} 项{mode}；失败 {len(failures)} 项")
    for item in failures:
        print("  !", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
