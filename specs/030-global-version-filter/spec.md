# Feature Specification: 版本筛选全局化

**Feature Branch**: `030-global-version-filter`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 030-AR。027 的版本筛选只作用于版本表；实际使用时选定版本后，切到需求、用例、缺陷表仍然看到全部行，版本上下文断掉。本需求把版本筛选提到全局：选定某版本后，其余三张表也只显示该版本关联的行。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 版本筛选只管版本表 | 027 实现只在 `table.id.endsWith("-ver")` 时过滤 | 切到需求表仍见全部 28 行，版本上下文丢失 |
| 关联关系是现成的 | ver.indep、ver.runs→run.case、ver.bugs 已在数据里 | 不需要新接口，前端按关联 id 过滤即可 |

## Clarifications

### Session 2026-11-22

- Q: 需求表怎么知道属于哪个版本？ → A: 读版本行的 `独立需求管理` 关联数组，按行 id 过滤。
- Q: 用例表呢？ → A: 版本行 `测试用例` 存的是 run 行 id，需经 run 的 `用例` 字段映射到 case 行 id 再过滤。
- Q: 缺陷表呢？ → A: 读版本行 `Bug管理` 关联数组。
- Q: 选「全部版本」时？ → A: 三张表都不过滤，显示全部行。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 需求表按所选版本过滤 (Priority: P1)

选定某版本后，切到独立规格需求表只看到该版本关联的需求。

**Independent Test**: 选 v0.7.2，需求表只显示 029/030/031 三行。

**Acceptance Scenarios**:

1. **Given** 版本筛选为 v0.7.2，**When** 切到独立规格需求表，**Then** 只显示该版本关联的需求行。
2. **Given** 版本筛选为「全部版本」，**When** 切到需求表，**Then** 显示全部需求行。
3. **Given** 所选版本没有关联需求，**When** 看需求表，**Then** 显示空状态而不是全部行。

### User Story 2 - 用例表按所选版本过滤 (Priority: P1)

选定某版本后，测试用例表只显示该版本纳入的用例。

**Independent Test**: 选 v0.7.1，用例表只显示该版本的 33 条。

**Acceptance Scenarios**:

1. **Given** 版本筛选为 v0.7.1，**When** 切到测试用例表，**Then** 只显示该版本 `ver.runs` 对应的用例行。
2. **Given** 版本筛选为「全部版本」，**When** 看用例表，**Then** 显示全部 183 条。

### User Story 3 - 缺陷表按所选版本过滤 (Priority: P1)

选定某版本后，缺陷表只显示该版本 Bug 管理集合内的行。

**Independent Test**: 选 v0.7.1，缺陷表只显示该版本关联的缺陷。

**Acceptance Scenarios**:

1. **Given** 版本筛选为某版本，**When** 切到缺陷表，**Then** 只显示该版本 `Bug管理` 关联的缺陷行。
2. **Given** 该版本没有关联缺陷，**When** 看缺陷表，**Then** 显示空状态。

### User Story 4 - 不改变数据与判定 (Priority: P1)

过滤只影响渲染，接口与计算字段不变。

**Independent Test**: 过滤前后同一行读回值一致。

**Acceptance Scenarios**:

1. **Given** 任一筛选状态，**When** 对比接口返回与界面显示，**Then** 行数与内容一致（过滤后）。
2. **Given** 筛选状态，**When** 跑 `check_board`，**Then** 差异仍为 0。

## Requirements *(mandatory)*

- **FR-001**: 版本筛选状态 MUST 为全局（跨表保持），切换表时不重置。
- **FR-002**: 选定版本后，独立规格需求表 MUST 按 `ver.indep` 过滤。
- **FR-003**: 选定版本后，测试用例表 MUST 按 `ver.runs → run.case` 过滤。
- **FR-004**: 选定版本后，缺陷表 MUST 按 `ver.bugs` 过滤。
- **FR-005**: 选「全部版本」时四张表 MUST 都不过滤。
- **FR-006**: 过滤 MUST 只影响渲染，MUST NOT 改接口、数据或判定。
- **FR-007**: 依赖需求表 MUST 按 `ver.dep` 同样过滤（与其余三张表一致）。

## Non-Goals

- 不改版本筛选的「最新/全部/指定」三态（027 的范围）。
- 不改数据模型与接口。
- 不做跨版本对比视图。

## Success Criteria

- 选 v0.7.2 后，需求表 3 行、用例表 33 条（若已派生）、缺陷表按关联。
- 选「全部版本」后各表恢复全量。
- `check_board` 差异 0。
