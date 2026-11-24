# 任务清单：测试列弹层显示执行结果

- **需求**：043-AR
- **规格**：`specs/043-run-result-column/spec.md`
- **计划**：`specs/043-run-result-column/plan.md`
- **生成时间**：2026-11-24
- **生成者**：tf-dev-implement

- [x] T001 契约与类型：board@5.yaml 的 ver.runs 加 result_field，RelationOptions 加同名字段（覆盖场景：043-US1-AS1）
- [x] T002 弹层渲染：resolveColumns 解析结果列，按枚举渲染标签，列序 编号→用例号→状态→结果（覆盖场景：043-US1-AS2、043-US1-AS3）
- [x] T003 空值与缺配置：结果为空显示 `—`、未配置不渲染列、失效行同样占位（覆盖场景：043-US2-AS1、043-US2-AS2、043-US2-AS3）
- [x] T004 契约一致性测试：断言 board@5.yaml 的 ver.runs 声明 result_field
- [x] T005 跑通全量测试并记录结果
