# 任务清单：阶段产物与证据强制

- **需求**：038-AR
- **规格**：`specs/038-stage-evidence/spec.md`
- **计划**：`specs/038-stage-evidence/plan.md`
- **生成时间**：2026-11-23
- **生成者**：tf-dev-implement

- [x] T001 实现 US1 阶段状态必须能被证明（覆盖场景：038-US1-AS1、038-US1-AS2、038-US1-AS3）——新增 `stage_evidence.py`：阶段状态从非 done 变为 done 时，「阶段证据」必须含对应 `<阶段>=<证据>` 行，缺则 400；`tf-dev-plan` 与 `tf-dev-implement` 在改状态前先写证据。
- [x] T002 实现 US2 复用既有产物需留痕（覆盖场景：038-US2-AS1、038-US2-AS2、038-US2-AS3）——`tf-dev-plan` 按 `reused:<路径>@<版本>` 写入 constitution 证据；引擎新增 S2：复用来源版本与当前宪法版本不一致时，证据行必须写明「已重新确认仍适用」，否则 400。
- [x] T003 实现 US3 历史空值保持"无法证明"（覆盖场景：038-US3-AS1、038-US3-AS2、038-US3-AS3）——新增 `GET /api/projects/{项目}/stages?spec=<编号>`，逐阶段返回取值、证据与 `unprovable`；引擎只在状态变化那一刻校验，历史已 done 缺证据不改写、不阻断无关编辑；无证据无法批量置 done。
- [x] T004 实现 US4 单规格完成不等于版本完成（覆盖场景：038-US4-AS1、038-US4-AS2）——由 042 的 `full_scope` 判定承担：`--spec` 只覆盖部分规格时不推进版本节点。
- [x] T005 补齐单元测试（覆盖上述全部实现项）——`backend/tests/test_stage_evidence_038.py` 10 项：缺证据拒绝、带证据通过、先写证据再改状态、na/doing 免证、历史不回改、键互不顶替、解析忽略噪声、阶段视图标记 unprovable、未知规格 404。
- [x] T006 更新文档与契约引用（如涉及）——契约 board@5 新增 `spec.stage_evidence` 字段与 `stage_artifact_matrix`、`stage_done_needs_evidence`、`stage_unprovable`、`stage_backfill`、`stage_reuse` 五条规则；迁移脚本纳入该字段（dry-run 8 项目 64 项）。
- [x] T007 跑通全量测试并记录结果——`.venv/bin/python -m pytest -q` → 262 passed。
