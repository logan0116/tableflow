# Feature Specification: 界面体验打磨（v0.3.0）

**Feature Branch**: `004-ui-polish`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "enum 状态色标签；数字右对齐 + 等宽数字；首列 sticky 与横向滚动阴影；加载骨架；空状态区分（空项目 / 空表 / 加载中 / 失败）；行密度两档（紧凑 / 舒适）与斑马纹；列宽记忆（localStorage 存 UI 偏好，不碰业务数据）。"

## Clarifications

### Session 2026-11-06

- Q: 状态色从哪来？ → A: 来自 002 的 enum `options.items[].tone`（`neutral/info/success/warning/danger`），可选 `color` 覆盖；前端只维护 tone → CSS 变量映射，不硬编码任何业务值。
- Q: 首列指哪一列？ → A: 当前表中 `order` 最小且 `visible=1` 的字段列；列头与单元格同时 sticky。
- Q: 横向滚动阴影怎么做？ → A: 纯 CSS（`background` 多层渐变 + `local`/`scroll` 附着），不监听 scroll 事件，避免滚动掉帧。
- Q: 列宽记忆存什么？ → A: 只存 `{tableId: {fieldId: 像素}}` 与行密度，键为 `tableflow.ui.columnWidths.v1` / `tableflow.ui.density.v1`；MUST NOT 存任何业务值。
- Q: 行密度默认哪档？ → A: 舒适；紧凑为可选，选择结果持久化。
- Q: 斑马纹与 hover 冲突怎么办？ → A: 偶数行浅底色；hover 覆盖为高亮底色；sticky 首列同步使用同一行底色，避免"首列白块"。
- Q: 骨架屏覆盖哪些区域？ → A: 表格数据区（表头 + 8 行占位）；项目/表格切换区用轻量占位条，不整页闪白。
- Q: 空状态怎么区分？ → A: 六种独立文案：加载中、暂无项目、暂无表格、暂无数据、暂无字段、读取失败（带重试）；MUST NOT 互相复用或显示错误。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - enum 状态色标签 (Priority: P1)

状态列不再是一段纯文本，而是带底色与文字色的标签。颜色由字段 options 里的 `tone` 决定；新增一个状态只改数据，不改前端代码。

**Why this priority**: 状态是看板最常扫的信息；颜色让"已发布 / 计划中 / 已阻塞"在一屏内可分辨。

**Independent Test**: 同一 enum 字段分别写入 5 种 tone 的值，截图/计算样式核对 5 种底色；修改 options 的 tone 后刷新，颜色变化且无代码改动。

**Acceptance Scenarios**:

1. **Given** enum 字段某选项 `tone=success`，**When** 渲染该值，**Then** 标签使用成功色（底色 + 文字色），并带 `enum-tone-success` 类。
2. **Given** 5 种 tone 各一个值，**When** 同屏渲染，**Then** 5 个标签的背景色互不相同，文字对比度可读。
3. **Given** `tone` 缺失或未知，**When** 渲染，**Then** 使用 `neutral` 样式，不报错。
4. **Given** 选项带 `color={bg,fg}`，**When** 渲染，**Then** 内联样式覆盖默认 tone 色。
5. **Given** 前端源码，**When** grep 业务状态值（`released` / `planned` / `待办` 等），**Then** 命中数为 0。

---

### User Story 2 - 数字右对齐与等宽数字 (Priority: P1)

数字列右对齐，数字使用等宽字形；同一列上下对齐后，人扫一列数字不用左右跳。

**Why this priority**: 看板里数字与状态同等高频；对齐是最低成本的可用性提升。

**Independent Test**: 数字列的计算样式为 `text-align: right` 且 `font-variant-numeric: tabular-nums`；不同位数的数字在等宽字体下逐位对齐。

**Acceptance Scenarios**:

1. **Given** number 字段，**When** 渲染单元格，**Then** 单元格带 `cell-number` 类，计算样式 `text-align: right`。
2. **Given** number 字段，**When** 渲染，**Then** 计算样式包含 `font-variant-numeric: tabular-nums`（或等价的 `font-feature-settings: "tnum"`）。
3. **Given** 数字列列头，**When** 渲染，**Then** 列头同样右对齐，与数据列对齐一致。
4. **Given** 空值或非数字值，**When** 渲染，**Then** 仍按右对齐占位，不破坏列宽。

---

### User Story 3 - 首列 sticky 与横向滚动阴影 (Priority: P2)

横向滚动时首列固定，行身份始终可见；表格右侧出现阴影提示"还有内容"，滚到最右阴影消失。

**Why this priority**: 列多时（版本表 12 列）没有 sticky，滚动后不知道自己在看哪一行。

**Independent Test**: 横向滚动 200px，首列仍可见且背景不透明；`scrollLeft=0` 时左侧无阴影、右侧有阴影；滚动后左侧出现阴影，滚到底时右侧阴影消失。

**Acceptance Scenarios**:

1. **Given** 表格宽度超过容器，**When** 横向滚动，**Then** 首列（表头与单元格）保持可见，`position: sticky; left: 0`。
2. **Given** 表格可横向滚动，**When** `scrollLeft=0`，**Then** 右侧有阴影、左侧无阴影；**When** 滚到底，**Then** 右侧阴影消失、左侧出现阴影（纯 CSS 实现）。
3. **Given** 斑马纹与 hover，**When** 首列处于偶数行或 hover 行，**Then** 首列背景与整行一致，不出现白块。
4. **Given** 首列 sticky，**When** 连续滚动 5 秒，**Then** 帧率仍 ≥50fps，无 >50ms 长任务。

---

### User Story 4 - 加载骨架 (Priority: P2)

切换表格或首次加载时，数据区显示与真实表格同构的骨架（表头 + 8 行占位），而不是一句「加载中…」或整页空白。

**Why this priority**: 骨架降低等待感，也避免加载时布局跳动。

**Independent Test**: 人为延迟接口 1s，加载期间 DOM 存在骨架节点、无「暂无数据」；加载完成后骨架移除、真实行出现。

**Acceptance Scenarios**:

1. **Given** 表格数据请求进行中，**When** 页面渲染，**Then** 数据区显示骨架：1 行表头 + 8 行占位，列数与字段数一致。
2. **Given** 骨架显示中，**When** 数据返回，**Then** 骨架被真实表格替换，无重复渲染。
3. **Given** 用户开启「减少动态效果」（`prefers-reduced-motion: reduce`），**When** 骨架渲染，**Then** 不播放闪烁动画。
4. **Given** 加载中，**When** 查看文案，**Then** 不出现「暂无数据」或错误提示。

---

### User Story 5 - 空状态区分 (Priority: P2)

六种状态各有各的文案与视觉：加载中、暂无项目、暂无表格、暂无数据、暂无字段、读取失败。人不应该把"加载失败"看成"没有数据"。

**Why this priority**: 001 只有零散文案；把失败与空混淆会让人以为数据丢了。

**Independent Test**: 分别构造无项目、项目无表、表无行、无可见字段、接口失败、加载中六种场景，核对文案与是否有重试按钮。

**Acceptance Scenarios**:

1. **Given** 项目列表为空，**When** 渲染，**Then** 显示「暂无项目」，不显示重试按钮。
2. **Given** 选中项目没有任何表格，**When** 渲染，**Then** 显示「暂无表格」，保留项目切换器。
3. **Given** 选中表格没有数据行，**When** 渲染，**Then** 显示「暂无数据」，保留列头。
4. **Given** 接口失败，**When** 渲染，**Then** 显示「读取失败」与「重试」按钮，文案与空状态不同。
5. **Given** 加载中，**When** 渲染，**Then** 显示骨架或「加载中」，不显示空状态文案。

---

### User Story 6 - 行密度两档与斑马纹 (Priority: P3)

工具栏可切换「舒适 / 紧凑」两档行高；斑马纹让长行更易横向追读。选择结果刷新后保留。

**Why this priority**: 12 列 × 十几行时，密度与斑马纹直接影响扫读效率；但它不是正确性问题，排在 P3。

**Independent Test**: 切换密度，行高从 ≥40px 变为 ≤32px；刷新后保持；偶数行背景与奇数行不同。

**Acceptance Scenarios**:

1. **Given** 默认舒适档，**When** 渲染，**Then** 行高 ≥40px，表格容器带 `data-density="comfortable"`。
2. **Given** 切换到紧凑档，**When** 渲染，**Then** 行高 ≤32px，容器带 `data-density="compact"`。
3. **Given** 已选择紧凑档，**When** 刷新页面，**Then** 仍为紧凑档（localStorage 记忆）。
4. **Given** 任意密度，**When** 渲染，**Then** 偶数行有浅底色，hover 行覆盖为高亮底色。
5. **Given** 斑马纹，**When** 首列 sticky，**Then** 首列底色与所在行一致。

---

### User Story 7 - 列宽记忆 (Priority: P2)

用户拖动列宽后，宽度按「表 + 字段」记住；刷新或再次打开同一张表时恢复。存储只放 UI 偏好，不放任何业务值。

**Why this priority**: 12 列的表每次打开都要重调宽度，是高频摩擦；但必须守住"localStorage 不碰业务数据"的宪法边界。

**Independent Test**: 拖宽某列到 240px，刷新后仍为 240px；读取 localStorage，内容只含表 id、字段 id 与数字；清空存储后恢复默认。

**Acceptance Scenarios**:

1. **Given** 表头有拖拽手柄，**When** 用户拖动列宽，**Then** 列宽实时变化，最小 48px、最大 600px。
2. **Given** 列宽已调整，**When** 刷新页面，**Then** 同一表同一字段恢复为记忆宽度。
3. **Given** 列宽已调整，**When** 读取 `tableflow.ui.columnWidths.v1`，**Then** 内容形如 `{"<tableId>":{"<fieldId>":240}}`，不含行值、状态值或任何业务文本。
4. **Given** 存储内容损坏或字段已删除，**When** 加载，**Then** 忽略非法项并回退默认宽度，不报错。
5. **Given** 用户点击「重置列宽」，**When** 确认，**Then** 当前表的记忆被清除并恢复默认。

---

### Edge Cases

- 表格没有可见字段：不渲染表格，显示「暂无字段」类空状态（不报错）。
- 首列字段被隐藏（`visible=0`）：sticky 顺延到下一个可见列。
- 只有 1 列：不出现横向滚动阴影。
- 列宽拖到边界：钳制在 48–600px，不出现负宽或 0 宽。
- localStorage 被禁用（隐私模式）：读取失败静默回退默认，写入失败不报错。
- localStorage 内容超限：只保留最近 200 条列宽记录，超出淘汰最旧项。
- 浏览器缩放 / 不同字号：等宽数字仍对齐，sticky 不遮挡内容。
- `prefers-reduced-motion`：骨架与过渡动画降级为静态。
- 接口慢于 1s：骨架持续显示，不中途闪「暂无数据」。
- 接口失败：显示失败状态与重试，不显示骨架或空状态。

## Requirements *(mandatory)*

### Functional Requirements

**状态色**

- **FR-001**: enum 单元格 MUST 渲染为标签；标签 MUST 带 `enum-tone-{tone}` 类，`tone` 取 002 定义的五个值。
- **FR-002**: `tone` 缺失或未知 MUST 回退 `neutral`，MUST NOT 报错。
- **FR-003**: 选项含 `color={bg,fg}` 时 MUST 以内联样式覆盖默认 tone 色；`color` 非法时 MUST 回退 tone 色。
- **FR-004**: 前端 MUST NOT 硬编码业务状态值（如 `released` / `planned` / `待办`）；颜色映射只按 `tone`。

**数字对齐**

- **FR-005**: number 与 computed number 单元格 MUST 右对齐，并 MUST 使用等宽数字（`font-variant-numeric: tabular-nums` 或等价）。
- **FR-006**: number 列列头 MUST 与数据列同向对齐。
- **FR-007**: 空值单元格 MUST 保持列对齐占位，MUST NOT 改变列宽。

**首列与滚动**

- **FR-008**: 当前表第一个可见字段列 MUST sticky（`position: sticky; left: 0`），表头与单元格同时生效。
- **FR-009**: 横向滚动阴影 MUST 纯 CSS 实现，MUST NOT 监听 scroll 事件；滚动到边界时对应侧阴影 MUST 消失。
- **FR-010**: sticky 首列背景 MUST 与所在行（斑马纹 / hover）一致，MUST NOT 出现白块。
- **FR-011**: 表格容器 MUST 支持横向滚动，MUST NOT 因此出现纵向布局抖动。

**加载与空状态**

- **FR-012**: 表格数据加载中 MUST 显示骨架：表头 + 8 行占位，列数与字段数一致；MUST NOT 同时显示空状态文案。
- **FR-013**: 骨架动画 MUST 在 `prefers-reduced-motion: reduce` 下降级为静态。
- **FR-014**: 系统 MUST 区分六种状态并显示不同中文文案：加载中、暂无项目、暂无表格、暂无数据、暂无字段、读取失败。
- **FR-015**: 读取失败 MUST 提供「重试」按钮；空状态 MUST NOT 提供重试按钮。
- **FR-016**: 空表 MUST 保留列头；空项目 MUST 保留项目切换器。

**行密度与斑马纹**

- **FR-017**: 工具栏 MUST 提供「舒适 / 紧凑」两档切换；默认舒适。
- **FR-018**: 舒适档行高 MUST ≥40px，紧凑档行高 MUST ≤32px；切换 MUST 不重新请求数据。
- **FR-019**: 偶数行 MUST 有浅底色（斑马纹）；hover 行 MUST 覆盖为高亮底色。
- **FR-020**: 行密度选择 MUST 持久化到 `tableflow.ui.density.v1`，刷新后恢复。

**列宽记忆**

- **FR-021**: 表头 MUST 提供列宽拖拽手柄；宽度 MUST 钳制在 48–600px。
- **FR-022**: 列宽 MUST 按 `{tableId: {fieldId: px}}` 存入 `tableflow.ui.columnWidths.v1`；MUST NOT 存业务值。
- **FR-023**: 页面加载时 MUST 恢复已记忆列宽；非法/损坏/已删除字段的条目 MUST 被忽略并回退默认。
- **FR-024**: 列宽记录 MUST 上限 200 条；超出 MUST 淘汰最旧项。
- **FR-025**: 工具栏 MUST 提供「重置列宽」入口，清除当前表的记忆并恢复默认。
- **FR-026**: localStorage 不可用时 MUST 静默降级，MUST NOT 阻塞渲染或报错。

**通用**

- **FR-027**: 界面文案 MUST 全部中文。
- **FR-028**: 本 spec MUST NOT 引入新依赖、MUST NOT 引入 canvas/虚拟滚动/重型表格库。
- **FR-029**: 性能基线 MUST 保持：14 行首屏 ≤500ms、关闭硬件加速滚动 ≥50fps、无 >50ms 长任务。
- **FR-030**: 本 spec MUST NOT 改变接口契约与业务数据；只改渲染与 UI 偏好。

### Key Entities

- **UI 偏好（UiPreference）**：列宽与行密度，只存在浏览器 localStorage，按「表 + 字段」索引，不含业务值。
- **状态标签（EnumTag）**：由 enum 值与 tone 驱动的只读标签。
- **骨架（Skeleton）**：与真实表格同构的加载占位。
- **空状态（EmptyState）**：六种互斥状态的统一展示组件。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 5 种 tone 各渲染一次，标签背景色互不相同；修改 options 的 tone 后刷新，颜色变化且无代码改动。
- **SC-002**: 前端源码 grep 业务状态值命中数为 0。
- **SC-003**: number 单元格计算样式为 `text-align: right` 且 `font-variant-numeric: tabular-nums`；列头同向。
- **SC-004**: 横向滚动 200px 后首列仍可见；`scrollLeft=0` 时左侧无阴影、右侧有阴影，滚到底时右侧阴影消失；首列在斑马纹/hover 行背景与整行一致。
- **SC-005**: 人为延迟 1s，加载期间存在骨架节点（表头 + 8 行）且无「暂无数据」；数据返回后骨架移除。
- **SC-006**: 六种状态文案两两不同；仅「读取失败」有重试按钮。
- **SC-007**: 舒适档行高 ≥40px、紧凑档 ≤32px；刷新后密度保持；偶数行底色与奇数行不同。
- **SC-008**: 列宽拖到 240px 后刷新仍为 240px；localStorage 内容只含 tableId/fieldId/数字；清空后恢复默认；非法条目被忽略。
- **SC-009**: localStorage 中检索不到任何行值或状态值（用当前表 10 行数据逐值比对，命中 0）。
- **SC-010**: 首屏 ≤500ms、滚动 ≥50fps、无 >50ms 长任务；`cd frontend && npx tsc --noEmit` 零错误；`cd backend && .venv/bin/pytest -q` 全绿（本 spec 不改后端，作为回归门禁）。

## Assumptions

- 002 已交付 enum `tone` 与 options 结构；004 只消费，不重新定义语义。
- 首列 sticky 只针对 PC 桌面；移动端适配仍属宪法非目标。
- 列宽记忆以字段 id 为键；字段删除后对应条目在下次加载时被忽略，不主动清理远端数据。
- localStorage 只存 UI 偏好，符合宪法原则 II 的例外条款；键名统一 `tableflow.ui.*`，与业务数据隔离。
- 不引入前端测试框架；验收以 `npx tsc --noEmit`、DOM/计算样式核对与 quickstart 手工步骤为准。
- 骨架列数取当前字段数；字段数为 0 时显示空状态而非骨架。

## 未来范围

- 移动端适配、主题切换、列显示/隐藏配置、视图体系（筛选/分组/看板）仍属宪法 v6.0.0 非目标，不在本 spec 范围。
- 计算字段的语义与落库由 003 交付；004 只负责计算值的视觉呈现（右对齐、布尔标签、覆盖标记样式）。
