# Tasks: 关联条目显示字段配置化（v0.4.1）

**Input**: Design documents from `/specs/006-relation-display/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、005 已合入

**Tests**: 前端不引入测试框架；`npx tsc --noEmit` 类型门禁；DOM 核对 + 手工点击验收；后端 pytest 回归门禁。

## Format: `[ID] [P?] [Story] Description`

## 验证命令

- 前端：`cd frontend && npx tsc --noEmit`
- 后端：`cd backend && .venv/bin/pytest -q`
- 合规：`grep -rn "TITLE_NAMES\|STATUS_NAMES" frontend/src` 命中 0

## Phase 1: 类型与组件

- [x] T001 `frontend/src/types.ts`：`RelationOptions` 增加 `display_field?` 与 `status_field?`
- [x] T002 `frontend/src/components/RelationListModal.tsx`：删除 `TITLE_NAMES` / `STATUS_NAMES` / `pickTitleField` / `pickStatusField`
- [x] T003 [US1] `frontend/src/components/RelationListModal.tsx`：新增 `resolveColumns`，按 `options.display_field` / `options.status_field` 在目标表字段里取列
- [x] T004 [US1] `frontend/src/components/RelationListModal.tsx`：列头改用字段 `name`；`display` 缺失不渲染第二列，`status` 缺失不渲染第三列
- [x] T005 [US1] `frontend/src/components/RelationListModal.tsx`：`status` 字段为 enum 时渲染 `EnumTag`，非 enum 时渲染纯文本
- [x] T006 [US2] `frontend/src/components/RelationListModal.tsx`：配置字段不存在时忽略并回退为只显示编号列

## Phase 2: 迁移

- [x] T007 `data/migrate_relation_display.py`：遍历 6 个项目全部 relation 字段，按目标表结构推导 `display_field`（第二个 text）与 `status_field`（第一个 enum），先 `--dry-run` 打印 18 条映射
- [x] T008 人工核对映射后执行写入；脚本对已存在同值跳过（幂等），重复运行输出「无需变更」
- [x] T009 回读校验：18 个 relation 字段的 options 均含两个键

## Phase 3: 验证与发布

- [x] T010 `cd frontend && npx tsc --noEmit` 零错误
- [x] T011 `cd backend && .venv/bin/pytest -q` 全绿
- [x] T012 `grep -rn "TITLE_NAMES\|STATUS_NAMES" frontend/src` 命中 0
- [x] T013 浏览器验收：版本表「需求关联（依赖）」弹层三列正常、状态列有标签；未配置字段只显示编号
- [x] T014 版本号升到 0.4.1（package.json / package-lock / pyproject / docker-compose）
- [x] T015 `npm run build` → git commit + tag `v0.4.1` → `HOST=user@your-host bash deploy/deploy.sh`
- [x] T016 tableflow 登记 006-AR 与 DEP-02-BR、建 v0.4.1 并关联，确认发布条件=是后发布

## Dependencies

```text
T001 → T002..T006 → T007 → T008 → T009 → T010..T013 → T014..T016
```
