# Quickstart / 验收记录：界面视觉打磨（v0.4.0）

**日期**: 2026-11-10
**环境**: Linux，Chrome headless（`--disable-gpu`），1280×800 视口，本地 8000 + 5173

## 1. 复现命令

```bash
# 结构色对比度（读 styles.css 变量，按 WCAG 相对亮度计算）
python3 scripts/contrast_check.py

# 类型门禁
cd frontend && npx tsc --noEmit

# 后端回归
cd backend && .venv/bin/pytest -q

# 首屏与滚动（headless Chrome + CDP，需先起 8000 与 5173）
python3 scripts/perf_check.py http://127.0.0.1:5173/ --rows 14
```

## 2. 结果

### 2.1 结构色对比度（SC-001）

| 令牌 | 值 | 对白底 | 阈值 | 结论 |
|---|---|---|---|---|
| `--color-border`（容器边框） | `#c9d1d9` | 1.543:1 | ≥1.50 | 通过 |
| `--color-border-soft`（行分隔线） | `#e1e6ec` | 1.255:1 | ≥1.25 | 通过 |
| `--color-header`（表头带） | `#edf1f4` | 1.136:1 | ≥1.12 | 通过 |
| `--color-hover`（悬停底） | `#e3eefb` | 1.174:1 | ≥1.15 | 通过 |
| `--color-zebra`（斑马纹） | `#f3f6f9` | 1.085:1 | ≥1.08 | 通过 |

改前对应值为 1.45/1.17/1.06/1.11/1.04，四项低于可感知水平。

### 2.2 列宽（SC-002 / SC-003）

`独立规格需求`表 18 列，总宽 3008px。表头实测宽度（DOM）：

| 列 | 宽度 | 表头是否完整 |
|---|---|---|
| 编号（首列） | 184 | 是 |
| speckit-constitution状态 | 228 | 是 |
| speckit-specify状态 | 188 | 是 |
| speckit-plan状态 | 168 | 是 |
| speckit-task状态 | 168 | 是 |
| speckit-implement状态 | 204 | 是 |
| speckit-clarify状态 | 188 | 是 |
| speckit-analyze状态 | 188 | 是 |
| speckit-checklist状态 | 204 | 是 |

改前 9 列统一 110px，全部渲染为 `speckit-c…`/`s…`/`p…`/`t…`/`i…`。`版本管理`表的「需求关联（独立）」与「需求关联（依赖）」改前同为「需求关联…」，改后完整区分。

### 2.3 性能（SC-004 / SC-008）

| 指标 | 实测 | 门槛 | 结论 |
|---|---|---|---|
| 首屏（14 行，首行渲染完成） | 85ms | ≤500ms | 通过 |
| 滚动 5 秒平均帧率（`--disable-gpu`） | 60.4fps | ≥50fps | 通过 |
| >50ms 长任务 | 0 个 | 0 | 通过 |

测量方法：`scripts/perf_check.py` 用 headless Chrome + CDP 注入 `MutationObserver` 记录首行出现时间，再用 `requestAnimationFrame` 计数 5 秒并驱动 `.table-wrap` 横向滚动。14 行数据为临时写入 fd_system 版本表的 `perf-01`…`perf-10`，测完已删除（该表恢复 4 行）。

### 2.4 类型与回归（SC-007）

| 命令 | 结果 |
|---|---|
| `npx tsc --noEmit` | 零错误 |
| `.venv/bin/pytest -q` | 97 passed |

### 2.5 视觉评审（SC-008）

用本地 VL 模型（Qwen3.8-27B，`http://47.108.92.192/v1`）对改前/改后截图各评审一次。

改前结论：需求关联列名截断；表格下方大量无效留白；主标题与 Tab 间距局促；灰色状态标签对比度偏弱。

改后结论：层级清晰、视觉权重递减合理；所有列名完整展示、无意义截断消失；行边界仍偏淡，仅靠悬停才能一眼区分当前行；建议统一工具栏次要按钮样式。

**偏差记录**：改前评审中 VL 判定"斑马纹与表头处理良好"，与实测 1.04:1 / 1.06:1 矛盾。结论是 VL 对低对比度不敏感，对比度类结论以脚本计算为准，VL 只用于层级与截断类判断。改后"行边界仍偏淡"的反馈已通过把斑马纹从 1.055:1 提到 1.085:1 缓解，未继续加深以保持 Primer 风格。

## 3. 已知未做项

- 深色模式、主题切换：宪法非目标，需先修订宪法。
- 移动端适配：宪法非目标。
- `RelationListModal` 的状态列在目标表「状态」字段为 `text` 类型时渲染为空（既存问题，不在 005 范围）。
- `RelationListModal` 内按列名（「标题」「状态」等）挑选字段，与宪法原则 III「MUST NOT 硬编码业务列名」冲突（既存问题，不在 005 范围）。
