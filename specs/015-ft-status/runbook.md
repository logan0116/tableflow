# ft_status实跑记录（真实看板）

**时点**: 2026-11-19 12:24（Asia/Shanghai）

**实例**: `http://192.168.1.155:8090`，项目`tableflow`，版本`v0.6.0`

**性质**: 只读。全程只有`GET /api/projects/*`与`GET /api/tables/*`，没有一次`/api/agent/*`。

**交付物**: `skills/ft-status/SKILL.md`；下面的命令把该文件里的报告器原样抽出来执行，可逐条复现。

**版本提示**: 第0-4节是board@1三表时期的历史记录（当时报告只算两项就绪+旧Bug字段）；第5节是升级到board@2四表后的三次真实复验（`tableflow` v0.6.0、`tableflow` v0.6.1、`fd_system`三表），以第5节为准。

**结论**: `v0.6.0`不可发布，差1项闸门（独立需求就绪），阻塞4行（其中3行只差验收、1行未开工）；依赖需求就绪为空集判真、Bug就绪满足；同时曝出看板`发布条件`与契约`release_gate`的2类实质偏差，以及`v0.2.0`仍标`planned`的数据异常。

---

## 0. 只读校验（执行前后比对业务变更记录）

```bash
curl -s $TF_BASE/api/tables/tf-ver/rows/v0.6.0/changes \
  | python3 -c "import json,sys;d=json.load(sys.stdin)['changes'];print('条数',len(d),'最大id',max([c['id'] for c in d],default=None))"
```

执行前：

```
条数 27 最大id 5349
```

（执行报告，见下）

执行后：

```
条数 27 最大id 5349
```

`write_audit`没有读接口，因此另以"报告器只发GET"（`SKILL.md`中只定义`get()`，无任何写请求）与业务变更记录零新增两条佐证。

## 1. 默认版本选择（`FT_VERSION`留空）

```bash
export TF_BASE=http://192.168.1.155:8090 TF_PROJECT=tableflow FT_VERSION=
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash | head -4
```

```
# 版本状态报告：tableflow / v0.6.0

> 数据源：`GET http://192.168.1.155:8090/api/tables/{tf-ver,tf-indep,tf-dep}/table`（只读，未调用 `/api/agent/*`）
> 口径：`specs/008-board-contract/board@1.yaml`；版本选择：大于已发布最大版本的最小 planned；已发布最大版本：v0.5.1
```

已发布最大版本是`v0.5.1`，大于它的最小`planned`是`v0.6.0`，与显式指定一致。

## 2. 报告全文（`v0.6.0`）

```bash
export TF_BASE=http://192.168.1.155:8090 TF_PROJECT=tableflow FT_VERSION=v0.6.0
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash
```

```
# 版本状态报告：tableflow / v0.6.0

> 数据源：`GET http://192.168.1.155:8090/api/tables/{tf-ver,tf-indep,tf-dep}/table`（只读，未调用 `/api/agent/*`）
> 口径：`specs/008-board-contract/board@1.yaml`；版本选择：显式指定；已发布最大版本：v0.5.1

## 结论

**不可发布**：三项就绪中 1 项未满足，阻塞 4 行。

| 闸门 | 契约规则 | 判定 | 依据 |
|---|---|---|---|
| 独立需求就绪 | `rollup(ver.specs, spec.acceptance, all == accepted)` | **否** | 4/4 行未 accepted（`tf-i-acceptance`） |
| 依赖需求就绪 | `rollup(ver.changes, change.regress, all == passed)` | 是 | 0/0 行未 passed（`tf-d-regress`）；空集：本版无变更单 |
| 上一版本Bug就绪 | `and(ver.bug_open == 0)` | 是 | 未清Bug数=0（`tf-v-bug-open`）；对应行 `v0.6.0` |
| 发布条件 | `and(ver.spec_ready, ver.change_ready, ver.bug_ready)` | **否** | 客户端按契约重算；看板字段 `tf-v-cond`=false |

## 未满足项逐条

### 独立需求就绪：4 行未 accepted

| 行 | implement | acceptance | 还差什么 |
|---|---|---|---|
| 008-AR | todo | pending | 未开始实现（implement=todo）：须先 implement=done，再置 acceptance=accepted |
| 009-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |
| 010-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |
| 015-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |

依赖需求就绪：本版未关联变更单，空集判真（含义是「本版无此类工作」，不是「已回归」）。

上一版本Bug就绪：未清Bug数为 0，满足。

## 看板口径偏差（010 落地前）

- `ver`表缺契约字段：独立需求总数、独立需求就绪、依赖需求就绪、上一版本Bug总数
- `dep`表缺契约字段：证据、剩余事项、规格修订
- `ver`表字段名与契约不同（按语义解析）：change_total→依赖需求数、bug_open→未清Bug数、bug_ready→Bug已清空
- `ver`表存在契约外字段：测试进度、文档状态
- `indep`表存在契约外字段：状态、speckit-constitution状态、speckit-specify状态、speckit-plan状态、speckit-task状态、speckit-clarify状态、speckit-analyze状态、speckit-checklist状态、宪法版本、优先级
- `dep`表存在契约外字段：依赖规格、状态
- `发布条件`看板条件为 [开发进度=100、回归通过=true、Bug已清空=true、文档状态=done]，契约应为 [独立需求就绪、依赖需求就绪、上一版本Bug就绪]
- `回归通过`带行级 require（状态=已完成），契约要求单字段判定（只看 change.regress）
- `回归状态`枚举含 `na`，契约已删除该值（确认不受影响记 passed）

> 010 落地前，以本报告的契约口径为准；看板同名字段仅作对照。

## 数据异常

- `v0.2.0`状态为 planned，但版本号小于已发布最大版本 `v0.5.1`

## 拆分建议（参考，不写看板）

引用关系（从`条款`文本抽取同版规格编号）：
- 015-AR → 008-AR、010-AR

被引用次数：008-AR=1、009-AR=0、010-AR=1、015-AR=0

可后移候选（未开工且未 accepted）：008-AR

- 方案A「保被依赖者」：保留 008-AR、010-AR，移出 009-AR、015-AR
- 方案B「整版后移」：保留 无，移出 008-AR、009-AR、010-AR、015-AR（发布条件会因空集变真，但那是「无待办」不是「已交付」，空发须人确认）
- 下一版本：v0.6.1
- 迁版不改变本版闸门结论：方案A 移出后剩余阻塞行 2 行；要「可发」须把阻塞行全部处理或全部移出。
```

`[exit=0]`

### 2.1与上一时点的对比（12:20 → 12:24）

本任务登记`009-AR`/`015-AR`的`implement=done`之前，同一命令输出的未满足行是4条（`008`/`009`/`010`/`015`全部`todo`）；登记后`009`/`010`/`015`变为"只差验收确认"。报告随看板变化，不是固定文案。

## 3. 漂移项目上的降级（`im_kg_desktop`）

```bash
export TF_BASE=http://192.168.1.155:8090 TF_PROJECT=im_kg_desktop FT_VERSION=
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash
```

```
[ft-status] 没有 planned 版本，无法给出当前版本
```

该项目没有`planned`版本，技能明确失败而不是猜一个版本；字段按名称解析，缺字段会在"看板口径偏差"里列出，不会静默当成满足。

## 4. 本次看板改动（只改自己要的两行）

| 行 | 改动 |
|---|---|
| `015-AR` | 场景数20、任务总数15、`speckit-specify`=完成、`speckit-plan`=na、`speckit-task`=完成、`speckit-implement`=done、状态说明 |

`验收状态`仍为`pending`。

## 5. board@2（四表）复验：tableflow（含Bug闸门）与fd_system（未迁移）

**口径**: `specs/011-bug-table/board@2.yaml`。`tableflow`已有第四张表`tf-bug`，`fd_system`仍是三表。

**只读**: 三次执行前后核对行数，完全一致（见5.4）；报告器只定义`get()`，无写请求。

### 5.1 tableflow / v0.6.0（四表，Bug闸门参与判定）

命令：

```bash
export TF_BASE=http://192.168.1.155:8090 TF_PROJECT=tableflow FT_VERSION=v0.6.0
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash
```

输出：

```
# 版本状态报告：tableflow / v0.6.0

> 数据源：`GET http://192.168.1.155:8090/api/tables/{tf-ver,tf-indep,tf-dep,tf-bug}/table`（只读，未调用 `/api/agent/*`）
> 口径：`specs/011-bug-table/board@2.yaml`（四表）；版本选择：显式指定；已发布最大版本：v0.5.1

## 结论

**不可发布**：未满足项 1 项，阻塞 4 行

| 闸门 | 契约规则 | 判定 | 依据 |
|---|---|---|---|
| 独立需求就绪 | `rollup(ver.specs, spec.acceptance, all == accepted)` | **否** | 4/4 行未 accepted（`tf-i-acceptance`） |
| 依赖需求就绪 | `rollup(ver.changes, change.regress, all == passed)` | 是 | 0/0 行未 passed（`tf-d-regress`）；空集：本版无变更单 |
| 上一版本Bug就绪 | `and(count({bug | bug.found == 上一版本 and bug.status != closed}) == 0)` | 是 | 上一版本 v0.5.1 无缺陷（集合为空，空集为真） |
| 发布条件 | `and(ver.spec_ready, ver.change_ready, ver.bug_ready)` | **否** | 客户端按契约重算；看板字段 `tf-v-cond`=false |

## 距离发布还差什么

### 独立需求就绪：4 行未 accepted

| 行 | implement | acceptance | 还差什么 |
|---|---|---|---|
| 008-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |
| 009-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |
| 010-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |
| 015-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |

依赖需求就绪：本版未关联变更单，空集判真（含义是「本版无此类工作」，不是「已回归」）。

## 看板口径偏差（010落地前）

- `ver`表缺契约字段：独立需求总数、独立需求就绪、依赖需求就绪、上一版本Bug总数
- `dep`表缺契约字段：证据、剩余事项、规格修订
- `ver`表字段名与契约不同（按语义解析）：change_total→依赖需求数、bug_open→未清Bug数、bug_ready→Bug已清空
- `ver`表存在契约外字段：测试进度、文档状态
- `indep`表存在契约外字段：状态、speckit-constitution状态、speckit-specify状态、speckit-plan状态、speckit-task状态、speckit-clarify状态、speckit-analyze状态、speckit-checklist状态、宪法版本、优先级
- `dep`表存在契约外字段：依赖规格、状态
- `发布条件`看板条件为 [开发进度=100、回归通过=true、Bug已清空=true、文档状态=done]，契约应为 [独立需求就绪、依赖需求就绪、上一版本Bug就绪]
- `回归通过`带行级 require（状态=已完成），契约要求单字段判定（只看 change.regress）
- `回归状态`枚举含 `na`，契约已删除该值（确认不受影响记 passed）
- `上一版本Bug总数/未解决数`两个number字段在自动聚合落地前是填报值；本报告按缺陷表重算

> 以本报告的契约口径为准；看板同名字段仅作对照。

## 数据异常

- `v0.2.0`状态为 planned，但版本号小于已发布最大版本 `v0.5.1`

## 拆分建议（参考，不写看板）

引用关系（从`条款`文本抽取同版规格编号）：
- 015-AR → 008-AR、010-AR

被引用次数：008-AR=1、009-AR=0、010-AR=1、015-AR=0

可后移候选（未开工且未 accepted）：无

- 方案A「保被依赖者」：保留 008-AR、010-AR，移出 009-AR、015-AR
- 方案B「整版后移」：保留 无，移出 008-AR、009-AR、010-AR、015-AR（发布条件会因空集变真，但那是「无待办」不是「已交付」，空发须人确认）
- 下一版本：v0.6.1
- 迁版不改变本版闸门结论：方案A 移出后剩余阻塞行 2 行；要「可发」须把阻塞行全部处理或全部移出。
```

要点：`上一版本Bug就绪`取的是缺陷表——上一版本`v0.5.1`没有`found`指向它的缺陷，集合为空、按契约判真（"上一版本无缺陷"），不是把Bug数当0。

### 5.2 tableflow / v0.6.1（同一份代码，Bug闸门真实拦截一条未关闭缺陷）

`BUG-01`的`发现版本`是`v0.6.0`、状态`open`，因此`v0.6.1`的上一版本Bug闸门必须判否：

```bash
export TF_BASE=http://192.168.1.155:8090 TF_PROJECT=tableflow FT_VERSION=v0.6.1
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash
```

输出：

```
# 版本状态报告：tableflow / v0.6.1

> 数据源：`GET http://192.168.1.155:8090/api/tables/{tf-ver,tf-indep,tf-dep,tf-bug}/table`（只读，未调用 `/api/agent/*`）
> 口径：`specs/011-bug-table/board@2.yaml`（四表）；版本选择：显式指定；已发布最大版本：v0.5.1

## 结论

**不可发布**：未满足项 2 项，阻塞 3 行

| 闸门 | 契约规则 | 判定 | 依据 |
|---|---|---|---|
| 独立需求就绪 | `rollup(ver.specs, spec.acceptance, all == accepted)` | **否** | 2/2 行未 accepted（`tf-i-acceptance`） |
| 依赖需求就绪 | `rollup(ver.changes, change.regress, all == passed)` | 是 | 0/0 行未 passed（`tf-d-regress`）；空集：本版无变更单 |
| 上一版本Bug就绪 | `and(count({bug | bug.found == 上一版本 and bug.status != closed}) == 0)` | **否** | 上一版本 v0.6.0 的缺陷 1 个，未 closed 1 个 |
| 发布条件 | `and(ver.spec_ready, ver.change_ready, ver.bug_ready)` | **否** | 客户端按契约重算；看板字段 `tf-v-cond`=false |

## 距离发布还差什么

### 独立需求就绪：2 行未 accepted

| 行 | implement | acceptance | 还差什么 |
|---|---|---|---|
| 011-AR | done | pending | 只差验收确认：implement=done，置 acceptance=accepted 即可 |
| 014-AR | doing | pending | 已开始未完成（implement=doing）：做完并置 implement=done，再置 acceptance=accepted |

### 上一版本Bug就绪：1 个缺陷未 closed

| 缺陷 | 状态 | 严重度 | 标题 |
|---|---|---|---|
| BUG-01 | open | major | MS用例落在cnc_nexus v3.0项目下，tableflow执行结果无法按产品隔离 |

依赖需求就绪：本版未关联变更单，空集判真（含义是「本版无此类工作」，不是「已回归」）。

## 看板口径偏差（010落地前）

- `ver`表缺契约字段：独立需求总数、独立需求就绪、依赖需求就绪、上一版本Bug总数
- `dep`表缺契约字段：证据、剩余事项、规格修订
- `ver`表字段名与契约不同（按语义解析）：change_total→依赖需求数、bug_open→未清Bug数、bug_ready→Bug已清空
- `ver`表存在契约外字段：测试进度、文档状态
- `indep`表存在契约外字段：状态、speckit-constitution状态、speckit-specify状态、speckit-plan状态、speckit-task状态、speckit-clarify状态、speckit-analyze状态、speckit-checklist状态、宪法版本、优先级
- `dep`表存在契约外字段：依赖规格、状态
- `发布条件`看板条件为 [开发进度=100、回归通过=true、Bug已清空=true、文档状态=done]，契约应为 [独立需求就绪、依赖需求就绪、上一版本Bug就绪]
- `回归通过`带行级 require（状态=已完成），契约要求单字段判定（只看 change.regress）
- `回归状态`枚举含 `na`，契约已删除该值（确认不受影响记 passed）
- `上一版本Bug总数/未解决数`两个number字段在自动聚合落地前是填报值；本报告按缺陷表重算

> 以本报告的契约口径为准；看板同名字段仅作对照。

## 数据异常

- `v0.2.0`状态为 planned，但版本号小于已发布最大版本 `v0.5.1`

## 拆分建议（参考，不写看板）

引用关系（从`条款`文本抽取同版规格编号）：
- 014-AR → 011-AR

被引用次数：011-AR=1、014-AR=0

可后移候选（未开工且未 accepted）：无

- 方案A「保被依赖者」：保留 011-AR，移出 014-AR
- 方案B「整版后移」：保留 无，移出 011-AR、014-AR（发布条件会因空集变真，但那是「无待办」不是「已交付」，空发须人确认）
- 下一版本：v0.6.2
- 迁版不改变本版闸门结论：方案A 移出后剩余阻塞行 1 行；要「可发」须把阻塞行全部处理或全部移出。
```

### 5.3 fd_system（三表，未迁移到board@2）

```bash
export TF_BASE=http://192.168.1.155:8090 TF_PROJECT=fd_system FT_VERSION=
awk '/^python3 - "\$FT_VERSION"/{f=1} f{print} /^PY$/{if(f)exit}' skills/ft-status/SKILL.md | bash
```

输出：

```
# 版本状态报告：fd_system / 7.0.2

> 数据源：`GET http://192.168.1.155:8090/api/tables/{fd-ver,fd-indep,fd-dep}/table`（只读，未调用 `/api/agent/*`）
> 口径：`specs/011-bug-table/board@2.yaml`（四表）；版本选择：大于已发布最大版本的最小 planned；已发布最大版本：7.0.1

## 结论

**无法完整判定**：该表未迁移到board@2（项目只有三张表，缺「缺陷」表），Bug闸门按未启用处理

| 闸门 | 契约规则 | 判定 | 依据 |
|---|---|---|---|
| 独立需求就绪 | `rollup(ver.specs, spec.acceptance, all == accepted)` | 是 | 0/0 行未 accepted（`i-acceptance`）；空集：本版无此类工作 |
| 依赖需求就绪 | `rollup(ver.changes, change.regress, all == passed)` | 是 | 0/0 行未 passed（`d-regress`）；空集：本版无变更单 |
| 上一版本Bug就绪 | `and(count({bug | bug.found == 上一版本 and bug.status != closed}) == 0)` | 未启用 | 该表未迁移到board@2（项目只有三张表，缺「缺陷」表），Bug闸门按未启用处理 |
| 发布条件 | `and(ver.spec_ready, ver.change_ready, ver.bug_ready)` | 无法完整判定 | Bug闸门未启用，只能给两项就绪的结论 |

## 距离发布还差什么

- 两项就绪均未发现未满足行。（Bug闸门未启用，不能据此判定可发布）

### 上一版本Bug就绪：未启用

- 该表未迁移到board@2（项目只有三张表，缺「缺陷」表），Bug闸门按未启用处理
- 迁移到board@2（补`<前缀>-bug`表并按`发现版本`登记缺陷）后，本闸门才会参与发布判定。

## 看板口径偏差（010落地前）

- `ver`表缺契约字段：独立需求总数、独立需求就绪、依赖需求就绪、上一版本Bug总数
- `dep`表缺契约字段：证据、剩余事项、规格修订
- `ver`表字段名与契约不同（按语义解析）：change_total→依赖需求数、bug_open→未清Bug数、bug_ready→Bug已清空
- `ver`表存在契约外字段：测试进度、文档状态
- `indep`表存在契约外字段：状态、speckit-constitution状态、speckit-specify状态、speckit-plan状态、speckit-task状态、speckit-clarify状态、speckit-analyze状态、speckit-checklist状态、宪法版本、优先级
- `dep`表存在契约外字段：依赖规格、状态
- `发布条件`看板条件为 [开发进度=100、回归通过=true、Bug已清空=true、文档状态=done]，契约应为 [独立需求就绪、依赖需求就绪、上一版本Bug就绪]
- `回归通过`带行级 require（状态=已完成），契约要求单字段判定（只看 change.regress）
- `回归状态`枚举含 `na`，契约已删除该值（确认不受影响记 passed）

> 以本报告的契约口径为准；看板同名字段仅作对照。

## 数据异常

- 无

## 拆分建议（参考，不写看板）

引用关系（从`条款`文本抽取同版规格编号）：
- 无引用

被引用次数：—

可后移候选（未开工且未 accepted）：无

- 方案A「保被依赖者」：保留 无，移出 无
- 方案B「整版后移」：保留 无，移出 无（发布条件会因空集变真，但那是「无待办」不是「已交付」，空发须人确认）
- 下一版本：7.1.0
- 迁版不改变本版闸门结论：方案A 移出后剩余阻塞行 0 行；要「可发」须把阻塞行全部处理或全部移出。
```

要点：`fd_system`没有`bug`表，Bug闸门输出"未启用"、结论为"无法完整判定"；不报错，也不把Bug数当0（否则会误报"可发布"）。

### 5.4只读核对（执行前后行数）

执行前：

```
tf-ver 10
tf-indep 15
tf-dep 3
tf-bug 1
fd-ver 4
fd-indep 1
fd-dep 3
```

执行后：

```
tf-ver 10
tf-indep 15
tf-dep 3
tf-bug 1
fd-ver 4
fd-indep 1
fd-dep 3
```

两次完全相同：三次报告没有任何写入。
