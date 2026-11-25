import type { Project, RowDetailResponse, TableResponse, TableSummary } from "./types";

const TIMEOUT_MS = 5000;

async function getJson<T>(url: string): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, { cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(body?.detail ?? `请求失败（${response.status}）`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("请求超时，请重试");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export function fetchProjects(): Promise<Project[]> {
  return getJson<{ projects: Project[] }>("/api/projects").then((data) => data.projects);
}

export function fetchTables(projectId: string): Promise<TableSummary[]> {
  return getJson<{ tables: TableSummary[] }>(
    `/api/projects/${encodeURIComponent(projectId)}/tables`,
  ).then((data) => data.tables);
}

export function fetchTable(tableId: string): Promise<TableResponse> {
  return getJson<TableResponse>(`/api/tables/${encodeURIComponent(tableId)}/table`);
}

export function fetchRow(tableId: string, rowId: string): Promise<RowDetailResponse> {
  return getJson<RowDetailResponse>(
    `/api/tables/${encodeURIComponent(tableId)}/rows/${encodeURIComponent(rowId)}`,
  );
}

/* ---------- 设置页（045）：管理口令 + API key ---------- */

export interface ApiKeyRecord {
  id: string;
  label: string;
  note: string | null;
  created_at: string;
  revoked_at: string | null;
  revoked_by: string | null;
}

/** 管理接口错误带 HTTP 状态：503=未配置口令，401=口令错误，400=参数不合法。 */
export class AdminRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AdminRequestError";
  }
}

async function adminRequest<T>(
  path: string,
  token: string,
  init?: { method?: string; body?: unknown },
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      method: init?.method ?? "GET",
      cache: "no-store",
      signal: controller.signal,
      headers: {
        // 口令只走请求头，不进 URL 与日志
        ...(token ? { "X-Admin-Token": token } : {}),
        ...(init?.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    });
    const body = (await response.json().catch(() => null)) as
      | { detail?: string; error?: string }
      | null;
    if (!response.ok) {
      throw new AdminRequestError(
        body?.error ?? body?.detail ?? `请求失败（${response.status}）`,
        response.status,
      );
    }
    return body as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new AdminRequestError("请求超时，请重试", 0);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export function adminUnlock(token: string): Promise<void> {
  return adminRequest<{ result: string }>("/api/admin/unlock", token, {
    method: "POST",
  }).then(() => undefined);
}

export function adminListKeys(token: string): Promise<ApiKeyRecord[]> {
  return adminRequest<{ keys: ApiKeyRecord[] }>("/api/admin/keys", token).then(
    (data) => data.keys,
  );
}

export function adminIssueKey(
  token: string,
  label: string,
  note: string,
): Promise<{ key: ApiKeyRecord; plaintext: string }> {
  return adminRequest<{ key: ApiKeyRecord; plaintext: string }>("/api/admin/keys", token, {
    method: "POST",
    body: { label, note: note.trim() ? note.trim() : null },
  });
}

export function adminRevokeKey(token: string, keyId: string): Promise<ApiKeyRecord> {
  return adminRequest<{ key: ApiKeyRecord }>(
    `/api/admin/keys/${encodeURIComponent(keyId)}/revoke`,
    token,
    { method: "POST" },
  ).then((data) => data.key);
}
