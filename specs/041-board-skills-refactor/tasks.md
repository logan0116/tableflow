# 任务清单：看板操作技能重构

- **需求**：041-AR
- **规格**：`specs/041-board-skills-refactor/spec.md`
- **计划**：`specs/041-board-skills-refactor/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 用新技能登记需求与变更单（覆盖场景：041-US1-AS1、041-US1-AS2、041-US1-AS3、041-US1-AS4、041-US1-AS5）——新增 `tf-register`：按 `classify.order` 自动分派 in_place/change/cross/new_spec/out_of_board 五种情况，`--kind` 可强制；发请求前做规则预检（C4 未验收不得开变更单、C1/C2 重复挂载），最终判定仍由引擎执行。
- [x] T002 实现 US2 用新技能出发布就绪报告（覆盖场景：041-US2-AS1、041-US2-AS2、041-US2-AS3、041-US2-AS4）——新增 `tf-release-status`：只读，按 board@5 `发布条件 = and(六节点全部 done)` 复算，三布尔降为展示字段；released/planned/dropped 三态都能报；每条判定带复算口径与数据来源。线上实测：v0.8.0 不可发布、v0.7.3 已终止、v0.7.4 可发布。
- [x] T003 实现 US3 五个旧技能被彻底移除（覆盖场景：041-US3-AS1、041-US3-AS2、041-US3-AS3）——`tf-update`、`tf-status`、`ms-update`、`ms-implement`、`ms-summary` 已从仓库删除；活跃技能的文档交叉引用全部改指新技能（单测扫描确认无残留）；全局技能目录本就只有六个在役技能，无需清理。
- [x] T004 实现 US4 新技能覆盖登记与报告之外的必要操作（覆盖场景：041-US4-AS1、041-US4-AS2）——新增 `tf-lifecycle`：`drop`（先摘版本再置 dropped，写理由与时间）、`split`（新建承接方 + 写拆分记录）、`cleanup`（跨版本重复只保留首次出现，且要求 036 已生效）。线上实测 `cleanup` 正确拦下了未迁移的环境。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_skills_041.py` 11 项：旧技能已删除、活跃技能齐备、文档无残留引用、classify 五个分支、强制分派、semver 排序三则。
- [x] T006 更新文档与契约引用（如涉及）——三个新技能各配 SKILL.md；`tf-dev-plan`/`tf-test-plan`/`tf-test-implement`/`tableflow-board` 的交叉引用改指新技能。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 308 passed。
