#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ms_summary.py —— ms-summary skill 的执行体：执行结果 → tf-bug 缺陷行。

输入（三选一，可叠加）：
  1. **用例级结果**：功能用例库的 `lastExecuteResult`（无计划关联时可读，绕开计划）；
  2. **计划级结果**：`/test-plan/functional/case/page` 的 `lastExecResult`（有真实关联行时最准）；
  3. **人工确认的缺陷**：`--defect` 直接给一条已核实的缺陷（证据仍必须指到 MS 用例号）。

归类口径：
  - `ERROR` → 缺陷候选；
  - `BLOCKED` → 只有**显式给出产品缺陷原因**（`--block-reason`）才算缺陷；没给原因的一律进
    "待判定"，不登记（环境/设备/数据阻塞不是产品缺陷）；
  - `SUCCESS` → 不登记；若同用例存在未关闭缺陷，只输出"可关闭建议"，**必须人确认**才写 closed；
  - `PENDING` → 不登记（没人跑过，不是结论）。

两轴去重（本 skill 的核心）：
  轴1 执行记录唯一 id：`plan:<planId>:<linkId>:<lastExecTime>` 或 `case:<caseId>:<result>:<updateTime>`；
      已消费的记在 `.tmp-shots/ms-summary/consumed.json`，同一次执行不会登记第二行；
  轴2 缺陷实体：标题归一化后相同（或多用例给了同一个 `--signature`）视为同一缺陷 → **合并**到已有行：
      追加 MS 用例号、证据里记"复现 N 次"，不新增行。

写后回读：`GET /api/tables/tf-bug/table` 与单行接口逐字段核对，不信 `{"result":"success"}`。

用法：
    # 只读演练：扫描真实执行结果，打印将写入的行（不写看板）
    python3 skills/ms-summary/assets/ms_summary.py --dry-run
    # 真写一次
    python3 skills/ms-summary/assets/ms_summary.py --apply --found v0.6.0
    # 人工确认过的缺陷（不进执行结果扫描，直接登记一行）
    python3 skills/ms-summary/assets/ms_summary.py --apply --defect-file /tmp/bug.json --found v0.6.0
    # 关闭：必须有该用例更新的 SUCCESS 记录 + 人确认
    python3 skills/ms-summary/assets/ms_summary.py --close BUG-01 --confirm-close --reason "复测通过"

环境变量：
    TF_BASE   tableflow 看板地址（默认 http://192.168.1.155:8090）
    TF_AGENT  写入审计身份（默认 agent-tf-ms）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MS_TOOLS_DEFAULT = os.path.expanduser("~/PycharmProjects/cnc_nexus/tools/metersphere")
TF_BASE = os.environ.get("TF_BASE", "http://192.168.1.155:8090").rstrip("/")
TF_AGENT = os.environ.get("TF_AGENT", "agent-tf-ms")
TF_ORIGIN = "human-request"
PROJECT = os.environ.get("TF_PROJECT", "tableflow")
BUG_TABLE = None            # 由 configure() 按项目解析，不写死 tf-bug
DEFAULT_MODULE = None       # 不写死版本号；默认按 "TF · <project>" 前缀匹配
STATE_DIR = ROOT / ".tmp-shots" / "ms-summary"
CONSUMED = STATE_DIR / "consumed.json"

# 缺陷表字段按「名称」解析（board@3 语义键→字段名），不绑死某个项目的 tf-b-* 组合
FIELD_NAMES = {
    "id": "编号", "title": "标题", "status": "状态", "severity": "严重度",
    "source": "来源", "specs": "关联规格", "found": "发现版本号",
    "evidence": "证据", "rest": "剩余事项", "ms": "MS用例号", "owner": "负责人",
}
F: dict[str, str] = {}


# ── tableflow 写/读 ─────────────────────────────────────────────────────────
def tf_get(path: str):
    req = urllib.request.Request(TF_BASE + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))



def configure(project: str, table: str | None = None) -> None:
    """按项目解析缺陷表与其字段 id（board@3 字段按名称匹配），不写死 tf-bug。"""
    global BUG_TABLE, F
    tables = tf_get(f"/api/projects/{project}/tables").get("tables", [])
    if table:
        tid = table
    else:
        cands = [t["id"] for t in tables if t["id"].endswith("-bug")]
        if not cands:
            raise SystemExit(f"项目 {project} 没有缺陷表（<前缀>-bug）；请先建表或用 --table 指定")
        tid = cands[0]
    fields = tf_get(f"/api/tables/{tid}/table").get("fields", [])
    by_name = {f["name"]: f["id"] for f in fields}
    missing = [n for n in FIELD_NAMES.values() if n not in by_name]
    if missing:
        raise SystemExit(f"{tid} 缺字段：{missing}（board@3 口径不匹配，先对齐契约）")
    BUG_TABLE = tid
    F = {k: by_name[n] for k, n in FIELD_NAMES.items()}

def tf_write(method: str, path: str, body: dict) -> tuple[str, dict]:
    """写接口三态：success / failed(400) / unknown(503)，只认响应体里的 result。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        TF_BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "X-Agent-Id": TF_AGENT, "X-Origin": TF_ORIGIN},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raw = json.loads(exc.read().decode("utf-8", "replace") or "{}")
    return raw.get("result", "unknown"), raw


def bug_rows() -> list[dict]:
    return tf_get(f"/api/tables/{BUG_TABLE}/table").get("rows", [])


def row_values(row: dict) -> dict:
    return row.get("values", {}) or {}


# ── MS 执行结果采集 ─────────────────────────────────────────────────────────
def load_ms():
    tools = os.environ.get("MS_TOOLS_DIR") or MS_TOOLS_DEFAULT
    if not (Path(tools) / "ms_env.py").exists():
        raise SystemExit(f"找不到 ms_env.py：{tools}（用 MS_TOOLS_DIR 指定）")
    sys.path.insert(0, tools)
    from ms_env import ids, ms_client  # noqa: PLC0415

    return ms_client(), ids()[0]


def ms_projects_map() -> dict:
    """tableflow 项目 → MeterSphere 项目 id 的映射。

    路径 $MS_PROJECTS_FILE，默认 ~/.config/ms/projects.json，形如
    {"fd_system": "1699362720433840128", "tableflow": "1695095876583694336"}。
    """
    candidates = [os.environ.get("MS_PROJECTS_FILE"),
                  str(ROOT / ".ms-projects.json"),
                  os.path.expanduser("~/.config/ms/projects.json")]
    for path in candidates:
        if not path:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            continue
        except Exception:  # noqa: BLE001
            continue
    return {}


def load_ms_project(ms_project: str | None, project: str) -> tuple:
    """多产品共用一个 MS 实例：命令行 > 映射文件 > ms_env，并把来源打印出来。"""
    ms, env_pid = load_ms()
    if ms_project:
        pid, source = ms_project, "命令行 --ms-project"
    else:
        mapped = ms_projects_map().get(project)
        pid, source = (str(mapped), "映射文件") if mapped else (env_pid, "ms_env 默认")
    try:
        name = ms.request("GET", f"/project/get/{pid}")["data"]["name"]
    except Exception:  # noqa: BLE001
        name = "（名称未知）"
    print(f"MS 项目：{name}（{pid}）｜来源：{source}")
    if source == "ms_env 默认":
        print(f"  ⚠ 未配置 {project} → MS 项目映射，正在读 ms_env 的默认项目；"
              f"若这不是 {project} 的测试数据，请用 --ms-project 或写 ~/.config/ms/projects.json")
    return ms, pid


def collect(ms, pid: str, module: str | None, plan_filter: list[str]) -> list[dict]:
    """采执行记录：用例库（用例级）+ 各计划（计划级）。"""
    records: list[dict] = []
    # 用例级：只取本 skill 模块内的用例
    modules = {n["id"]: n.get("name") for n in
               (ms.request("GET", f"/functional/case/module/tree/{pid}")["data"] or [])}
    rows, page = [], 1
    while True:
        d = ms.request("POST", "/functional/case/page",
                       {"projectId": pid, "current": page, "pageSize": 100})["data"]
        rows += d["list"]
        if len(rows) >= d["total"]:
            break
        page += 1
    for r in rows:
        if module and modules.get(r.get("moduleId")) != module:
            continue
        if r.get("lastExecuteResult") in (None, "PENDING"):
            continue
        records.append({
            "record_id": f"case:{r['id']}:{r['lastExecuteResult']}:{r.get('updateTime')}",
            "scope": "case", "plan": None, "case_id": r["id"], "case_num": r.get("num"),
            "case_name": r["name"], "result": r["lastExecuteResult"],
            "exec_time": r.get("updateTime"), "module": modules.get(r.get("moduleId")),
        })
    # 计划级
    plans = ms.request("POST", "/test-plan/page",
                       {"projectId": pid, "type": "ALL", "current": 1, "pageSize": 100})["data"]["list"]
    for p in plans:
        if plan_filter and p["name"] not in plan_filter:
            continue
        cur, got = 1, []
        while True:
            d = ms.request("POST", "/test-plan/functional/case/page",
                           {"testPlanId": p["id"], "current": cur, "pageSize": 50})["data"]
            got += d["list"]
            if len(got) >= d["total"] or not d["list"]:
                break
            cur += 1
        for r in got:
            if r.get("lastExecResult") in (None, "PENDING"):
                continue
            records.append({
                "record_id": f"plan:{p['id']}:{r['id']}:{r.get('lastExecTime')}",
                "scope": "plan", "plan": p["name"], "case_id": r.get("caseId"),
                "case_num": r.get("num"), "case_name": r["name"],
                "result": r["lastExecResult"], "exec_time": r.get("lastExecTime"),
                "module": r.get("moduleName"),
            })
    return records


# ── 归类与去重 ──────────────────────────────────────────────────────────────
def norm(text: str) -> str:
    return "".join((text or "").split()).lower()


def load_consumed() -> dict:
    if CONSUMED.exists():
        return json.loads(CONSUMED.read_text(encoding="utf-8"))
    return {"records": {}}


def save_consumed(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONSUMED.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def classify(records: list[dict], block_reasons: dict[str, str]) -> dict:
    """ERROR→候选；BLOCKED 有产品缺陷原因→候选，否则待判定；SUCCESS→关闭建议。"""
    out = {"candidates": [], "pending": [], "success": []}
    for rec in records:
        # BLOCKED 的原因键：计划级用 linkId，用例级用 caseId；两种都试
        reason = block_reasons.get(rec["record_id"]) or block_reasons.get(rec["case_id"], "")
        if rec["result"] == "ERROR":
            out["candidates"].append({**rec, "why": "ERROR"})
        elif rec["result"] == "BLOCKED":
            if reason:
                out["candidates"].append({**rec, "why": f"BLOCKED-产品缺陷：{reason}"})
            else:
                out["pending"].append({**rec, "why": "BLOCKED 未给出产品缺陷原因"})
        elif rec["result"] == "SUCCESS":
            out["success"].append(rec)
    return out


def bug_index(rows: list[dict]) -> dict[str, dict]:
    """缺陷实体索引：标题归一化 → 行；用于轴2合并。"""
    idx: dict[str, dict] = {}
    for row in rows:
        v = row_values(row)
        idx.setdefault(norm(v.get(F["title"], "")), row)
    return idx


def next_bug_id(rows: list[dict]) -> str:
    nums = [0]
    for row in rows:
        raw = (row.get("id") or "").replace("BUG-", "")
        nums.append(int(raw) if raw.isdigit() else 0)
    return f"BUG-{max(nums) + 1:02d}"


def build_row(bug_id: str, cand: dict, found: str, specs: list[str], severity: str,
              count: int) -> dict:
    """一条缺陷 → tf-bug 行值（字段口径见 specs/011-bug-table/board@2.yaml）。"""
    title = cand["title"]
    ms_id = str(cand.get("ms") or cand.get("case_num") or cand.get("case_id") or "")
    if cand.get("scope") == "manual":
        # 人工确认的缺陷没有 MS 执行记录：证据用调用方给的原文，不编造"结果 ERROR"
        head = cand.get("evidence") or ""
        evidence = f"{head}\n【归类】人工确认（无 MS 执行记录，证据见上）\n【复现】{count} 次"
        if cand.get("detail"):
            evidence += f"\n【现象】{cand['detail']}"
    else:
        evidence = (
            f"【MS】{ms_id}「{cand.get('case_name', '')}」结果 {cand.get('result')}"
            f"（执行记录 {cand.get('record_id')}）\n"
            f"【归类】{cand.get('why', '')}\n"
            f"【复现】{count} 次\n"
            f"【现象】{cand.get('detail', '')}"
        )
    return {
        F["id"]: bug_id, F["title"]: title, F["status"]: "open",
        F["severity"]: severity,
        F["source"]: "manual" if cand.get("scope") == "manual" else "ms_case",
        F["specs"]: specs,
        F["found"]: found, F["evidence"]: evidence.strip(),
        F["rest"]: "", F["ms"]: ms_id, F["owner"]: TF_AGENT,
    }


def readback(bug_id: str, expect: dict,
             *, contains: dict[str, list[str]] | None = None) -> tuple[bool, list[str]]:
    """写后回读：单行 + 整表各核一次，返回 (是否一致, 差异项)。

    `contains` 是"必含子串"校验：{字段: [子串]}，用于文本字段（如证据里的
    `【原剩余事项】`/`【关闭】`）——只比整值不够，丢了一段也能"看起来成功"。
    """
    diff: list[str] = []
    try:
        row = tf_get(f"/api/tables/{BUG_TABLE}/rows/{bug_id}")["row"]
        values = row_values(row)
    except Exception as exc:  # noqa: BLE001
        return False, [f"单行读回失败：{exc}"]
    for field, needles in (contains or {}).items():
        got = str(values.get(field) or "")
        for needle in needles:
            if needle not in got:
                diff.append(f"{field}: 期望包含「{needle}」，读回没有")
    for k, want in expect.items():
        got = values.get(k)
        if isinstance(want, list) or isinstance(got, list):
            if sorted(map(str, want or [])) != sorted(map(str, got or [])):
                diff.append(f"{k}: 期望 {want} 实际 {got}")
        elif str(want or "") != str(got or ""):
            diff.append(f"{k}: 期望 {str(want)[:40]} 实际 {str(got)[:40]}")
    all_ids = [r.get("id") for r in bug_rows()]
    if bug_id not in all_ids:
        diff.append(f"整表里找不到 {bug_id}")
    return (not diff), diff


def main() -> int:
    ap = argparse.ArgumentParser(description="MS 执行结果 → tf-bug（ms-summary）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将写入的行")
    ap.add_argument("--apply", action="store_true", help="真写看板")
    ap.add_argument("--project", default=PROJECT, help="tableflow 项目 id（默认 tableflow）")
    ap.add_argument("--ms-project", default=None, help="MeterSphere 项目 id（默认取 ms_env 的 MS_PROJECT_ID）")
    ap.add_argument("--table", help="缺陷表 id（默认按 <前缀>-bug 解析）")
    ap.add_argument("--module", default=None,
                    help="用例级结果只取该模块；默认按 'TF · <project>' 前缀匹配（空串=全项目）")
    ap.add_argument("--plans", nargs="*", default=[], help="限定计划名（默认全部计划）")
    ap.add_argument("--block-reason", action="append", default=[],
                    help="判为产品缺陷的 BLOCKED：<caseId或record_id>=<原因>")
    ap.add_argument("--found", required=False, help="发现版本号（文本，如 v0.6.4；写缺陷时必填）")
    ap.add_argument("--specs", nargs="*", default=[], help="关联规格行 id，如 014-AR")
    ap.add_argument("--severity", default="major", choices=["blocker", "critical", "major", "minor"])
    ap.add_argument("--defect-file", help="人工确认的缺陷 JSON（字段：title/severity/source/specs/evidence/ms/rest/detail）")
    ap.add_argument("--close", help="要关闭的缺陷行 id")
    ap.add_argument("--reason", default="", help="关闭依据（必须可核验）")
    ap.add_argument("--confirm-close", action="store_true", help="人已确认关闭")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    configure(args.project, args.table)
    if args.module is None:
        args.module = f"TF · {args.project}"
    if not (args.dry_run or args.apply or args.close):
        ap.error("至少给一个动作：--dry-run / --apply / --close")

    if args.close:
        rows = bug_rows()
        row = next((r for r in rows if r.get("id") == args.close), None)
        if not row:
            raise SystemExit(f"找不到缺陷行 {args.close}（现有：{[r.get('id') for r in rows]}）")
        v = row_values(row)
        if not args.reason:
            raise SystemExit("关闭必须给 --reason（依据要能核验）")
        if not args.confirm_close:
            print(f"{args.close} 当前状态 {v.get(F['status'])}；关闭依据：{args.reason}")
            print("→ 关闭需人确认：加 --confirm-close 才会写 closed")
            return 0
        # 关闭要清空 rest（契约要求），但原待办不能静默丢：先把原文并入证据固定段
        rest_orig = (v.get(F["rest"]) or "").strip()
        extra = ""
        if rest_orig:
            extra += f"\n【原剩余事项】{rest_orig}"
        extra += f"\n【关闭】{args.reason}"
        print(f"原剩余事项：{rest_orig!r}" + ("（将并入证据后清空）" if rest_orig else "（为空，不写【原剩余事项】）"))
        expect = {F["status"]: "closed", F["rest"]: ""}
        contains = {F["evidence"]: (["【原剩余事项】"] if rest_orig else []) + ["【关闭】"]}
        patch = {"values": {F["status"]: "closed", F["rest"]: "",
                            F["evidence"]: (v.get(F["evidence"]) or "") + extra}}
        result, raw = tf_write("PATCH", f"/api/agent/tables/{BUG_TABLE}/rows/{args.close}", patch)
        print(f"写接口三态：{result} {json.dumps(raw, ensure_ascii=False)[:160]}")
        ok, diff = readback(args.close, expect, contains=contains)
        print(f"读回：{'一致' if ok else '不一致'}")
        for d in diff:
            print(f"  ⚠️ {d}")
        return 0 if (result == "success" and ok) else 1

    ms, pid = load_ms_project(args.ms_project, args.project)
    records = collect(ms, pid, args.module or None, args.plans)
    block_reasons = {}
    for item in args.block_reason:
        key, _, reason = item.partition("=")
        block_reasons[key.strip()] = reason.strip()
    cls = classify(records, block_reasons)
    state = load_consumed()
    rows = bug_rows()
    idx = bug_index(rows)

    print(f"扫描执行记录 {len(records)} 条 → ERROR/缺陷候选 {len(cls['candidates'])}"
          f"｜BLOCKED 待判定 {len(cls['pending'])}｜SUCCESS {len(cls['success'])}")
    for rec in cls["pending"]:
        print(f"  ? 待判定 {rec['result']} {rec['case_name'][:44]}（{rec['record_id']}）——未给出产品缺陷原因")

    # 人工确认的缺陷 → 作为候选（record_id 用 defect:<n>，便于轴1记录）
    cands = list(cls["candidates"])
    if args.defect_file:
        d = json.loads(Path(args.defect_file).read_text(encoding="utf-8"))
        cands.append({
            "record_id": f"defect:{norm(d['title'])[:30]}:{d.get('ms', '')}", "scope": "manual", "plan": None,
            "case_id": d.get("ms", ""), "case_num": d.get("ms", ""),
            "case_name": d.get("case_name", ""), "result": "ERROR",
            "why": d.get("why", "人工确认"), "title": d["title"],
            "detail": d.get("detail", ""), "severity": d.get("severity", args.severity),
            "source": d.get("source", "test"), "specs": d.get("specs", args.specs),
            "ms": d.get("ms", ""), "rest": d.get("rest", ""),
            "evidence": d.get("evidence", ""),
        })

    plans = {"create": [], "merge": [], "skip": []}
    for cand in cands:
        cand.setdefault("title", re_strip_sid(cand["case_name"]))
        if cand["record_id"] in state["records"]:
            plans["skip"].append({**cand, "why_reason": f"执行记录已消费→{state['records'][cand['record_id']]['bug']}"})
            continue
        hit = idx.get(norm(cand["title"]))
        if hit:
            plans["merge"].append({**cand, "bug": hit.get("id"),
                                   "why_reason": "同一缺陷实体（标题归一化相同）"})
        else:
            plans["create"].append(cand)

    # 关闭建议：同用例有未关闭缺陷，且 SUCCESS 晚于该缺陷登记时刻
    close_hints = []
    succ_at: dict[str, int] = {}
    for r in cls["success"]:
        for key in (str(r["case_id"]), str(r.get("case_num") or "")):
            if key:
                succ_at.setdefault(key, r.get("exec_time") or 0)
    # 缺陷登记时刻：取消费账里该 bug 第一条记录的时间（毫秒）
    reg_at: dict[str, int] = {}
    for meta in state["records"].values():
        ts = int(datetime.fromisoformat(meta["at"]).timestamp() * 1000) if meta.get("at") else 0
        reg_at[meta.get("bug", "")] = max(reg_at.get(meta.get("bug", ""), 0), ts)
    for row in rows:
        v = row_values(row)
        if v.get(F["status"]) == "closed":
            continue
        ms_ids = {x.strip() for x in str(v.get(F["ms"], "")).replace("，", ",").split(",") if x.strip()}
        later = [k for k in ms_ids if k in succ_at and succ_at[k] > reg_at.get(row.get("id"), 0)]
        if later:
            close_hints.append({"bug": row.get("id"), "case": sorted(later),
                                "why": "该用例在缺陷登记之后出现了 SUCCESS 执行记录"})

    for c in plans["create"]:
        print(f"\n+ 新建 {next_bug_id(rows)}｜{c['title']}")
        print(f"  发现版本={args.found} 规格={c.get('specs') or args.specs} 严重度={c.get('severity', args.severity)}"
              f" 来源={c.get('source', 'test')}")
        print(f"  MS用例={c.get('ms') or c.get('case_num')}｜证据={c.get('evidence', '')[:80] or c.get('detail', '')[:80]}")
    for c in plans["merge"]:
        print(f"\n~ 合并到 {c['bug']}｜{c['title']}（追加 MS 用例 {c.get('ms') or c.get('case_num')}，复现 +1）")
    for c in plans["skip"]:
        print(f"\n= 跳过｜{c['title'][:56]}（{c['why_reason']}）")
    for hint in close_hints:
        print(f"\n✎ 可关闭 {hint['bug']}｜用例 {hint['case']} 已 SUCCESS —— 需人确认："
              f"--close {hint['bug']} --confirm-close --reason <依据>")

    if args.dry_run:
        print("\n（dry-run：未写看板）")
        if args.json:
            print(json.dumps({"create": plans["create"], "merge": plans["merge"],
                              "skip": plans["skip"], "close_hints": close_hints,
                              "pending": cls["pending"]}, ensure_ascii=False, indent=1))
        return 0

    # ── 真写 ──
    written = 0
    for cand in plans["create"]:
        bug_id = next_bug_id(rows)
        expect = build_row(bug_id, cand, args.found, cand.get("specs") or args.specs,
                           cand.get("severity", args.severity), 1)
        if cand.get("evidence") and cand.get("scope") != "manual":
            expect[F["evidence"]] = cand["evidence"] + "\n" + expect[F["evidence"]]
        if cand.get("rest"):
            expect[F["rest"]] = cand["rest"]
        if cand.get("source"):
            expect[F["source"]] = cand["source"]
        if cand.get("ms"):
            expect[F["ms"]] = cand["ms"]
        result, raw = tf_write("POST", f"/api/agent/tables/{BUG_TABLE}/rows/{bug_id}",
                               {"values": expect})
        print(f"\n写 {bug_id}：{result} {json.dumps(raw, ensure_ascii=False)[:120]}")
        if result != "success":
            print("  ✗ 写接口未返回 success，不登记消费记录")
            continue
        ok, diff = readback(bug_id, expect)
        print(f"  读回：{'一致' if ok else '不一致'}")
        for d in diff:
            print(f"    ⚠️ {d}")
        if ok:
            state["records"][cand["record_id"]] = {"bug": bug_id, "at": datetime.now().isoformat(timespec="seconds")}
            rows = bug_rows()
            written += 1
    for cand in plans["merge"]:
        row = next((r for r in rows if r.get("id") == cand["bug"]), None)
        v = row_values(row)
        ms_ids = [x.strip() for x in str(v.get(F["ms"], "")).replace("，", ",").split(",") if x.strip()]
        new_ms = cand.get("ms") or str(cand.get("case_num") or "")
        if new_ms and new_ms not in ms_ids:
            ms_ids.append(new_ms)
        repro = str(v.get(F["evidence"], "")).count("【复现】") + 1
        evidence = (v.get(F["evidence"]) or "") + f"\n【复现】再次出现：MS {new_ms}（{cand['record_id']}）"
        result, raw = tf_write("PATCH", f"/api/agent/tables/{BUG_TABLE}/rows/{cand['bug']}",
                               {"values": {F["ms"]: ",".join(ms_ids), F["evidence"]: evidence}})
        print(f"\n合并 {cand['bug']}：{result}（MS 用例 {','.join(ms_ids)}，复现 {repro} 次）")
        if result == "success":
            state["records"][cand["record_id"]] = {"bug": cand["bug"], "at": datetime.now().isoformat(timespec="seconds")}
            rows = bug_rows()
            written += 1
    save_consumed(state)
    print(f"\n汇总：新写/合并 {written} 行｜跳过 {len(plans['skip'])}｜待判定 {len(cls['pending'])}"
          f"｜消费记录存 {CONSUMED}")
    if args.json:
        print(json.dumps({"created": plans["create"], "merged": plans["merge"],
                          "skipped": plans["skip"], "close_hints": close_hints},
                         ensure_ascii=False, indent=1))
    return 0


def re_strip_sid(name: str) -> str:
    """缺陷标题：去掉用例的 S<n>.<m>/NNN-US-AS 前缀，保留现象描述。"""
    parts = (name or "").split(" ", 1)
    return parts[1] if len(parts) == 2 else (name or "")


if __name__ == "__main__":
    raise SystemExit(main())
