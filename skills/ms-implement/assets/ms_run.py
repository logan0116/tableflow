#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ms_run.py —— ms-implement skill 的执行体：读计划用例、回写执行结果与证据。

分工：本脚本只做"读计划 / 校验输入 / 回写结果 / 读回核对 / 落证据账"，
具体执行（点界面、跑命令、截图）由执行者做——脚本不替人执行、不编造结果。

端点（v3.6.9-lts，155:8081 实测）：
  计划内用例列表  POST /test-plan/functional/case/page  {testPlanId, current, pageSize}
                  返回行里的 `id` 才是回写要的**关联行 id**，`caseId` 是用例本身。
  结果回写        POST /test-plan/functional/case/run
                  必填：id（关联行 id）、testPlanId、caseId、projectId、lastExecResult；
                  缺一个就 400 `parameter validate failure`，报错文本会点名字段。
                  ⚠️ 实测只有 `SUCCESS` / `ERROR` 会真正进入回写分支；`FAIL`/`BLOCKED`/`SKIP`/
                  `PENDING` 返回 100200 但**什么都不做**（静默空转）。故本脚本只放行这两个值，
                  其它结论（阻塞/跳过）用 ERROR + note 说明原因，避免"报成功其实没写"。

回写的可信边界（务必在报告里体现）：
  - `lastExecResult` 变了不等于"用例真的被执行过"——它是人/脚本的自述；
  - 判据是：本地证据文件（截图/日志）+ 证据账（runlog.jsonl 含 sha256）能对上这次结果。

计划↔用例关联的缺口：v3.6.9-lts 没有关联写入端点（18 个候选路径全 `No static resource`）。
新计划必须先在 MS 界面「计划详情 → 功能用例 → 关联用例」把用例挂进来，本脚本才能回写；
`--list` 返回 0 条时就是没关联，不要拿"跑完了"当结论。

用法：
    python3 skills/ms-implement/assets/ms_run.py --list
    python3 skills/ms-implement/assets/ms_run.py --case 008-US1-AS1 --result SUCCESS \
        --evidence .tmp-shots/ms-evidence/008-US1-AS1.png --note "契约解析 16/16/9"
    python3 skills/ms-implement/assets/ms_run.py --case 008-US1-AS1 --result ERROR --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MS_TOOLS_DEFAULT = os.path.expanduser("~/PycharmProjects/cnc_nexus/tools/metersphere")
PLAN_NAME = "tableflow v0.6.0 · 契约与技能验收"
EVIDENCE_DIR = ROOT / ".tmp-shots" / "ms-evidence"
ALLOWED_RESULTS = ("SUCCESS", "ERROR")   # 实测唯一会被服务端处理的两个值


# ── 凭据与客户端（同 ms_sync.py：走项目统一 ms_env，不打印 AK/SK） ───────────
def load_ms():
    tools = os.environ.get("MS_TOOLS_DIR") or MS_TOOLS_DEFAULT
    if not (Path(tools) / "ms_env.py").exists():
        raise SystemExit(f"找不到 ms_env.py：{tools}（用 MS_TOOLS_DIR 指定目录）")
    sys.path.insert(0, tools)
    from ms_env import ids, ms_client  # noqa: PLC0415

    ms = ms_client()
    pid, _tid, _prio = ids()
    return ms, pid


# ── 计划与用例 ──────────────────────────────────────────────────────────────
def find_plan(ms, pid: str, name: str) -> dict:
    data = ms.request("POST", "/test-plan/page",
                      {"projectId": pid, "type": "ALL", "current": 1, "pageSize": 100})["data"]
    hit = next((p for p in data["list"] if (p.get("name") or "") == name), None)
    if not hit:
        names = "、".join(p.get("name", "") for p in data["list"][:8])
        raise SystemExit(f"找不到计划「{name}」。现有计划：{names}")
    return hit


def plan_cases(ms, plan_id: str) -> list[dict]:
    rows, page = [], 1
    while True:
        data = ms.request("POST", "/test-plan/functional/case/page",
                          {"testPlanId": plan_id, "current": page, "pageSize": 50})["data"]
        rows += data["list"]
        if len(rows) >= data["total"]:
            return rows
        page += 1


def match_case(rows: list[dict], key: str) -> dict:
    """按场景号前缀或完整名称定位计划内用例；命中多条直接报错（不猜）。"""
    hits = [r for r in rows if (r.get("name") or "").startswith(key + " ")]
    if not hits:
        hits = [r for r in rows if (r.get("name") or "") == key]
    if not hits:
        raise SystemExit(
            f"计划里没有「{key}」——先确认它已关联进计划（本版本无关联写入 API，须界面操作）"
        )
    if len(hits) > 1:
        raise SystemExit(f"「{key}」命中 {len(hits)} 条，改用完整用例名："
                         + " | ".join(h["name"] for h in hits))
    return hits[0]


# ── 证据账 ──────────────────────────────────────────────────────────────────
def evidence_entry(paths: list[str], note: str, case: str, result: str) -> dict:
    files = []
    for p in paths:
        f = Path(p)
        if not f.is_absolute():
            f = ROOT / p
        if not f.exists():
            raise SystemExit(f"证据文件不存在：{p}（没有证据不得回写结果）")
        files.append({
            "path": str(f), "bytes": f.stat().st_size,
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest()[:16],
        })
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "case": case, "result": result, "note": note, "files": files,
    }
    log = EVIDENCE_DIR / "runlog.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"entry": entry, "log": str(log)}


# ── 回写 ────────────────────────────────────────────────────────────────────
def write_result(ms, pid: str, plan_id: str, row: dict, result: str, *, dry: bool) -> dict:
    payload = {
        "id": row["id"],                  # 关联行 id
        "testPlanId": plan_id,
        "caseId": row["caseId"],
        "projectId": pid,
        "lastExecResult": result,
    }
    if dry:
        return {"payload": payload, "written": False}
    resp = ms.request("POST", "/test-plan/functional/case/run", payload)
    # 读回核对：只认 page 里的 lastExecResult，不认 200/100200
    after = next((r for r in plan_cases(ms, plan_id) if r["id"] == row["id"]), None)
    ok = bool(after) and after.get("lastExecResult") == result
    return {"payload": payload, "response": resp, "readback": {
        "lastExecResult": after.get("lastExecResult") if after else None,
        "lastExecTime": after.get("lastExecTime") if after else None,
        "executeUserName": after.get("executeUserName") if after else None,
    }, "written": ok}


def main() -> int:
    ap = argparse.ArgumentParser(description="计划用例执行结果回写（ms-implement）")
    ap.add_argument("--plan", default=PLAN_NAME, help=f"计划名（默认 {PLAN_NAME}）")
    ap.add_argument("--list", action="store_true", help="列出计划内用例与最近结果")
    ap.add_argument("--case", help="用例名或场景号前缀，如 008-US1-AS1")
    ap.add_argument("--result", choices=ALLOWED_RESULTS, help="SUCCESS / ERROR（ERROR 用于失败/阻塞，原因写 --note）")
    ap.add_argument("--evidence", nargs="*", default=[], help="证据文件（截图/日志），没有证据拒绝回写")
    ap.add_argument("--note", default="", help="结论说明（失败原因、降级路径等）")
    ap.add_argument("--dry-run", action="store_true", help="只打印请求体，不写")
    ap.add_argument("--json", action="store_true", help="输出机器可读摘要")
    args = ap.parse_args()

    ms, pid = load_ms()
    plan = find_plan(ms, pid, args.plan)
    rows = plan_cases(ms, plan["id"])

    if args.list:
        print(f"计划：{plan['name']}（{plan['id']}）｜关联用例 {len(rows)} 条")
        for r in rows:
            print(f"  [{r.get('lastExecResult')}] {r['name']}  关联行 {r['id']}")
        if not rows:
            print("  0 条 = 尚未关联用例。本版本无关联写入 API，请先在界面「计划详情 → 功能用例 →"
                  " 关联用例」挂进来，再回写结果；不要据此宣称执行过。")
        return 0

    if not args.case or not args.result:
        ap.error("回写需要 --case 与 --result；只查询用 --list")
    if args.result == "SUCCESS" and not args.note:
        ap.error("SUCCESS 必须带 --note 说明执行了什么、结论依据是什么")

    row = match_case(rows, args.case)
    ev = evidence_entry(args.evidence, args.note, args.case, args.result) if args.evidence else None
    out = write_result(ms, pid, plan["id"], row, args.result, dry=args.dry_run)
    out.update({"case": row["name"], "linkId": row["id"], "caseId": row["caseId"],
                "planId": plan["id"], "evidence": ev})

    print(f"用例：{row['name']}｜关联行 {row['id']}｜目标结果 {args.result}")
    print(f"请求体：{json.dumps(out['payload'], ensure_ascii=False)}")
    if ev:
        print(f"证据：{len(ev['entry']['files'])} 个文件 → {ev['log']}")
        for f in ev["entry"]["files"]:
            print(f"  - {f['path']}（{f['bytes']}B, sha256:{f['sha256']}）")
    if args.dry_run:
        print("预览模式：未写平台")
        return 0
    print(f"服务端响应：{json.dumps(out.get('response'), ensure_ascii=False)[:200]}")
    print(f"读回：{json.dumps(out.get('readback'), ensure_ascii=False)}")
    if not out["written"]:
        print("⚠️ 读回不一致：结果未落库，按未验证处理，不要报成功")
        return 1
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
