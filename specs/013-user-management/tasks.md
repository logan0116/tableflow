# Tasks: 用户管理（兼容期，013）

**Input**: `specs/013-user-management/spec.md`（条款取自看板`GET /api/tables/tf-indep/rows/013-AR`）

**范围**: 只动`backend/src/tableflow/`、`backend/scripts/`、`backend/tests/`与`specs/013-user-management/`；不改字段类型、不改前端与skill、不部署。

## Phase 1: 文档

- [x] T001写`specs/013-user-management/spec.md`：兼容期规则、key存储与审计、负责人填充、CLI、旧库迁移
- [x] T002写`specs/013-user-management/tasks.md`：任务分解、验证口径、非目标

## Phase 2: 存储与身份

- [x] T003 `db.py`：新增`api_keys`表与`write_audit.key_id`列；旧库用`_ensure_column`幂等补列
- [x] T004 `app.py`：启动lifespan幂等补表补列（库不存在则交给seed；迁移失败只告警不阻断只读）
- [x] T005新增`auth.py`：SHA-256摘要、签发/吊销/列出/审计查询、`resolve_caller`（key优先、`X-Agent-Id`回退、401/400）
- [x] T006 `write_service.py`：`run_write`带`key_id`落审计；新增`record_auth_failure`（鉴权失败也留failed审计）
- [x] T007 `app.py`：写接口统一收集`X-API-Key`/`X-Agent-Id`，身份解析后把`actor`/`key_id`传进写服务；无效key返回401

## Phase 3: 负责人填充

- [x] T008 `write_service.create_row`：识别负责人文本字段（id以`-owner`结尾，或名称"负责人"），key调用者缺省填充；显式值优先、多义不猜、更新与旧调用不填

## Phase 4: CLI

- [x] T009 `backend/scripts/tf_keys.py`：`issue`/`revoke`/`list`/`audit`四个子命令；明文只打印一次；签发与吊销落`write_audit`

## Phase 5: 测试

- [x] T010兼容期旧调用用例：`X-Agent-Id`写入成功、审计无key标识、负责人不填、缺凭据仍400
- [x] T011 key识别用例：审计带`key_id`与label、key优先于`X-Agent-Id`、业务变更actor、库内只有摘要
- [x] T012拒绝用例：无效key 401且不写数据、已吊销key 401且错误带key_id、无效key不回退旧身份
- [x] T013负责人填充用例：key新建填充、显式值优先、旧调用与更新不填、多义/无字段不猜
- [x] T014 CLI用例：issue→list→写入→revoke→401→audit全链路；吊销不存在的key返回1
- [x] T015旧库迁移用例：无`api_keys`/无`key_id`的旧库启动后自动补齐，旧审计行保留
- [x] T016跑`cd backend && .venv/bin/python -m pytest -q`：`120 passed`（013前基线`108 passed`）

## Phase 6: 登记

- [x] T017线上做前后快照比对，确认除`013-AR`行外业务数据未变
- [x] T018更新看板`013-AR`行：场景数18、任务总数18、阶段状态与`implement=done`

## 非目标

- 不强制要求key（兼容期），不做权限分级/有效期/项目隔离。
- 不改字段类型、不回填存量负责人、不改前端与skill。
- 不新增HTTP管理路由。
- 不提交代码、不部署、不重启线上服务（发布由队长执行）。
