---
name: tf-update
description: "把用户口述的一条需求，按board@3判定树分类（就地改/变更单/新规格/横切/不进看板）后登记到tableflow看板并挂到人明确指定的目标版本（不自动选版本）：先读看板现状与specs/*/spec.md、必须给出规格编号+场景号依据、指不到就只问一个问题、幂等且三态可辨。触发词：tf_update、需求登记、需求进看板、开变更单、挂版本、分类判定。"
---

# tf_update：口述需求 → 看板的一行（或一条明确的拒绝）

一条口述需求进来，本技能只做三件事：**判定它落在哪张表**、**把行写进去并挂到目标版本**、**回读证明它真的在了**。不做第四件：不写规格、不改验收、不猜版本。

依据唯一来源：`specs/017-bug-relation/board@3.yaml`（四表契约，取代board@2与board@1；`classify`各版一致）。其中`classify.order`是判定树，`tables.*.fields`是字段口径，`rules`是完成判定。字段按名称解析，不绑死某个项目的字段id。

## 何时用

- 用户口述一条需求，问"这算新需求还是改已有规格""要不要开变更单""挂哪个版本"。
- 需求已经明确、只差"进看板"这一步。
- 需要复核某条需求当初是按什么依据分类的。

## 何时不用

- 写规格本身（spec.md/tasks.md）→ speckit流程。
- 改验收状态、发布、回归推进 → 人工或发布流程。
- 查状态、算差什么 → `tf-status`技能。
- 建表、建字段、改计算口径 → 010/011的范围。

## 五条硬约束

| 约束 | 含义 | 违反后果 |
|---|---|---|
| 不写规格 | 不动`specs/`下任何文件 | 文档与代码脱节，规格改动绕过评审 |
| 不改验收 | 不写`验收状态`，`accepted`只能需求方给 | 完成判定失真，`就绪`闸门被污染 |
| 不猜版本 | 目标版本必须由人明确给出；没给就拒绝登记并追问，且必须晚于最近已发布版本 | 需求挂错版本，发布范围与就绪统计失真 |
| 不建结构 | 不建表、不建字段、不改计算字段配置 | 契约外的结构漂移 |
| 不删数据 | 只删自己演练建的`≥090`行 | 破坏他人关联 |

## 连接与身份

```bash
export TF_BASE=http://localhost:8090        # 实例地址
export TF_AGENT=agent-tf-ftskills               # 写接口审计身份，必带
export TF_PROJECT=tableflow                     # 目标项目 id
```

写请求统一带两个头：`X-Agent-Id: $TF_AGENT`（审计）与`X-Origin: human-request`（标记"人发起、Agent执行"）。响应三态：`success` / `failed`(400) / `unknown`(503)，**只看HTTP 200不算成功**。

## 流程总览

| 步 | 动作 | 产物 | 只读否 |
|---|---|---|---|
| 1 | 读上下文：版本表、indep行、specs场景索引 | 现状快照 | 只读 |
| 2 | 分类：走判定树，落到唯一分支 + 依据 | 分类结论 | 只读 |
| 3 | 判重：按行id + 归一化条款查已有行 | `new`/`already_registered`/`conflict` | 只读 |
| 4 | 登记：POST新行（或PATCH就地改） | 行id | 写 |
| 5 | 挂版本：校验人给的版本（planned且晚于最近已发布）后追加relation数组 | 版本关联 | 写 |
| 6 | 回读：行 + 版本各GET一次，比对四项 | `success`/`failed`/`unknown` | 只读 |

任一步失败就停在该步并报终态，不跳步、不"先写后补依据"。

## 步骤1：读上下文

```bash
# 版本表（挑选目标版本的唯一依据）
curl -s $TF_BASE/api/tables/tf-ver/table \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print([(r['id'],r['values'].get('tf-v-status'),r['values'].get('tf-v-date')) for r in d['rows']])"

# indep 行（判断"是否已覆盖""是否已 accepted"）
curl -s $TF_BASE/api/tables/tf-indep/table \
  | python3 -c "import json,sys;d=json.load(sys.stdin);[print(r['id'],r['values'].get('tf-i-implement'),r['values'].get('tf-i-acceptance'),r['values'].get('tf-i-dir')) for r in d['rows']]"
```

场景索引（分类证据的取值范围；场景号 = `### User Story`块内`**Acceptance Scenarios**`的编号）：

```bash
python3 - <<'PY'
import glob, re
for path in sorted(glob.glob("specs/*/spec.md")):
    text = open(path, encoding="utf-8").read()
    stories = re.split(r"^### User Story ", text, flags=re.M)[1:]
    total = 0
    for index, block in enumerate(stories, 1):
        title = block.splitlines()[0].split("(Priority")[0].strip()
        scenes = len(re.findall(r"^\d+\. \*\*Given\*\*", block, flags=re.M))
        total += scenes
        print(f"{path}  US{index}  AS{scenes}  {title}")
    print(f"{path}  合计 US{len(stories)} AS{total}")
PY
```

归属表：`specs/<dir>/`对应看板`tf-indep`里`规格目录`相同的行，行id即规格编号（`008-AR`）。

覆盖检索（关键词只是线索，命中行必须读原文，见「常见坑」）：

```bash
grep -rniE "关键词1|关键词2" specs/*/spec.md || echo "命中 0"
```

## 步骤2：分类（判定树唯一来源：`board@3.classify.order`）

按顺序判定，命中即停。顺序即优先级，不许跳着判。

| # | 分支 | 条件（board@3原文） | 动作 | 依据写法 |
|---|---|---|---|---|
| 1 | `in_place` | 现有规格的条款/场景已覆盖，且该规格尚未`accepted` | 改该规格的spec与indep行，不新建行 | `<规格编号>#US<n>-AS<m>` |
| 2 | `change` | 现有规格已`accepted`，需求改变其行为或验收口径 | 在dep开一行，挂被改规格 | `<规格编号>#US<n>-AS<m>`（被改的那个场景） |
| 3 | `new_spec` | 现有规格都不覆盖，需要新条款或新场景 | 在indep新增一行 | `新增条款` + 已比对过的规格编号 |
| 4 | `cross` | 一次改动横切多份已`accepted`规格 | 一张dep挂多份规格，影响面分别写清 | 每份规格各给场景号 |
| 5 | `out_of_board` | 不改变产品行为（构建/部署/环境/文档） | 不进看板，只记版本变更说明 | `不改产品行为` + 落点 |

补充规则（`board@3`明确写死的）：

- 一条需求同时"新增能力"又"改已accepted规格"：拆一条`indep`与一条`dep`，影响面互相引用。
- `change_done = regress == passed`；`regress`只有`todo/doing/passed/failed`，确认不受影响也记`passed`并把理由写进`影响面`（看板缺`证据`字段时）。
- 已`accepted`的规格冻结：再改一律开`dep`，不回头改spec。

**指不到依据时**：只问一个问题，且只问这一件：

> 这条需求要改/新增哪份规格的哪个场景？（现有001-008里没有找到覆盖它的条款）

不问版本、不问优先级、不问负责人；不建行、不改行。依据补上后再回到步骤2。

## 步骤3：判重（幂等键 = 行id + 归一化条款）

归一化 = 去掉空白与中英文标点，再逐字比较。三条结论：

| 情形 | 结论 | 动作 |
|---|---|---|
| 行不存在 | `new` | 继续步骤4 |
| 行存在、归一化条款相同 | `already_registered` | 不写，报告已有行id |
| 行存在、条款不同 | `conflict` | 报`failed`，**不覆盖** |

编号分配：`indep`取现有最大`NNN-AR`的NNN+1；`dep`沿用项目已有前缀取最大序号+1（如现有`DEP-03-BR` → `DEP-04-BR`）。演练用`≥090`保留号段，结束后删除。

## 步骤4-6：登记器（定版本 → 写行 → 挂版本 → 回读，一次跑完）

### 目标版本规则（V060-02，硬性）

目标版本**必须由人明确给出**，写进参数`version`。技能不自动选版本，也不按"最早planned"或"发布时间最早"推断。

| 情形 | 处理 |
|---|---|
| 参数里没有`version` | `failed`，输出**一条提问**"这条需求要挂到哪个版本？当前planned版本：…"，一行都不写 |
| `version`指向不存在的版本 | `failed`，列出当前planned版本，不写 |
| `version`的发布状态不是`planned` | `failed`（只能挂planned版本） |
| `version`不晚于最近一个已发布版本 | `failed`（防止把新需求挂回老版本，线上`v0.2.0`就是这种坑） |

版本校验在写行之前完成：校验不过就没有孤儿行。目标版本从口述/任务单里的人话里取，不猜；人没提版本就先问，问到了再登记。

把下面的脚本原样执行，参数是一段JSON：

两种调用（同一段脚本，改`TF_PAYLOAD`即可）：

```bash
# ① indep 新规格：kind / row_id / clause / dir / version（version必填，由人给出）
export TF_PAYLOAD='{"kind":"indep","row_id":"016-AR","clause":"<口述需求原文的归一化表述>","dir":"specs/016-xxx/","version":"v0.6.0"}'
# ② dep 变更单：kind / row_id / clause / specs / impact / version
# export TF_PAYLOAD='{"kind":"dep","row_id":"DEP-04-BR","clause":"<规格编号#US-AS 改动点>","specs":["007-AR"],"impact":"<受影响能力/接口/场景/下游>","version":"v0.6.0"}'
python3 - "$TF_PAYLOAD" <<'PY'
import json, os, re, sys, urllib.error, urllib.request

BASE = os.environ["TF_BASE"].rstrip("/")
AGENT = os.environ.get("TF_AGENT", "agent-tf-update")
PROJECT = os.environ.get("TF_PROJECT", "tableflow")


def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agent-Id", AGENT)
    req.add_header("X-Origin", "human-request")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return {"http": resp.status, **(json.loads(resp.read().decode() or "{}"))}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"error": raw[:300]}
        return {"http": exc.code, "result": "unknown" if exc.code == 503 else "failed", **payload}
    except Exception as exc:
        return {"http": 0, "result": "unknown", "error": f"{type(exc).__name__}: {exc}"}


def norm(text):
    return re.sub(r"[\s，,。；;：:、]", "", text or "")


def tables():
    data = call("GET", f"/api/projects/{PROJECT}/tables")
    by_name = {t["name"]: t["id"] for t in data["tables"]}
    out = {}
    for key, name, suffix in (("ver", "版本管理", "-ver"), ("indep", "独立规格需求", "-indep"), ("dep", "依赖变更需求", "-dep")):
        out[key] = by_name.get(name) or next((t["id"] for t in data["tables"] if t["id"].endswith(suffix)), None)
        if not out[key]:
            raise SystemExit(f"[tf-update] 项目 {PROJECT} 缺少「{name}」表")
    return out


def field_map(table_id):
    data = call("GET", f"/api/tables/{table_id}/table")
    return {f["name"]: f["id"] for f in data["fields"]}


def row_of(table_id, row_id):
    data = call("GET", f"/api/tables/{table_id}/rows/{row_id}")
    return None if data.get("http") == 404 else (data.get("row") or data)


def semver(value):
    m = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", value or "")
    return tuple(int(x) for x in m.groups()) if m else (999, 999, 999)


def resolve_version(ver_table, wanted):
    """目标版本必须由人明确给出：不自动选择；且必须晚于最近一个已发布版本。"""
    data = call("GET", f"/api/tables/{ver_table}/table")
    fields = {f["name"]: f["id"] for f in data["fields"]}
    rows = {r["id"]: r for r in data["rows"]}
    planned = sorted(r["id"] for r in data["rows"] if r["values"].get(fields.get("发布状态")) == "planned")
    released = [r["id"] for r in data["rows"] if r["values"].get(fields.get("发布状态")) == "released"]
    latest = max(released, key=semver) if released else None
    if not wanted:
        return None, data, {
            "error": "未指定目标版本，拒绝登记（不自动选择版本）",
            "question": f"这条需求要挂到哪个版本？当前 planned 版本：{'、'.join(planned) or '无'}",
            "latest_released": latest,
        }
    row = rows.get(wanted)
    if row is None:
        return None, data, {"error": f"目标版本 {wanted} 不存在", "planned": planned, "latest_released": latest}
    status = row["values"].get(fields.get("发布状态"))
    if status != "planned":
        return None, data, {"error": f"目标版本 {wanted} 的发布状态是 {status}，只能挂到 planned 版本", "latest_released": latest}
    if latest is not None and semver(wanted) <= semver(latest):
        return None, data, {"error": f"目标版本 {wanted} 不晚于最近已发布版本 {latest}，拒绝登记", "latest_released": latest}
    return row, data, None


def main():
    arg = json.loads(sys.argv[1])
    kind, row_id, clause = arg["kind"], arg["row_id"], arg["clause"]
    if kind not in ("indep", "dep"):
        raise SystemExit("[tf-update] kind 只能是 indep 或 dep")
    tabs = tables()
    table = tabs[kind]
    names = field_map(table)
    report = {"kind": kind, "row_id": row_id, "table": table, "clause": clause, "steps": []}

    # 版本先行：未指定或不合规就拒绝登记，一行都不写
    target, ver_data, version_error = resolve_version(tabs["ver"], arg.get("version"))
    if version_error:
        report.update(result="failed", **version_error)
        report["steps"].append("版本校验未通过：未写行、未挂载")
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1
    ver_names = {f["name"]: f["id"] for f in ver_data["fields"]}
    rel_field = (ver_names.get("独立需求管理") or ver_names.get("独立需求关联")
                 or ver_names.get("需求关联（独立）")) if kind == "indep" \
        else (ver_names.get("依赖需求管理") or ver_names.get("依赖需求关联")
              or ver_names.get("需求关联（依赖）"))
    report["version"] = target["id"]

    already = False
    existing = row_of(table, row_id)
    if existing:
        old = existing["values"].get(names["条款"])
        if norm(old) != norm(clause):
            report.update(result="failed", http=200, error="行 id 已被占用且条款不同，拒绝覆盖", existing_clause=old)
            print(json.dumps(report, ensure_ascii=False, indent=1))
            return 1
        already = True
        report["steps"].append("先读：行已存在且条款一致，跳过写入")
    else:
        values = {names["编号"]: row_id, names["条款"]: clause}
        if kind == "indep":
            if arg.get("dir") and "规格目录" in names:
                values[names["规格目录"]] = arg["dir"]
            if "验收状态" in names:
                values[names["验收状态"]] = "pending"
            if "speckit-implement状态" in names:
                values[names["speckit-implement状态"]] = "todo"
        else:
            values[names["关联的独立规格需求"]] = arg.get("specs") or []
            values[names["影响面"]] = arg["impact"]
            values[names["回归状态"]] = "todo"
        write = call("POST", f"/api/agent/tables/{table}/rows/{row_id}", {"values": values})
        report["write"] = write
        report["steps"].append(f"写行：{write.get('result')} (http {write.get('http')})")
        if write.get("result") == "unknown":
            back = row_of(table, row_id)
            if back and norm(back["values"].get(names["条款"])) == norm(clause):
                report["write_confirmed_by"] = "readback"
                report["steps"].append("unknown 回读：行已存在且条款一致，按 success 处理")
            else:
                report.update(result="failed", error=write.get("error") or "写接口不可达")
                report["steps"].append("unknown 回读：行不存在，按 failed 处理")
                print(json.dumps(report, ensure_ascii=False, indent=1))
                return 1
        elif write.get("result") != "success":
            report.update(result="failed", error=write.get("error"))
            print(json.dumps(report, ensure_ascii=False, indent=1))
            return 1

    current = list(target["values"].get(rel_field) or [])
    if row_id in current:
        report["steps"].append(f"挂版本：{target['id']} 已包含，跳过")
    else:
        patched = call("PATCH", f"/api/agent/tables/{tabs['ver']}/rows/{target['id']}", {"values": {rel_field: current + [row_id]}})
        report["attach"] = patched
        report["steps"].append(f"挂版本：{target['id']} {patched.get('result')} (http {patched.get('http')})")
        if patched.get("result") != "success":
            again = call("GET", f"/api/tables/{tabs['ver']}/rows/{target['id']}")
            if row_id in ((again.get("row") or {}).get("values", {}).get(rel_field) or []):
                report["steps"].append("挂版本回读：关联已写入，按 success 处理")
            else:
                report.update(result="failed", error=patched.get("error") or "挂版本失败")
                print(json.dumps(report, ensure_ascii=False, indent=1))
                return 1

    back = row_of(table, row_id)
    ver_back = call("GET", f"/api/tables/{tabs['ver']}/rows/{target['id']}")
    ver_back = ver_back.get("row") or {}
    checks = {
        "行存在": bool(back),
        "条款一致": bool(back) and norm(back["values"].get(names["条款"])) == norm(clause),
        "验收状态pending": kind == "dep" or (back or {}).get("values", {}).get(names.get("验收状态")) == "pending",
        "版本关联含行": row_id in (ver_back.get("values", {}).get(rel_field) or []),
    }
    report["readback"] = checks
    if all(checks.values()):
        report["result"] = "already_registered" if already else "success"
        report["steps"].append("回读：四项一致")
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    report.update(result="failed", error="回读校验不通过：" + "、".join(k for k, v in checks.items() if not v))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1


sys.exit(main())
PY
echo "[exit=$?]"
```

脚本做的事，按顺序：解析表与字段（**按字段名解析，不硬编码字段id**，容忍各项目字段漂移）→ **校验人给的版本**（缺失/不存在/非planned/不晚于最近已发布都直接拒绝）→ 判重 → POST新行 → PATCH版本relation数组（幂等追加）→ GET回读四项 → 打印终态。`exit 0`表示`success`或`already_registered`，`exit 1`表示`failed`。

复现时直接从本文件抽取脚本执行，不必复制粘贴：

```bash
awk '/^python3 - "\$TF_PAYLOAD"/{f=1} f{print} /^PY$/{if(f)exit}' skills/tf-update/SKILL.md | bash
```

`in_place`不改行id，只PATCH记录字段（`条款`/`规格目录`），不碰`验收状态`：

```bash
curl -s -H "X-Agent-Id: $TF_AGENT" -H 'X-Origin: human-request' -H 'Content-Type: application/json' \
  -X PATCH $TF_BASE/api/agent/tables/tf-indep/rows/008-AR \
  -d '{"values":{"tf-i-clause":"<合并后的条款>","tf-i-dir":"specs/008-board-contract/"}}'
```

## 报告格式（六个字段，缺一不可）

```jsonc
{
  "classification": "new_spec",              // in_place/change/new_spec/cross/out_of_board
  "evidence": "新增条款（比对 001-008，无覆盖）",  // 指到 <编号>#US-AS；指不到时必须为空并附一个问题
  "action": "indep 新增 016-AR",              // 干了什么
  "version": "v0.6.0",                        // 人指定的目标版本；没给就拒绝登记（不自动选）
  "write": "success",                         // success/failed/unknown（写接口响应体，不是 HTTP 码）
  "readback": {"行存在": true, "条款一致": true, "验收状态pending": true, "版本关联含行": true}
}
```

人只看这六个字段就能复核；`steps`是过程，`readback`是证据。

登记器打印的是执行事实（`kind`/`row_id`/`write`/`attach`/`readback`/`version`/`result`）；`classification`与`evidence`来自步骤2的分类结论。两者拼起来才是完整报告，不能只贴脚本输出就宣称"已分类"。

## 三态处理

| 写接口返回 | 处理 | 报告 |
|---|---|---|
| `success` + 回读四项一致 | 完成 | `success` |
| `failed`(400) | **不重试**（重试还是400） | `failed` + 原始`error` |
| `unknown`(503) | 立即GET回读：行在且条款一致→按成功；行不在→按失败；回读也失败→保留`unknown` | 注明"由回读确认" |
| `success`但回读不符 | 按失败处理 | `failed` + 差异项 |

`unknown`不得当成功：行没落库却报完成，是最难查的一类错。

## 演练与清理

演练用`≥090`号段（如`099-AR`），并显式把`version`指向一个临时`planned`版本（如`v0.0.1-test`，日期随便填，规则不看日期），演练结束删行删版本；正式版本一个都不挂。

清理顺序（先摘关联，再删行，最后删临时版本，避免悬空关联）：

```bash
H=(-s -H "X-Agent-Id: $TF_AGENT" -H 'X-Origin: human-request' -H 'Content-Type: application/json')
curl "${H[@]}" -X PATCH $TF_BASE/api/agent/tables/tf-ver/rows/v0.0.1-test -d '{"values":{"tf-v-indep":[]}}'
curl "${H[@]}" -X DELETE $TF_BASE/api/agent/tables/tf-indep/rows/099-AR
curl "${H[@]}" -X DELETE $TF_BASE/api/agent/tables/tf-ver/rows/v0.0.1-test
curl -s -o /dev/null -w '099-AR http=%{http_code}\n' $TF_BASE/api/tables/tf-indep/rows/099-AR   # 期望 404
```

清理后必须回读：演练行404、行数与演练前一致、正式版本行（如`v0.6.0`）的值与演练前逐字段相同。

## 常见坑

| 坑 | 说明 |
|---|---|
| 关键词命中就当覆盖 | `grep "导出"`会命中005的"推导出的像素宽度"；命中行必须读原文，词形重合不是覆盖 |
| 把场景数当User Story数 | 契约的`场景数`= `**Acceptance Scenarios**`的条目数（008是3 US / 10 AS，看板记10） |
| 行id当可变字段 | 行id创建后不可改；判重先看id再看条款 |
| 没给版本就登记 | 参数里没有`version`一律`failed`并追问，不自动选版本 |
| 自动取"最早planned" | 线上`v0.2.0`仍是planned且日期更早，自动取就会把新需求挂回老版本（V060-02） |
| 版本不晚于已发布 | `version`必须晚于最近一个已发布版本，否则拒绝登记 |
| 挂dep后没提后果 | 挂`todo`的变更单会让该版本`依赖需求是否完成`转否，报告必须点明 |
| 写`accepted` | 验收是需求方的判定，Agent只登记 |
| 重试400 | `failed`是确定性的，重试只会再失败；只有`unknown`才回读/重试一次 |
| 覆盖已有行 | 同id不同条款是冲突，不是更新；覆盖会改掉别人的需求 |
| 用旧字段名写values | 各项目字段id不同，必须按字段名解析；写未知字段键返回400且不落库 |

## 实跑记录

`specs/009-tf-update/runbook.md`：真实看板（`localhost:8090`）上的分类、登记、幂等、冲突、回读、清理全过程，命令与输出可逐条复现。
