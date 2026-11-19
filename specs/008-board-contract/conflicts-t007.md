# 008 T007：skill与契约的冲突清单

**背景**: `specs/008-board-contract/tasks.md` T007要求"列出skill中与契约冲突的表述，只记录不修改，交011同步"。011已把契约从`board@1`推进到`board@2`（四表），本次（V060-01）一次性把`skills/tableflow-board/SKILL.md`对齐到`board@2`，并把冲突逐条落在这里。

**范围**: `skills/tableflow-board/SKILL.md`（v0.5.x口径）对`specs/011-bug-table/board@2.yaml`（生效契约）与`specs/008-board-contract/board@1.yaml`（被取代，留档）。`tf-update`的挂版本行为缺陷见V060-02，附在本文附录。

**核对方法**: 逐字段比对`board@2.yaml`的`tables.*.fields`（53个字段，含4张表）与skill的字段表；再比对`classify`、`rules`、`status_definitions`的文字表述。本次核对脚本结论：**53个字段全部命中且类型一致，0缺失**。

## 一、冲突清单

| # | skill原文（改前） | 契约要求（board@2） | 本次是否已改 |
|---|---|---|---|
| C-01 | 第111行"**没有第四张表**：需求不单独建表，它以`条款`字段挂在规格行上；任务与Bug不进看板（只汇总成数）" | `tables`有四张表：`ver`/`indep`/`dep`/`bug`；缺陷有独立表与独立状态机（`status_definitions.bug`） | **已改**：四表范式，`bug`有独立小节"bug的真实语义" |
| C-02 | 第126行`开发进度`(computed)、`测试进度`(text)、`未清Bug数`(number)、`Bug已清空`(computed)、`回归通过`(computed)、`文档状态`(enum)、`任务总数`(computed) | ver 16字段：`独立需求总数/就绪`、`依赖需求总数/就绪`、`上一版本Bug总数/未解决数/就绪`、`发布条件`、`场景总数`；没有开发/测试进度、文档状态、任务总数 | **已改**：字段表按board@2重列，旧字段名在skill中命中0 |
| C-03 | 第131行`发布条件`= 进度=100且Bug已清空 且 回归通过 | `ver.gate = and(ver.spec_ready, ver.change_ready, ver.bug_ready)`；三项就绪各自是单字段判定 | **已改**：发布条件改为三项就绪的and，并给七个计算字段的options |
| C-04 | 第130/142行`回归通过`= `rollup` + `require:[{状态=已完成}]` | `change_ready = rollup(ver.changes, change.regress, all == passed)`；契约"单字段判定，不需要require" | **已改**：`依赖需求就绪`无`require`；坑表新增"给rollup配require"一条 |
| C-05 | 第134行`回归状态` enum含`na` | `change.regress`只有`todo/doing/passed/failed`，没有`na`；确认不受影响记`passed`，理由写证据 | **已改**：枚举去掉`na`，坑表写明 |
| C-06 | 第174行dep有`回归状态`之外的`状态`(text)；第171行dep有`依赖规格`(text) | dep 9字段，只有`change.spec`(relation)，没有`状态`、没有`依赖规格`文本字段 | **已改**：dep字段表按9字段重列 |
| C-07 | 第157行indep有`状态`(text)"一句话现状" | `rules.single_source`：不另设"状态"字段，避免同一问题两个真相；完成判据只有`验收状态` | **已改**：删除`状态`字段 |
| C-08 | 第160行indep有`优先级`(enum `P0`~`P3`) | indep 16字段，无`优先级` | **已改**：删除`优先级`字段 |
| C-09 | 第163行"`speckit-implement状态`必须enum，其余阶段用text或enum均可" | 8个阶段状态全部是enum（`spec.stage.*`），`implement`无`na`，其余可取`na` | **已改**：8个阶段一律enum，并写清哪些可取`na` |
| C-10 | 第121/125行`需求关联（独立）`、`需求关联（依赖）` | `ver.specs`名称`独立需求关联`、`ver.changes`名称`依赖需求关联` | **已改**：字段表用契约名称；提示skill的登记脚本按名称兼容两版叫法 |
| C-11 | 第196/200行"挂上变更单后`回归通过`转否；没挂时`回归通过`显示是" | 同上，判定字段是`依赖需求就绪`；空集为真表示"本版无此类工作"，不是"已验证" | **已改**：全文改为`依赖需求就绪`，并补"空版本三项就绪全真、发布条件也为真=无待办不是可交付" |
| C-12 | 第202行"新建版本`回归通过`显示是…还差`开发进度=100`与`Bug已清空`" | 空集语义 + 三项就绪；没有开发进度/Bug已清空这两个判定项 | **已改**：按三项就绪重写空集段 |
| C-13 | 第209行"看板只汇总`未清Bug数`"、第210行"Bug、缺陷→缺陷跟踪" | 缺陷进`bug`表，版本表的`上一版本Bug`按`bug.found`汇总 | **已改**：反例清单指向`bug`表；新增bug语义小节（挂接键、closed准入、严重度不进闸门） |
| C-14 | 第221-226行落地检查单：3张表、dep 0行、`未清Bug数`写0、字段顺序indep→dep→ver | 四张表（含`bug`），dep与bug都0行；`上一版本Bug未解决数`写0；字段顺序indep→dep→bug→ver | **已改**：检查单按四表重写 |
| C-15 | 第143-145行六个计算字段（percent/and/rollup/sum），含`allow_override:true`与文档闸门 | 七个计算字段的options见board@2 `ver.*.rule`；闸门字段不得人工覆盖 | **已改**：七个options按契约重写，去掉`allow_override`与文档闸门，闸门字段标注不得覆盖 |
| C-16 | 第224行行id例`S01`、`v1.0.0` | `conventions.row_id`：`v0.6.0`/`008-AR`/`D01`/`BUG-01` | **已改**：示例统一为契约编号形态 |

## 二、不属于冲突、但已同步改写的表述

| # | 位置 | 改法 |
|---|---|---|
| N-01 | 两表引用关系"ver→indep、ver→dep" | 补两条：`bug→ver`（发现版本/修复版本）与`bug→indep`（关联规格） |
| N-02 | 常用配方1的建表/建字段/建行顺序 | 增加`px-bug`表与bug字段、行；字段顺序改为indep→dep→bug→ver |
| N-03 | 顶部description与"何时用" | 触发词与用途补"缺陷表/登记缺陷" |
| N-04 | 坑表 | 新增：缺陷当需求、`修复版本`当挂接键、不修复就不关单、严重度进闸门、空版本发布条件显示"是"、存量项目字段照抄 |

## 三、核对与验收命令

```bash
# 1) 三处冲突表述（V060-01 点名）命中应为 0
grep -c "没有第四张表" skills/tableflow-board/SKILL.md
grep -c "不进看板" skills/tableflow-board/SKILL.md
grep -c "其余阶段用text或enum均可" skills/tableflow-board/SKILL.md
grep -c "只汇总成数" skills/tableflow-board/SKILL.md

# 2) 旧字段名命中应为 0（开发进度/测试进度/未清Bug数/Bug已清空/回归通过/文档状态/依赖需求数）
grep -cE "开发进度|测试进度|未清Bug数|Bug已清空|回归通过|文档状态|依赖需求数" skills/tableflow-board/SKILL.md

# 3) 53 个契约字段逐个比对（脚本见附录 B）
```

本次执行结果：

```
没有第四张表 0
不进看板 0
其余阶段用text或enum均可 0
只汇总成数 0
旧字段名合计 0
契约字段 53 缺失/类型不符 0
```

## 附录A：V060-02只读复现（改前行为）

线上`tf-ver`的`v0.2.0`仍是`planned`且`发布时间`为`2026-11-30`，`v0.6.0/1/2`为`planned`但发布时间为空。旧规则"发布时间升序、空日期排最后"会选中`v0.2.0`：

```bash
python3 - <<'PY'
import json, re, urllib.request
B = "http://localhost:8090"
d = json.load(urllib.request.urlopen(B + "/api/tables/tf-ver/table"))
sem = lambda v: (lambda m: tuple(map(int, m.groups())) if m else (999, 999, 999))(re.match(r"^v(\d+)\.(\d+)\.(\d+)$", v))
nm = {f["id"]: f["name"] for f in d["fields"]}
val = lambda r, n: r["values"].get(next(f for f, i in nm.items() if i == n))
p = [r for r in d["rows"] if val(r, "发布状态") == "planned"]
p.sort(key=lambda r: (val(r, "发布时间") or "9999-12-31", sem(r["id"])))
print([(r["id"], val(r, "发布时间")) for r in p]); print("旧规则选中:", p[0]["id"])
PY
```

```
[('v0.2.0', '2026-11-30T00:00:00+08:00'), ('v0.6.0', None), ('v0.6.1', None), ('v0.6.2', None)]
旧规则选中: v0.2.0
```

## 附录B：53个契约字段比对脚本

```bash
python3 - <<'PY'
import re, yaml
c = yaml.safe_load(open("specs/011-bug-table/board@2.yaml", encoding="utf-8"))
skill = open("skills/tableflow-board/SKILL.md", encoding="utf-8").read()
lines = skill.splitlines()
total, miss = 0, []
for tname, table in c["tables"].items():
    rows = {}
    for line in lines:
        m = re.match(r"^\| (.+?) \| `([^`]+)` \| (text|number|datetime|enum|relation|computed)[^|]* \|", line)
        if m:
            rows[m.group(1).strip()] = (m.group(2), m.group(3))
    for f in table["fields"]:
        total += 1
        got = rows.get(f["name"])
        if not got:
            miss.append(f"{tname}.{f['key']} 缺 {f['name']}")
        elif got[1] != f["type"]:
            miss.append(f"{tname}.{f['key']} 类型 {f['name']}: skill={got[1]} 契约={f['type']}")
print("契约字段", total, "缺失/类型不符", len(miss))
for m in miss:
    print(" -", m)
PY
```

## 未在本次范围内

- `board@2`的bug表落库与存量迁移（011/后续需求）。
- 版本表"上一版本Bug"自动聚合的实现（契约明确另立需求）。
- ~~`tf-status`仍按board@1名称解析~~：已由t17同步到board@2四表（Bug闸门取缺陷表；三表项目明确提示未迁移、不当0）。`tf-update`的版本规则已由t14修复。
