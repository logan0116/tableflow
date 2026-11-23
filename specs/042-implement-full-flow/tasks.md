# 任务清单：开发节点完成 speckit 实现侧全流程

- **需求**：042-AR
- **规格**：`specs/042-implement-full-flow/spec.md`
- **计划**：`specs/042-implement-full-flow/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 开发节点跑完实现侧三段（覆盖场景：042-US1-AS1、042-US1-AS2、042-US1-AS3、042-US1-AS4）——`tf_dev_implement.py` 改为 plan → tasks → implement 三阶段：缺 `plan.md`/`tasks.md` 时按 spec 生成骨架并逐条回链场景号，缺产物或回链不全直接拒绝。
- [x] T002 实现 US2 版本需求设计节点产出 spec（覆盖场景：042-US2-AS1、042-US2-AS2、042-US2-AS3、042-US2-AS4）——`tf_dev_plan.py` 增加 039 结构下限校验（US≥2/场景≥5/FR≥6/边界≥3）并写 spec 侧阶段字段；`spec.md` 内容仍由需求方撰写，本节点只校验与登记。
- [x] T003 实现 US3 八个阶段字段全部有写入者（覆盖场景：042-US3-AS1、042-US3-AS2、042-US3-AS3）——`tf-dev-plan` 写 constitution/specify/clarify/analyze/checklist 五个，`tf-dev-implement` 写 plan/task/implement 三个，八字段全部有确定写入者；`na` 取值附理由写入报告 `stage_na_reasons`。
- [x] T004 实现 US4 单个规格完成不自动推进版本（覆盖场景：042-US4-AS1、042-US4-AS2）——新增 `full_scope` 判定：`--spec` 只覆盖版本内部分规格时只写规格状态，不推进版本节点（FR-010）。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_dev_implement_042.py` 8 项（标题剥离、场景号、plan/tasks 回链、骨架必然未勾选、覆盖率、测试命令探测）、`backend/tests/test_dev_plan_042.py` 9 项（章节计数边界、clarify 三态、结构下限、五字段集合）。
- [x] T006 更新文档与契约引用（如涉及）——`skills/tf-dev-implement/SKILL.md` 重写为三阶段口径，`skills/tf-dev-plan/SKILL.md` 增补结构下限与五字段写入表。
- [x] T007 跑通全量测试并记录结果——`backend/.venv/bin/python -m pytest -q` → 218 passed，1 warning，7.60s。
