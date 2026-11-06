# Implementation Plan: 只读状态看板（v0）

**Branch**: `001-readonly-dashboard` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-readonly-dashboard/spec.md`

## Summary

v0 交付一块局域网内的只读看板：打开页面、选择项目、看到该项目的当前数据行。列由数据里的字段定义驱动，增删列只改数据、不改代码。后端 FastAPI 暴露两个只读接口，直接读 tableflow 自己的 SQLite（WAL 模式）；前端 React + Vite + TypeScript，用 TanStack Table 承担表格逻辑（headless），表格本体用原生 DOM 渲染。数据由一次性导入脚本从原平台初始化，导入后以 tableflow 为准。

## Technical Context

**Language/Version**: Python 3.11+（后端）；TypeScript 5.x + Node 24（前端）

**Primary Dependencies**: FastAPI、uvicorn（后端）；React 18、Vite、TypeScript、@tanstack/react-table（前端）

**Storage**: SQLite（WAL），标准库 sqlite3，不引入 ORM

**Testing**: pytest + httpx（后端接口、导入脚本）；前端不引入测试框架，验收按 quickstart 的场景执行

**Target Platform**: Linux（本机或局域网服务器），Chrome / Edge 桌面浏览器

**Project Type**: web application（backend + frontend）

**Performance Goals**: 14行首屏 ≤500ms；关闭硬件加速滚动 ≥50fps 且无 >50ms 长任务

**Constraints**: 只读；无任何读缓存；表格必须 DOM 渲染；界面全中文；禁 canvas、禁自研虚拟滚动、禁重型表格库

**Scale/Scope**: ≤20项目、单项目 ≤500行；2个只读接口、1个导入脚本、3个页面组件

## Constitution Check

*GATE: 对照宪法 v3.0.0 逐条核验。*

| 原则 | 本计划的落实方式 | 结论 |
|---|---|---|
| I 人只读、Agent 读写 | 路由只有 GET；导入脚本是唯一入数路径；v0 无写接口、无占位路由 | PASS |
| II 无读缓存 | 接口带 `Cache-Control: no-store`；前端 fetch 不落盘；后端无进程内缓存 | PASS |
| III Schema 驱动 | fields 表驱动列；前端按 type 通用渲染；代码中无业务列名 | PASS |
| IV DOM 表格 | 原生 `<table>` + TanStack Table（headless）；无 canvas、无虚拟滚动 | PASS |
| V 固定技术栈 | FastAPI + SQLite(WAL) + uv；React + Vite + TypeScript；uv.lock 入库 | PASS |
| VI 中文单语 | 全部中文文案；无 i18n 依赖与 locales 目录 | PASS |
| VII 边界收敛 | 非目标清单外不实现任何能力；写接口只在 spec「未来范围」出现，不进代码 | PASS |

无违规项，Complexity Tracking 留空。

## Project Structure

### Documentation (this feature)

```text
specs/001-readonly-dashboard/
├── plan.md              # 本文件
├── research.md          # Phase 0：决策与备选
├── data-model.md        # Phase 1：表结构与类型映射
├── quickstart.md        # Phase 1：跑起来 + 验收场景
├── contracts/
│   └── api.md           # Phase 1：两个只读接口契约
└── tasks.md             # /speckit-tasks 生成，本命令不产出
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── uv.lock
├── src/tableflow/
│   ├── __init__.py
│   ├── app.py            # FastAPI 应用与两个只读路由
│   ├── config.py         # 数据库路径等配置
│   ├── db.py             # SQLite 连接（WAL、只读）
│   ├── repository.py     # 项目 / 字段 / 行的只读查询
│   └── schemas.py        # 响应模型
├── scripts/import_data.py  # 一次性导入（唯一入数路径）
└── tests/
    ├── test_api.py
    └── test_import.py

frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx            # 项目切换 + 加载/错误/空状态
    ├── api.ts             # 两个只读接口调用（no-store）
    ├── types.ts
    └── components/
        ├── ProjectSwitcher.tsx
        ├── DataTable.tsx  # TanStack Table + 原生 table
        └── Cell.tsx       # 按 type 渲染：文本/数字/日期时间/枚举

data/
├── seed.example.json      # 导入样例（14行、四种类型）
└── tableflow.db           # 运行期库（gitignore）
```

**Structure Decision**: 采用 `backend/` + `frontend/` 双目录。前端需要独立构建产物，后端需要独立 uv 环境；v0 不引入 monorepo 工具，避免为两个包引入额外构建层。

## Complexity Tracking

无违规项，本节留空。
