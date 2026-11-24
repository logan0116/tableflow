"""v0.8.0 验收映射：每条验收场景对应到验证它的测试。

一条场景可以映射到多个测试（多个测试共同守住），用列表表示。映射的键是场景号
（`<规格号>-US<n>-AS<m>`），值是一组 `文件::函数` 引用。

**这份映射是执行用例的证据来源**：`tf-test-implement` 记录某条用例通过时，证据就是
这里列出的测试。新增或修改场景时必须同步这张表，`test_acceptance_coverage_080.py`
会检查「规格里的每条场景都在表里」且「表里引用的测试都真实存在」。
"""

from __future__ import annotations

COVERED: dict[str, tuple[str, ...]] = {
    # ---------- 033 交付记录与规格演进分离 ----------
    "033-US1-AS1": ("test_delivery_033.py::test_spec_without_changes_reports_initial_revision",),
    "033-US1-AS2": ("test_delivery_033.py::test_spec_with_effective_change_reports_that_change",),
    "033-US1-AS3": ("test_delivery_033.py::test_unpassed_change_is_listed_but_not_effective",),
    "033-US2-AS1": ("test_board_rules_033.py::test_c1_rejects_same_spec_in_second_version",),
    "033-US2-AS2": ("test_board_rules_033.py::test_c2_rejects_same_change_in_second_version",),
    "033-US2-AS3": ("test_board_rules_033.py::test_c3_rejects_dep_before_spec_version",),
    "033-US2-AS4": ("test_board_rules_033.py::test_c3_allows_same_version",),
    "033-US2-AS5": ("test_board_rules_033.py::test_c3_multi_spec_uses_latest",),
    "033-US3-AS1": ("test_cleanup_033.py::test_plan_keeps_first_occurrence",),
    "033-US3-AS2": ("test_cleanup_033.py::test_plan_keeps_first_occurrence",),
    "033-US3-AS3": ("test_cleanup_033.py::test_plan_handles_semver_order",),
    "033-US3-AS4": ("test_cleanup_033.py::test_cleanup_leaves_runs_and_changes_untouched",),
    "033-US4-AS1": ("test_board_rules_033.py::test_033_us4_as1_rejection_carries_four_elements",),
    "033-US4-AS2": ("test_board_rules_033.py::test_rejection_is_atomic",),
    # ---------- 034 拆分与放弃 ----------
    "034-US1-AS1": ("test_split_034.py::test_split_log_records_time_clauses_and_target",),
    "034-US1-AS2": ("test_split_034.py::test_split_log_appends_without_losing_history",),
    "034-US1-AS3": ("test_split_034.py::test_split_log_records_time_clauses_and_target",),
    "034-US1-AS4": ("test_split_034.py::test_split_keeps_origin_alive",),
    "034-US2-AS1": ("test_spec_lifecycle_034.py::test_drop_succeeds_after_detaching",),
    "034-US2-AS2": ("test_spec_lifecycle_034.py::test_lifecycle_report_shows_abandon_trace",),
    "034-US2-AS3": ("test_spec_lifecycle_034.py::test_dropped_is_terminal",),
    "034-US3-AS1": ("test_spec_lifecycle_034.py::test_lifecycle_report_parses_split_chain",),
    "034-US3-AS2": ("test_spec_lifecycle_034.py::test_lifecycle_report_shows_abandon_trace",),
    "034-US3-AS3": ("test_spec_lifecycle_034.py::test_lifecycle_report_finds_split_in",),
    "034-US4-AS1": ("test_spec_lifecycle_034.py::test_split_rejected_after_accepted",),
    "034-US4-AS2": ("test_spec_lifecycle_034.py::test_dropped_spec_cannot_be_attached",),
    "034-US4-AS3": ("test_spec_lifecycle_034.py::test_dropped_spec_cannot_open_change",),
    "034-US4-AS4": ("test_spec_lifecycle_034.py::test_drop_requires_detaching_from_version",),
    # ---------- 035 交付范围与测试范围解耦 ----------
    "035-US1-AS1": ("test_scope_035.py::test_version_accepts_out_of_scope_runs",),
    "035-US1-AS2": ("test_scope_035.py::test_out_of_scope_case_does_not_change_delivery_ratio",),
    "035-US1-AS3": ("test_scope_035.py::test_case_still_traces_to_its_spec",),
    "035-US2-AS1": ("test_scope_035.py::test_delivery_scope_only_lists_own_work",),
    "035-US2-AS2": ("test_scope_035.py::test_pure_regression_version_has_empty_delivery",),
    "035-US2-AS3": ("test_scope_035.py::test_pure_regression_version_still_advances_nodes",),
    "035-US3-AS1": ("test_test_plan_035.py::test_split_scope_separates_historical_capability",),
    "035-US3-AS2": ("test_scope_035.py::test_missing_source_scenario_is_reported_as_orphan",),
    "035-US3-AS3": ("test_scope_035.py::test_same_case_gets_independent_run_per_version",),
    "035-US4-AS1": ("test_board_rules_033.py::test_035_us4_as1_rejection_suggests_using_cases",),
    "035-US4-AS2": ("test_board_rules_033.py::test_rejection_is_atomic",),
    # ---------- 036 测试验收按版本自身结果判定 ----------
    "036-US1-AS1": ("test_test_accept_036.py::test_failing_run_blocks_close",),
    "036-US1-AS2": ("test_test_accept_036.py::test_all_pass_allows_close",),
    "036-US1-AS3": ("test_test_accept_036.py::test_unexecuted_run_blocks_close",),
    "036-US2-AS1": ("test_test_accept_036.py::test_036_us2_as1_rejudge_old_version_stays_failed",),
    "036-US2-AS2": ("test_test_accept_036.py::test_conclusion_not_rewritten_by_later_version",),
    "036-US2-AS3": ("test_test_accept_036.py::test_conclusion_not_rewritten_by_later_version",),
    "036-US3-AS1": ("test_test_accept_036.py::test_036_us3_as1_unwaived_fail_is_listed",),
    "036-US3-AS2": ("test_test_accept_036.py::test_valid_waiver_allows_close",),
    "036-US3-AS3": ("test_test_accept_036.py::test_valid_waiver_allows_close",),
    "036-US3-AS4": ("test_test_accept_036.py::test_waiver_flag_expires_after_pass",),
    "036-US4-AS1": ("test_test_accept_036.py::test_036_us4_as1_failed_version_can_be_dropped",),
    # ---------- 037 依赖需求完整变更流 ----------
    "037-US1-AS1": ("test_change_flow_037.py::test_037_us1_as1_multi_spec_baselines_are_separate",),
    "037-US1-AS4": ("test_change_flow_037.py::test_037_us1_as4_integration_record_is_separate",),
    "037-US2-AS1": ("test_change_flow_037.py::test_037_us2_as1_single_scenario_change_still_needs_four_parts",),
    "037-US2-AS2": ("test_change_flow_037.py::test_037_us2_as2_reuse_records_source_version",),
    "037-US2-AS3": ("test_change_flow_037.py::test_not_needed_with_evidence_is_allowed",),
    "037-US3-AS1": ("test_delivery_033.py::test_spec_with_effective_change_reports_that_change",),
    "037-US3-AS2": ("test_delivery_033.py::test_spec_with_effective_change_reports_that_change",),
    "037-US3-AS3": ("test_per_spec_revision_037.py::test_affected_clauses_decide_which_spec_gets_revision",),
    "037-US4-AS2": ("test_change_flow_037.py::test_037_us4_as2_missing_affected_clause_blocks",),
    # ---------- 038 阶段产物与证据强制 ----------
    "038-US1-AS1": ("test_stage_evidence_038.py::test_038_us1_as1_report_returns_plan_evidence",),
    "038-US1-AS2": ("test_skill_e2e_083.py::test_s3_skeleton_plan_is_not_done",),
    "038-US1-AS3": ("test_stage_evidence_038.py::test_038_us1_as3_missing_artifact_lists_requirement",),
    "038-US2-AS2": ("test_stage_evidence_038.py::test_038_us2_as2_reuse_with_matching_version_is_allowed",),
    "038-US2-AS3": ("test_stage_evidence_038.py::test_038_us2_as3_superseded_version_is_rejected",),
    "038-US3-AS1": ("test_stage_evidence_038.py::test_038_us3_as1_empty_stage_reports_unprovable",),
    "038-US4-AS1": ("test_dev_implement_042.py::test_tasks_block_implement_until_checked",),
    "038-US4-AS2": ("test_dev_implement_042.py::test_tasks_block_implement_until_checked",),
    # ---------- 039 规格结构完整性 ----------
    "039-US1-AS1": ("test_spec_structure_039.py::test_missing_functional_requirements_is_flagged",),
    "039-US1-AS2": ("test_spec_structure_039.py::test_good_spec_passes_all_gates",),
    "039-US2-AS1": ("test_spec_structure_039.py::test_below_floor_reports_each_dimension",),
    "039-US2-AS2": ("test_spec_structure_039.py::test_good_spec_passes_all_gates",),
    "039-US2-AS3": ("test_spec_structure_039.py::test_missing_edge_cases_is_flagged",),
    "039-US3-AS1": ("test_spec_structure_039.py::test_scenario_without_when_is_malformed_not_counted",),
    "039-US3-AS2": ("test_board_rules_033.py::test_c1_rejects_same_spec_in_second_version",),
    # ---------- 040 看板规则固化 ----------
    "040-US1-AS1": ("test_board_rules_033.py::test_040_us1_as1_direct_api_write_is_rejected",),
    "040-US1-AS2": ("test_spec_lifecycle_034.py::test_drop_requires_reason_and_time",),
    "040-US1-AS3": ("test_board_rules_033.py::test_c3_allows_same_version",),
    "040-US3-AS1": ("test_rules_040.py::test_every_rule_has_all_fields",),
    "040-US3-AS3": ("test_rules_040.py::test_rule_doc_is_in_sync",),
    "040-US4-AS1": ("test_rules_040.py::test_prefix_filter",),
    "040-US4-AS2": ("test_rules_040.py::test_api_lists_rules",),
    # ---------- 041 看板操作技能重构 ----------
    "041-US1-AS1": ("test_skills_041.py::test_classify_in_place_when_spec_not_accepted",),
    "041-US1-AS2": ("test_skills_041.py::test_classify_change_when_spec_accepted",),
    "041-US1-AS3": ("test_skills_041.py::test_classify_new_spec_without_spec",),
    "041-US1-AS4": ("test_skills_041.py::test_classify_forced_kind_wins",),
    "041-US1-AS5": ("test_skills_041.py::test_classify_forced_kind_wins",),
    "041-US2-AS1": ("test_release_status_041.py::test_dropped_version_reports_terminated",),
    "041-US2-AS2": ("test_release_status_041.py::test_all_nodes_done_reports_releasable",),
    "041-US2-AS3": ("test_release_status_041.py::test_every_check_carries_its_basis",),
    "041-US2-AS4": ("test_release_status_041.py::test_every_check_carries_its_basis",),
    "041-US3-AS1": ("test_skills_041.py::test_deprecated_skills_are_gone",),
    "041-US3-AS2": ("test_skills_041.py::test_no_stale_references_in_active_docs",),
    "041-US3-AS3": ("test_skills_041.py::test_active_skills_exist",),
    "041-US4-AS1": ("test_spec_lifecycle_034.py::test_split_allowed_before_accepted",),
    "041-US4-AS2": ("test_cleanup_033.py::test_cleanup_requires_036_effective",),
    # ---------- 042 开发节点驱动实现侧全流程 ----------
    "042-US1-AS1": ("test_dev_implement_042.py::test_render_plan_covers_every_scenario",),
    "042-US1-AS2": ("test_stage_evidence_038.py::test_evidence_written_first_then_status",),
    "042-US1-AS3": ("test_dev_implement_042.py::test_rendered_tasks_block_implement",),
    "042-US1-AS4": ("test_dev_implement_042.py::test_tasks_block_implement_until_checked",),
    "042-US2-AS1": ("test_dev_plan_042.py::test_structure_numbers_counts_only_named_sections",),
    "042-US2-AS2": ("test_dev_plan_042.py::test_structure_floor_reports_each_short_dimension",),
    "042-US2-AS4": ("test_skill_e2e_083.py::test_s6_non_semver_version_can_derive_cases",),
    "042-US3-AS2": ("test_stage_evidence_038.py::test_evidence_written_first_then_status",),
    "042-US3-AS3": ("test_dev_plan_042.py::test_stage_fields_cover_five_spec_side_stages",),
    "042-US4-AS1": ("test_dev_implement_042.py::test_tasks_block_implement_until_checked",),
    "042-US4-AS2": ("test_dev_implement_042.py::test_tasks_block_implement_until_checked",),
}

# 复核后确认的缺口：场景要求的行为当前实现没有，或没有机器可验的判据。
# 复核记录见 specs/verify-121-mapping.md。
GAPS = {
    "033-US3-AS5": "摘除需求后版本仍为 failed：没有对应用例",
    "036-US4-AS2": "版本不得停在既不推进也不结束：没有生命周期用例",
    "037-US1-AS2": "共同设计只写一次、差异分列：写作约定，无机器判据",
    "037-US1-AS3": "一致性检查报出两规格冲突：没有冲突检测实现",
    "037-US4-AS1": "提示改用规格间关联：没有该提示",
    "038-US2-AS1": "复用未修改宪法时写「未修改」标记：技能未写该标记",
    "038-US3-AS2": "批量补写历史空值必须拒绝：没有批量入口",
    "038-US3-AS3": "补做阶段记录时间与操作者：没有补做机制",
    "040-US2-AS1": "技能在发请求前自检并给冲突信息：没有端到端用例",
    "040-US2-AS2": "规则更新后技能用新规则：没有对应用例",
    "040-US2-AS3": "引擎与技能对同一输入判定一致：没有对比用例",
    "040-US3-AS2": "文档条目与反例测试必须同时提交：流程要求，无自动判据",
    "042-US2-AS3": "写入宪法版本号与未修改标记：技能未写该标记",
    "042-US3-AS1": "八个阶段字段各指向确定节点：没有字段级用例",
    "039-US1-AS3": "场景数远多于功能需求时提示比例异常：没有该提示实现",
}

# 断言只覆盖场景 Then 的一部分：映射仍有效，但覆盖不完整。
PARTIAL = {
    "034-US4-AS4": "已断言必须先摘除，未断言历史结论不被改写",
    "038-US4-AS1": "已断言任务未勾选阻断，未断言规格齐备不自动置 done",
    "039-US3-AS1": "已断言畸形场景被计数，未断言逐份列出缺失项与建议",
    "039-US3-AS2": "已断言已验收规格不能重复挂载（间接走依赖需求），未断言补齐结构本身作为依赖需求执行",
    "041-US1-AS4": "已断言强制分类生效，未断言发请求前失败",
    "042-US4-AS2": "已断言任务未勾选阻断，未断言列出未完成规格编号",
    "042-US2-AS4": "已验证按场景派生用例，未直接断言第 2 节点链路",
    "037-US2-AS1": "已断言受影响条款/一致性/集成三项，未断言基线修订与验证证据；实现只校验三项",
}
