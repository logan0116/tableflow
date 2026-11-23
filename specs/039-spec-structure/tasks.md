# 任务清单：规格结构完整性

- **需求**：039-AR
- **规格**：`specs/039-spec-structure/spec.md`
- **计划**：`specs/039-spec-structure/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 规格必须包含规范层与验证层（覆盖场景：039-US1-AS1、039-US1-AS2、039-US1-AS3）——新增 `spec_structure.py` 纯解析器（章节、下限、场景可判定性、FR↔场景追溯）与 `backend/scripts/spec_structure_report.py` 差距报告；缺 Functional Requirements 或 Edge Cases 时功能需求/边界计数为 0，天然低于下限。
- [x] T002 实现 US2 结构下限被强制（覆盖场景：039-US2-AS1、039-US2-AS2、039-US2-AS3）——`tf-dev-plan` 在 specify 阶段与版本需求设计节点都执行 US≥2/场景≥5/FR≥6/边界≥3 校验，不达标 `failed` 且列出各维度实际值与差额（042 已落地，039 补规则与报告）。
- [x] T003 实现 US3 现有规格按新标准补齐（覆盖场景：039-US3-AS1、039-US3-AS2）——差距报告已产出并可重复运行：41 份规格中 17 份达标，23 份缺 Functional Requirements、15 份缺 Edge Cases、3 份缺 User Scenarios。**决定不做批量回填**（2026-11-23 与用户确认）：这 23 份是已发布版本的历史规格，当初就没有规范层，现在补写等于为凑下限编造需求，比保留缺口更有害。回填策略改为渐进式——新规格按新标准写，历史规格在被下一次改动时顺带补齐；差距报告持续作为可视化的欠账清单。
- [x] T004 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_spec_structure_039.py` 9 项：达标无缺口、缺章节、缺边界、低于下限、缺 When 计入 malformed、追溯 linked/absent、场景号生成、深层标题不提前关闭章节。
- [x] T005 更新文档与契约引用（如涉及）——契约 board@5 新增 `spec_structure_floor`、`spec_scenario_form`、`spec_traceability` 三条规则。
- [x] T006 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 271 passed。
