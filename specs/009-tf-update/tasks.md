# Tasks: tf_update需求登记技能

**Input**: `specs/009-tf-update/spec.md`

**范围**: 只交付`skills/tf-update/SKILL.md`与`specs/009-tf-update/`产物；不写业务代码、不改看板结构、不动他人的行。

## Phase 1: 口径与判定

- [x] T001判定树取`board@1.classify.order`五分支，写清顺序即优先级与每个分支的动作
- [x] T002依据格式定为`<规格编号>#US<n>-AS<m>`、`新增条款`、`不改产品行为`三种写法，并写"指不到只问一个问题"的边界
- [x] T003场景索引器：按`### User Story`与`**Acceptance Scenarios**`计数，用008-AR（US3/AS10，看板场景数=10）核对称谓

## Phase 2: 技能实现

- [x] T004读上下文：版本表、indep行、场景索引、覆盖检索四段命令写进技能
- [x] T005判重：行id + 归一化条款，三结论（new/already_registered/conflict）
- [x] T006登记器：按字段名解析、校验人给的版本（missing/不存在/非planned/不晚于已发布都拒绝）、POST新行、幂等追加relation、回读四校验
- [x] T007三态处理：`failed`不重试、`unknown`回读判定、`success`但回读不符按失败
- [x] T008 `in_place`就地改路径：只改记录字段，不碰`验收状态`
- [x] T009报告六字段：分类/依据/动作/版本/三态/回读

## Phase 3: 实跑与清理（证据见`runbook.md`）

- [x] T010真实看板演练：`099-AR`登记并显式挂到临时`planned`版本`v0.0.1-test`（V060-02修复后改为显式版本，见runbook第10节）
- [x] T011幂等：同参数重跑返回`already_registered`，行数不变
- [x] T012冲突：同id换条款返回`failed`，不覆盖已有行
- [x] T013清理：摘关联 → 删演练行 → 删临时版本；回读404、`tf-indep`回到15行、`v0.6.0`逐字段与执行前相同
- [x] T014命令与输出贴进`runbook.md`，含执行前后快照

## Phase 4: 登记

- [x] T015更新看板`009-AR`：场景数、任务总数、阶段状态、`implement=done`

> 验收（`acceptance=accepted`）由需求方判定，不在本清单内。
