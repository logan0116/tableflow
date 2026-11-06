# TableFlow 只读状态看板（v0）

替代在 smart_table 上"看一眼状态"的做法：一块局域网内的只读看板，打开即见某项目的当前数据行。人只读，Agent 读写（v0 只交付读侧；写接口在 v1，见宪法原则 I）。

规格与设计见 `specs/001-readonly-dashboard/`：`spec.md`（需求）、`plan.md`（实施计划）、`data-model.md`（表结构）、`contracts/api.md`（接口契约）、`quickstart.md`（验收步骤）。

## 目录

```text
backend/    FastAPI + SQLite（WAL），只读接口与样例脚本
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

样例为 2 个项目、9 个字段、14 行，覆盖文本/数字/日期时间/枚举四种类型，并含一个 `visible = 0` 的字段。脚本为**全量替换**：重复执行不会累加，但会覆盖手工改动。

规模数据（用于 20 项目 / 500 行验收）：

```bash
uv run python scripts/seed_data.py --projects 20 --rows 500
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

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 探活；数据存储不可用时 503 |
| GET | `/api/projects` | 项目列表，按 id 升序 |
| GET | `/api/projects/{id}/table` | 字段（仅 visible=1，按 order 升序）+ 全部数据行 |

全部响应带 `Cache-Control: no-store`；没有任何写方法（POST/PUT/PATCH/DELETE 返回 405）。细节见 `specs/001-readonly-dashboard/contracts/api.md`。

## 验收

按 `specs/001-readonly-dashboard/quickstart.md` 的 V1–V7 执行。性能两项需在 Chrome DevTools 里测：

- 首屏：14 行首次可见 ≤ 500ms（禁缓存、局域网、5 次中位数）
- 滚动：`--disable-gpu` 下连续滚动 5 秒，平均 ≥ 50fps 且无 > 50ms 长任务

## 约束

宪法 `.specify/memory/constitution.md`（v4.0.0）是本项目的硬约束，重点几条：

- 只读：无写路由、无写接口占位
- 无读缓存：接口 `no-store`，前端不持久化业务数据
- 列由数据驱动：增删列只改 `fields` 表，不改前端代码
- 表格 DOM 渲染：禁 canvas、禁自研虚拟滚动、禁重型表格库

## 常见问题

- **`uv run` 在沙箱里报 `Read-only file system`**：uv 需要写 `~/.cache/uv`；在普通终端不受影响，沙箱内可直接用 `backend/.venv/bin/python`。
- **只读连接打不开库**：WAL 模式下只读连接需要能访问 `-wal` / `-shm`；先跑完样例写入再启动服务。
- **端口占用**：改后端 `--port` 时同步改 `frontend/vite.config.ts` 的代理目标。
