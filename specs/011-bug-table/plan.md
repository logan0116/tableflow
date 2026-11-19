# Implementation Plan: bug表与board@2契约（v0.6.1）

**Branch**: `011-bug-table` | **Date**: 2026-11-19 | **Spec**: [spec.md](./spec.md)

**Input**: 看板`011-AR`条款："在看板新增第四张表<前缀>-bug（一行=一个缺陷），定义字段、状态枚举与完成判定，并把契约从board@1扩展到board@2；同时约定版本表上一版本Bug三个字段的数据来源。"

## Summary

把缺陷从"聊天记录里的事实"变成看板上的第四张表：契约`board@2.yaml`在`board@1`基础上新增`bug`表（12字段），并定义缺陷完成判据（`status=closed`）与版本表挂接口径（按`发现版本`取上一版本集合，总数/未解决数/就绪三个口径）；同时交付一次性脚本在线上`tableflow`项目建出`tf-bug`表与12个字段，建后回读逐字段核对，重复执行只跳过。不改后端代码，不改现有三表的字段与行。

## Technical Context

**Language/Version**: Python 3.11+（建表脚本，标准库`urllib`）；YAML 1.0（契约）

**Primary Dependencies**: 无新增依赖；脚本只用标准库，PyYAML 仅用于可选的契约交叉核对

**Storage**: 线上`tableflow`项目新增一张表`tf-bug`与12个字段；不迁移、不删除

**Testing**: 脚本`--dry-run`/二次执行/回读核对；YAML解析与字段数断言；线上`GET /api/tables/tf-bug/table`比对

**Target Platform**: 线上看板`http://localhost:8090`

**Project Type**: web application（契约+运维脚本，无前端/后端代码改动）

**Constraints**: 无后端`src/`改动（010/013在用）、无三表数据改动、无git操作、不部署不重启

**Scale/Scope**: 1份契约、3份文档、1个脚本、线上1张表12个字段

## Constitution Check

*GATE: 对照宪法 v7.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 建表全部走`/api/agent/*`，带`X-Agent-Id: agent-tf-doc`与`X-Origin: human-request`，落写审计 | PASS |
| II 无读缓存 | 脚本每次现读线上状态再决定建/跳过，不落任何本地缓存 | PASS |
| III Schema 驱动 | 缺陷表是数据层新增`fields`记录，前端按`type`渲染，无需改前端代码 | PASS |
| IV DOM 表格 | 不涉及表格渲染改动 | PASS |
| V 固定技术栈 | 不新增依赖，脚本只用标准库 | PASS |
| VI 中文单语 | 契约与文档中文，字段名称中文；枚举值为约定的英文小写 | PASS |
| VII 边界收敛 | 只做契约、建表与本次核对；不做聚合实现、MS同步、协议、用户管理 | PASS |

无违规项。需注意：写入`tf-bug`表与字段会在`write_audit`留下记录，属预期审计，不是业务数据变更。

## Project Structure

```text
specs/011-bug-table/
├── spec.md                    # 需求、场景、FR/SC、非目标
├── plan.md                    # 本文件
├── tasks.md                   # 任务清单
└── board@2.yaml               # 四表契约（board@1 + bug 表 + 挂接口径）

backend/scripts/
└── create_bug_table.py        # 一次性建表脚本（可重入、回读核对、--dry-run）
```

## 实现要点

### 1. 契约增量（board@1 → board@2）

| 段落 | 变更 |
|---|---|
| `meta` | `id: board@2`、`supersedes: board@1`、scope 增加"缺陷完成判据与挂接口径"，`out_of_scope` 把"bug表"换成"自动聚合实现" |
| `conventions` | 字段id字母表加入`b`；行id举例加`BUG-01` |
| `status_definitions` | 新增`bug`状态域：`open`/`fixing`/`verifying`/`closed`，一个问题"修到哪一步、结论是什么" |
| `rules` | 新增缺陷规则：`bug_done`、`bug_flow`、`bug_closed_evidence`、`bug_fix_record`、`bug_severity_record`、`bug_unattributed`、`bug_intake`；新增挂接规则：`bug_version_hookup`、`bug_prev_version`、`ver_bug_total`、`ver_bug_open`、`ver_bug_ready`、`bug_aggregate_impl` |
| `classify` | 补`bug_note`：缺陷不进需求分类树 |
| `tables.bug` | 新增12字段（见下） |
| `tables.ver` | 三个Bug字段的`note`改为指向`rules.ver_bug_*`；类型与判定规则不变 |
| `decisions` | 追加6条缺陷相关决定 |

`bug`表字段（语义键 → 线上字段id）：

| 语义键 | 名称 | 类型 | 线上字段id | 枚举/关联 |
|---|---|---|---|---|
| `bug.id` | 编号 | text | `tf-b-id` | 必填，行id`BUG-01` |
| `bug.title` | 标题 | text | `tf-b-title` | 必填 |
| `bug.status` | 状态 | enum | `tf-b-status` | `open`/`fixing`/`verifying`/`closed`，必填 |
| `bug.severity` | 严重度 | enum | `tf-b-severity` | `blocker`/`critical`/`major`/`minor`，必填 |
| `bug.source` | 来源 | enum | `tf-b-source` | `test`/`prod`/`review`/`user`，必填 |
| `bug.specs` | 关联规格 | relation→indep | `tf-b-indep` | 多对多，可空 |
| `bug.found` | 发现版本 | relation→ver | `tf-b-found` | 单值，必填 |
| `bug.fix` | 修复版本 | relation→ver | `tf-b-fix` | 单值，可空 |
| `bug.evidence` | 证据 | text | `tf-b-evidence` | |
| `bug.rest` | 剩余事项 | text | `tf-b-rest` | |
| `bug.ms_case` | MS用例号 | text | `tf-b-ms` | |
| `bug.owner` | 负责人 | text | `tf-b-owner` | |

枚举用`options.items`对象形式携带`constraints.required`（002起支持），每项带`value`/`label`/`tone`（`danger`/`warning`/`info`/`success`/`neutral`）；relation字段配`display_field`/`status_field`（指向目标表的标题列与状态列），与006的约定一致；`bug.found`加`required`与`relation_must_exist`约束。

### 2. 建表脚本

`backend/scripts/create_bug_table.py`，步骤：

1. `GET /api/tables/tf-bug/table`：`200`→复用现有表并逐字段比对；`404`→`POST /api/agent/projects/tableflow/tables`建表（`{"id":"tf-bug","name":"缺陷","order":4}`）。
2. 建字段顺序按契约字段表（`01`→`12`）；relation的`display_field`/`status_field`指向`tf-indep`/`tf-ver`既有的`tf-i-clause`/`tf-i-implement`/`tf-v-ver`/`tf-v-status`，建前先确认`tf-indep`/`tf-ver`存在。
3. 逐字段：已存在且`name`/`type`/`options`（契约声明的键）一致→跳过；配置冲突→打印差异并以退出码1结束，不修改、不删除；不存在→`POST /api/agent/tables/tf-bug/fields`。
4. 建后回读：`GET /api/tables/tf-bug/table`，核对字段集合与契约完全一致（不多不少）、每个字段的名称/类型/枚举/关联目标一致，逐字段打印`OK`/`MISMATCH`。
5. `--dry-run`只打印计划；`--base`覆盖地址，默认`$TF_BASE`或线上`localhost:8090`；`--contract`可选，用PyYAML把脚本内期望与`board@2.yaml`交叉核对，防两处漂移。

幂等判定只看字段id与配置，不依赖行数据；脚本不写任何缺陷行，`tf-bug`建完为0行。

### 3. 版本表挂接（只定口径，不改字段）

- 挂接键：`bug.found`（必填单值，指向`tf-ver`）。
- `上一版本`：按版本号语义序取紧邻前一版（不看发布时间与发布状态）；`v0.6.2`的上一版本是`v0.6.1`。
- `ver.bug_total = count(发现版本==上一版本)`；`ver.bug_open = count(同上且状态!=closed)`；`ver.bug_ready = and(bug_open==0)`；空集为真。
- 自动聚合另立需求；本期由脚本或人工按上式填报`tf-v-bug-open`/`tf-v-bug-total`（线上字段名为`未清Bug数`，口径一致）。

## 验收方法

1. `python3 -c "import yaml; ..."`解析`board@2.yaml`：`ver`/`indep`/`dep`/`bug`字段数`16/16/9/12`，语义键无重复。
2. `python3 backend/scripts/create_bug_table.py --dry-run`：只打印计划，0次写。
3. 正式执行：输出建表、建字段、回读核对三段；`GET /api/tables/tf-bug/table`字段数12。
4. 二次执行：输出全部跳过，写入0次，字段数仍12，退出码0。
5. 快照比对：重复执行脚本前后`tf-ver`/`tf-indep`/`tf-dep`的字段与行集合字节一致（`GET .../table`的JSON比对）；`011-AR`登记后的行变化与下游重算单独列出，不算建表引起。
6. 看板`011-AR`行更新后读取回核：场景数/任务总数/阶段状态与文档条数一致。

## 风险

| 风险 | 应对 |
|---|---|
| 字段id与其它表冲突 | 字段id全局唯一，统一`tf-b-`前缀；脚本回读校验字段集合 |
| relation指向未建好的字段 | 先建全部field的基础类型，relation的`display_field`/`status_field`在建字段时目标字段已存在（`tf-i-clause`/`tf-i-implement`/`tf-v-ver`/`tf-v-status`均在线上存在） |
| 二次执行造重复字段 | 以字段id为准跳过；配置冲突不覆盖、直接报错退出 |
| "不修复"缺陷永远占闸门 | 规则允许`closed`且修复版本留空、证据写依据；契约与spec都锁定 |
| 版本表口径与未来聚合实现漂移 | 口径写在`rules.ver_bug_*`；聚合实现落地时必须引用同一条规则 |
| 误改现有三表 | 脚本只写`tf-bug`；执行前后做三表JSON快照比对 |
| skill文本仍说"没有第四张表" | 非本需求范围；已在spec非目标记录，交技能维护方同步 |
