# Feature Specification: 看板测试体系（v0.6.5，MS独立项目与危险清单用例）

**Feature Branch**: `018-ms-cases`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 018-AR。看板长期只靠手写脚本抽查，2026-11-19 一天内暴露两类问题：①写接口对错误请求形状静默成功（`PATCH` 把字段名放在顶层，返回 `success` 却一字未写）；②契约改了但数据与模板没跟上（7 个项目、15 处 relation 把阶段进度当完成判据，`data/template_board5.py` 仍是 board@2）。两者都不是"少写了几条测试"，而是**没有危险清单、没有一致性门禁**。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 错误形状静默成功 | `specs/012-protocol/spec.md` P-019 明文"多余顶层键被忽略"；实测 `PATCH {"tf-b-source":"review"}` → `success`，读回未变 | 客户端写错形状无法自察，人以为改了、其实没改 |
| 值域不校验 | `BUG-02` 的`来源`写成`manual`（枚举只有 test/prod/review/user），写入照收 | 枚举外值污染统计与前端标签 |
| 契约↔数据漂移 | 7 项目 15 处 relation 的`status_field`指到`speckit-implement状态`；`data/template_board5.py` 仍按 board@2 建表 | 弹层把"阶段完成"当"验收通过"；从模板起新项目直接造出旧口径表 |
| HTTP 层用例只测正确路径 | `backend/tests/test_agent_api.py` 8 条全部按 `{"values":{…}}` 构造 | 形状类缺陷在单测里永远看不见 |

## Clarifications

### Session 2026-11-19

- Q: 用例落在哪？ → A: MeterSphere **功能用例**（走 `ms_update`），不碰这个实例坏掉的接口测试数据模型（内部 REST 假成功）。
- Q: 为什么不在仓库写 pytest？ → A: 可重复靠 spec 场景 + `ms_update` 幂等同步，执行结果与证据留在 MS 台账，避免测试与规格两套真源。
- Q: 契约一致性怎么测？ → A: 做成"可执行断言"而不是口头检查，由门禁脚本产出结果，MS 用例记录该结果。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 写接口不再对错误请求形状静默成功 (Priority: P1)

客户端把字段名放在请求体顶层（而不是 `values` 里）、`values` 不是对象、`id` 与路径不一致时，服务端必须拒绝，并且不留下任何写入。

**Independent Test**: 对 `tf-bug/BUG-02` 发 `PATCH {"tf-b-source":"review"}`，期望 `400`，且读回`来源`仍是原值。

**Acceptance Scenarios**:

1. **Given** 一行已存在且某字段有值，**When** PATCH 请求体把字段名放在顶层、不带 `values`，**Then** 返回 400 failed，错误信息指出不认识的顶层键，该行该字段读回不变。
2. **Given** 同上，**When** `values` 传成数组而不是对象，**Then** 返回 400 failed，该行读回不变。
3. **Given** 请求体带 `id` 且与路径里的行 id 不一致，**When** 提交，**Then** 返回 400 failed，不落库。
4. **Given** 请求体既有正确 `values` 又有未知顶层键，**When** 提交，**Then** 返回 400 failed，且不产生部分写入（读回逐字段不变）。
5. **Given** 请求体形状正确，**When** 提交，**Then** 返回 200 success，读回值等于提交值。

### User Story 2 - 写入前校验值域与引用，非法值不落库 (Priority: P1)

枚举外值、不存在的关联目标、跨项目关联、计算字段直写、闸门字段覆盖，都必须拒绝。

**Independent Test**: 对 `tf-bug/BUG-02` 的`来源`写 `manual`，期望 `400`，读回仍是合法值。

**Acceptance Scenarios**:

1. **Given** 一个枚举字段，**When** 写入不在枚举内的值，**Then** 返回 400 failed，错误信息列出合法取值，读回不变。
2. **Given** 一个关系字段，**When** 写入不存在的目标行 id，**Then** 返回 400 failed，不落库。
3. **Given** 一个关系字段，**When** 写入另一项目表的行 id，**Then** 返回 400 failed，不落库。
4. **Given** 一个计算字段，**When** 直接写入，**Then** 返回 400 failed，提示改用 `overrides`。
5. **Given** 一个带 `gate=true` 的计算字段，**When** 用 `overrides` 覆盖，**Then** 返回 400 failed；**When** 清除覆盖（值为 null），**Then** 允许并回读为空。

### User Story 3 - 契约与数据的一致性可被断言 (Priority: P1)

按 `board@3` 校验全部项目与模板产物：字段名、类型、顺序、relation 的显示列与状态列、闸门标记、计算口径，任一处漂移都要失败并指出位置。

**Independent Test**: 造一个字段顺序被调换的项目副本，跑门禁，期望失败并指出"字段顺序不符"。

**Acceptance Scenarios**:

1. **Given** `specs/017-bug-relation/board@3.yaml`，**When** 校验全部项目的四表字段名、类型、顺序与每张表的单元选项集合（枚举取值，不比显示顺序），**Then** 差异为 0，任何不符都按项目/表/字段列出。
2. **Given** 全部 relation 字段，**When** 校验 `display_field` 与 `status_field`，**Then** 状态列指向该表的完成判据字段（indep→验收状态、dep→回归状态、bug→状态），无一处缺失或指错。
3. **Given** 版本表的三个闸门布尔与`发布条件`，**When** 校验计算口径，**Then** 三者都是 `gate=true`、`发布条件`是它们的`and`，且数量类字段没有被打标。
4. **Given** 模板脚本 `data/template_board5.py` 的产物，**When** 用同一门禁校验，**Then** 与 `board@3` 差异为 0。

### User Story 4 - 用例台账可重复且不产生重复条目 (Priority: P2)

同一版本的 spec 场景同步两次，第二次不新增用例；测试计划按版本建或复用。

**Independent Test**: 连续两次跑 `ms_update --version v0.6.5`，第二次"新建 0"。

**Acceptance Scenarios**:

1. **Given** 本 spec，**When** 跑 `ms_update` 预览，**Then** 解析出的场景数等于本 spec 的验收场景条数。
2. **Given** 已同步过一次，**When** 再跑一次 `--apply`，**Then** 新建 0、更新/跳过覆盖全部条目、模块内无重复用例名。
3. **Given** 版本 `v0.6.5`，**When** 建或复用测试计划，**Then** 计划名为 `tableflow v0.6.5 · …`、类型为 `TEST_PLAN`、能在界面打开。

## Requirements *(mandatory)*

- **FR-001**: 写接口 MUST 拒绝 `values/overrides/id` 之外的顶层键，返回 400 且零写入；`values` 非对象、`id` 与路径不一致同样拒绝。
- **FR-002**: 枚举字段 MUST 校验取值在枚举内，错误信息 MUST 列出合法取值。
- **FR-003**: 关系字段 MUST 校验目标行存在且同项目；计算字段 MUST 拒绝直写；`gate=true` 的计算字段 MUST 拒绝 `overrides` 覆盖（清除覆盖允许）。
- **FR-004**: 提供一致性门禁入口，按 `board@3` 校验全部项目的字段名/类型/顺序、relation 的两列配置、闸门标记与计算口径，输出可机器判定的结果。
- **FR-005**: 模板脚本 MUST 产出与 `board@3` 一致的版本表与 indep 字段，且纳入同一门禁校验。
- **FR-006**: 本需求的验收场景 MUST 通过 `ms_update` 同步成 MS 功能用例，用例名以 `018-USn-ASm` 开头，重复同步幂等。
- **FR-007**: 一致性门禁 MUST 把 enum 字段的取值集合纳入比对（不只比字段名/类型/顺序），并 MUST 报告行内取值不在枚举内的存量数据——BUG-04 就是这类漂移（契约一套、线上另一套、数据里还有自由文本）。

## Non-Goals

- 不改 `board@3` 的字段口径本身（那是 016/017 的范围）。
- 不做 MS 与 TF 之间的缺陷自动闭环（014 的范围）。
- 不做前端 UI 的人工验收（视觉与交互另开）。
- 不恢复/不使用本实例的接口测试模块（内部 REST 假成功，见 018 背景）。

## Success Criteria

- 危险清单五类（错误形状、枚举外值、悬空/跨项目引用、计算字段直写、闸门覆盖）都有用例且执行通过。
- 门禁在 `board@3` 与 8 个项目上跑出"差异 0"，对模板产物同样为 0。
- `ms_update` 第二次同步新建 0 条，用例总数 = 本 spec 验收场景数。
- 发布前 `v0.6.5` 的三比率达标、`发布条件=是`。
