# 实现计划：测试列弹层显示执行结果

- **需求**：043-AR
- **规格**：`specs/043-run-result-column/spec.md`
- **生成时间**：2026-11-24
- **基线修订**：首次
- **生成者**：tf-dev-implement

## 实现项

### US1 弹层里直接看到执行结果（P1）

- 覆盖场景：043-US1-AS1、043-US1-AS2、043-US1-AS3
- 实现要点：relation options 增加 `result_field`；`ver.测试用例` 指向 `tf-r-result`；弹层 `resolveColumns` 解析结果列，按枚举渲染标签（复用 `EnumTag`），列顺序为 编号→用例号→执行状态→执行结果
- 影响面：`frontend/src/components/RelationListModal.tsx`（渲染）、`frontend/src/types.ts`（RelationOptions 类型）、`specs/019-test-contract/board@5.yaml`（契约）、线上 `tf-ver` 的 `tf-v-runs` 字段 options
- 验证方式：`tsc --noEmit` + `vite build` 通过；浏览器打开 v0.8.5 行点「测试」列，实测四列且结果标签正确

### US2 结果为空与结果列缺失都不能出错（P2）

- 覆盖场景：043-US2-AS1、043-US2-AS2、043-US2-AS3
- 实现要点：结果值为空时显示 `—`；未配置 `result_field` 时不渲染该列；关联行失效时该行结果同样显示 `—`；结果字段不是枚举时按原值显示
- 影响面：`RelationListModal.tsx` 的空值分支与列存在性判断
- 验证方式：构造未执行用例（结果为空）与未配置 result_field 的项目，弹层不报错且列数正确

## 验证

- 单测范围：契约一致性测试（`board@5.yaml` 的 `ver.runs` 声明 `result_field`）；前端无单测框架，以类型检查与构建代替
- 验证命令：`backend/.venv/bin/python -m pytest -q`
- 结论：见收口报告
