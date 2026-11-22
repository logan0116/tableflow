# Tasks: 版本筛选全局化（030）

- [x] T001 新增版本作用域加载：选定版本时取该版本行的 indep/dep/bugs/runs 关联
- [x] T002 用例表按 `ver.runs → run.case` 映射成 case 行 id 过滤（需加载 run 表）
- [x] T003 需求表按 `ver.indep` 过滤、缺陷表按 `ver.bugs` 过滤、依赖需求表按 `ver.dep` 过滤
- [x] T004 选「全部版本」时四张表都不过滤；版本筛选状态跨表保持
- [x] T005 所选版本无关联行时显示空状态，不回落成全量
- [x] T006 `npm run build` 通过，切版本后四张表行数随之变化
