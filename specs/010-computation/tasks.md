# Tasks: 计算口径落地（010）

**Input**: `specs/010-computation/spec.md`（条款取自看板`GET /api/tables/tf-indep/rows/010-AR`）

**范围**: 只动`backend/src/tableflow/`的计算与覆盖校验、`backend/tests/`的新增用例、`specs/010-computation/`文档；不改存量数据、不改接口、不部署。

## Phase 1: 文档

- [x] T001写`specs/010-computation/spec.md`：空集、悬空、闸门、写后重算四组条款与判定理由
- [x] T002写`specs/010-computation/tasks.md`：任务分解、验证口径、非目标

## Phase 2: 计算收口

- [x] T003 [a] 固定空集语义并加注释：`count=0`、`sum=0`、`rollup all/none=true`、`percent=null`（`calculation.py`五种kind分支）
- [x] T004 [b] `_selected_target_rows`返回（现存行, 悬空数）；布尔`rollup`在悬空时`all`/`none`判否、`any`按已核验成员判定
- [x] T005 [b] 边界确认：数量类维持"忽略悬空"，空集上`min/max/count_distinct`仍走原口径
- [x] T006 [c] 新增计算字段`options.gate`校验：必须布尔、只允许`and`与布尔`rollup`，否则`400`
- [x] T007 [c] `apply_overrides`拒绝闸门字段设值（`400`+整体回滚），允许清除历史覆盖
- [x] T008 [d] 确认行写路径（`create_row`/`update_row`/`delete_row`）已在同事务调用`recompute_for_write`，无需改动

## Phase 3: 用例

- [x] T009新增`backend/tests/test_computation_010.py`：a组空集1例、b组悬空3例、c组闸门4例、d组写后重算3例，共11例
- [x] T010跑`cd backend && .venv/bin/python -m pytest -q`：基线`97 passed`，新增后`108 passed`

## Phase 4: 验证与登记

- [x] T011线上7个项目21张表做前后快照比对，确认除`010-AR`行外业务数据未变
- [x] T012更新看板`010-AR`行：场景数14、任务总数12、阶段状态与`implement=done`

## 非目标

- 不给存量计算字段打`gate`标记（存量迁移另立需求）。
- 不改relation写入校验、不改读侧、不新增路由或计算`kind`。
- 不做展示层（`%`渲染、"就绪"文案）。
- 不提交代码、不部署、不重启线上服务（发布由队长执行）。
