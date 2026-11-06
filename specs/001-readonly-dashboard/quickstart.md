# 快速开始与验收

**Feature**: 001-readonly-dashboard | **Constitution**: v3.0.0

本文档只描述"怎么跑起来、怎么判定通过"，不包含实现代码。数据模型见 [data-model.md](./data-model.md)，接口见 [contracts/api.md](./contracts/api.md)。

## 1. 前置条件

- Python 3.11+，uv（0.11+）
- Node 24+，npm
- 端口：后端 `8000`，前端 `5173`
- 浏览器：近两年版本的 Chrome / Edge

## 2. 安装依赖

```bash
cd backend && uv sync
cd ../frontend && npm install
```

期望：`backend/uv.lock` 生成；`frontend/node_modules` 就绪。

## 3. 初始化样例数据

```bash
cd backend
uv run python scripts/seed_data.py --seed ../data/seed.example.json --db ../data/tableflow.db
```

期望：

- 输出写入计数（项目数、字段数、行数），与 seed 文件一致
- `data/tableflow.db` 生成
- `sqlite3 data/tableflow.db "PRAGMA journal_mode;"` 返回 `wal`
- 重复执行时全量替换，计数不累加

## 4. 启动

```bash
# 终端 1
cd backend && uv run uvicorn tableflow.app:app --port 8000

# 终端 2
cd frontend && npm run dev
```

打开 `http://localhost:5173`。前端通过 Vite 代理把 `/api` 转发到 `8000`，避免 CORS 配置。

## 5. 验收场景

### V1 — 打开即见当前状态（US1 / SC-004）

1. 浏览器打开 `http://localhost:5173`，选择"产线改造"项目
2. 期望：表格显示14行，列顺序与 `fields.order` 一致
3. 用 `sqlite3` 改掉某行某列的值为新值
4. 重新打开页面（或刷新），期望：显示新值，不出现旧值
5. 停掉后端，刷新页面，期望：中文错误提示 + 重试按钮，页面不残留旧数据

### V2 — 多项目切换（US2）

1. seed 中包含至少两个项目
2. 在项目切换区来回切换
3. 期望：每次切换后只显示该项目的数据与列；切到空项目时显示"暂无数据"且保留列头

### V3 — 增删列只改数据（US3 / SC-003）

1. 在 `fields` 表插入一条新字段定义，并在 `row_records.data` 补上对应键值
2. 刷新页面，期望：新列出现，位置由 `order` 决定，类型渲染正确；期间无任何代码改动与重启
3. 删除该字段定义，刷新页面，期望：该列消失，其余列正常
4. 把某字段 `visible` 置 0，刷新，期望：该列不显示，但数据仍在库中

注意：不要重跑 `seed_data.py`，它会全量替换三张表并覆盖上面的手工改动。

### V4 — 边界情形

先用规模数据跑一遍：`uv run python scripts/seed_data.py --projects 20 --rows 500 --db ../data/tableflow.db`，再逐条验证：

- 空单元格：不出现 `null` / `undefined` / `NaN`
- 未知 `type`：该列按纯文本显示，页面不报错
- 500行项目：滚动到底部能看到最后一行，不截断
- 20个项目：切换区仍可点击

### V5 — SC-001 首屏 500ms

1. Chrome DevTools → Network 勾选 `Disable cache`，限速设为 `No throttling`（局域网本机）
2. DevTools → Performance → 录制 → 刷新页面 → 第14行可见时停止
3. 读取 `navigationStart` 到最后一帧渲染的时间，重复5次取中位数
4. 期望：≤ 500ms

### V6 — SC-002 滚动帧率

1. 用关闭硬件加速的方式启动 Chrome：`chrome --disable-gpu`
2. DevTools → Performance 录制5秒连续滚动
3. 期望：平均帧率 ≥ 50fps，无超过 50ms 的长任务

### V7 — 只读边界（宪法原则 I）

```bash
curl -i -X POST http://localhost:8000/api/projects
```

期望：`405 Method Not Allowed`；`GET /api/projects` 的响应头含 `Cache-Control: no-store`。

## 6. 常见问题

- **只读连接打不开库**：WAL 模式下只读连接需要能访问 `-wal` / `-shm` 文件。先跑完样例写入、再启动服务；确认库文件与目录对服务进程可读。
- **端口占用**：`8000` 被占用时改 `--port`，同时改 `frontend/vite.config.ts` 的代理目标。
- **页面一直显示加载中**：检查 `GET /api/health` 是否返回 200；代理目标是否与后端端口一致。
