# Feature Specification: Bug表与版本表的关系补正（v0.6.4，008关联需求）

**Feature Branch**: `017-bug-relation`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 017-AR。008/011 的关系设计有缺陷：`tf-bug` 用「发现版本」「修复版本」两个 relation 指向版本表，版本表却没有任何字段指向 bug，导致"本版要清零哪些缺陷"无法表达，总数与已解决数也就无从计算。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 方向单一 | `tf-bug` 的 `tf-b-found`/`tf-b-fix` 指向 `tf-ver`，`tf-ver` 无反向字段 | 版本行数不出缺陷总数，`未清Bug数`只能手填（历史即为 0，永远"已清空"） |
| 引擎禁双向 | `write_service._reverse_relation_exists` 对双向 relation 直接 400 | 不能"两边都加"，必须选一个方向 |
| 修复版本无意义 | `tf-b-fix` 从未被使用（BUG-01 为空） | 死字段 |

## Clarifications

### Session 2026-11-19

- Q: 关系方向选哪个？ → A: 版本→缺陷（"Bug管理"），因为统计发生在版本行；缺陷的"哪版发现"改为文本记录。
- Q: 会不会丢信息？ → A: 不丢。`发现版本号`文本保留来源；"修复版本"由"被哪个版本行收录"隐含表达。
- Q: 契约怎么办？ → A: `board@2` 的四表结构不变，版本表补 `Bug管理`，缺陷表把两个 relation 换成文本；契约升 `board@3`。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 版本行能列出本版要清零的缺陷 (Priority: P1)

版本表的「Bug管理」直接打开缺陷列表，能看到本版要清零的缺陷及其状态。

**Independent Test**: `v0.6.0` 的「Bug管理」显示 `BUG-01`，状态 `closed`。

**Acceptance Scenarios**:

1. **Given** 某缺陷属于本版需清零范围，**When** 查看该版本的「Bug管理」，**Then** 弹层显示缺陷编号、标题、状态。
2. **Given** 没有缺陷，**When** 查看，**Then** 显示为空，不报错。

### User Story 2 - 缺陷保留来源且不再有反向关系 (Priority: P1)

缺陷表的「发现版本号」是文本；「发现版本」「修复版本」两个 relation 已不存在。

**Acceptance Scenarios**:

1. **Given** 缺陷表字段清单，**When** 核对，**Then** 含 `发现版本号`（text），不含两个版本 relation。
2. **Given** `BUG-01`，**When** 读取，**Then** `发现版本号 = v0.6.0`。

### User Story 3 - 数据无损迁移 (Priority: P2)

迁移前已有的关联值被搬进文本字段，行数与其余字段不变。

**Acceptance Scenarios**:

1. **Given** 迁移前 `BUG-01.tf-b-found = ["v0.6.0"]`，**When** 迁移后，**Then** `tf-b-found-ver = "v0.6.0"`。
2. **Given** 迁移全过程，**When** 比对行数，**Then** 22 表 193 行不变。

## Requirements *(mandatory)*

- **FR-001**: `tf-ver` 新增 `Bug管理`（relation→`tf-bug`，display=标题，status=状态）。
- **FR-002**: `tf-bug` 新增 `发现版本号`（text），迁移时把原 `发现版本` 的行 id 写入。
- **FR-003**: 删除 `tf-bug` 的 `发现版本`、`修复版本` 两个 relation 字段。
- **FR-004**: 契约升 `board@3`：版本表 15 字段（含 Bug管理与三个比率、三个布尔），缺陷表 12 字段（发现版本号替代两个 relation）。
- **FR-005**: 迁移只对 `tableflow` 项目执行；迁移前已有备份（JSON 与 sqlite）。

## Success Criteria *(mandatory)*

- **SC-001**: 缺陷表无版本 relation，版本表有 `Bug管理`。
- **SC-002**: `BUG-01` 的来源信息不丢。
- **SC-003**: 全程无双向 relation 报错。

## Non-Goals

- 缺陷自动聚合的写入机制（由 014 的 ms_summary 负责）。
- 其余 6 个项目的迁移。
