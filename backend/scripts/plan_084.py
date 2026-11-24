#!/usr/bin/env python3
"""v0.8.4 规划：新建修复版本，把 v0.8.3 登记的缺陷全部挂上去。

v0.8.3 是发现/复现版本（红灯、不发布），v0.8.4 是修复版本；缺陷与版本的关系
由 ``ver.Bug管理`` 反向表达，所以同一条缺陷可以同时挂在两个版本上。

幂等：版本行存在则跳过，Bug管理做并集。默认 dry-run，``--apply`` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/plan_084.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "")
TABLES = {"ver": "tf-ver", "bug": "tf-bug"}
VERSION = "v0.8.4"
PREVIOUS = "v0.8.3"
STAGE_FIELDS = (
    "tf-v-stage-plan", "tf-v-stage-test-design", "tf-v-stage-dev",
    "tf-v-stage-dev-accept", "tf-v-stage-test", "tf-v-stage-test-accept",
)
NOTE = "缺陷修复版：v0.8.3 复现出的 20 条问题按依赖顺序修复，逐条转绿后再谈发布"


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
        raise SystemExit("[084] 未设置 TF_BASE")

    mode = "写入" if args.apply else "预览"
    planned: list[str] = []
    failures: list[str] = []

    ver = call("GET", f"/api/tables/{TABLES['ver']}/table")
    if ver.get("http") != 200:
        raise SystemExit(f"[084] 读取版本表失败：{ver}")
    rows = {row["id"]: row for row in ver.get("rows") or []}
    previous = (rows.get(PREVIOUS) or {}).get("values", {})
    bugs = list(previous.get("tf-v-bug") or [])
    if not bugs:
        raise SystemExit(f"[084] {PREVIOUS} 上没有挂缺陷，先跑 register_083_bugs.py")

    if VERSION in rows:
        planned.append(f"版本行 {VERSION} 已存在，跳过创建")
    else:
        planned.append(f"新建版本行 {VERSION}（planned，六节点 todo，挂 {len(bugs)} 条缺陷）")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}", {"values": {
                "tf-v-ver": VERSION,
                "tf-v-status": "planned",
                **{field: "todo" for field in STAGE_FIELDS},
                "tf-v-indep": [],
                "tf-v-dep": [],
                "tf-v-runs": [],
                "tf-v-bug": bugs,
                "tf-v-note": NOTE,
            }})
            if result.get("http") not in (200, 201):
                failures.append(f"版本行 {VERSION}：{result.get('error') or result}")

    ver = call("GET", f"/api/tables/{TABLES['ver']}/table")
    current = next(
        (row["values"].get("tf-v-bug") or [] for row in ver.get("rows") or [] if row["id"] == VERSION),
        [],
    )
    merged = sorted(set(list(current) + bugs))
    if merged != list(current):
        planned.append(f"版本 {VERSION} 的 Bug管理 {len(current)} → {len(merged)} 条")
        if args.apply:
            result = call("PATCH", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}",
                          {"values": {"tf-v-bug": merged}})
            if result.get("http") not in (200, 201):
                failures.append(f"版本 Bug管理：{result.get('error') or result}")
    else:
        planned.append(f"版本 {VERSION} 的 Bug管理已收录 {len(merged)} 条，跳过")

    print(f"[084] 共 {len(planned)} 项{mode}")
    for item in planned:
        print("  -", item)
    print(f"\n合计 {len(planned)} 项{mode}；失败 {len(failures)} 项")
    for item in failures:
        print("  !", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
