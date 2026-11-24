# TableFlow

局域网内的研发治理看板。人只读，Agent 通过 `/api/agent` 写：定义表与字段、登记需求与版本、推进六节点、执行用例、登记缺陷。

- 六张表：版本、独立规格需求、依赖变更需求、测试用例、用例执行情况、缺陷
- 版本六节点：版本需求设计 → 测试设计 → 开发 → 开发验收 → 测试 → 测试验收（串行推进，不可跳过）
- 写接口按 `X-API-Key` 鉴权（容器默认 `enforced`）；每次写入落 `write_audit`，字段级变化另记 `business_changes`
- SQLite（WAL）；后端 FastAPI，前端 React + Vite

契约以 `specs/019-test-contract/board@5.yaml` 为准；`specs/001-readonly-dashboard/contracts/api.md` 是 v0 只读看板的历史文档，已标 SUPERSEDED。

## 目录

```text
backend/    FastAPI + SQLite：人侧 GET + /api/agent 写接口
frontend/   React + Vite + TypeScript
data/       样例数据与运行期库（*.db 不入库）
specs/      规格与契约（001–044）
skills/     Agent 技能：tf-dev-plan / tf-test-plan / tf-dev-implement / tf-dev-check /
            tf-test-implement / tf-test-check / tf-register / tf-lifecycle /
            tf-release-status / tableflow-board
deploy/     部署脚本、compose、seed、容器入口
```

## 本地开发

```bash
cd backend && uv sync
cd ../frontend && npm install
```

- 后端测试：`cd backend && uv run pytest -q`
- 前端构建：`cd frontend && npm run build`
- 本地实例默认 `TABLEFLOW_AUTH_MODE=legacy`（未带 key 时回退 `X-Agent-Id`）；容器默认 `enforced`

## 部署

```bash
bash deploy/deploy.sh          # 只更新代码，不动数据
bash deploy/deploy.sh --seed   # 重建数据（seed 会先在线备份旧库）
```

脚本把仓库同步到 `deploy/.env` 里的 `HOST`，用 `docker compose` 重建镜像；镜像 tag 由 git tag 驱动。容器以非 root（UID 10001）运行，带 HEALTHCHECK。

### API Key

容器 `enforced` 模式下写请求必须带有效 key：

```bash
cd backend && uv run python scripts/tf_keys.py issue --label <name>
```

`--seed` 会自动签发一把 seed key 到容器 `/data/seed-key.txt`。技能侧通过 `TF_API_KEY` 环境变量携带。

## 版本

当前 `v0.10.5`。版本号单一源在 `backend/src/tableflow/__init__.py`；前端 `package.json` 由 CI 校验一致；镜像 tag 由 git tag 驱动。
