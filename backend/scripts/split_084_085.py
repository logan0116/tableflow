#!/usr/bin/env python3
"""拆分 v0.8.4 / v0.8.5：已修的进本版，未修的挪到下一版。

v0.8.4 只保留 13 条已修缺陷及其复现用例；未修的 7 条连同对应用例移到 v0.8.5。
只动 ``ver.Bug管理`` 与 ``ver.测试用例``，不改缺陷状态、不删任何行。

幂等：重复运行结果一致。默认 dry-run，``--apply`` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/split_084_085.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "")
CURRENT = "v0.8.4"
NEXT = "v0.8.5"
TABLES = {"ver": "tf-ver"}

# 未修的缺陷 → 对应的复现用例（一起挪走）
MOVING = {
    "BUG-083-03": "083-US2-AS1",   # B2 新建行绕过变更流
    "BUG-083-04": "083-US3-AS1",   # B3 已发布版本可改范围
    "BUG-083-05": "083-US3-AS2",   # B4 放弃非原子
    "BUG-083-12": "083-US5-AS3",   # S3 空骨架算完成
    "BUG-083-17": "083-US9-AS1",   # C4 复用永久豁免
    "BUG-083-19": "083-US9-AS3",   # C5 映射一测多场景
    "BUG-083-20": "083-US10-AS1",  # S7 验收不落 failed
}
NEXT_NOTE = "缺陷修复版（第二批）：承接 v0.8.4 未修的 7 条，需先定口径再动手"


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
        raise SystemExit("[split] 未设置 TF_BASE")

    mode = "写入" if args.apply else "预览"
    planned: list[str] = []
    failures: list[str] = []

    detail = call("GET", f"/api/tables/{TABLES['ver']}/table")
    if detail.get("http") != 200:
        raise SystemExit(f"[split] 读取版本表失败：{detail}")
    rows = {row["id"]: row["values"] for row in detail.get("rows") or []}
    if CURRENT not in rows:
        raise SystemExit(f"[split] {CURRENT} 不存在")

    moving_bugs = sorted(MOVING)
    moving_runs = sorted(f"{CURRENT}--{case}" for case in MOVING.values())
    current_bugs = list(rows[CURRENT].get("tf-v-bug") or [])
    current_runs = list(rows[CURRENT].get("tf-v-runs") or [])
    keep_bugs = [b for b in current_bugs if b not in moving_bugs]
    keep_runs = [r for r in current_runs if r not in moving_runs]

    if len(keep_bugs) == len(current_bugs) and len(keep_runs) == len(current_runs):
        planned.append(f"{CURRENT} 已经拆分过（缺陷 {len(keep_bugs)} / 用例 {len(keep_runs)}），跳过")
    else:
        planned.append(
            f"{CURRENT}：缺陷 {len(current_bugs)} → {len(keep_bugs)}，用例 {len(current_runs)} → {len(keep_runs)}"
        )
        if args.apply:
            result = call("PATCH", f"/api/agent/tables/{TABLES['ver']}/rows/{CURRENT}",
                          {"values": {"tf-v-bug": keep_bugs, "tf-v-runs": keep_runs}})
            if result.get("http") not in (200, 201):
                failures.append(f"{CURRENT} 解绑：{result.get('error') or result}")

    if NEXT in rows:
        planned.append(f"版本行 {NEXT} 已存在，跳过创建")
    else:
        planned.append(f"新建版本行 {NEXT}（planned，挂 {len(moving_bugs)} 条未修缺陷）")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['ver']}/rows/{NEXT}", {"values": {
                "tf-v-ver": NEXT,
                "tf-v-status": "planned",
                **{f"tf-v-stage-{s}": "todo" for s in
                   ("plan", "test-design", "dev", "dev-accept", "test", "test-accept")},
                "tf-v-indep": [],
                "tf-v-dep": [],
                "tf-v-runs": [],
                "tf-v-bug": moving_bugs,
                "tf-v-note": NEXT_NOTE,
            }})
            if result.get("http") not in (200, 201):
                failures.append(f"版本行 {NEXT}：{result.get('error') or result}")

    print(f"[split] 共 {len(planned)} 项{mode}")
    for item in planned:
        print("  -", item)
    print(f"\n合计 {len(planned)} 项{mode}；失败 {len(failures)} 项")
    for item in failures:
        print("  !", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
