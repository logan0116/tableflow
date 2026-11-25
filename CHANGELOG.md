# 更新日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)与 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [1.0.0] - 2026-11-25

首个稳定版。`board@5` 看板契约与 `/api/agent`、`/api/admin` 接口从这一版起按语义化版本演进：MINOR 只新增，MAJOR 才改语义并附迁移脚本。

### 包含

- **六表看板**：版本、独立规格需求、依赖变更需求、测试用例、用例执行情况、缺陷；表与字段定义见 `specs/019-test-contract/board@5.yaml`。
- **六节点闸门**：版本需求设计 → 测试设计 → 开发 → 开发验收 → 测试 → 测试验收，串行推进、不可跳过；发布条件 = `and(六节点全部 done)`。`released` 会冻结版本的范围、节点与状态。
- **计算字段**：`ratio` / `rollup` / `sum` / `and` / `percent`，写侧求值、读侧只读；闸门字段拒绝人工覆盖。
- **写入可核验**：所有写经 `write_service` 单点落库；每次写入记 `write_audit`（调用者、key 标识、来源、结果），字段值真实变化另记 `business_changes`。
- **鉴权**：`TABLEFLOW_AUTH_MODE=enforced` 时写请求必须带有效 `X-API-Key`；key 只存 SHA-256，明文仅在签发时显示一次，吊销即时生效。
- **设置页**：口令解锁后在页内签发 / 吊销 API key，无需 SSH 上机；未配置口令时管理接口返回 503（fail-closed）。
- **10 个 Agent 技能**：`tf-register`、`tf-dev-plan`、`tf-test-plan`、`tf-dev-implement`、`tf-dev-check`、`tf-test-implement`、`tf-test-check`、`tf-lifecycle`、`tf-release-status`、`tableflow-board`。
- **只读前端**：版本表六节点合并为灯组，版本筛选为全局口径，需求 / 用例 / 缺陷按版本关联过滤。
- **部署**：多阶段镜像（Node 构建 → Python 运行时）、非 root（UID 10001）、HEALTHCHECK、在线备份的 seed 脚本。
- **测试**：后端 448 条单测；CI 跑 `uv lock --check`、pytest、`tsc --noEmit`、`vite build`、`npm audit --audit-level=high` 与版本号一致性检查。

### 升级

- 从 `0.x` 升级：跑 `backend/scripts/migrate_board5.py`（先把旧库备份，脚本幂等；`--dry-run` 可预览）。
- 首次部署：`deploy/seed.sh` 会在重建前用 `sqlite3.backup` 做在线备份并签发 seed key 到 `/data/seed-key.txt`。
- 新增环境变量 `TABLEFLOW_ADMIN_TOKEN`（设置页管理口令，至少 8 位）；不配则设置页不可用，看板其余功能不受影响。

### 已知边界

- 只读接口不鉴权；按「内网单机」设计，公网部署需前置反代与 TLS，详见 `SECURITY.md`。
- API key 是调用者身份而非权限边界：一把有效 key 可写所有项目，按项目隔离靠 label 与审计追溯。
- 写请求返回 `503 {"result":"unknown"}` 表示提交结果未知，客户端必须回读确认。

## [0.x] - 2026-09 至 2026-11

`1.0.0` 之前的演进（按需求编号，记录保留在 `specs/`）：只读看板与数据模型 → 字段系统与计算字段 → 版本闸门与契约一致性门禁 → 四表 / 六表看板（board@1 → board@5）→ 角色视图与版本筛选 → API key 与强制鉴权 → 设置页。

[1.0.0]: https://github.com/logan0116/tableflow/releases/tag/v1.0.0
