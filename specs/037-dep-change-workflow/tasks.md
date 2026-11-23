# 任务清单：依赖需求完整变更工作流

- **需求**：037-AR
- **规格**：`specs/037-dep-change-workflow/spec.md`
- **计划**：`specs/037-dep-change-workflow/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [ ] T001 实现 US1 一次变更跨多份规格并统一编排（覆盖场景：037-US1-AS1、037-US1-AS2、037-US1-AS3、037-US1-AS4）
- [x] T002 实现 US2 小补丁同样走完整流程（覆盖场景：037-US2-AS1、037-US2-AS2、037-US2-AS3）——`change_flow.py` 在回归状态推进到 passed 时强制校验受影响条款、一致性检查、集成验收三项非空，规模不影响判定；规格修订取 not_needed 必须写判定依据。
- [ ] T003 实现 US3 变更产出新的规格修订（覆盖场景：037-US3-AS1、037-US3-AS2、037-US3-AS3）
- [ ] T004 实现 US4 仅做关联不产生依赖需求（覆盖场景：037-US4-AS1、037-US4-AS2）
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_change_flow_037.py` 7 项：缺三项被拒、齐备通过、缺一项被拒且只报缺的那项、not_needed 缺依据被拒、带依据通过、历史导入已 passed 不校验、未迁移表不阻断。
- [x] T006 更新文档与契约引用（如涉及）——契约 board@5：dep 新增 增量说明/基线修订/受影响条款/设计与任务/一致性检查/集成验收 六字段；新增 change_flow_full、change_regress_precondition、change_revision_not_needed、change_revision_tag、change_no_increment 五条规则；迁移脚本纳入（dry-run 8 项目 112 项）。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 278 passed。
