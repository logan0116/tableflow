# Tasks: bug表与board@2契约

**Input**: `specs/011-bug-table/spec.md`

**范围**: 契约、三份文档、线上建表与核对；不含自动聚合实现、MS同步、交互协议、用户管理。

## Phase 1: 契约与文档

- [x] T001 从看板`011-AR`提取条款，写`spec.md`：背景证据、澄清、4个用户故事、边界、FR/SC、非目标
- [x] T002 写`board@2.yaml`：`meta`（id/supersedes/scope/out_of_scope）、`conventions`补`b`前缀与`BUG-01`行id
- [x] T003 新增`bug`状态域（`open`/`fixing`/`verifying`/`closed`），每状态只回答一个问题
- [x] T004 新增`bug`表12字段：编号/标题/状态/严重度/来源/关联规格/发现版本/修复版本/证据/剩余事项/MS用例号/负责人
- [x] T005 定义缺陷完成判据：`status=closed`唯一终态，覆盖修复发布与明确不修复，不引入`na`/`wontfix`
- [x] T006 定义版本表挂接口径：挂接键`发现版本`、上一版本语义序、总数/未解决数/就绪、空集为真
- [x] T007 更新`ver`表三个Bug字段的`note`指向新规则；类型与判定不变
- [x] T008 校验YAML可解析：`ver`/`indep`/`dep`/`bug`字段数`16/16/9/12`，语义键无重复
- [x] T009 写`plan.md`：字段id映射、脚本算法、验收方法、风险
- [x] T010 写`tasks.md`

## Phase 2: 线上建表

- [x] T011 写`backend/scripts/create_bug_table.py`：幂等建表建字段、回读核对、`--dry-run`、`--contract`交叉核对
- [x] T012 `--dry-run`核对建表计划（只读，0次写）
- [x] T013 线上执行：建`tf-bug`（order 4）与12个字段
- [x] T014 回读逐字段核对：`GET /api/tables/tf-bug/table`与`board@2.yaml`一致、无多余字段
- [x] T015 二次执行验证幂等：0次字段写入、字段数仍12、退出码0
- [x] T016 三表快照比对：重复执行脚本前后`tf-ver`/`tf-indep`/`tf-dep`字段与行集合字节一致；此后的行变化仅来自`011-AR`登记与下游重算

## Phase 3: 登记与交付

- [x] T017 更新看板`011-AR`：场景数/任务总数/阶段状态/状态文本，验收状态保持`pending`
- [ ] T018 交验收：附`GET`输出、脚本两次执行输出、YAML解析结果
