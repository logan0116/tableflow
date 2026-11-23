# 任务清单：未完成需求的范围拆分与放弃

- **需求**：034-AR
- **规格**：`specs/034-scope-split-drop/spec.md`
- **计划**：`specs/034-scope-split-drop/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 拆分一条做不完的需求（覆盖场景：034-US1-AS1、034-US1-AS2、034-US1-AS3、034-US1-AS4）——`tf-lifecycle --action split`：新建承接方并在原需求写结构化拆分记录；原需求不置终态、继续按保留范围交付；已 accepted 时由引擎 L6 拒绝。
- [x] T002 实现 US2 放弃一条不做的需求（覆盖场景：034-US2-AS1、034-US2-AS2、034-US2-AS3）——`spec_lifecycle.py` 实现：置 dropped 必须同时给出放弃理由与放弃时间、且必须先摘除全部版本关联；dropped 为终态不可回退；保留当时阶段状态与未完成结论。
- [x] T003 实现 US3 拆分与放弃之后仍然可追溯（覆盖场景：034-US3-AS1、034-US3-AS2、034-US3-AS3）——新增只读接口 `GET /api/projects/{项目}/lifecycle?spec=<编号>`：解析拆分记录为结构化条目，双向给出 `split_out`/`split_in`，沿 `split_out` 展开多层 `chain`（防环、深度上限 10），并返回终态与放弃留痕。
- [x] T004 实现 US4 非法操作被明确拒绝（覆盖场景：034-US4-AS1、034-US4-AS2、034-US4-AS3、034-US4-AS4）——已 accepted 不得写拆分记录；已 dropped 不得挂版本；已 dropped 的规格不得新开依赖需求；拒绝信息含实际状态与下一步建议。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_spec_lifecycle_034.py` 8 项：放弃缺理由/缺时间、未摘除版本、摘除后成功、终态不可回退、已放弃不得挂版本、已放弃不得开变更单、未验收可拆分、已验收拒绝拆分。
- [x] T006 更新文档与契约引用（如涉及）——契约 board@5：`验收状态` 增加 dropped 终态；indep 新增 放弃理由/放弃时间/拆分记录 三字段；新增 spec_terminal_states、spec_drop、spec_drop_immutable、spec_split、spec_split_not_terminal 五条规则；迁移脚本 `backend/scripts/migrate_board5.py` 覆盖 board@5 全部字段（dry-run：8 个项目 56 项）。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 252 passed。
