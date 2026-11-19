---
name: ft-status
description: "只读报告tableflow看板某版本距离发布还差什么：按board@3四表契约（版本/独立规格需求/依赖需求/缺陷）逐条列出未满足的闸门、原因与对应行，给出可后移候选与拆版方案，并点出看板计算字段与契约的偏差；三表项目明确提示未迁移而不是当0。触发词：ft_status、版本状态、能不能发、发布条件、差什么、拆版、版本差距、Bug闸门。"
---

# ft_status：这个版本还差什么，能不能发

输入一个版本号，输出一份**只读**报告：结论（可发/不可发/无法完整判定）→ 四项逐项判定（独立需求是否完成、依赖需求是否完成、上一版本Bug是否清空、发布条件）→ 每个未满足项逐行说清"差哪一步" → 看板口径偏差与数据异常 → 拆分建议。

**只读是硬承诺**：全程只发`GET`，不碰`/api/agent/*`，不改`发布状态`、`验收状态`、版本关联。需要动作时只给命令，不代跑。

## 何时用

- 发布前问"这版能不能发、还差什么"。
- 版本范围太大，问"哪几行可以挪到下一个版本"。
- 怀疑看板的`发布条件`不可信，要按契约口径复算一遍。
- 项目刚升契约（三表→四表）或字段漂移（`demo`、`demo-im`等）时，要能出报告而不是报错。

## 何时不用

- 登记需求、开变更单 → `tf-update`技能。
- 改数据、推进回归、置验收 → 人工或发布流程。
- 实现/修复计算口径 → 010的需求范围。

## 口径（唯一来源`specs/017-bug-relation/board@3.yaml`）

| 闸门 | 契约规则 | 判定字段 | 空集 |
|---|---|---|---|
| 独立需求就绪 | `rollup(ver.specs, spec.acceptance, all == accepted)` | 规格行的`验收状态` | 真（本版无此类工作） |
| 依赖需求就绪 | `rollup(ver.changes, change.regress, all == passed)` | 变更单的`回归状态` | 真（本版无变更单） |
| 上一版本Bug是否清空 | `rollup(ver.bugs, bug.status, all == closed)` | 版本行`Bug管理`挂的缺陷 | 真（本版无缺陷要清） |
| 发布条件 | `and(三项布尔)` | 客户端重算 | — |

三条口径要点（都来自board@3，别自己发挥）：

- **上一版本**＝版本号按`v<主>.<次>.<修>`语义序严格小于当前版本的最大版本；不看发布时间、不看发布状态。
- **挂接方向是 ver→bug**：版本行的`Bug管理`列出本版需清零的缺陷；缺陷表的`发现版本号`只是文本来源，不反向持有关系。
- **缺陷表缺失不等于0**：缺「缺陷」表的项目，Bug闸门按**未启用**处理，发布条件只能给出"无法完整判定"。

闸门值由本技能在客户端按契约重算；看板同名计算字段的值只作对照列在报告里，**不作判据**。

## 连接

```bash
export TF_BASE=http://localhost:8090   # 实例地址
export TF_PROJECT=tableflow                # 项目 id
export FT_VERSION=v0.6.0                   # 目标版本；留空则按规则自动选当前版本
export FT_JSON=0                           # 1 则输出同结构 JSON（给 Agent 用）
```

版本选择规则（`FT_VERSION`为空时）：取"版本号大于已发布最大版本的最小`planned`版本"；没有则取最小`planned`；再没有就`failed`，不猜。版本号允许不带`v`前缀（存量项目常见`7.0.2`这种写法）。

## 一条命令出报告

```bash
python3 - "$FT_VERSION" <<'PY'
import json, os, re, sys, urllib.request

BASE = os.environ["TF_BASE"].rstrip("/")
PROJECT = os.environ.get("TF_PROJECT", "tableflow")
WANT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] not in ("", "-") else None
AS_JSON = os.environ.get("FT_JSON") == "1"

CONTRACT = {
    "ver": [("version", "版本号"), ("release_date", "发布时间"), ("gate", "发布条件"),
            ("release_status", "发布状态"), ("specs", "独立需求管理"), ("spec_ratio", "独立需求已完成/总数"),
            ("spec_done", "独立需求是否完成"), ("changes", "依赖需求管理"), ("change_ratio", "依赖需求已完成/总数"),
            ("change_done", "依赖需求是否完成"), ("bugs", "Bug管理"), ("bug_ratio", "上一版本Bug已修复/总数"),
            ("bug_clear", "上一版本Bug是否清空"), ("owner", "负责人"), ("note", "变更说明")],
    "indep": [("id", "编号"), ("clause", "条款"), ("dir", "规格目录"), ("scenes", "场景数"), ("tasks", "任务总数"),
              ("implement", "speckit-implement状态"), ("acceptance", "验收状态"), ("owner", "负责人")],
    "dep": [("id", "编号"), ("clause", "条款"), ("spec", "关联的独立规格需求"), ("impact", "影响面"),
            ("regress", "回归状态"), ("evidence", "证据"), ("rest", "剩余事项"), ("spec_revision", "规格修订")],
    "bug": [("id", "编号"), ("title", "标题"), ("status", "状态"), ("severity", "严重度"), ("source", "来源"),
            ("specs", "关联规格"), ("found_version", "发现版本号"), ("evidence", "证据"),
            ("rest", "剩余事项"), ("ms_case", "MS用例号"), ("owner", "负责人")],
}
# 存量项目字段命名（board@2之前的叫法），按语义键兜底解析
# board@2/board@1 时代的旧名，仍按语义键兜底解析（存量项目已迁到 board@3，保留以防漏迁）
ALIAS = {"ver": {"specs": ["需求关联（独立）", "独立需求关联"], "changes": ["需求关联（依赖）", "依赖需求关联"],
                 "bug_clear": ["Bug已清空"], "spec_done": ["独立需求就绪"], "change_done": ["依赖需求就绪"],
                 "bug_ratio": ["上一版本Bug总数"]}}
RULES = {
    "spec_done": "rollup(ver.specs, spec.acceptance, all == accepted)",
    "change_done": "rollup(ver.changes, change.regress, all == passed)",
    "bug_clear": "rollup(ver.bugs, bug.status, all == closed)",
    "gate": "and(ver.spec_done, ver.change_done, ver.bug_clear)",
}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as resp:
        return json.loads(resp.read().decode())


def load(project):
    tables = get(f"/api/projects/{project}/tables")["tables"]
    by_name = {t["name"]: t["id"] for t in tables}
    ids = {}
    for key, name, suffix in (("ver", "版本管理", "-ver"), ("indep", "独立规格需求", "-indep"),
                              ("dep", "依赖变更需求", "-dep"), ("bug", "缺陷", "-bug")):
        ids[key] = by_name.get(name) or next((t["id"] for t in tables if t["id"].endswith(suffix)), None)
    if not ids["ver"] or not ids["indep"] or not ids["dep"]:
        raise SystemExit("[ft-status] 项目缺版本/独立规格需求/依赖需求表，无法出报告")
    return ids, {k: (get(f"/api/tables/{ids[k]}/table") if ids[k] else None) for k in ids}


def resolve(table_data, table):
    if table_data is None:
        return {}, [], {}, [], None
    by_name = {f["name"]: f["id"] for f in table_data["fields"]}
    by_id = {f["id"]: f for f in table_data["fields"]}
    sem, missing, alias, used = {}, [], {}, set()
    for key, name in CONTRACT[table]:
        fid = by_name.get(name)
        if not fid:
            for alt in ALIAS.get(table, {}).get(key, []):
                if alt in by_name:
                    fid = by_name[alt]
                    alias[key] = alt
                    break
        if fid:
            sem[key] = fid
            used.add(fid)
            used.add(by_id[fid]["name"])
        else:
            missing.append(name)
    extra = [f["name"] for f in table_data["fields"]
             if f["name"] not in used and f["type"] != "computed" and f["name"] != "编号"]
    return sem, missing, alias, extra, table_data


def semver(text):
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", text or "")
    return tuple(int(x) for x in m.groups()) if m else (999, 999, 999)


def value(row, sem, key):
    fid = sem.get(key)
    return row["values"].get(fid) if fid else None


def show(v):
    return ("true" if v else "false") if isinstance(v, bool) else v


def pick_version(rows, sem):
    rel = [r for r in rows if value(r, sem, "release_status") == "released"]
    rel_max_id = max((r["id"] for r in rel), key=semver, default=None)
    rel_max = semver(rel_max_id) if rel_max_id else None
    planned = [r for r in rows if value(r, sem, "release_status") == "planned"]
    if WANT:
        hit = [r for r in rows if r["id"] == WANT]
        if not hit:
            raise SystemExit(f"[ft-status] 版本不存在：{WANT}")
        return hit[0], rel_max, rel_max_id, planned
    newer = [r for r in planned if rel_max is None or semver(r["id"]) > rel_max]
    if newer:
        return min(newer, key=lambda r: semver(r["id"])), rel_max, rel_max_id, planned
    if planned:
        return min(planned, key=lambda r: semver(r["id"])), rel_max, rel_max_id, planned
    raise SystemExit("[ft-status] 没有 planned 版本，无法给出当前版本")


def spec_reason(impl, acc):
    if acc == "rejected":
        return "验收被拒（acceptance=rejected）：改实现与条款后重验"
    if impl == "done" and acc == "pending":
        return "只差验收确认：implement=done，置 acceptance=accepted 即可"
    if impl == "todo":
        return "未开始实现（implement=todo）：须先 implement=done，再置 acceptance=accepted"
    if impl == "doing":
        return "已开始未完成（implement=doing）：做完并置 implement=done，再置 acceptance=accepted"
    return f"实现状态未知（implement={impl}）：先补 implement 再判验收"


def dep_reason(regress):
    return {
        "todo": "未合入（regress=todo）：先合入再验证",
        "doing": "已合入待验（regress=doing）：补验证后置 passed",
        "failed": "回归不通过（regress=failed）：修复后重验",
        "na": "枚举越界（regress=na）：契约已删除 na，确认不受影响也记 passed 并把理由写进影响面",
    }.get(regress, f"回归状态未知（regress={regress}）")


def bug_gate(bug_data, sem_bug, current, sem_ver):
    """board@3：版本行的 Bug管理 直接持有本版需清零的缺陷，不再按“上一版本”反查。"""
    if bug_data is None:
        return {"state": "not_migrated", "value": None,
                "detail": "该表未迁移到board@3（项目缺「缺陷」表），Bug闸门按未启用处理"}
    if not sem_bug.get("status"):
        return {"state": "unknown", "value": None,
                "detail": "缺陷表缺字段：状态，Bug闸门无法判定"}
    if not sem_ver.get("bugs"):
        return {"state": "unknown", "value": None,
                "detail": "版本表没有 `Bug管理` 字段，Bug闸门无法判定"}
    rel = value(current, sem_ver, "bugs") or []   # 字段存在但没填 = 本版未挂缺陷 = 空集
    by_id = {b["id"]: b for b in bug_data["rows"]}
    ids = [i for i in rel if i in by_id]
    open_bugs = [by_id[i] for i in ids if value(by_id[i], sem_bug, "status") != "closed"]
    detail = f"本版需清零缺陷 {len(ids)} 个，未 closed {len(open_bugs)} 个"
    if not rel:
        detail = "本版未挂缺陷（集合为空，空集为真）"
    return {"state": "ok", "value": not open_bugs, "total": len(ids),
            "open": [{"id": b["id"], "status": value(b, sem_bug, "status"),
                      "severity": value(b, sem_bug, "severity"),
                      "title": value(b, sem_bug, "title")} for b in open_bugs],
            "detail": detail}


ids, data = load(PROJECT)
sem, missing, alias, extra = {}, {}, {}, {}
for t in ("ver", "indep", "dep", "bug"):
    sem[t], missing[t], alias[t], extra[t], _ = resolve(data[t], t)

current, rel_max, rel_max_id, planned = pick_version(data["ver"]["rows"], sem["ver"])
cur = current["id"]
spec_ids = value(current, sem["ver"], "specs") or []
change_ids = value(current, sem["ver"], "changes") or []
indep_by_id = {r["id"]: r for r in data["indep"]["rows"]}
dep_by_id = {r["id"]: r for r in data["dep"]["rows"]}
dangling_specs = [i for i in spec_ids if i not in indep_by_id]
dangling_changes = [i for i in change_ids if i not in dep_by_id]
specs = [indep_by_id[i] for i in spec_ids if i in indep_by_id]
changes = [dep_by_id[i] for i in change_ids if i in dep_by_id]

spec_gap, change_gap = [], []
for r in specs:
    impl, acc = value(r, sem["indep"], "implement"), value(r, sem["indep"], "acceptance")
    if acc != "accepted":
        spec_gap.append({"id": r["id"], "implement": impl, "acceptance": acc, "need": spec_reason(impl, acc)})
for r in changes:
    reg = value(r, sem["dep"], "regress")
    if reg != "passed":
        change_gap.append({"id": r["id"], "regress": reg, "need": dep_reason(reg),
                           "impact": (value(r, sem["dep"], "impact") or "")[:50]})
bug = bug_gate(data["bug"], sem["bug"], current, sem["ver"])

spec_done = not spec_gap and not dangling_specs
change_done = not change_gap and not dangling_changes
gate = (spec_done and change_done and bug["value"]) if bug["value"] is not None else None

notes = {r["id"] for r in specs}
edges = {}
for r in specs:
    text = value(r, sem["indep"], "clause") or ""
    refs = set(re.findall(r"\b\d{3}-AR\b", text))
    for marker in re.findall(r"(?:依赖|前置)([^。；]*)", text):
        refs.update(m + "-AR" for m in re.findall(r"(?<!\d)(\d{3})(?!\d)", marker))
    edges[r["id"]] = sorted(x for x in refs if x in notes and x != r["id"])
inbound = {i: sum(1 for refs in edges.values() if i in refs) for i in notes}
candidates = [r["id"] for r in specs
              if value(r, sem["indep"], "implement") == "todo"
              and value(r, sem["indep"], "acceptance") != "accepted"]
keep_a = sorted(i for i in notes if inbound[i] > 0)
move_a = sorted(notes - set(keep_a))
newer = sorted((r for r in planned if semver(r["id"]) > semver(cur)), key=lambda r: semver(r["id"]))
next_ver = newer[0]["id"] if newer else None

drift = []
for t in ("ver", "indep", "dep", "bug"):
    if missing[t]:
        drift.append(f"`{t}`表缺契约字段：{'、'.join(missing[t])}")
if alias["ver"]:
    drift.append("`ver`表字段名与契约不同（按语义解析）：" + "、".join(f"{k}→{v}" for k, v in alias["ver"].items()))
for t in ("ver", "indep", "dep", "bug"):
    if extra[t]:
        drift.append(f"`{t}`表存在契约外字段：{'、'.join(extra[t])}")

ver_fields = {f["id"]: f for f in data["ver"]["fields"]}
cond = ver_fields.get(sem["ver"].get("gate"))
if cond and (cond.get("options") or {}).get("kind") == "and":
    parts = []
    for c in cond["options"].get("conditions", []):
        parts.append(f"{ver_fields.get(c['field_id'], {}).get('name', c['field_id'])}={show(c.get('equals'))}")
    drift.append(f"`发布条件`看板条件为 [{'、'.join(parts)}]，契约应为 [独立需求是否完成、依赖需求是否完成、上一版本Bug是否清空]")
dep_regress = next((f for f in data["dep"]["fields"] if f["id"] == sem["dep"].get("regress")), None)
if dep_regress and "na" in [o["value"] for o in (dep_regress.get("options") or [])]:
    drift.append("`回归状态`枚举含 `na`，契约已删除该值（确认不受影响记 passed）")
if bug["state"] in ("ok", "no_prev"):
    found = next((f for f in data["bug"]["fields"] if f["name"] == "发现版本号"), None)
    if found is None or found.get("type") != "text":
        drift.append("缺陷表的版本来源应为文本`发现版本号`；当前不是，检查是否残留 relation")

anomalies = []
if rel_max is not None:
    rel_text = rel_max_id
    for r in planned:
        if semver(r["id"]) <= rel_max:
            anomalies.append(f"`{r['id']}`状态为 planned，但版本号小于已发布最大版本 `{rel_text}`")
if bug["state"] == "ok" and data["bug"]["rows"] == []:
    anomalies.append("缺陷表为空：若已有未登记缺陷，Bug闸门会失真")

report = {
    "project": PROJECT, "version": cur,
    "selection": "显式指定" if WANT else "大于已发布最大版本的最小 planned",
    "released_max": rel_max_id,
    "tables": {k: ids[k] for k in ids},
    "contract": "board@3",
    "gates": {
        "spec_done": {"value": spec_done, "rule": RULES["spec_done"], "field": sem["indep"].get("acceptance"),
                       "blocking": [g["id"] for g in spec_gap], "dangling": dangling_specs, "empty": not spec_ids},
        "change_done": {"value": change_done, "rule": RULES["change_done"], "field": sem["dep"].get("regress"),
                         "blocking": [g["id"] for g in change_gap], "dangling": dangling_changes, "empty": not change_ids},
        "bug_clear": {"value": bug["value"], "rule": RULES["bug_clear"], "state": bug["state"],
                      "prev": bug.get("prev"), "total": bug.get("total"), "open": bug.get("open", []),
                      "detail": bug["detail"], "field": sem["bug"].get("found")},
        "gate": {"value": gate, "rule": RULES["gate"],
                 "board_field": sem["ver"].get("gate"), "board_value": value(current, sem["ver"], "gate")},
    },
    "gap_rows": {"spec": spec_gap, "change": change_gap, "bug": bug.get("open", [])},
    "drift": drift, "anomalies": anomalies,
    "split": {"edges": {k: v for k, v in edges.items() if v}, "inbound": inbound, "candidates": candidates,
              "plan_a": {"keep": keep_a, "move": move_a},
              "plan_b": {"keep": [], "move": sorted(notes), "note": "整版后移"},
              "next_version": next_ver},
    "readonly": "仅 GET /api/projects/* 与 /api/tables/*；未调用 /api/agent/*",
}

if AS_JSON:
    print(json.dumps(report, ensure_ascii=False, indent=1))
    raise SystemExit(0)

mark = lambda flag: "是" if flag else "**否**"
bug_mark = {"ok": None, "no_prev": None, "not_migrated": "未启用", "unknown": "无法判定"}
print(f"# 版本状态报告：{PROJECT} / {cur}\n")
print(f"> 数据源：`GET {BASE}/api/tables/{{{','.join(ids[k] for k in ids if ids[k])}}}/table`（只读，未调用 `/api/agent/*`）")
print(f"> 口径：`specs/017-bug-relation/board@3.yaml`（四表）；版本选择：{report['selection']}；已发布最大版本：{report['released_max'] or '无'}\n")
blocked = len(spec_gap) + len(change_gap) + len(bug.get("open", []))
if gate is None:
    head = f"**无法完整判定**：{bug['detail']}"
elif gate:
    head = "**可发布**：三项就绪同时为真"
else:
    head = f"**不可发布**：未满足项 {sum([not spec_done, not change_done, not (bug['value'] is True)])} 项，阻塞 {blocked} 行"
print("## 结论\n")
print(head + "\n")
print("| 闸门 | 契约规则 | 判定 | 依据 |")
print("|---|---|---|---|")
print(f"| 独立需求就绪 | `{RULES['spec_done']}` | {mark(spec_done)} | {len(spec_gap)}/{len(specs)} 行未 accepted（`{sem['indep'].get('acceptance')}`）{'；空集：本版无此类工作' if not spec_ids else ''} |")
print(f"| 依赖需求就绪 | `{RULES['change_done']}` | {mark(change_done)} | {len(change_gap)}/{len(changes)} 行未 passed（`{sem['dep'].get('regress')}`）{'；空集：本版无变更单' if not change_ids else ''} |")
if bug["value"] is None:
    bug_cell = bug_mark.get(bug["state"], "无法判定")
else:
    bug_cell = mark(bug["value"])
print(f"| 上一版本Bug是否清空 | `{RULES['bug_clear']}` | {bug_cell} | {bug['detail']} |")
if gate is None:
    print(f"| 发布条件 | `{RULES['gate']}` | 无法完整判定 | Bug闸门未启用，只能给两项就绪的结论 |\n")
else:
    print(f"| 发布条件 | `{RULES['gate']}` | {mark(gate)} | 客户端按契约重算；看板字段 `{sem['ver'].get('gate')}`={show(value(current, sem['ver'], 'gate'))} |\n")

print("## 距离发布还差什么\n")
if not spec_gap and not change_gap and not bug.get("open"):
    avail = "两项就绪" if bug["value"] is None else "三项就绪"
    tail = "（Bug闸门未启用，不能据此判定可发布）" if bug["value"] is None else ""
    print(f"- {avail}均未发现未满足行。{tail}\n")
else:
    if spec_gap or dangling_specs:
        print(f"### 独立需求就绪：{len(spec_gap)} 行未 accepted\n")
        print("| 行 | implement | acceptance | 还差什么 |")
        print("|---|---|---|---|")
        for g in spec_gap:
            print(f"| {g['id']} | {g['implement']} | {g['acceptance']} | {g['need']} |")
        if dangling_specs:
            print(f"\n悬空关联：{'、'.join(dangling_specs)}（目标行已不存在，按契约不得视为达标）")
        print()
    if change_gap or dangling_changes:
        print(f"### 依赖需求就绪：{len(change_gap)} 行未 passed\n")
        print("| 行 | regress | 影响面摘要 | 还差什么 |")
        print("|---|---|---|---|")
        for g in change_gap:
            print(f"| {g['id']} | {g['regress']} | {g['impact']} | {g['need']} |")
        if dangling_changes:
            print(f"\n悬空关联：{'、'.join(dangling_changes)}")
        print()
    if bug.get("open"):
        print(f"### 上一版本Bug是否清空：{len(bug['open'])} 个缺陷未 closed\n")
        print("| 缺陷 | 状态 | 严重度 | 标题 |")
        print("|---|---|---|---|")
        for b in bug["open"]:
            print(f"| {b['id']} | {b['status']} | {b['severity']} | {b['title']} |")
        print()
    if not change_ids:
        print("依赖需求就绪：本版未关联变更单，空集判真（含义是「本版无此类工作」，不是「已回归」）。\n")
    if not spec_ids:
        print("独立需求就绪：本版未关联规格，空集判真（含义是「本版无此类工作」）。\n")

if bug["state"] == "not_migrated":
    print("### 上一版本Bug是否清空：未启用\n")
    print(f"- {bug['detail']}")
    print("- 迁移到board@3（补`<前缀>-bug`表，并在版本行用`Bug管理`挂本版需清零的缺陷）后，本闸门才会参与发布判定。\n")
elif bug["state"] == "unknown":
    print("### 上一版本Bug是否清空：无法判定\n")
    print(f"- {bug['detail']}\n")

print("## 看板口径偏差（010落地前）\n")
for line in drift:
    print(f"- {line}")
print("\n> 以本报告的契约口径为准；看板同名字段仅作对照。\n")
print("## 数据异常\n")
print("\n".join(f"- {line}" for line in anomalies) if anomalies else "- 无")
print()
print("## 拆分建议（参考，不写看板）\n")
print("引用关系（从`条款`文本抽取同版规格编号）：")
shown = [f"- {k} → {'、'.join(v)}" for k, v in sorted(edges.items()) if v]
print("\n".join(shown) if shown else "- 无引用")
print(f"\n被引用次数：{'、'.join(f'{k}={inbound[k]}' for k in sorted(inbound)) or '—'}")
print(f"\n可后移候选（未开工且未 accepted）：{'、'.join(candidates) if candidates else '无'}\n")
print(f"- 方案A「保被依赖者」：保留 {'、'.join(keep_a) or '无'}，移出 {'、'.join(move_a) or '无'}")
print(f"- 方案B「整版后移」：保留 无，移出 {'、'.join(sorted(notes)) or '无'}（发布条件会因空集变真，但那是「无待办」不是「已交付」，空发须人确认）")
print(f"- 下一版本：{next_ver or '无（需新建 planned 版本，由人确认）'}")
rest = len(set(keep_a) & {g['id'] for g in spec_gap})
print(f"- 迁版不改变本版闸门结论：方案A 移出后剩余阻塞行 {rest} 行；要「可发」须把阻塞行全部处理或全部移出。")
PY
```

脚本按字段名解析（契约名，兼容存量叫法），只调`GET`；`FT_JSON=1`时输出与Markdown同结构的JSON。

复现时直接从本文件抽取脚本执行：

```bash
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash
```

## 报告怎么读

1. **结论行**：`可发布`／`不可发布`／`无法完整判定`。第三种只在项目未迁移到board@3（缺缺陷表）或版本行缺`Bug管理`时出现，**不要**把它读成"可发"或"不可发"。
2. **四项判定**：三项就绪 + 发布条件，每项给契约规则原文、判定与依据字段；空集项标注"本版无此类工作"。
3. **距离发布还差什么**：逐行给`行 id / 字段现值 / 还差什么`；Bug闸门列出未closed的缺陷（编号/状态/严重度/标题）。
4. **看板口径偏差**：缺字段、存量叫法、契约外字段、`发布条件`条件集差异、`回归状态`含`na`。
5. **数据异常**：`planned`版本号小于已发布版本、缺陷表为空、版本行没有Bug字段值等。
6. **拆分建议**：依赖边、被引用次数、可后移候选、方案A/B、下一版本。

## 原因话术表（判定与解释共用）

| implement | acceptance | 还差什么 |
|---|---|---|
| todo | pending | 未开始实现 → 先implement=done → 再accepted |
| doing | pending | 已开始未完成 → 同上 |
| done | pending | 只差验收确认 |
| 任意 | rejected | 验收被拒 → 改实现与条款后重验 |

| regress | 还差什么 |
|---|---|
| todo | 未合入 → 先合入再验证 |
| doing | 已合入待验 → 补验证后置passed |
| failed | 回归不通过 → 修复后重验 |
| na | 枚举越界（契约已删除）→ 确认不受影响记passed |

| bug.status | 还差什么 |
|---|---|
| open | 待修 |
| fixing | 修复中 |
| verifying | 已修待验 → 验证通过后置closed |
| closed | 已关闭（完成判据，唯一终态） |

## 拆分建议规则

- 依赖边：从每条规格的`条款`文本里抽同版其他规格编号（形如`008-AR`，以及"依赖008与010"这类简写）；抽不到就报"无引用"，不猜。
- 可后移候选 = 本版里`implement=todo`且`acceptance≠accepted`的行。
- 方案A（保被依赖者）：保留被同版其他行引用的行，移出其余。
- 方案B（整版后移）：全部移出。注意空集语义——版本变空后`发布条件`会变真，那只是"无待办"，不是"已交付"。
- 下一版本：版本号大于当前的最小`planned`版本；没有就提示"需新建planned版本，由人确认"。
- 结尾必须说明：迁版不改变本版闸门结论，只是缩小范围。

## 常见坑

| 坑 | 说明 |
|---|---|
| 三表项目当四表跑 | 缺`<前缀>-bug`时Bug闸门报"未启用"、结论"无法完整判定"，不报错也不当0 |
| 缺陷表为空就当"没缺陷" | 空集合按契约确实为真，但若缺陷没登记，闸门会偏低；报告会单列"缺陷表为空"的数据异常 |
| 用缺陷反查版本 | 方向是 ver→bug：看版本行的`Bug管理`；缺陷的`发现版本号`只是文本，不反向持有 |
| 把看板`发布条件`当结论 | 它可能仍是旧口径（开发进度/文档状态等）；本报告按契约三项就绪重算 |
| 空集读成"已回归" | 空集为真含义是"本版无此类工作" |
| 硬编码字段id | 各项目字段id不同，必须按契约字段名解析；缺字段要标出而不是当满足 |
| 悬空关联当达标 | 版本关联指向已删除行时，按契约"悬空不得视为达标"判否 |
| 报告完顺手改数据 | 本技能只读；要改给命令，人确认后由`tf-update`或人工执行 |

## 实跑记录

`specs/015-ft-status/runbook.md`：`tableflow`（四表，报出Bug闸门）与`demo`（三表，未迁移提示）两份真实输出，命令与输出可逐条复现。
