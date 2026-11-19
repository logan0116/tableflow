# Feature Specification: 计算口径落地（v0.6.0）

**Feature Branch**: `010-computation`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 看板`010-AR`行条款："看板计算口径落地：按board@1定义的公式与空集语义实现重算（总数/就绪/发布条件），悬空关联不得视为达标，闸门字段禁止人工覆盖；以临时库单测验证，不改存量数据。"

## 背景与问题证据

| 现状 | 证据 | 后果 |
|---|---|---|
| 悬空引用被静默忽略 | `backend/src/tableflow/calculation.py`的`_selected_target_rows`（第414–441行）跳过目标表已不存在的行；`specs/003-calculated-fields/spec.md`场景3与第236–237行写明"悬空引用被忽略" | 删除被关联行后，只要现存行都达标，`rollup all`就为真；"就绪"在无法核验的集合上被放行 |
| 闸门没有数据层落点 | `specs/008-board-contract/board@1.yaml`第117/131/146/151行给四个字段标`gate: true`，但`fields.options`里没有对应键；`calculation.py`的`apply_overrides`只看`allow_override` | 闸门字段一旦开了`allow_override`就能被人工改成真，发布资格可被伪造 |
| 空集语义只靠代码隐含 | `calculation.py`中`count`返回`len(matched)`、`percent`在`total==0`返回`None`、`rollup all`走`all([])` | 语义没有用例锁定，后续改动容易回退 |
| 写后重算缺少回归用例 | `write_service.py`第758/807/853行在行写后调用`recompute_for_write`，但现有用例只覆盖部分路径 | 下游重算被改坏时没有警报 |

## Clarifications

### Session 2026-11-19

- Q: 悬空关联怎么处理——删除被引用行时拒绝，还是计算时判未就绪？ → A: 计算时判未就绪。理由：`003`已把"删除被关联行后重算"写成验收场景（`specs/003-calculated-fields/spec.md`场景3、FR-016），删除拒绝会推翻已交付规格的既定写侧流程；`010`是新的独立需求，无权改写`003`的写侧语义。判定收口放在判定侧：布尔`rollup`只要关联集合里有悬空引用，`all`/`none`一律为否（未确立），`any`只在已核验成员命中时为真。人工修法是先摘掉失效id。
- Q: 数量类（`count`/`sum`/`percent`/`min`/`max`/`count_distinct`）也判未就绪吗？ → A: 不判。数量描述"仍然存在的行"，悬空不计入（`003` FR-016保持）；"就绪"是资格判定，两者分工不同。
- Q: 闸门字段在数据层怎么识别？ → A: 计算字段的`options.gate=true`（布尔）。board@1的`gate`是契约属性，必须能在数据层表达；后端拿不到YAML契约，只能靠字段配置。`gate`只允许打在布尔判定字段（`and`或`rollup`的`all`/`any`/`none`），数量类没有"放行/不放行"的含义。契约侧已在`conventions.gate_mapping`声明该映射（V060-03）。
- Q: 闸门字段被覆盖时返回什么？ → A: 400，写请求整体回滚。即使`allow_override=true`也不放行——`gate`优先，闸门是判定结论，人工改写等于伪造资格。
- Q: 闸门字段的历史覆盖能清除吗？ → A: 能。清除（`value=null`）是撤回，不是伪造资格；否则打标之前写入的覆盖会永久卡住数据。
- Q: 存量字段要不要打`gate`标记？ → A: 不打。`010`只落地能力与用例；打标与存量计算配置的迁移属于非目标（与本任务"不改存量数据"一致）。
- Q: 读侧要不要兜底重算？ → A: 不要。与`003`一致：读侧只读`computed_values`，缺失显示"—"。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 空集口径固定 (Priority: P1)

版本表未关联任何行时，四个口径的取值固定：`count=0`、`sum=0`、`rollup all=true`、`percent`仍为`null`。这样说清"本版无此类工作"，也不会把"没有数据"显示成"已完成0%"。

**Why this priority**: 空集是最常见的边界，口径漂移会让"就绪"在两种解读间来回跳。

**Independent Test**: 造一个`v-rel=[]`的汇总行，四类计算字段各建一个，读接口与`computed_values`落库值同时核对。

**Acceptance Scenarios**:

1. **Given** 汇总行未关联任何目标行，**When** 读取`count`与`sum`，**Then** 两者都是`0`，且落库值也是数字`0`（不是`null`）。
2. **Given** 汇总行未关联任何目标行，**When** 读取`rollup all=true`，**Then** 值为真（"本版无此类工作"），落库值为布尔真。
3. **Given** 汇总行未关联任何目标行，**When** 读取`percent`，**Then** 值为`null`（显示"—"），不写`0`；依赖它的`and`条件判否。

### User Story 2 - 悬空关联不得让就绪变真 (Priority: P1)

关联里引用的目标行被删除后，集合里就有一行无法核验。此时布尔判定必须判否，不能因为"现存行都达标"而放行。

**Why this priority**: 这是"发布条件"最危险的一种假真：数据被删干净了，门禁反而打开。

**Independent Test**: 造三行关联（两行达标、一行不达标），删掉不达标那行，读`rollup all`与依赖它的`and`闸门。

**Acceptance Scenarios**:

1. **Given** 关联`[S1,S2,S3]`中只有`S2`不达标，**When** 删除`S2`（`003`允许删除被关联行），**Then** `rollup all`仍为否，不因现存`S1`/`S3`都达标而变真。
2. **Given** 上述悬空状态，**When** 读取依赖该`rollup`的`and`闸门字段，**Then** 闸门也为否。
3. **Given** 上述悬空状态，**When** 把关联改成`[S1,S3]`（摘掉失效id），**Then** `rollup all`与闸门恢复为真——修法是修关联，不是删数据以外的手段。
4. **Given** 上述悬空状态，**When** 读取`count`与`percent`，**Then** 仍只统计现存行（`2`、`100.0`），与`003` FR-016一致。

### User Story 3 - 闸门字段禁止人工覆盖 (Priority: P1)

`gate=true`的计算字段是"放行/不放行"的判定结论，任何时候都不接受人工覆盖；历史遗留的覆盖可以清除，但不能新建或改写。

**Why this priority**: 可覆盖的闸门等于没有闸门；这一条把board@1的`gate`标记变成运行期约束。

**Independent Test**: 建一个`gate=true`且`allow_override=true`的`rollup`字段，提交覆盖请求；再建一个不打标记的布尔字段做对照。

**Acceptance Scenarios**:

1. **Given** `gate=true`且`allow_override=true`的计算字段，**When** `PATCH`行提交`overrides`设值，**Then** 返回`400`，错误信息指明闸门字段，`computed_values`里不留覆盖值。
2. **Given** 数量类计算字段，**When** 尝试打`gate=true`，**Then** 返回`400`（数量类不是布尔判定）；`gate`取非布尔值同样`400`。
3. **Given** 不打`gate`标记的布尔计算字段，**When** 提交覆盖，**Then** 仍按`allow_override`放行——不误伤`003`留出的人工覆盖口。
4. **Given** 闸门字段存在打标之前写入的历史覆盖，**When** 提交`value=null`清除，**Then** 请求成功，覆盖被清掉并立即按当前数据重算。

### User Story 4 - 写行后下游重算保持 (Priority: P1)

任何行写入后，受影响表（本表与关联指向本表的计算字段所在表）在同一事务内重算并落库，读侧不做计算。

**Why this priority**: 看板的价值在"打开就是对的"；少一处重算，页面就显示旧结论，且无法从读侧发现。

**Independent Test**: 只写源表一行（不调重算接口），核对汇总表落库值与读接口值；再覆盖新增行、新增关联、新建汇总行、删除源行四条路径。

**Acceptance Scenarios**:

1. **Given** 已有关联的计算字段，**When** 修改一行源数据，**Then** 引用表的`count`/`percent`/`rollup`/`and`在同一次写事务内更新并落库，不需要额外调用`recompute`。
2. **Given** 同一组计算字段，**When** 新增源行、把新行加入关联、或新建一条汇总行，**Then** 新行立刻有计算值，旧行计数随关联变化。
3. **Given** 同一组计算字段，**When** 删除一行源数据，**Then** 引用表的重算值落库（悬空规则按US2另行生效）。

### Edge Cases

- 空集上的`and`：`percent`为`null`，`null`与任何值不相等，条件判否（不因空集变真）。
- 悬空集合上的`any`：已核验成员命中即为真，悬空不改变"存在"这一事实。
- 悬空集合上的`none`：无法证明"没有任何成员满足"，判否。
- 关联值里的重复id不算悬空；非字符串项不算悬空（历史脏值不阻断计算）。
- `rollup min`/`max`/`count_distinct`与`sum`维持忽略悬空，空集分别返回`null`/`null`/`0`/`0`。
- 闸门字段的覆盖被拒后，同一请求里的其他字段写入也整体回滚，不留半份结果。

## Requirements *(mandatory)*

- **FR-001**: `count`在空集上MUST落库数字`0`。
- **FR-002**: `sum`在空集上MUST落库数字`0`（不是`null`）。
- **FR-003**: `rollup`的`all`/`none`在空集上MUST为真，`any` MUST为假。
- **FR-004**: `percent`在分母为0（空集）时MUST落`null`，MUST NOT落`0`。
- **FR-005**: 布尔`rollup`的关联集合含悬空引用时，`all`/`none` MUST判否；`any`按已核验成员判定。
- **FR-006**: `count`/`sum`/`percent`/`min`/`max`/`count_distinct`维持`003`的"忽略悬空"，MUST NOT因悬空判失败。
- **FR-007**: 计算字段`options.gate`可选、MUST为布尔、默认`false`；`gate=true`仅允许`and`或`rollup`的`all`/`any`/`none`，否则写入返回`400`。
- **FR-008**: `gate=true`的字段，行写接口的`overrides`设值MUST返回`400`并整体回滚；清除（`value=null`）MUST允许。
- **FR-009**: 行创建/更新/删除后MUST在同一事务内重算受影响表（本表与关联指向本表的计算字段所在表）并落库；读接口MUST NOT计算。
- **FR-010**: 计算失败或校验失败MUST整体回滚，MUST NOT落部分结果或换算成`0`。
- **FR-011**: 不新增路由、不改现有接口形状；`PATCH /api/agent/tables/{table_id}/rows/{row_id}`的`overrides`语义不变。
- **FR-012**: MUST NOT修改存量行、存量字段配置与线上数据；`gate`标记由后续迁移需求负责打上。

## Key Entities

- **computed_values**：计算值落库（`value`），人工覆盖（`override_value`/`override_reason`/`override_by`/`override_at`）；读侧只读它。
- **fields.options（type=computed）**：`kind`、`source`、`where`、`field_id`、`aggregate`、`equals`、`decimals`、`allow_override`，本次新增`gate`。
- **row_records.data**：relation字段值是目标行id数组；数组里指向已删除行的id即悬空引用。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `cd backend && .venv/bin/python -m pytest -q`全绿；基线`97 passed`，新增后`108 passed`。
- **SC-002**: a/b/c/d四情形各有用例：`backend/tests/test_computation_010.py`共11个用例，按`test_a_*`/`test_b_*`/`test_c_*`/`test_d_*`分组。
- **SC-003**: 线上7个项目21张表的业务数据未被修改。前后快照比对结果：字段定义、行集合、其余6个项目全部无差异；唯一业务写入是看板`010-AR`行（场景数`None→14`、任务总数`None→12`、`specify/task=完成`、`plan=na`、`implement=done`、状态"实现完成，待验收"）。`tableflow/tf-ver/v0.6.0`的三个派生列随该行重算（开发进度`0.0→25.0`、场景总数`10.0→24.0`、任务总数`10.0→22.0`），是行写的必然结果，不是人工改数。
- **SC-004**: 实现改动可定位到`backend/src/tableflow/calculation.py`三处：空集语义的既有实现与注释（第465–500行）、悬空判定（第496–516行）、闸门配置校验（第221、306–310行）与覆盖拒绝（第954–957行）。

### SC-003的核验方法与基线（V060-08补强）

发布前后各取一次只读基线，比对三部分：字段定义（id/name/type/options）、行id集合、每行的非计算字段值。计算字段随写行重算是允许变化，不进比对；`write_audit`与`business_changes`等技术审计表也不进比对。取法（只读GET）：

```bash
python3 - <<'PYEOF'
import hashlib, json, urllib.request
B = "http://192.168.1.155:8090"
get = lambda p: json.load(urllib.request.urlopen(B + p, timeout=30))
snap = {}
for p in get("/api/projects")["projects"]:
    for t in get(f"/api/projects/{p['id']}/tables")["tables"]:
        d = get(f"/api/tables/{t['id']}/table")
        computed = {f["id"] for f in d["fields"] if f["type"] == "computed"}
        snap[t["id"]] = {
            "fields": [[f["id"], f["name"], f["type"], f["options"]] for f in d["fields"]],
            "rows": {r["id"]: {k: v for k, v in r["values"].items() if k not in computed}
                     for r in d["rows"]},
        }
print(hashlib.sha256(json.dumps(snap, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode()).hexdigest())
PYEOF
```

2026-11-19修复时采集的基线：7项目、22张表、192行，快照sha256`b4e353c55ab8595785fdc812dc086704d038717fcc3fb98c25438a78f8f2e279`，文件`.tmp-shots/repair-v060/baseline-2026-11-19.json`（同目录`take_baseline.py`可重采）。其中`tableflow/tf-bug`（0行）是011新建的缺陷表，不属于010交付面的变化。

## 非目标

- 不给存量计算字段打`gate`标记、不迁移存量计算配置（由后续迁移需求负责）。
- 不改relation写入校验（`relation_must_exist`等由`002`/`003`负责）。
- 不做board@1的字段改名、加项目前缀、三表字段对齐（属于009/011等需求）。
- 不做展示层（`%`渲染、"就绪"文案、列顺序）。
- 不新增计算`kind`，不开放用户表达式。
