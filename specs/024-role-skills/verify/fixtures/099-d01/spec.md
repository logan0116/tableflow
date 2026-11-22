# Feature Specification: D-01 --apply 回放夹具

**Feature Branch**: `024-role-skills/verify/fixtures/099-d01`

**Status**: Test Fixture

**Input**: 只服务 D-01 的 024 US4-AS1/US4-AS3：需要一份「任务未勾完 + 验收待定」的规格来证明开发节点被拦住。

## User Scenarios & Testing

### User Story 1 - 被未勾任务拦住的开发节点 (Priority: P1)

**Independent Test**: 对 099-AR 运行 `tf-dev-implement --apply`，期望 failed 并列出未完成任务。

**Acceptance Scenarios**:

1. **Given** 099-AR 的 tasks.md 仍有一条未勾选任务，**When** 运行 `tf-dev-implement --apply`，**Then** 返回 failed 并列出未完成任务，indep 与 ver 零变更。
