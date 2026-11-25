# Feature Specification: 设置页口令解锁与 API Key 管理

**Feature Branch**: `045-admin-key-settings`
**Created**: 2026-11-24
**Status**: Implemented（v0.10.8 已发布）

## 背景与问题证据

155 实例自 v0.10.0 起 `TABLEFLOW_AUTH_MODE=enforced`，写接口必须带有效 `X-API-Key`。但签发与吊销 key 目前只能 SSH 到宿主机跑 `backend/scripts/tf_keys.py`——每给一个项目开一把 key，都要运维登录一次，用户已明确反馈「有的麻烦」。

看板本身是只读界面（人只读、Agent 读写），没有任何设置入口；但 key 管理属于低频、需要人工确认的运维动作，放进界面并加一道口令，比反复 SSH 更合适。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 用口令进入设置 (Priority: P1)

运维在页头点「设置」，输入管理口令，进入设置面板。

**Why this priority**: 没有口令就没有授权边界——设置页直接暴露签发 key 的能力，等于把写权限发给任何能打开看板的人。

**Independent Test**: 在未配置口令的实例上点设置，看到「未启用」提示；配置口令后输入正确口令可进入。

**Acceptance Scenarios**:

1. **Given** 实例未配置 `TABLEFLOW_ADMIN_TOKEN`，**When** 输入任意口令，**Then** 提示「管理口令未配置」，不进入设置
2. **Given** 实例已配置口令，**When** 输入错误口令，**Then** 返回 401 并提示口令错误，不泄露任何正确口令信息
3. **Given** 实例已配置口令，**When** 输入正确口令，**Then** 进入设置面板并显示 key 管理

### User Story 2 - 在设置里查看与签发 key (Priority: P1)

设置面板列出全部 key（不含明文），可以签发新 key 并拿到一次性明文。

**Why this priority**: 签发是这次需求的核心目的——让每个项目自己领 key，不必再找运维。

**Independent Test**: 在设置面板签发一把 label 为 `demo-agent` 的 key，列表新增一行，明文显示一次；刷新页面后明文不再出现。

**Acceptance Scenarios**:

1. **Given** 已解锁设置，**When** 打开 key 列表，**Then** 每行显示 key_id、label、状态、签发时间、备注，**不显示明文与摘要**
2. **Given** 已解锁设置，**When** 填写 label 与备注并签发，**Then** 返回一次性明文，列表同时新增该行
3. **Given** 刚签发过一把 key，**When** 关闭并重新打开设置，**Then** 明文不再显示，只能看到 key_id 与 label

### User Story 3 - 在设置里吊销 key (Priority: P2)

某把 key 泄露或不再使用，可在设置面板直接吊销，立即失效。

**Why this priority**: 签发能力下放后，吊销也必须同样可达，否则泄露只能等运维介入。

**Independent Test**: 吊销一把在用 key，用它调写接口立即返回 401。

**Acceptance Scenarios**:

1. **Given** 列表里有有效 key，**When** 点吊销并确认，**Then** 该行状态变为「已吊销」且吊销时间可见
2. **Given** 某把 key 刚被吊销，**When** 用它调用任意写接口，**Then** 返回 401

### Edge Cases

- 未配置口令时，管理接口一律 503，不得退化为「无口令放行」
- 口令只存在 `sessionStorage`，关闭标签页失效；不得写入 `localStorage`、URL 或日志
- 列表中的 key 已全部吊销时，签发入口仍可用（否则无法恢复）
- 签发时 label 为空或超长，返回 400 且不落库

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 管理接口 MUST 用请求头 `X-Admin-Token` 校验口令，口令取自环境变量 `TABLEFLOW_ADMIN_TOKEN`，比较 MUST 为常量时间
- **FR-002**: 未配置 `TABLEFLOW_ADMIN_TOKEN` 时，全部管理接口 MUST 返回 503（fail-closed），不得降级为放行
- **FR-003**: 口令错误 MUST 返回 401，响应体 MUST NOT 包含正确口令的任何片段
- **FR-004**: key 列表 MUST 返回 key_id、label、备注、签发时间、吊销时间与吊销人，MUST NOT 返回明文或摘要
- **FR-005**: 签发 MUST 返回一次性明文，服务端只存 SHA-256 摘要；同一把 key 的明文此后 MUST 不可再取
- **FR-006**: 签发与吊销 MUST 落 `write_audit`（action 为 `key.issue` / `key.revoke`），actor 记为 `admin`
- **FR-007**: 吊销 MUST 立即生效——下一次请求即拒绝，无需重启服务
- **FR-008**: 前端 MUST 默认不显示 key 管理；口令校验通过后才显示，且口令只存 `sessionStorage`
- **FR-009**: 前端 MUST NOT 把口令写入 `localStorage`、URL query 或浏览器日志
- **FR-010**: 管理接口 MUST 只允许签发与吊销 key，MUST NOT 提供删除 key 或改 label 的能力

### Key Entities

- **API key**：`api_keys` 表一行；字段 id、key_hash、label、note、created_at、revoked_at、revoked_by
- **管理口令**：部署侧环境变量，不落库、不进界面

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 给一个新项目开 key 从「SSH + 命令」降为「点设置 + 输口令 + 填 label」，全程不超过 1 分钟
- **SC-002**: 口令错误时，看板其它功能不受影响（只读接口仍可用）
- **SC-003**: 吊销后 1 秒内该 key 的写请求返回 401（实测一次请求即可确认）
