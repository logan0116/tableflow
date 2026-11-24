#!/usr/bin/env python3
"""补登 v0.8.6：版本行 + 缺陷 + 用例 + 执行记录。

v0.8.6 是前端显示缺陷的 hotfix（测试列回落 0/0），当时直接部署未走看板。
本脚本补齐看板登记，之后按 1→6 节点正常推进。

幂等：存在即跳过。默认 dry-run，``--apply`` 才写。

    TF_BASE=http://localhost:8090 python3 backend/scripts/register_086.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TF_BASE", "")
VERSION = "v0.8.6"
BUG = "BUG-083-21"
CASE = "083-US11-AS1"
RUN = f"{VERSION}--{CASE}"
TABLES = {"ver": "tf-ver", "bug": "tf-bug", "case": "tf-case", "run": "tf-run"}
STAGE_FIELDS = (
    "tf-v-stage-plan", "tf-v-stage-test-design", "tf-v-stage-dev",
    "tf-v-stage-dev-accept", "tf-v-stage-test", "tf-v-stage-test-accept",
)
NOTE = "前端显示修复：版本表「测试」列回落 0/0，数据一直正确，坏在渲染"


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
        raise SystemExit("[086] 未设置 TF_BASE")

    mode = "写入" if args.apply else "预览"
    planned: list[str] = []
    failures: list[str] = []

    # 1) 缺陷
    detail = call("GET", f"/api/tables/{TABLES['bug']}/table")
    bugs = {row["id"] for row in detail.get("rows") or []}
    if BUG in bugs:
        planned.append(f"缺陷 {BUG} 已存在，跳过")
    else:
        planned.append(f"新建缺陷 {BUG}：版本表「测试」列显示 0/0")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['bug']}/rows/{BUG}", {"values": {
                "tf-b-id": BUG,
                "tf-b-title": "版本表「测试」列显示 0/0，已完成/总数未拼装",
                "tf-b-status": "open",
                "tf-b-severity": "major",
                "tf-b-source": "review",
                "tf-b-indep": ["026-AR"],
                "tf-b-found-ver": VERSION,
                "tf-b-evidence": "GroupRatioCell 只认字符串；用例组喂的是「用例总数」数字 → 回落 0/0；"
                                 "接口返回 7/7，前端显示 0/0",
                "tf-b-rest": "用例组用「已完成用例数/用例总数」拼装；已部署 v0.8.6",
            }})
            if result.get("http") not in (200, 201):
                failures.append(f"{BUG}：{result.get('error') or result}")

    # 2) 用例
    detail = call("GET", f"/api/tables/{TABLES['case']}/table")
    cases = {row["id"] for row in detail.get("rows") or []}
    if CASE in cases:
        planned.append(f"用例 {CASE} 已存在，跳过")
    else:
        planned.append(f"新建用例 {CASE}：测试列显示已完成/总数")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['case']}/rows/{CASE}", {"values": {
                "tf-c-id": CASE,
                "tf-c-name": "版本表「测试」列显示已完成/总数，不回落 0/0",
                "tf-c-indep": ["026-AR"],
                "tf-c-precondition": "版本行有用例关联且已有执行结果，",
                "tf-c-steps": "打开版本管理表查看「测试」列，",
                "tf-c-expect": "显示「已完成用例数/用例总数」，空集才是 0/0",
                "tf-c-priority": "P1",
            }})
            if result.get("http") not in (200, 201):
                failures.append(f"{CASE}：{result.get('error') or result}")

    # 3) 执行记录
    detail = call("GET", f"/api/tables/{TABLES['run']}/table")
    runs = {row["id"] for row in detail.get("rows") or []}
    if RUN in runs:
        planned.append(f"执行记录 {RUN} 已存在，跳过")
    else:
        planned.append(f"新建执行记录 {RUN}（todo）")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['run']}/rows/{RUN}", {"values": {
                "tf-r-id": RUN,
                "tf-r-case_no": CASE,
                "tf-r-case": [CASE],
                "tf-r-state": "todo",
            }})
            if result.get("http") not in (200, 201):
                failures.append(f"{RUN}：{result.get('error') or result}")

    # 4) 版本行
    detail = call("GET", f"/api/tables/{TABLES['ver']}/table")
    versions = {row["id"] for row in detail.get("rows") or []}
    if VERSION in versions:
        planned.append(f"版本行 {VERSION} 已存在，跳过")
    else:
        planned.append(f"新建版本行 {VERSION}（planned，挂 {BUG} 与 1 条用例）")
        if args.apply:
            result = call("POST", f"/api/agent/tables/{TABLES['ver']}/rows/{VERSION}", {"values": {
                "tf-v-ver": VERSION,
                "tf-v-status": "planned",
                **{field: "todo" for field in STAGE_FIELDS},
                "tf-v-indep": [],
                "tf-v-dep": [],
                "tf-v-runs": [RUN],
                "tf-v-bug": [BUG],
                "tf-v-note": NOTE,
            }})
            if result.get("http") not in (200, 201):
                failures.append(f"{VERSION}：{result.get('error') or result}")

    print(f"[086] 共 {len(planned)} 项{mode}")
    for item in planned:
        print("  -", item)
    print(f"\n合计 {len(planned)} 项{mode}；失败 {len(failures)} 项")
    for item in failures:
        print("  !", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
