# 任务清单：依赖需求完整变更工作流

- **需求**：037-AR
- **规格**：`specs/037-dep-change-workflow/spec.md`
- **计划**：`specs/037-dep-change-workflow/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 一次变更跨多份规格并统一编排（覆盖场景：037-US1-AS1、037-US1-AS2、037-US1-AS3、037-US1-AS4）——dep 表以「基线修订」「受影响条款」「设计与任务」「一致性检查」「集成验收」五个字段承载跨规格编排：共用设计只写一次、受影响条款按规格分行、集成验收与单规格验证分列；置 passed 时三项缺一即拒（D1）。
- [x] T002 实现 US2 小补丁同样走完整流程（覆盖场景：037-US2-AS1、037-US2-AS2、037-US2-AS3）——`change_flow.py` 在回归状态推进到 passed 时强制校验受影响条款、一致性检查、集成验收三项非空，规模不影响判定；规格修订取 not_needed 必须写判定依据。
- [x] T003 实现 US3 变更产出新的规格修订（覆盖场景：037-US3-AS1、037-US3-AS2、037-US3-AS3）——交付记录按「受影响条款」逐份判定：条款里点名了哪几份规格，就只给那几份产生修订标识 `<依赖需求编号>@<所在版本>`；未点名的规格不因该变更产生修订。`GET /api/projects/{项目}/delivery` 的 `effective_revisions` 与 `current_revision` 据此计算。
- [x] T004 实现 US4 仅做关联不产生依赖需求（覆盖场景：037-US4-AS1、037-US4-AS2）——`tf-register` 登记变更单时强制 `--affected`，没有实际增量的关联在入口即被拒（037 FR-009）；引擎侧由 D1 兜底：无受影响条款的依赖需求永远无法置 passed。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_change_flow_037.py` 7 项：缺三项被拒、齐备通过、缺一项被拒且只报缺的那项、not_needed 缺依据被拒、带依据通过、历史导入已 passed 不校验、未迁移表不阻断。
- [x] T006 更新文档与契约引用（如涉及）——契约 board@5：dep 新增 增量说明/基线修订/受影响条款/设计与任务/一致性检查/集成验收 六字段；新增 change_flow_full、change_regress_precondition、change_revision_not_needed、change_revision_tag、change_no_increment 五条规则；迁移脚本纳入（dry-run 8 项目 112 项）。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 278 passed。
