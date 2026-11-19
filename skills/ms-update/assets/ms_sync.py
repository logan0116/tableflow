#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ms_sync.py —— ms-update skill 的执行体：spec 场景 → MS 功能用例 + 测试计划。

真源是 `specs/<feature>/spec.md` 的「User Story / Acceptance Scenarios」；
MeterSphere 是派生。改 spec 后重跑本脚本，不在 MS 里手改用例。

一场景一用例（三条铁律，全部实测）：
  - 用例名 = `<规格号>-US<故事号>-AS<场景号> <Then 摘要>`，**场景号保留**，以便追溯与查重；
  - `steps` 必须是 **JSON 字符串**（传数组会被后端静默丢弃，落库成 `[]`）；
  - add/update 必须 **multipart**（JSON 直传报 500）。

三条纪律：
  1. **写前查重**：按 `规格号-US-AS` 前缀在目标模块内查（MS 不落 `refId`，名称前缀才是稳定幂等键）；
  2. **写后 GET 读回**：`/functional/case/detail/{id}` 逐字段核对，不信 200；
  3. **只读 spec**：不改 `specs/` 下任何文件。

计划-用例关联的实测缺口（v3.6.9-lts / 155:8081）：
  该版本**没有**关联写入端点（`batch/add`、`batch/relate`、`relate`、`association` 等 18 个候选路径全 500
  `No static resource`，见本文件 `probe_association()` 的探测清单）。因此本脚本只建计划、
  不假装关联成功：关联须在 MS 界面「计划详情 → 功能用例 → 关联用例」完成，或按
  `08-MS操控手册.md` 第五节直写 DB（需 SSH，不在本 skill 内做）。

用法（凭据来自 ms_env，绝不打印 AK/SK）：
    python3 skills/ms-update/assets/ms_sync.py                    # 预览（不写）
    python3 skills/ms-update/assets/ms_sync.py --apply            # 同步用例 + 建/复用计划
    python3 skills/ms-update/assets/ms_sync.py --specs 008 --apply
    python3 skills/ms-update/assets/ms_sync.py --report           # 只读：输出平台现状

环境变量：
    MS_TOOLS_DIR  ms_env.py 所在目录（默认 ~/PycharmProjects/demo-cnc/tools/metersphere）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# ── 常量：v0.6.0 的 spec 范围与本项目在 MS 的落点 ────────────────────────────
ROOT = Path(__file__).resolve().parents[3]          # skills/ms-update/assets → 仓库根
DEFAULT_SPECS = ("008-board-contract", "009-tf-update", "010-computation", "015-ft-status")
# 以下三项由 main() 按 --project/--version/--ms-project 覆盖，不再写死 tableflow v0.6.0
CASE_MODULE = ""                                    # 功能用例模块（新建）
PLAN_MODULE = ""                                     # 测试计划模块（新建）
PLAN_NAME = ""                                       # 测试计划名
PLAN_DESC = (
    "按 specs/008/009/010/015 的验收场景建立的回归计划。"
    "执行由 skills/ms-implement 负责：逐条跑、截图、把结果与证据回写。"
    "范围：看板三表契约（008）、tf_update 登记（009）、计算口径落地（010）、ft_status 差距报告（015）。"
)
MS_TOOLS_DEFAULT = os.path.expanduser("~/PycharmProjects/demo-cnc/tools/metersphere")
READONLY = {
    "createTime", "updateTime", "createUser", "updateUser", "createUserName", "deleted",
    "moduleName", "num", "versionId", "versionName", "latest", "lastExecuteResult",
    "bugCount", "caseCount", "commentCount", "caseReviewCount", "demandCount",
    "followFlag", "historyCount", "relateEdgeCount", "reviewStatus", "testPlanCount",
    "commentList", "attachments", "functionalPriority",
}

US_RE = re.compile(r"^###\s+User Story\s+(\d+)\s*[-—–]\s*(.*?)\s*\(Priority:\s*(P\d)\)")
AS_RE = re.compile(
    r"^(\d+)\.\s+\*\*Given\*\*\s*(.*?)\s*[，,]\s*\*\*When\*\*\s*(.*?)\s*[，,]\s*\*\*Then\*\*\s*(.*)$"
)
SEEN_BLOCK_START = re.compile(r"^\*\*Acceptance Scenarios\*\*")


# ── 1. 凭据与客户端 ─────────────────────────────────────────────────────────

def _ms_projects_map() -> dict:
    """tableflow 项目 → MS 项目 id；$MS_PROJECTS_FILE > <repo>/.ms-projects.json > ~/.config/ms/projects.json。"""
    cands = [os.environ.get("MS_PROJECTS_FILE"), str(ROOT / ".ms-projects.json"),
             os.path.expanduser("~/.config/ms/projects.json")]
    for path in cands:
        if not path:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            continue
    return {}

def load_ms(ms_project: str | None = None):
    """导入项目统一客户端 ms_env（凭据在 ms_creds.env，不打印、不外发）。"""
    tools = os.environ.get("MS_TOOLS_DIR") or MS_TOOLS_DEFAULT
    if not (Path(tools) / "ms_env.py").exists():
        raise SystemExit(f"找不到 ms_env.py：{tools}（用 MS_TOOLS_DIR 指定目录）")
    sys.path.insert(0, tools)
    from ms_env import ids, ms_client  # noqa: PLC0415

    ms = ms_client()
    pid, tid, priority_field = ids()
    return ms, (ms_project or pid), tid, priority_field


def multipart(ms, path: str, payload: dict) -> dict:
    """功能用例 add/update 只吃 multipart（request part 放 JSON 字符串）。"""
    from ms_client import sign  # noqa: PLC0415

    b = "----MSBoundary7MA4YWxkTrZu0gW"
    data = (
        f"--{b}\r\nContent-Disposition: form-data; name=\"request\"\r\n"
        "Content-Type: application/json;charset=UTF-8\r\n\r\n"
        f"{json.dumps(payload, ensure_ascii=False)}\r\n--{b}--\r\n"
    ).encode("utf-8")
    req = urllib.request.Request(
        ms.base + path, data=data, method="POST",
        headers={"accessKey": ms.ak, "signature": sign(ms.ak, ms.sk),
                 "Content-Type": f"multipart/form-data; boundary={b}",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


# ── 2. 解析 spec ────────────────────────────────────────────────────────────
def _plain(text: str) -> str:
    """去掉 Markdown 强调与反引号：MS 的 steps 只承载纯文本。"""
    return re.sub(r"\*\*|`", "", text).strip()


def summarize(then: str, when: str = "") -> str:
    """用例名摘要：取 Then 第一分句（验收结果），太短带第二分句。"""
    t = _plain(then).strip(" ，。：；")
    if not t:
        return _plain(when)[:30]
    parts = [p.strip(" ，。：；") for p in re.split(r"[，。；]", t) if p.strip()]
    seg = parts[0] if parts else t
    if len(seg) < 10 and len(parts) > 1:
        seg = f"{seg}，{parts[1]}"
    return seg[:34].strip()


def parse_spec(spec_dir: Path) -> list[dict]:
    """一份 spec.md → 用例列表（US 号、AS 号、Given/When/Then、优先级）。"""
    md = (spec_dir / "spec.md").read_text(encoding="utf-8")
    num = spec_dir.name[:3]
    out: list[dict] = []
    us_no, us_title, prio = None, "", "P1"
    for raw in md.splitlines():
        s = raw.strip()
        if m := US_RE.match(s):
            us_no, us_title, prio = m.group(1), m.group(2), m.group(3)
            continue
        if us_no and (m := AS_RE.match(s)):
            given, when, then = (_plain(m.group(2)), _plain(m.group(3)), _plain(m.group(4)))
            out.append({
                "spec": spec_dir.name, "num": num, "us": us_no,
                "us_title": us_title, "as": m.group(1), "priority": prio,
                "given": given, "when": when, "then": then,
            })
    return out


def build_case(sc: dict) -> dict:
    """一场景 → 一条用例（名称/前置条件/步骤/预期/描述/标签）。"""
    sid = f"{sc['num']}-US{sc['us']}-AS{sc['as']}"
    name = f"{sid} {summarize(sc['then'], sc['when'])}"
    src = f"specs/{sc['spec']}/spec.md#US{sc['us']}-AS{sc['as']}"
    prereq = "\n".join([
        f"【前置条件】{sc['given']}",
        f"【来源】{src}（自动生成，勿在 MS 手改；改 spec 后重跑 skills/ms-update/assets/ms_sync.py）",
        f"【验收场景】{sid} · {sc['us_title']}",
        "【环境】MeterSphere 功能用例；被测系统为 tableflow 实例（人只读、Agent 读写）",
    ])
    steps = [{"num": 1, "desc": sc["when"], "result": f"预期：{sc['then']}"}]
    esc = lambda t: (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))  # noqa: E731
    description = (
        f"<p><strong>{sid}</strong></p>"
        f"<p><strong>前置条件：</strong>{esc(sc['given'])}</p>"
        f"<p><strong>操作步骤：</strong>{esc(sc['when'])}</p>"
        f"<p><strong>预期结果：</strong>{esc(sc['then'])}</p>"
        f"<p><em>真源：{src}</em></p>"
    )
    return {
        "sid": sid, "name": name, "priority": sc["priority"],
        "prerequisite": prereq, "steps": steps, "description": description,
        "tags": [sc["num"], f"US{sc['us']}-AS{sc['as']}", sc["priority"]],
        "source": src,
    }


# ── 3. 平台查询 ─────────────────────────────────────────────────────────────
def page_cases(ms, pid: str) -> list[dict]:
    rows, page = [], 1
    while True:
        data = ms.request("POST", "/functional/case/page",
                          {"projectId": pid, "current": page, "pageSize": 100})["data"]
        rows += data["list"]
        if len(rows) >= data["total"]:
            return rows
        page += 1


def case_modules(ms, pid: str) -> list[dict]:
    return ms.request("GET", f"/functional/case/module/tree/{pid}")["data"] or []


def plans(ms, pid: str) -> list[dict]:
    data = ms.request("POST", "/test-plan/page",
                      {"projectId": pid, "type": "ALL", "current": 1, "pageSize": 100})["data"]
    return data["list"]


def plan_modules(ms, pid: str) -> list[dict]:
    return ms.request("GET", f"/test-plan/module/tree/{pid}")["data"] or []


def first_case_template(ms, pid: str, rows: list[dict]) -> str:
    """templateId 优先取项目内已有用例（响应里叫 id，不叫 templateId）。

    项目刚建、一条用例都没有时回退到项目默认用例模板
    `GET /functional/case/default/template/field/{pid}`——新建 MS 项目只有一个
    `functional_default`，不先建一条脏用例也能开张（018：独立项目首次同步）。
    """
    if rows:
        detail = ms.request("GET", f"/functional/case/detail/{rows[0]['id']}")["data"]
        tid = detail.get("templateId")
        if tid:
            return tid
    default = ms.request("GET", f"/functional/case/default/template/field/{pid}").get("data") or {}
    tid = default.get("id")
    if not tid:
        raise SystemExit("拿不到用例模板：项目内没有用例，默认模板接口也没返回 id")
    return tid


# ── 4. 用例同步（查重 → 写 → 读回） ─────────────────────────────────────────
def ensure_case_module(ms, pid: str) -> str:
    for node in case_modules(ms, pid):
        if (node.get("name") or "") == CASE_MODULE:
            return node["id"]
    resp = ms.request("POST", "/functional/case/module/add",
                      {"projectId": pid, "name": CASE_MODULE, "parentId": "NONE"})
    mid = resp.get("data")
    if not mid:
        raise SystemExit(f"建用例模块失败：{resp}")
    print(f"  + 建用例模块 {CASE_MODULE} → {mid}")
    return mid


def same_case(detail: dict, case: dict) -> bool:
    """读回比对：只比语义字段。steps 落库后会多出 id/actualResult/executeResult，
    直接比 JSON 会永远不等（第二次跑就全变成"更新"），必须归一化后比。"""
    steps = json.loads(detail.get("steps") or "[]")
    norm = [(s.get("num"), (s.get("desc") or "").strip(), (s.get("result") or "").strip())
            for s in steps]
    want = [(s["num"], s["desc"].strip(), s["result"].strip()) for s in case["steps"]]
    return (
        detail.get("name") == case["name"]
        and (detail.get("prerequisite") or "") == case["prerequisite"]
        and norm == want
        and (detail.get("tags") or []) == case["tags"]
    )


def sync_cases(ms, pid: str, template_id: str, priority_field: str,
               cases: list[dict], module_id: str, *, apply: bool) -> dict:
    rows = page_cases(ms, pid)
    scoped = [r for r in rows if r.get("moduleId") == module_id]
    by_sid: dict[str, dict] = {}
    for r in scoped:
        if m := re.match(r"^(\d{3}-US\d+-AS\d+)\s", r.get("name") or ""):
            by_sid.setdefault(m.group(1), r)

    created = updated = skipped = failed = 0
    problems: list[str] = []
    for case in cases:
        old = by_sid.get(case["sid"])
        if not apply:
            print(f"  {'~' if old else '+'} {case['name']}")
            continue
        try:
            if old:
                detail = ms.request("GET", f"/functional/case/detail/{old['id']}")["data"]
                if same_case(detail, case):
                    skipped += 1
                    continue
                base = {k: v for k, v in detail.items() if k not in READONLY and k != "customFields"}
                base.update({
                    "id": detail["id"], "projectId": pid,
                    "templateId": detail.get("templateId") or template_id,
                    "moduleId": module_id, "name": case["name"], "caseEditType": "STEP",
                    "prerequisite": case["prerequisite"],
                    "steps": json.dumps(case["steps"], ensure_ascii=False),
                    "description": case["description"], "tags": case["tags"],
                    "customFields": [{"caseId": detail["id"], "fieldId": priority_field,
                                      "value": case["priority"]}],
                })
                multipart(ms, "/functional/case/update", base)
                updated += 1
            else:
                resp = multipart(ms, "/functional/case/add", {
                    "projectId": pid, "templateId": template_id, "moduleId": module_id,
                    "refId": case["sid"], "name": case["name"], "caseEditType": "STEP",
                    "prerequisite": case["prerequisite"],
                    "steps": json.dumps(case["steps"], ensure_ascii=False),
                    "description": case["description"], "tags": case["tags"],
                    "aiCreate": False,
                })
                new_id = (resp.get("data") or {}).get("id") if isinstance(resp, dict) else None
                if not new_id:
                    raise RuntimeError(f"add 未返回 id：{str(resp)[:160]}")
                # add 不落 customFields 的 caseId 绑定，补一次 update 让优先级落库
                detail = ms.request("GET", f"/functional/case/detail/{new_id}")["data"]
                base = {k: v for k, v in detail.items() if k not in READONLY and k != "customFields"}
                base.update({
                    "id": new_id, "projectId": pid,
                    "templateId": detail.get("templateId") or template_id,
                    "moduleId": module_id, "name": case["name"], "caseEditType": "STEP",
                    "prerequisite": case["prerequisite"],
                    "steps": json.dumps(case["steps"], ensure_ascii=False),
                    "description": case["description"], "tags": case["tags"],
                    "customFields": [{"caseId": new_id, "fieldId": priority_field,
                                      "value": case["priority"]}],
                })
                multipart(ms, "/functional/case/update", base)
                created += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            problems.append(f"{case['sid']} 写入失败：{str(exc)[:180]}")
            print(f"  !! {case['name'][:48]} → {str(exc)[:140]}")

    if not apply:
        return {"planned": len(cases), "created": 0, "updated": 0, "skipped": 0, "failed": 0,
                "problems": []}

    # ── 读回核对：不信 200，只认 detail ──
    rows = page_cases(ms, pid)
    scoped = [r for r in rows if r.get("moduleId") == module_id]
    by_sid = {}
    for r in scoped:
        if m := re.match(r"^(\d{3}-US\d+-AS\d+)\s", r.get("name") or ""):
            by_sid.setdefault(m.group(1), r)
    verified = 0
    for case in cases:
        hit = by_sid.get(case["sid"])
        if not hit:
            problems.append(f"{case['sid']} 读回找不到")
            continue
        detail = ms.request("GET", f"/functional/case/detail/{hit['id']}")["data"]
        steps = json.loads(detail.get("steps") or "[]")
        bad = []
        if detail.get("name") != case["name"]:
            bad.append("名称")
        if detail.get("moduleId") != module_id:
            bad.append("模块")
        if not (detail.get("prerequisite") or "").startswith("【前置条件】"):
            bad.append("前置条件")
        if not steps or not all((s.get("desc") or "").strip() and (s.get("result") or "").strip()
                                for s in steps):
            bad.append("步骤/预期")
        if bad:
            problems.append(f"{case['sid']} 读回不符：{'/'.join(bad)}")
        else:
            verified += 1
    return {"planned": len(cases), "created": created, "updated": updated,
            "skipped": skipped, "failed": failed, "verified": verified, "problems": problems}


# ── 5. 计划（建/复用 + 关联缺口说明） ───────────────────────────────────────
def ensure_plan(ms, pid: str, *, apply: bool) -> dict:
    existing = next((p for p in plans(ms, pid) if (p.get("name") or "") == PLAN_NAME), None)
    if existing:
        return {"id": existing["id"], "created": False}
    if not apply:
        print(f"  + 建测试计划 {PLAN_NAME}（预览）")
        return {"id": None, "created": False}
    module_id = None
    for node in plan_modules(ms, pid):
        if (node.get("name") or "") == PLAN_MODULE:
            module_id = node["id"]
            break
    if not module_id:
        resp = ms.request("POST", "/test-plan/module/add",
                          {"projectId": pid, "name": PLAN_MODULE, "parentId": "NONE"})
        module_id = resp.get("data")
        print(f"  + 建计划模块 {PLAN_MODULE} → {module_id}")
    resp = ms.request("POST", "/test-plan/add", {
        "projectId": pid, "moduleId": module_id, "name": PLAN_NAME,
        "type": "TEST_PLAN", "description": PLAN_DESC, "groups": [], "testPlanning": None,
    })
    plan_id = (resp.get("data") or {}).get("id") if isinstance(resp, dict) else None
    if not plan_id:
        raise SystemExit(f"建计划失败：{str(resp)[:200]}")
    return {"id": plan_id, "created": True}


def _exc_status(exc: Exception) -> int | None:
    """尽量从客户端异常里取 HTTP 状态码；取不到返回 None，不猜。"""
    for attr in ("status", "status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    text = str(getattr(exc, "body", "") or exc)
    match = re.search(r"\b([45]\d\d)\b", text)
    return int(match.group(1)) if match else None


def probe_association(ms) -> dict:
    """关联写入端点的实测缺口：18个候选路径逐个探测，全部不可达就明确报"无API"。

    返回实际状态码与示例响应，不写死任何结论码（历史上曾把结论码写错，实测为 500）。
    """
    cands = [
        "/test-plan/functional/case/batch/add/0", "/test-plan/functional/case/batch/relate/0",
        "/test-plan/functional/case/relate/0", "/test-plan/functional/case/relate",
        "/test-plan/functional/case/add", "/test-plan/functional/case/association/0",
        "/test-plan/association/0/case", "/test-plan/association/case/0",
        "/test-plan/case/add", "/test-plan/case/relate",
        "/test-plan/functional/case/batch", "/test-plan/functional/case/batch/delete/0",
        "/test-plan/functional/case/remove/0/0", "/test-plan/functional/case/batch/remove/0",
        "/test-plan/functional/case/copy/0", "/test-plan/functional/case/batch/copy/0",
        "/test-plan/functional/case/add-case/0", "/test-plan/functional/case/association",
    ]
    alive: list[str] = []
    failures: list[dict] = []
    for path in cands:
        try:
            ms.request("POST", path, {})
            alive.append(path)
        except Exception as exc:  # noqa: BLE001
            body = str(getattr(exc, "body", "") or exc)
            if "No static resource" not in body:
                alive.append(path)
                continue
            failures.append({"path": path, "status": _exc_status(exc), "body": body[:160]})
    statuses = sorted({item["status"] for item in failures if item["status"] is not None})
    return {"candidates": len(cands), "reachable": alive, "failures": failures, "statuses": statuses}


def describe_association(api: dict) -> str:
    """把 probe_association 的结果格式化成一行（状态码来自实测，不写死）。"""
    if api["reachable"]:
        return f"可达：{api['reachable']}"
    codes = "、".join(str(code) for code in api["statuses"]) or "无HTTP状态"
    sample = api["failures"][0]["body"] if api["failures"] else ""
    return f"无（{api['candidates']}个候选全部不可达，实测状态码：{codes}；示例：{sample}）"


def plan_case_count(ms, plan_id: str) -> int:
    return ms.request("POST", "/test-plan/functional/case/page",
                      {"testPlanId": plan_id, "current": 1, "pageSize": 5})["data"]["total"]


# ── 6. CLI ──────────────────────────────────────────────────────────────────
def report(ms, pid: str, module_id: str | None) -> int:
    """只读：列出本 skill 在平台上的落点与缺口。"""
    rows = page_cases(ms, pid)
    mods = {n["id"]: n.get("name") for n in case_modules(ms, pid)}
    mine = [r for r in rows if module_id and r["moduleId"] == module_id]
    print(f"项目用例总数：{len(rows)}")
    print(f"本 skill 模块：{CASE_MODULE}｜用例 {len(mine)} 条")
    for r in sorted(mine, key=lambda x: x["name"]):
        print(f"  - {r['name']}  [{mods.get(r['moduleId'], r['moduleId'])}]  result={r.get('lastExecuteResult')}")
    pl = next((p for p in plans(ms, pid) if (p.get("name") or "") == PLAN_NAME), None)
    if pl:
        print(f"测试计划：{PLAN_NAME} → {pl['id']}｜已关联用例 {plan_case_count(ms, pl['id'])} 条")
    else:
        print(f"测试计划：{PLAN_NAME} 尚未创建")
    print("关联写入端点：", probe_association(ms))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="spec 场景 → MS 用例 + 测试计划（ms-update）")
    ap.add_argument("--project", default="tableflow", help="tableflow 项目 id（用于模块/计划命名）")
    ap.add_argument("--version", default="", help="版本号（如 v0.6.4），拼进模块与计划名")
    ap.add_argument("--module", help="功能用例模块名（默认 TF · <project> v<version>）")
    ap.add_argument("--plan-module", help="测试计划模块名（默认 TF · <project>）")
    ap.add_argument("--plan-name", help="测试计划名（默认 <project> v<version> · 契约与技能验收）")
    ap.add_argument("--ms-project", default=None, help="MeterSphere 项目 id（默认取 ms_env）")
    ap.add_argument("--specs", nargs="*", default=list(DEFAULT_SPECS),
                    help="specs/ 下的目录名（默认 008 009 010 015）")
    ap.add_argument("--apply", action="store_true", help="真正写入 MS（默认只预览）")
    ap.add_argument("--report", action="store_true", help="只读：输出平台现状")
    ap.add_argument("--json", action="store_true", help="末尾输出机器可读摘要")
    args = ap.parse_args()

    global CASE_MODULE, PLAN_MODULE, PLAN_NAME
    CASE_MODULE = args.module or (f"TF · {args.project}" + (f" {args.version}" if args.version else ""))
    PLAN_MODULE = args.plan_module or f"TF · {args.project}"
    PLAN_NAME = args.plan_name or (
        f"{args.project} {args.version} · 契约与技能验收" if args.version
        else f"{args.project} · 契约与技能验收")
    resolved_ms = args.ms_project or _ms_projects_map().get(args.project)
    ms, pid, _tid, priority_field = load_ms(resolved_ms)
    mods = [n for n in case_modules(ms, pid) if (n.get("name") or "") == CASE_MODULE]
    module_id = mods[0]["id"] if mods else None

    if args.report:
        return report(ms, pid, module_id)

    cases: list[dict] = []
    for name in args.specs:
        spec_dir = ROOT / "specs" / name
        if not (spec_dir / "spec.md").exists():
            print(f"  !! 跳过不存在的 spec：{name}")
            continue
        found = parse_spec(spec_dir)
        cases.extend(build_case(sc) for sc in found)
        print(f"  解析 {name}：{len(found)} 个验收场景")
    if not cases:
        raise SystemExit("没有可同步的用例")

    print(f"目标：模块「{CASE_MODULE}」｜计划「{PLAN_NAME}」｜用例 {len(cases)} 条"
          f"｜{'写入' if args.apply else '预览'}")
    module_id = ensure_case_module(ms, pid) if args.apply else (
        module_id or "<待建模块>")
    template_id = first_case_template(ms, pid, page_cases(ms, pid))
    stats = sync_cases(ms, pid, template_id, priority_field, cases, module_id, apply=args.apply)
    plan = ensure_plan(ms, pid, apply=args.apply)

    if args.apply:
        # 用例写完后，计划侧只有"建"是 API，可做的；关联如实报告缺口
        stats["plan"] = {"id": plan["id"], "created": plan["created"],
                         "linked_cases": plan_case_count(ms, plan["id"]) if plan["id"] else 0}
        stats["association_api"] = probe_association(ms)
        print(f"\n计划：{PLAN_NAME} → {plan['id']}"
              f"（{'新建' if plan['created'] else '复用'}）｜已关联用例 {stats['plan']['linked_cases']} 条")
        print("关联写入端点：" + describe_association(stats["association_api"]))
        print("→ 关联须在 MS 界面「计划详情 → 功能用例 → 关联用例」完成，或用 08 手册的直写 DB 法")
        print(f"\n汇总：新建 {stats['created']}｜更新 {stats['updated']}｜跳过 {stats['skipped']}"
              f"｜失败 {stats['failed']}｜读回核对通过 {stats.get('verified', 0)}/{len(cases)}")
        for p in stats["problems"]:
            print(f"  ⚠️ {p}")
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0 if not stats["failed"] and not stats["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
