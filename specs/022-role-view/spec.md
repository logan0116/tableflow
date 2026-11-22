# Feature Specification: 顶部通栏角色切换与角色配色（v0.7.0）

**Feature Branch**: `022-role-view`

**Created**: 2026-11-22

**Status**: Draft

**Input**: 需求 022-AR。board@4 把看板扩到六表后，三种角色（系统工程、软件开发、软件测试）在同一张表导航里看到同样的六张表、同样一套蓝色强调色，既看不出"我现在以什么身份在看板"，也要在无关表之间来回找。本规格按原型方案 C 落地：顶部一条角色通栏，四个入口（系统工程/软件开发/软件测试/全局），当前角色实心高亮且角色名常显；切换后表导航只列本角色关心的表，强调色随角色变化并记住上次选择。角色只改变可见表与配色，不改变只读边界与表格结构色。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 没有角色身份 | 当前 UI 只有项目与表两级，页头不体现角色；原型 `.tmp-shots/role-theme/index.html` 的方案 C 才补上角色名 | 用户不知道自己以哪个角色在看板，Agent 与人沟通时也缺共同上下文 |
| 表导航一视同仁 | `frontend/src/App.tsx` 的 `TableTabs` 列出全部 board 表；系统工程不需要用例表，测试不需要独立规格表 | 无关表占据导航，角色职责与表的对应关系丢失 |
| 强调色只有一套 | `frontend/src/styles.css` 的 `--color-accent` 固定蓝色 | 角色切换没有视觉反馈，无法一眼确认当前身份 |
| 角色选择不记忆 | 当前 UI 偏好只存列宽与行密度（`frontend/src/ui-prefs.ts`） | 每次刷新都回到同一视图，重复切换 |
| 配色容易误伤结构 | 005 用五个结构色阈值约束表格可读性（1.12/1.25/1.50/1.15/1.04:1） | 若角色色改结构令牌，长表可读性会回退 |

## Clarifications

### Session 2026-11-22

- Q: 为什么选方案 C？ → A: 通栏把角色身份放在全页最上层且不影响左右骨架；方案 A 只染强调元素，身份不够显眼；方案 B 整屏染色会盖过表格结构色；方案 D 再染侧栏，视觉重量过大。参考 `.tmp-shots/role-theme/theme-c-topbar.png`。
- Q: 角色与可见表怎么对应？ → A: 系统工程=版本管理/独立规格需求/依赖变更需求；软件开发=再加缺陷；软件测试=版本管理/测试用例/依赖变更需求/缺陷；全局=全部 board 表。映射按各角色的工作面取：系统工程聚焦版本与需求范围；开发在需求/变更之外还要看缺陷；测试以用例、依赖变更需求与缺陷为主——`change.regress`（回归结论）归属测试域，置 `passed/failed` 的证据来自测试执行，所以 dep 必须在测试角色可见；独立规格需求仍经 relation 弹层读取。024 的技能读写作用域不由此改变。
- Q: 被角色隐藏的表是不是不能访问？ → A: 不是。022 的角色只影响表导航，不改变人侧只读 GET，也不改变 024 的技能作用域；隐藏的表仍可经 relation 弹层（版本行的独立需求管理/依赖需求管理/Bug管理、用例的来源规格）读取。
- Q: 默认哪个角色？ → A: 全局。首次访问不隐藏任何表，行为与升级前一致；用户选过角色后按 localStorage 恢复。
- Q: 角色色怎么落到 CSS？ → A: 每个角色定义 `--role-accent`、`--role-accent-deep`、`--role-accent-weak`、`--page-bg` 四个变量，由 `html[data-role]` 切换；`--color-border`、`--color-border-soft`、`--color-header`、`--color-hover`、`--color-zebra` 一概不动。
- Q: 状态标签要不要跟着角色色变？ → A: 不要。原型阶段已排除：角色色与 enum 的 info/success/warning/danger 状态色会撞色，状态语义优先。
- Q: `run` 表在全局角色下出现吗？ → A: 不出现。021 的 `kind=detail` 规则先于角色过滤，执行清单只经版本行弹层展示。
- Q: 自定义表（不是六表合同）怎么处理？ → A: 语义键取不到的表对所有角色保留，避免角色过滤把不属于 board@4 合同的表静默吞掉。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 顶部通栏切换角色 (Priority: P1)

页面顶部始终有一条角色通栏：左边常显「当前角色 + 角色名」，右边四个入口；点一个入口，当前角色实心高亮，角色名与整页强调色立即变化，不需要刷新。

**Independent Test**: 依次点四个入口，核对通栏高亮、左侧角色名、页头角色徽章与表导航。

**Acceptance Scenarios**:

1. **Given** 页面加载完成，**When** 看顶部，**Then** 有 42px 高的角色通栏，左侧显示「当前角色 全局」，右侧四个入口：系统工程、软件开发、软件测试、全局。
2. **Given** 当前角色为全局，**When** 点「软件测试」，**Then** 「软件测试」按钮变为白底实心高亮且 `aria-pressed=true`，左侧角色名变为「软件测试」，页头角色徽章同步为「软件测试」。
3. **Given** 任一角色，**When** 通栏滚动到页面下方，**Then** 通栏仍吸附在视口顶部（`position: sticky`），不被表格盖住。
4. **Given** 四个入口，**When** 用键盘 Tab 聚焦并回车，**Then** 行为与点击一致；聚焦环在深色通栏上可见（白色描边）。

### User Story 2 - 角色决定可见表清单 (Priority: P1)

切到某角色后，表导航只列该角色关心的表；当前表若不属于新角色，自动落到新清单的第一张表，不出现空白页。

**Independent Test**: 在全局/测试/开发/系统四个角色间切换，数页签；从测试角色的「测试用例」切到「软件开发」，确认自动回到版本管理。

**Acceptance Scenarios**:

1. **Given** 六表项目（ver/indep/dep/case/run/bug），**When** 选择「系统工程」，**Then** 表导航只有 版本管理、独立规格需求、依赖变更需求 三个页签。
2. **Given** 同上，**When** 选择「软件开发」，**Then** 表导航有 版本管理、独立规格需求、依赖变更需求、缺陷 四个页签。
3. **Given** 同上，**When** 选择「软件测试」，**Then** 表导航有 版本管理、测试用例、依赖变更需求、缺陷 四个页签；不含独立规格需求。
4. **Given** 同上，**When** 选择「全局」，**Then** 表导航有 版本管理、独立规格需求、依赖变更需求、测试用例、缺陷 五个页签；全局仍不含「用例执行情况」（021 的 detail 规则）。
5. **Given** 当前在「测试用例」表，**When** 切到「软件开发」，**Then** 当前表自动切到「版本管理」，表数据正常加载，不显示空表或报错。
6. **Given** 当前角色隐藏了某表（如测试角色下的独立规格需求），**When** 从版本行的「独立需求管理」或用例的「来源规格」点开，**Then** 关联弹层仍能读取该表明细（角色不是权限边界）。
7. **Given** 一个项目带有非六表合同的表 id，**When** 切任意角色，**Then** 该表仍保留在导航中（不因语义键取不到被吞掉）。

### User Story 3 - 角色配色与结构色隔离 (Priority: P1)

角色切换时通栏、页头徽章、当前表/项目高亮与页面底色换色，表格表头带、斑马纹、行分隔线、悬停底、容器边框五种结构色保持不变；状态标签颜色不随角色变化。

**Independent Test**: 四个角色各截图，取同一张表比较表头/行/标签颜色；跑 `scripts/contrast_check.py` 对照 005 五阈值。

**Acceptance Scenarios**:

1. **Given** 系统工程角色，**When** 读取计算样式，**Then** `--role-accent=#0b5cab`、`--role-accent-deep=#08407a`、`--role-accent-weak=#ddf4ff`、`--page-bg=#f7fbff`。
2. **Given** 软件开发角色，**When** 读取计算样式，**Then** 四个变量分别为 `#1a7f37` / `#0f5323` / `#dafbe1` / `#f7fdf9`。
3. **Given** 软件测试角色，**When** 读取计算样式，**Then** 四个变量分别为 `#9a6700` / `#7d5300` / `#fff6de` / `#fdfbf4`。
4. **Given** 全局角色，**When** 读取计算样式，**Then** 四个变量分别为 `#57606a` / `#24292f` / `#eef1f4` / `#f6f7f9`。
5. **Given** 切换四个角色，**When** 比较表格结构色，**Then** `--color-border/--color-border-soft/--color-header/--color-hover/--color-zebra` 逐项不变，005 五阈值不下降。
6. **Given** 任一角色，**When** 看 enum 状态标签，**Then** 标签底色与文字色来自 enum 自身的 tone，不随角色色变化。

### User Story 4 - 记住上次角色 (Priority: P2)

刷新页面或下次打开，仍停留在上次选择的角色；localStorage 损坏/不可用时回退「全局」，不阻塞渲染。

**Independent Test**: 选「软件测试」→ 刷新 → 仍是软件测试且表导航为测试清单；把 localStorage 值改成非法字符串 → 刷新 → 回退全局。

**Acceptance Scenarios**:

1. **Given** 用户选择「软件测试」，**When** 刷新页面，**Then** 通栏高亮、角色名、徽章、表清单与配色都保持软件测试。
2. **Given** 用户选择「系统工程」，**When** 重新打开页面，**Then** 仍是系统工程。
3. **Given** `tableflow.ui.role.v1` 存了非法值，**When** 加载，**Then** 回退「全局」，不报错。
4. **Given** localStorage 被禁用或写入失败，**When** 切换角色，**Then** 当前会话内仍生效，刷新后回退全局，控制台不抛异常。
5. **Given** 角色存储，**When** 检视 localStorage，**Then** 只存角色 id，不存任何业务数据。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 页面 MUST 在顶部渲染 42px 角色通栏，横跨侧栏与主内容；通栏 MUST 使用 `position: sticky; top: 0`。
- **FR-002**: 通栏 MUST 常显「当前角色 + 角色名」，并提供四个入口，顺序为 系统工程、软件开发、软件测试、全局。
- **FR-003**: 当前角色按钮 MUST 为实心高亮（白底 + 角色深色字 + `aria-pressed=true`），其余入口 MUST 为半透明白字。
- **FR-004**: 页头 MUST 显示与通栏一致的角色徽章；徽章 MUST 使用角色弱底色与深色字。
- **FR-005**: 表导航 MUST 先应用 021 的 `kind != detail` 规则，再应用角色过滤；`run` 表 MUST NOT 出现在任何角色（含全局）的导航中。
- **FR-006**: 角色过滤 MUST 按 board@4 表 id 的语义后缀（`<前缀>-ver|indep|dep|case|run|bug`）识别表；语义键取不到的表 MUST 对所有角色保留。
- **FR-007**: 角色与可见表 MUST 按以下矩阵执行；「全局」MUST 不过滤。
- **FR-008**: 切换角色后，当前表若不在新清单中，MUST 自动落到新清单第一张表；新清单为空时 MUST 显示「暂无表格」，MUST NOT 保留旧表内容。
- **FR-009**: 角色只改前端可见性与配色，MUST NOT 改变接口请求、只读边界、relation 弹层可读性与 024 的技能作用域。
- **FR-010**: 角色色 MUST 由 `html[data-role]` 上的 CSS 变量驱动（`--role-accent`、`--role-accent-deep`、`--role-accent-weak`、`--page-bg`）；MUST NOT 在组件里写死颜色。
- **FR-011**: 角色色 MUST NOT 修改 005 的五个结构色令牌（`--color-border`、`--color-border-soft`、`--color-header`、`--color-hover`、`--color-zebra`），五阈值 MUST 不下降。
- **FR-012**: enum 状态标签 MUST 保持自身 tone，MUST NOT 随角色换色。
- **FR-013**: 角色选择 MUST 持久化到 `tableflow.ui.role.v1`（只存角色 id）；缺失或非法 MUST 回退 `all`。
- **FR-014**: 本规格 MUST NOT 实现深色模式、MUST NOT 引入新依赖、MUST NOT 改变表格结构、列宽、行密度行为。
- **FR-015**: `cd frontend && npm run build` MUST 通过（含 `tsc --noEmit`）；`scripts/contrast_check.py` MUST 五项全过。

### 角色矩阵

| 角色 | id | 可见 board 表 | `--role-accent` | `--role-accent-deep` | `--role-accent-weak` | `--page-bg` |
|---|---|---|---|---|---|---|
| 系统工程 | `systems` | 版本管理、独立规格需求、依赖变更需求 | `#0b5cab` | `#08407a` | `#ddf4ff` | `#f7fbff` |
| 软件开发 | `dev` | 版本管理、独立规格需求、依赖变更需求、缺陷 | `#1a7f37` | `#0f5323` | `#dafbe1` | `#f7fdf9` |
| 软件测试 | `test` | 版本管理、测试用例、依赖变更需求、缺陷 | `#9a6700` | `#7d5300` | `#fff6de` | `#fdfbf4` |
| 全局 | `all` | 全部 board 表 | `#57606a` | `#24292f` | `#eef1f4` | `#f6f7f9` |

### 对比度核对（对 005 的五个阈值）

| 项 | 颜色 | 对白底 | 005 阈值 | 结论 |
|---|---|---|---|---|
| 容器边框 | `#c9d1d9` | 1.543:1 | ≥1.50 | 不下降 |
| 行分隔线 | `#e1e6ec` | 1.255:1 | ≥1.25 | 不下降 |
| 表头带 | `#edf1f4` | 1.136:1 | ≥1.12 | 不下降 |
| 悬停底 | `#e3eefb` | 1.174:1 | ≥1.15 | 不下降 |
| 斑马纹 | `#f3f6f9` | 1.085:1 | ≥1.04 | 不下降 |

角色通栏文字对比度（白字对 accent）：系统工程 6.70:1、软件开发 5.08:1、软件测试 4.87:1、全局 6.39:1，均 ≥ WCAG AA 的 4.5:1；深色字对弱底分别为 9.12 / 8.27 / 6.27 / 12.92:1。

## Non-Goals

- 深色模式、跟随系统主题、用户自定义配色。
- 角色权限：服务端写接口不区分角色，024 的技能作用域不因 022 改变。
- 给 enum 状态标签换色或让角色色参与状态语义。
- 记住每个角色各自停留的表（本版只记角色）。
- 移动端布局与通栏折叠。
- 修改表格结构、列宽、行密度、关系弹层列推导。

## Success Criteria

- 顶部四个入口可切换，当前角色实心高亮、角色名常显。
- 四角色表导航分别为 3 / 4 / 4 / 5 个页签，`run` 表在所有角色下都不出现。
- 从测试角色的「测试用例」切到「软件开发」自动回到「版本管理」，无空白页。
- 刷新后角色保持；非法 localStorage 值回退「全局」。
- `cd frontend && npm run build` 退出码 0；`python3 scripts/contrast_check.py` 五项全过。
- 截图证据：四个角色的通栏与表导航、刷新后保持，路径见下方「验收证据」。

## 验收证据

**日期**: 2026-11-22
**环境**: 本地 uvicorn（127.0.0.1:8099，当前仓库 backend 原样代码）+ `frontend/dist`（本次构建产物）+ 六表夹具库（`TABLEFLOW_DB=.tmp-shots/021-case-view/fixture/tf021.db`）；浏览器视口 1280×800。

### 命令

| 命令 | 结果 |
|---|---|
| `cd frontend && npm run build` | 退出码 0；`tsc --noEmit` 零错误，vite 产物 `dist/assets/index-BjH4BIlu.js` / `index-CX8D44ek.css` |
| `python3 scripts/contrast_check.py` | 五项全过：边框 1.543、分隔线 1.255、表头带 1.136、悬停底 1.174、斑马纹 1.085 |
| 浏览器 localStorage 写入非法角色后刷新 | 回退「全局」，表导航恢复 5 个页签，控制台无异常 |

### 截图

| 截图 | 证明 |
|---|---|
| `.tmp-shots/022-role-view/role-all.png` | 默认「全局」：通栏 4 入口、当前角色白底实心高亮、角色名常显；表导航 5 个 board 页签 |
| `.tmp-shots/022-role-view/role-systems.png` | 「系统工程」蓝色通栏；表导航仅 版本管理/独立规格需求/依赖变更需求 3 个页签 |
| `.tmp-shots/022-role-view/role-dev.png` | 「软件开发」绿色通栏；表导航 版本管理/独立规格需求/依赖变更需求/缺陷 4 个页签；从测试角色的「测试用例」切过来时自动落到「版本管理」 |
| `.tmp-shots/022-role-view/role-test.png` | 「软件测试」琥珀色通栏；表导航 版本管理/测试用例/依赖变更需求/缺陷 4 个页签 |
| `.tmp-shots/022-role-view/role-test-reload.png` | 刷新后仍为「软件测试」，角色名/徽章/表清单/配色均保持（与上一张同图） |
| `.tmp-shots/022-role-view/role-invalid-fallback.png` | localStorage 写入非法值后刷新，回退「全局」 |

### 配色核对

- 结构色令牌未改动，`scripts/contrast_check.py` 五项结果与 005 基线完全一致（见上表）。
- 通栏白字对角色 accent：系统工程 6.70:1、软件开发 5.08:1、软件测试 4.87:1、全局 6.39:1；角色深色字对弱底 9.12 / 8.27 / 6.27 / 12.92:1。
- 四张角色截图中 enum 状态标签（已发布/计划中/是/否/Bug 状态）颜色一致，未随角色变化。

### 复现方式

```bash
cd frontend && npm run build
cd .. && TABLEFLOW_DB=$PWD/.tmp-shots/021-case-view/fixture/tf021.db \
TABLEFLOW_STATIC_DIR=$PWD/frontend/dist \
backend/.venv/bin/python .tmp-shots/021-case-view/fixture/serve_real.py
# 打开 http://127.0.0.1:8099/，点通栏四个入口
```

> 夹具与 021 共用（六表 + `kind`）；角色过滤按表 id 的语义后缀识别，不依赖夹具专用字段。正式验收应在 T1 迁移后的真实六表项目上复跑。

## Assumptions

- 角色色只影响页面 chrome（通栏、徽章、当前项目/表高亮、页面底色），表格卡片仍为白底，因此 005 的结构色阈值按「对白底」口径不变。
- 表 id 遵循 board@4 的 `<前缀>-ver|indep|dep|case|run|bug` 命名；不遵循的项目其表按自定义表处理（所有角色可见）。
- 024 的技能读写作用域独立于 022 的可见表清单：技能在命令行运行，不受前端导航过滤影响。
- 现有 `tableflow.ui.columnWidths.v1` / `tableflow.ui.density.v1` 键名与行为不变；新增 `tableflow.ui.role.v1`。
