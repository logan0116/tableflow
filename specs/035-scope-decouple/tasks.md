# 任务清单：交付范围与测试范围解耦

- **需求**：035-AR
- **规格**：`specs/035-scope-decouple/spec.md`
- **计划**：`specs/035-scope-decouple/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 复测历史能力而不重复挂载需求（覆盖场景：035-US1-AS1、035-US1-AS2、035-US1-AS3）——`tf-test-plan` 去掉「来源规格必须挂在版本」的强制失败；不在交付范围的来源照常派生，只写 `ver.测试用例`，报告列进 `out_of_scope_specs`。线上 v0.8.0 用 `--spec 019-AR --dry-run` 验证：派生 27 条、不写交付范围。
- [x] T002 实现 US2 交付范围只记录本版工作（覆盖场景：035-US2-AS1、035-US2-AS2、035-US2-AS3）——契约新增 `delivery_scope_only`：两个关联字段各自只表达一件事，不得互相推导；重复挂载由 033 的 C1 在引擎层拦截。
- [x] T003 实现 US3 用例纳入时的校验仍有约束（覆盖场景：035-US3-AS1、035-US3-AS2、035-US3-AS3）——源场景消失仍进 `orphans` 并拒绝静默删除；同一用例跨版本各自建 `<版本>--<用例>` 行、互不覆盖；来源能力未验收时允许纳入并记入 `unaccepted_specs`。
- [x] T004 实现 US4 拒绝把已交付需求重复挂载（覆盖场景：035-US4-AS1、035-US4-AS2）——由 033 的 C1 承担：引擎对重复挂载返回 400 并给出占用版本；033 已清理历史 13 处重复。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_test_plan_035.py` 4 项覆盖 `split_scope`：全在范围内、历史能力、纯回归版本、顺序保留。
- [x] T006 更新文档与契约引用（如涉及）——契约 board@5 新增 `case_scope_independent` 与 `delivery_scope_only`；`skills/tf-test-plan/SKILL.md` 增加跨版本来源与纯回归版本说明。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 237 passed。
