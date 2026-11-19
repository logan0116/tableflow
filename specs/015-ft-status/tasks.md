# Tasks: ft_status版本发布差距报告技能

**Input**: `specs/015-ft-status/spec.md`

**范围**: 只交付`skills/ft-status/SKILL.md`与`specs/015-ft-status/`产物；只读，不写看板。

## Phase 1: 口径

- [x] T001三项就绪与发布条件的契约规则表（board@2四表口径），标注空集语义与判定字段
- [x] T002字段按契约名解析（兼容存量叫法），缺字段标`unknown`；缺整张`bug`表标"未启用"，不报错也不当0
- [x] T003版本选择规则：显式参数优先；默认取"大于已发布最大版本的最小planned"；无planned则`failed`

## Phase 2: 技能实现

- [x] T004结论行（可发/不可发/无法完整判定）+ 四项判定表（规则原文、判定、依据字段）
- [x] T005未满足项逐条：行id / 字段现值 / 还差什么，原因按`implement × acceptance`、`regress`、`bug.status`状态机解释
- [x] T006悬空关联单列并使闸门判否；空集标注"本版无此类工作"
- [x] T007看板口径偏差：`发布条件`条件集、`回归通过`的`require`、`回归状态`含`na`、缺字段与契约外字段
- [x] T008数据异常：`planned`版本号小于已发布最大版本、版本行缺Bug字段值、缺陷表为空
- [x] T009拆分建议：依赖边抽取、被引用次数、可后移候选、方案A/B、下一版本号、迁版不改闸门结论
- [x] T009bBug闸门：上一版本按版本号语义序取严格小于当前版本的最大版本，缺陷按`发现版本`挂接，`status != closed`计未解决，空集为真
- [x] T009c未迁移项目：缺`bug`表时输出"该表未迁移到board@2，Bug闸门按未启用处理"，结论降级为"无法完整判定"
- [x] T010双输出：默认中文Markdown，`FT_JSON=1`输出同结构JSON

## Phase 3: 只读验证

- [x] T011代码检查：只有`GET /api/projects/*`与`GET /api/tables/*`，无`/api/agent/*`
- [x] T012执行前后对比`v0.6.0`业务变更记录条数与最大id，零新增；`write_audit`无读接口，以请求清单佐证

## Phase 4: 实跑与登记

- [x] T013对`v0.6.0`出真实报告（命令从`SKILL.md`抽取执行），输出贴进`runbook.md`
- [x] T014报告覆盖：4行未accepted（含1行`implement=done`只差验收）、空集闸门、2类口径偏差、1条数据异常
- [x] T015更新看板`015-AR`：场景数、任务总数、阶段状态、`implement=done`
- [x] T016四表复验（tableflow）：Bug闸门取缺陷表、上一版本v0.5.1无缺陷（空集为真）、发布条件=否，输出贴进`runbook.md`第5节
- [x] T017三表复验（demo）：输出"该表未迁移到board@2，Bug闸门按未启用处理"，结论"无法完整判定"，不崩溃、不当0，输出贴进`runbook.md`第5节

> 验收（`acceptance=accepted`）由需求方判定，不在本清单内。
