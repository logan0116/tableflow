/**
 * UI 偏好的本地存储：当前角色与版本筛选，不存任何业务数据。
 *
 * localStorage 不可用、内容损坏或超限时一律静默降级，绝不阻塞渲染。
 */

import { DEFAULT_ROLE, isRoleId, type RoleId } from "./roles";

export const ROLE_KEY = "tableflow.ui.role.v1";

function getStorage(): Storage | null {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return null;
    }
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readRole(): RoleId {
  const storage = getStorage();
  if (!storage) {
    return DEFAULT_ROLE;
  }
  try {
    const raw = storage.getItem(ROLE_KEY);
    return isRoleId(raw) ? raw : DEFAULT_ROLE;
  } catch {
    return DEFAULT_ROLE;
  }
}

/** 写入当前角色；写失败静默降级。 */
export function writeRole(role: RoleId): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(ROLE_KEY, isRoleId(role) ? role : DEFAULT_ROLE);
  } catch {
    // 忽略写入失败。
  }
}

/** 版本号语义序：`v<主>.<次>.<修>` 按数字比较，无法解析的排最前。 */
function versionKey(id: string): [number, number, number] | null {
  const match = /^v(\d+)\.(\d+)\.(\d+)$/.exec(id);
  if (!match) {
    return null;
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

export function compareVersion(a: string, b: string): number {
  const left = versionKey(a);
  const right = versionKey(b);
  if (!left && !right) return a.localeCompare(b);
  if (!left) return -1;
  if (!right) return 1;
  for (let i = 0; i < 3; i += 1) {
    if (left[i] !== right[i]) {
      return left[i] - right[i];
    }
  }
  return 0;
}

/** 版本行里语义序最大的那个 id；没有合法版本号时返回 null。 */
export function latestVersionId(ids: string[]): string | null {
  let best: string | null = null;
  for (const id of ids) {
    if (!versionKey(id)) {
      continue;
    }
    if (best === null || compareVersion(id, best) > 0) {
      best = id;
    }
  }
  return best;
}

/** 版本筛选：`latest`（默认）/`all`/具体版本行 id。 */
export const VERSION_FILTER_KEY = "tableflow.ui.versionFilter.v1";
export const VERSION_FILTER_DEFAULT = "latest";

export function readVersionFilter(): string {
  const storage = getStorage();
  if (!storage) {
    return VERSION_FILTER_DEFAULT;
  }
  try {
    return storage.getItem(VERSION_FILTER_KEY) || VERSION_FILTER_DEFAULT;
  } catch {
    return VERSION_FILTER_DEFAULT;
  }
}

export function writeVersionFilter(value: string): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(VERSION_FILTER_KEY, value || VERSION_FILTER_DEFAULT);
  } catch {
    // 忽略写入失败。
  }
}
