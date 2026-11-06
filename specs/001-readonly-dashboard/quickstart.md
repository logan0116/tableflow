# 快速开始与验收

**Feature**: 001-readonly-dashboard | **Constitution**: v5.0.0

本文只描述"怎么跑、怎么判定通过"，不含实现代码。数据模型见 [data-model.md](./data-model.md)，接口见 [contracts/api.md](./contracts/api.md) 与 [contracts/agent-api.md](./contracts/agent-api.md)。

## 1. 安装与初始化

```bash
cd backend && uv sync
cd ../frontend && npm install
cd ../backend && uv run python scripts/seed_data.py --seed ../data/seed.example.json
```

期望：输出 `项目 2 / 表格 3 / 字段 11 / 行 17`；`PRAGMA journal_mode` 为 `wal`。

## 2. 启动

```bash
cd backend && uv run uvicorn tableflow.app:app --port 8000
cd frontend && npm run dev     # 5173，/api 代理到 8000
```

打开 `http://localhost:5173`。

## 3. 验收场景

### V1 — 项目内多表浏览（US1 / SC-007）

1. 选择"产线改造"，期望看到"人员""任务"两个页签，默认选中"人员"
2. 切到"任务"，期望列变为 任务/状态/负责人/截止，且不再显示人员的行
3. 切到"设备维保"，期望只有"设备"一张表

### V2 — 关联字段与明细（US3 / SC-004）

1. 打开"任务"表，负责人列显示 `s-1`、`s-2`、`s-1、s-3` 这类目标行 id
2. 点击 `s-1`，期望弹层显示 姓名=张工、角色=电气，且不可编辑
3. 点击弹层外或"关闭"，期望回到表格
4. 删除人员表中的 `s-2` 后刷新，期望对应格子显示"关联已失效"

### V3 — Agent 定义表与字段（US2 / SC-003）

```bash
curl -s -X POST http://localhost:8000/api/agent/projects/proj-001/tables \
  -H 'X-Agent-Id: agent-cli' -H 'Content-Type: application/json' \
  -d '{"id":"t-test","name":"测试表"}'

curl -s -X POST http://localhost:8000/api/agent/tables/t-test/fields \
  -H 'X-Agent-Id: agent-cli' -H 'Content-Type: application/json' \
  -d '{"id":"tf-1","name":"名称","type":"text"}'
```

期望：刷新页面后项目下出现"测试表"，表内出现"名称"列；期间无代码发布。

### V4 — Agent 写行与审计（SC-005）

```bash
curl -s -X POST http://localhost:8000/api/agent/tables/t-test/rows \
  -H 'X-Agent-Id: agent-cli' -H 'Content-Type: application/json' \
  -d '{"id":"tr-1","values":{"tf-1":"第一行"}}'
```

期望：刷新后看到该行；`SELECT agent_id, action, target, result FROM write_audit` 每次调用都有一条。

### V5 — 写侧校验与三态（FR-018）

1. 写一个不存在的字段键：期望 400 `{"result":"failed"}`，且该行未落库
2. 不带 `X-Agent-Id` 写：期望 400，审计里有一条 `failed`（agent_id 为 `-`）
3. 数据存储不可用时：期望 503 `{"result":"unknown"}`

### V6 — 空表与隐藏列（FR-007 / FR-009）

- 空表：显示"暂无数据"并保留列头
- `visible = 0` 的字段（如"内部备注"）：不显示，且接口返回的行值里也没有该键

### V7 — 首屏与滚动（SC-001 / SC-002）

1. Chrome DevTools → Network 勾 Disable cache → Performance 录制 → 刷新，记第 14 行可见时间，5 次取中位数，期望 ≤ 500ms
2. `chrome --disable-gpu` 连续滚动 5 秒，期望平均 ≥ 50fps 且无 > 50ms 长任务

### V8 — 人侧只读（宪法原则 I）

```bash
curl -i -X POST http://localhost:8000/api/projects
curl -i -X POST http://localhost:8000/api/tables/t-task/table
```

期望：均 405；`GET` 响应头含 `Cache-Control: no-store`；前端无 `localStorage` / `indexedDB` / `canvas` / i18n。

## 4. 常见问题

- **旧库不可用**：数据模型已改为项目→表格，删除 `data/tableflow.db*` 后重新 seed
- **只读连接打不开库**：先跑完样例写入再启动服务；WAL 需要能访问 `-wal` / `-shm`
- **端口占用**：改后端端口时同步改 `frontend/vite.config.ts` 的代理目标
