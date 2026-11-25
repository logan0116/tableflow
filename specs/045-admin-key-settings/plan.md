# 实现计划：设置页口令解锁与 API Key 管理

- **需求**：045-AR
- **规格**：`specs/045-admin-key-settings/spec.md`
- **基线修订**：首次

## 实现项

### US1 用口令进入设置（P1）

- 覆盖场景：045-US1-AS1、045-US1-AS2、045-US1-AS3
- 实现要点：新增 `backend/src/tableflow/admin.py`——口令取自 `TABLEFLOW_ADMIN_TOKEN`，未配置或短于 8 位视为未启用；`verify_admin` 用 `secrets.compare_digest` 常量时间比较，未配置抛 `AdminDisabled`、不匹配抛 `AdminError`。`app.py` 增加 `X-Admin-Token` 头依赖与 `POST /api/admin/unlock`，两种失败分别映射 503 / 401。
- 影响面：只新增模块与路由，不改既有 Agent 写接口与只读接口；`/api/health` 不动。
- 验证方式：`backend/tests/test_admin_045.py` 覆盖未配置 503、过短按未配置、错口令 401 且响应不含口令、缺头 401、正确口令 200。

### US2 在设置里查看与签发 key（P1）

- 覆盖场景：045-US2-AS1、045-US2-AS2、045-US2-AS3
- 实现要点：`GET /api/admin/keys` 复用 `auth.list_keys`（只回标识与状态）；`POST /api/admin/keys` 复用 `auth.issue_key`，`by="admin"`，响应带一次性 `plaintext`。前端新增 `SettingsModal`：`sessionStorage` 存口令，解锁后渲染 key 表格与签发表单，明文只在当次渲染出现，带复制按钮。
- 影响面：`frontend/src/api.ts` 新增 `adminRequest` 与四个封装（含 `AdminRequestError` 状态码）、`frontend/src/components/SettingsModal.tsx`、`App.tsx` 页头「设置」按钮、`styles.css` 设置页样式。
- 验证方式：单测断言列表明文与摘要均不出现、签发后库内只存 SHA-256；前端以 `tsc --noEmit && vite build` 通过为证据。

### US3 在设置里吊销 key（P2）

- 覆盖场景：045-US3-AS1、045-US3-AS2
- 实现要点：`POST /api/admin/keys/{key_id}/revoke` 复用 `auth.revoke_key`（`by="admin"`）；吊销立即写 `revoked_at`，`resolve_caller` 下一次请求即 401。前端吊销前 `window.confirm`，成功后刷新列表。
- 影响面：不新增表、不改 schema；审计沿用 `write_audit`（`action=key.issue` / `key.revoke`）。
- 验证方式：单测断言吊销后列表状态、重复吊销 400、未知 key 400、用被吊销 key 调写接口 401 且零写入。

## 边界与取舍

- 口令不落库、不进 URL：只走 `X-Admin-Token` 请求头，前端只存 `sessionStorage`，关闭标签页失效。
- 未配置口令一律 503，不做「无口令放行」降级——设置页能签发 key，等于能发写权限。
- 管理接口只给签发与吊销，不提供删除 key 或改 label，避免绕过审计。

## 验证方式

```bash
cd backend && .venv/bin/python -m pytest -q          # 448+ 条，含 test_admin_045.py
cd frontend && npm run build                          # tsc --noEmit + vite build
```
