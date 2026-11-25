# 贡献指南

感谢愿意一起把 TableFlow 做得更结实。这个项目的核心约束只有一条：**口径只有一个真源**——看板契约在 `specs/019-test-contract/board@5.yaml`，任何与它冲突的实现都是 bug。

## 开发环境

```bash
cd backend && uv sync          # Python 3.12+，依赖由 uv.lock 锁定
cd frontend && npm ci          # Node 20+
```

本地起后端与前端：

```bash
cd backend && TABLEFLOW_DB=../data/tableflow.db uv run uvicorn tableflow.app:app --reload --port 8000
cd frontend && npm run dev     # 代理到 8000
```

本地默认 `TABLEFLOW_AUTH_MODE=legacy`，写请求可不带 key；想复现生产行为就设 `enforced` 并先签一把 key。

## 提交前自检

```bash
cd backend && uv run pytest -q        # 448 条，必须全绿
cd frontend && npm run build          # tsc --noEmit + vite build
uv lock --check --directory backend   # 改过依赖才需要
```

CI 会再跑一遍这些，外加 `npm audit --audit-level=high` 和版本号一致性检查（`backend/src/tableflow/__init__.py` 与 `frontend/package.json` 必须相同）。

## 改契约的流程

契约是机器可读的，不是文档摆设：

1. 改 `specs/019-test-contract/board@5.yaml`；
2. 跑 `python3 backend/scripts/render_rules.py` 生成 `backend/src/tableflow/rules.py` 与 `specs/019-test-contract/rules.md`（**不要手改生成物**）；
3. 补测试：至少一条断言固定新口径，一条断言旧行为被拒；
4. 若涉及表结构变化，加 `backend/scripts/migrate_*.py` 并在 `CHANGELOG.md` 写升级步骤。

计算字段、闸门字段、run 三态这类口径改动风险最高，请单独开 PR，别和功能改动混在一起。

## 提交规范

Conventional Commits，描述用中文：

```text
feat(045-AR): 设置页口令解锁 + API Key 管理
fix(090-36): 跨项目切换后重置不存在的版本筛选
docs: README 补设置页说明
```

一条提交只做一件事；涉及需求编号时带上（如 `045-AR`）。

## PR 要求

- 说明**为什么**改，而不是只列改了哪些文件；
- 行为变化附验证方式（测试名、curl 输出、截图）；
- 不提交 `data/*.db`、`deploy/.env`、任何明文密钥；
- 不为「看起来更整洁」重排无关代码，评审只看 diff 的因果。

## 报告问题

- 功能异常 / 复现步骤 → [Bug 报告](https://github.com/logan0116/tableflow/issues/new?template=bug_report.yml)
- 契约或口径有歧义 → 先用 issue 讨论，别直接改实现
- 安全漏洞 → 不要开公开 issue，按 [SECURITY.md](SECURITY.md) 私密报告

## 行为准则

参与本项目即表示同意 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
