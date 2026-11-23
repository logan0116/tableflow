# 任务清单：看板规则固化

- **需求**：040-AR
- **规格**：`specs/040-rule-enforcement/spec.md`
- **计划**：`specs/040-rule-enforcement/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 引擎在写入期拦住违规操作（覆盖场景：040-US1-AS1、040-US1-AS2、040-US1-AS3）——四条校验模块（board_rules / spec_lifecycle / stage_evidence / change_flow）全部接入 `write_service` 的建行与改行路径；每条拒绝都带规则号，返回 400 且零写入。
- [x] T002 实现 US2 技能使用同源规则自检（覆盖场景：040-US2-AS1、040-US2-AS2、040-US2-AS3）——判定只有引擎一份实现，技能不复制规则，只转述引擎返回的规则号与说明；技能侧凡是需要前置判断的（结构下限、产物回链、单测）都基于产物而非复制引擎判定。
- [x] T003 实现 US3 规则可枚举、可回归（覆盖场景：040-US3-AS1、040-US3-AS2、040-US3-AS3）——`rules.py` 为唯一来源（13 条）；`/api/rules` 可枚举与按前缀过滤；`backend/scripts/render_rules.py` 生成 `specs/019-test-contract/rules.md`，`--check` 纳入回归（文档手改即测试失败）。
- [x] T004 实现 US4 规则清单能回答"为什么被拒"（覆盖场景：040-US4-AS1、040-US4-AS2）——每条规则含编号、含义、判定式、实现位置与反例；拒绝信息以规则号开头，照着号码即可查表；废止规则保留记录（清单只增不删，改规则改含义不改号）。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_rules_040.py` 19 项：字段齐全、规则号唯一与查表、每个规则号都能在校验模块里找到、文档与清单逐字一致、前缀过滤、接口枚举、反例可读性。
- [x] T006 更新文档与契约引用（如涉及）——新增 `specs/019-test-contract/rules.md`（生成物）；契约 board@5 的规则与清单里的条目一一对应。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 297 passed。
