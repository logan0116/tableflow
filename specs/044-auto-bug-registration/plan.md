# 实现计划：测试验收不通过时批量登记缺陷

- **需求**：044-AR
- **规格**：`specs/044-auto-bug-registration/spec.md`
- **生成时间**：2026-11-24
- **基线修订**：首次
- **生成者**：tf-dev-implement

## 实现项

### US1 判定不通过时自动留下缺陷（P1）

- 覆盖场景：044-US1-AS1、044-US1-AS2、044-US1-AS3
- 实现要点：`tf-test-check` 在 `blockers` 非空时调用 `_register_defects`；类别分「执行结果未通过」与「变更回归未通过」；缺陷标题以 `[版本] 类别` 为前缀，证据逐行列编号；登记后把缺陷并入 `ver.Bug管理`
- 影响面：`skills/tf-test-check/scripts/tf_test_check.py`（登记逻辑）、`ALLOWED` 已含 `bug`、`ver` 的 `Bug管理` 关系
- 验证方式：端到端测试——有失败执行记录的版本跑验收，缺陷表新增一条且挂到版本

### US2 汇总与去重，不刷屏（P1）

- 覆盖场景：044-US2-AS1、044-US2-AS2、044-US2-AS3
- 实现要点：同一「版本 + 类别」只建一条；已有同前缀且未关闭的缺陷 → 证据取并集，不新建；已有缺陷已 `closed` → 新建一条
- 影响面：`_register_defects` 的匹配与合并分支
- 验证方式：连续两次判定不通过，缺陷总数不变；把缺陷置 closed 后再跑，新增一条

## 验证

- 单测范围：`backend/tests/test_skill_e2e_083.py` 风格的端到端（起真服务端 + subprocess 跑技能）
- 验证命令：`backend/.venv/bin/python -m pytest -q`
- 结论：见收口报告
