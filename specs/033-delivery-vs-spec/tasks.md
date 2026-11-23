# 任务清单：交付记录与规格演进分离

- **需求**：033-AR
- **规格**：`specs/033-delivery-vs-spec/spec.md`
- **计划**：`specs/033-delivery-vs-spec/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 区分规格、独立需求、依赖需求（覆盖场景：033-US1-AS1、033-US1-AS2、033-US1-AS3）——新增只读接口 `GET /api/projects/{项目}/delivery?spec=<编号>` 或 `?dir=<规格目录>`，返回 `delivered_in`（首次交付版本）、`current_revision`（当前生效修订，无则 `source=initial`）、`effective_revisions`、`all_changes`；目录→编号的解析在 `board_rules.resolve_spec_by_dir`。新增 7 项单测；线上数据复算核对：026-AR 交付于 v0.7.1、DEP-06-BR 在 v0.7.3 但规格修订为空故不生效、042-AR 交付于 v0.8.0。
- [x] T002 实现 US2 唯一性与先后约束（覆盖场景：033-US2-AS1、033-US2-AS2、033-US2-AS3、033-US2-AS4、033-US2-AS5）——`backend/src/tableflow/board_rules.py` 实现 C1/C2/C3，接入 `write_service` 的建行与改行两条路径；只校验新增，存量违规不阻断无关编辑；C3 在版本表与 dep 表两条路径上都校验，同请求内先挂需求再挂变更单按已交付处理。
- [x] T003 实现 US3 历史数据按规则清理（覆盖场景：033-US3-AS1、033-US3-AS2、033-US3-AS3、033-US3-AS4、033-US3-AS5）——036 生效后执行：v0.5.1 摘除 007-AR，v0.7.3/v0.7.4 各摘除 026-031，共 13 处；摘除原因写入各版本「变更说明」，清理前快照存 `.tmp-shots/dedup-snapshot-20261123-194418.json`；回读全版本并集计次全部为 1；v0.7.3 重新预演仍为 failed（gate=False），未被清理翻绿。
- [x] T004 实现 US4 拒绝时给出可操作信息（覆盖场景：033-US4-AS1、033-US4-AS2）——拒绝信息含规则号、冲突 id、已占用版本与修复建议；校验全部在任何落库之前，失败整请求零写入。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_board_rules_033.py` 8 项：C1/C2/C3 拒绝、同版本允许、同请求双挂、多规格取最晚、存量违规不阻断无关编辑。
- [x] T006 更新文档与契约引用（如涉及）——契约落 `specs/019-test-contract/board@5.yaml`（meta 升版、object_boundary/delivery_once 约定、C1/C2/C3 与修订指针规则、`spec_done_frozen` 语义修正）。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 226 passed。
