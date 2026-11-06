# Implementation Plan: TableFlow 多维表格看板（v0）

**Branch**: `001-readonly-dashboard` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-readonly-dashboard/spec.md`

## Summary

v0 交付一块多维表格看板：项目 → 多张表格 → 字段与数据行；同一项目内的表格可建立 relation 关联，关联格显示目标行 id，点击弹出只读明细。人侧只有读接口（全部 GET），Agent 通过 `/api/agent/*` 写接口定义表格、字段与数据行，每次写入落审计并返回三态。后端 FastAPI + SQLite（WAL），前端 React + Vite + TypeScript + TanStack Table（headless），表格用原生 DOM 渲染。

## Technical Context

**Language/Version**: Python 3.11+（后端）；TypeScript 5.x + Node 24（前端）

**Primary Dependencies**: FastAPI、uvicorn（后端）；React 18、Vite、TypeScript、@tanstack/react-table（前端）

**Storage**: SQLite（WAL），标准库 sqlite3，不引入 ORM；五张表见 data-model.md

**Testing**: pytest + httpx（读接口、写接口、审计、样例脚本）；前端不引入测试框架，验收按 quickstart 执行

**Target Platform**: Linux（本机或局域网服务器），Chrome / Edge 桌面浏览器

**Project Type**: web application（backend + frontend）

**Performance Goals**: 14行首屏 ≤500ms；关闭硬件加速滚动 ≥50fps 且无 >50ms 长任务；关联明细弹层 ≤300ms

**Constraints**: 人侧只读（只有 GET）；Agent 写接口必须带契约、审计、三态；无任何读缓存；表格必须 DOM 渲染；界面全中文

**Scale/Scope**: ≤20项目、每项目 ≤10表、单表 ≤500行；读接口 4 个、写接口 9 个、导入脚本 1 个

## Constitution Check

*GATE: 对照宪法 v5.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 人侧路由只有 GET；写接口集中在 `/api/agent/*`，每条写操作落 `write_audit`，返回 success/failed/unknown | PASS |
| II 无读缓存 | 读接口带 `Cache-Control: no-store`；前端 fetch 不落盘；无进程内缓存 | PASS |
| III Schema 驱动 | `fields` 表驱动列；`relation` 只是新增 type，前端仍按 type 通用渲染 | PASS |
| IV DOM 表格 | 原生 `<table>` + TanStack Table（headless）；无 canvas、无虚拟滚动 | PASS |
| V 固定技术栈 | FastAPI + SQLite(WAL) + uv；React + Vite + TypeScript；uv.lock 入库 | PASS |
| VI 中文单语 | 全部中文文案；无 i18n 依赖与 locales 目录 | PASS |
| VII 边界收敛 | 非目标清单外不实现；写接口只覆盖表/字段/行三类，不做权限、协作、视图 | PASS |

无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/001-readonly-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md          # 人侧只读接口
│   └── agent-api.md    # Agent 写接口
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── uv.lock
├── src/tableflow/
│   ├── __init__.py
│   ├── app.py            # FastAPI 应用：读路由 + 写路由挂载
│   ├── config.py         # 数据库路径
│   ├── db.py             # 连接（WAL、只读/读写）与建表
│   ├── repository.py     # 读查询：项目 / 表格 / 字段 / 行 / 单行明细
│   ├── write_service.py  # 写服务：表/字段/行 CRUD + 审计 + 三态
│   ├── schemas.py        # 响应模型
│   └── seed.py           # 样例数据校验与全量写入
├── scripts/seed_data.py
└── tests/
    ├── test_api.py
    ├── test_agent_api.py
    └── test_seed.py

frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx            # 项目 → 表格 → 数据 三级导航 + 三态
    ├── api.ts             # 读接口调用（no-store，5s 超时）
    ├── types.ts
    └── components/
        ├── ProjectSwitcher.tsx
        ├── TableTabs.tsx   # 项目内表格切换
        ├── DataTable.tsx   # TanStack Table + 原生 table
        ├── Cell.tsx        # text/number/datetime/enum/relation
        └── RelationModal.tsx  # 关联明细只读弹层

data/
├── seed.example.json
└── tableflow.db           # 运行期库（gitignore）
```

**Structure Decision**: 前后端双目录；写服务单独成文件，避免 `app.py` 同时承担读写两套路由。

## Complexity Tracking

无违规项，本节留空。
