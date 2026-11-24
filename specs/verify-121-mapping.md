# 121 条场景映射复核

复核口径：不要求「一场景一测试」，只判断**映射测试的断言是否真的验证了该场景的 Then**。
数据来源：`backend/tests/acceptance_manifest.py`、各 `test_*.py` 的 assert 语句、`specs/033-042` 的场景原文。

## 统计

| 判定 | 复核时 | 处置后 |
|---|---|---|
| covered | 94 | 107（含 5 条部分覆盖） |
| mismatch | 19 | 0 |
| partial | 5 | 5（已登记缺哪条断言） |
| gap | 3 | 14（已写原因） |

结论：**121 条里 107 条有语义对应的测试，14 条是明确缺口**。原先「121/121 通过」不再成立，替换为「107 有证据 + 14 缺口」。

处置明细：改映射 6 条（含 2 条因场景号写错而错配）、新增测试 3 条、标缺口 14 条、补 partial 说明 5 条。
自检规则已改为三态（covered / partial / gap），不再要求一测一场景。

## mismatch（19 条）

| 场景 | 当前映射 | Then 要求 | 实际验证 |
|---|---|---|---|
| 033-US3-AS5 | `test_cleanup_requires_036_effective` | 摘除需求后版本测试验收仍为 failed | cleanup 的前置检查是否存在 |
| 036-US4-AS2 | `test_unexecuted_run_blocks_close` | 不再出现既不推进也不结束的版本 | 未执行用例阻断验收 |
| 037-US1-AS2 | `test_037_us1_as2_single_scenario_change_still_needs_four_parts` | 共同设计只写一次，差异按规格分列 | 单场景变更的四要素（写错了场景） |
| 037-US1-AS3 | `test_missing_one_field_blocks` | 一致性检查能报出两规格冲突或遗漏 | 缺字段时阻断 |
| 037-US2-AS1 | `test_037_us1_as1_multi_spec_baselines_are_separate` | 只改一条场景仍含四要素 | 多规格基线分列 |
| 037-US2-AS2 | `test_new_row_without_evidence_is_rejected` | 复用设计文档要写明来源版本与是否仍适用 | 新建行缺证据被拒 |
| 037-US4-AS1 | `test_passed_without_flow_fields_is_rejected` | 拒绝并提示用规格间关联而非依赖需求 | 缺字段拒绝 |
| 037-US4-AS2 | `test_legacy_table_without_fields_is_not_blocked` | 缺受影响条款时拒绝推进 | 旧表不阻断 |
| 038-US2-AS1 | `test_stale_reuse_requires_reconfirmation` | 复用宪法未修改时写入版本号与「未修改」标记 | 版本不一致时拒绝 |
| 038-US3-AS2 | `test_done_without_evidence_is_rejected` | 批量补写历史空值必须拒绝 | 单行缺证据被拒 |
| 039-US3-AS2 | `test_missing_functional_requirements_is_flagged` | 补做阶段作为依赖需求执行，不改写原结论 | 缺 FR 章节被标记 |
| 040-US2-AS1 | `test_every_rule_id_appears_in_a_validator` | 技能在发请求前失败并给出冲突行与占用版本 | 每条规则在实现里出现 |
| 040-US2-AS2 | `test_every_rule_id_appears_in_a_validator` | 规则更新后技能用新规则、无需改代码 | 同上 |
| 040-US2-AS3 | `test_rule_doc_is_in_sync` | 引擎与技能对同一输入判定逐条一致 | 文档与规则表同步 |
| 040-US3-AS2 | `test_rule_doc_is_in_sync` | 文档条目与反例测试必须同时提交 | 文档与规则表同步 |
| 041-US2-AS4 | `test_blocked_version_lists_unfinished_nodes` | 报告口径随之更新，不改技能代码 | 阻塞版本列出未完成节点 |
| 042-US2-AS3 | `test_stage_fields_cover_five_spec_side_stages` | 写入宪法版本号与未修改标记 | 五个阶段字段齐全 |
| 042-US2-AS4 | `test_spec_without_changes_reports_initial_revision` | 能按验收场景派生用例 | 修订报告返回首次修订 |
| 042-US3-AS1 | `test_every_rule_id_appears_in_a_validator` | 八个字段各指向确定的节点与触发条件 | 每条规则在实现里出现 |

## partial（5 条）

| 场景 | 当前映射 | 缺口 |
|---|---|---|
| 034-US4-AS4 | `test_drop_requires_detaching_from_version` | 断言了「必须先摘除」，没断言「历史结论不被改写」 |
| 038-US4-AS1 | `test_tasks_block_implement_until_checked` | 断言任务未勾选阻断，没断言「规格齐备也不自动置 done」 |
| 039-US3-AS1 | `test_scenario_without_when_is_malformed_not_counted` | 断言了畸形场景被计数，没断言「逐份列出缺失项与建议」 |
| 041-US1-AS4 | `test_classify_forced_kind_wins` | 断言强制分类生效，没断言「发请求前失败并给冲突信息」 |
| 042-US4-AS2 | `test_tasks_block_implement_until_checked` | 断言任务未勾选阻断，没断言「列出未完成的规格编号」 |

## gap（3 条，实现缺失）

| 场景 | 要求 | 现状 |
|---|---|---|
| 038-US2-AS1 | 复用未修改的宪法时写入「未修改」标记 | 技能只写 `reused@版本`，无该标记 |
| 038-US3-AS2 | 批量把历史空值补成 done 时拒绝 | 无批量补写入口，也无拦截 |
| 038-US3-AS3 | 补做阶段时记录时间与操作者 | 无补做机制 |

## 处置

1. **mismatch**：先补测试（能补的），补不了的按 gap 处理。19 条里 040 的 5 条是「规则可枚举」类，可用一个参数化测试覆盖多条，成本低。
2. **partial**：给现有测试补一条断言即可，不动 fixture。
3. **gap**：在 manifest 标 `gap` 并写原因；是否补实现另议（这三条都不影响当前流程正确性）。
4. **自检**：改为「每条场景必须 covered / partial / gap 之一；gap 必须有原因；partial 必须写缺哪条断言」。不再要求一测一场景。
