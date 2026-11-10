# TableFlow 多维表格看板（v0）

局域网内的多维表格看板：项目 → 多张表格 → 字段与数据行；同一项目内的表格可用 relation 字段相互关联，关联格显示目标行 id，点击弹出只读明细。人只读，Agent 通过写接口定义表/字段/数据并写入，每次写入落审计。

规格与设计见 `specs/001-readonly-dashboard/`：`spec.md`、`plan.md`、`data-model.md`、`contracts/api.md`、`contracts/agent-api.md`、`quickstart.md`。

## 目录

```text
backend/    FastAPI + SQLite（WAL）：人侧读接口 + /api/agent 写接口
frontend/   React + Vite + TypeScript + TanStack Table（headless，原生 DOM 渲染）
data/       样例数据与运行期库（*.db 不入库）
specs/      规格、计划、任务与验收产物
```

## 安装

```bash
cd backend && uv sync
cd ../frontend && npm install
```

## 初始化样例数据

```bash
cd backend
uv run python scripts/seed_data.py --seed ../data/seed.example.json
```

样例为 2 个项目、3 张表格、11 个字段、17 行；其中「产线改造」项目的「任务」表通过 relation 字段关联到「人员」表。脚本为**全量替换**：重复执行会覆盖手工改动。

规模数据（用于 20 项目 / 每项目 10 表 / 单表 500 行验收）：

```bash
uv run python scripts/seed_data.py --projects 20 --tables 10 --rows 500
```

## 启动

```bash
# 终端 1：后端（8000）
cd backend && uv run uvicorn tableflow.app:app --port 8000

# 终端 2：前端（5173，/api 代理到 8000）
cd frontend && npm run dev
```

打开 `http://localhost:5173`。

## 接口

### 人侧（只读，全部 GET）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 探活 |
| GET | `/api/projects` | 项目列表 |
| GET | `/api/projects/{id}/tables` | 项目下的表格，按 order 升序 |
| GET | `/api/tables/{id}/table` | 字段（visible=1）+ 数据行 |
| GET | `/api/tables/{id}/rows/{row_id}` | 单行明细（关联弹层用） |

### Agent 侧（写入，需请求头 `X-Agent-Id`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/projects/{id}/tables` | 建表 |
| PATCH / DELETE | `/api/agent/tables/{id}` | 改名 / 删除（级联字段与行） |
| POST | `/api/agent/tables/{id}/fields` | 加字段（text/number/datetime/enum/relation） |
| PATCH / DELETE | `/api/agent/fields/{id}` | 改字段 / 删字段 |
| POST | `/api/agent/tables/{id}/rows/{row_id}` | 写行（行 id 在路径里，即业务编号） |
| PATCH / DELETE | `/api/agent/tables/{id}/rows/{row_id}` | 改行（合并 values）/ 删行 |

响应统一为 `{"result": "success" | "failed" | "unknown", ...}`；校验失败 400 且不落库，提交结果无法确认时返回 503 + `unknown`。每次调用（成功或失败）都写一条 `write_audit`。

## 验收

按 `specs/001-readonly-dashboard/quickstart.md` 的 V1–V8 执行。性能三项需在 Chrome DevTools 里测：

- 首屏：14 行首次可见 ≤ 500ms
- 滚动：`--disable-gpu` 下连续滚动 5 秒，平均 ≥ 50fps 且无 > 50ms 长任务
- 关联弹层：点击到明细显示 ≤ 300ms

界面视觉打磨（005）的验收脚本：

```bash
python3 scripts/contrast_check.py                 # 结构色对比度，退出码非 0 即不达标
python3 scripts/perf_check.py http://127.0.0.1:5173/ --rows 14   # 首屏与滚动（headless Chrome）
```

结果与口径见 `specs/005-ui-visual/quickstart.md`。

## 约束

宪法 `.specify/memory/constitution.md`（v7.0.0）是硬约束：

- 人侧只有 GET；Agent 写接口必须带契约、审计、三态
- 无读缓存：接口 `no-store`，前端不持久化业务数据
- 列由数据驱动：增删列只改 `fields` 表
- 表格 DOM 渲染：禁 canvas、禁自研虚拟滚动、禁重型表格库

## 常见问题

- **`uv run` 在沙箱里报 `Read-only file system`**：uv 需要写 `~/.cache/uv`；普通终端不受影响，沙箱内可用 `backend/.venv/bin/python`。
- **只读连接打不开库**：WAL 下只读连接需要能访问 `-wal` / `-shm`；先跑完样例写入再启动服务。
- **旧库升级**：数据模型从"项目=表"改为"项目→表"，旧库不可复用，删除 `data/tableflow.db*` 后重新 seed。
- **端口占用**：改后端 `--port` 时同步改 `frontend/vite.config.ts` 的代理目标。

## 许可

MIT，见 [LICENSE](./LICENSE)。
