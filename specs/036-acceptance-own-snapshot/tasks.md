# 任务清单：测试验收按版本自身执行结果判定

- **需求**：036-AR
- **规格**：`specs/036-acceptance-own-snapshot/spec.md`
- **计划**：`specs/036-acceptance-own-snapshot/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 有失败用例的版本不得通过测试验收（覆盖场景：036-US1-AS1、036-US1-AS2、036-US1-AS3）——`tf_test_check.py` 增加「执行结果全部通过」判据，`version_stage` 的「测试验收」闸门同步按结果判定；对 v0.7.3 只读预演已由「通过」变为 failed 并指出 `v0.7.3--031-US4-AS1`。
- [x] T002 实现 US2 后续版本的修复不改变前序版本结论（覆盖场景：036-US2-AS1、036-US2-AS2、036-US2-AS3）——判定只读本版执行行，不读其他版本；结论写入后不被后续版本的全局状态改写（v0.7.4 修复 BUG-06 后重跑 v0.7.3 仍为 failed）。
- [x] T003 实现 US3 失败与阻塞用例的放行通道（覆盖场景：036-US3-AS1、036-US3-AS2、036-US3-AS3、036-US3-AS4）——契约新增 run 表三字段（放行标记/放行批准人/放行理由），引擎要求三者齐备才放行；迁移脚本 `backend/scripts/migrate_board5_waiver.py` 就绪（8 个项目 24 个字段，待部署后执行）。
- [x] T004 实现 US4 v0.7.3 以红灯收口（覆盖场景：036-US4-AS1、036-US4-AS2）——发布状态由 planned 置 dropped（终止），测试验收保持 failed、发布条件保持假；失败用例 `v0.7.3--031-US4-AS1` 的结果与证据保留，未改写为通过。看板自此只剩 v0.8.0 一个 planned 版本。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_test_accept_036.py` 7 项：全通过可收口、失败拦下、阻塞拦下、有效放行通过、缺批准人/缺理由拦下、未执行拦下。
- [x] T006 更新文档与契约引用（如涉及）——契约 board@5 新增 run_result_judgement/run_waiver/acceptance_conclusion_immutable/test_accept_gate 四条规则并修正 case_progress_only 的自相矛盾表述；`skills/tf-test-check/SKILL.md` 同步。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 233 passed。
