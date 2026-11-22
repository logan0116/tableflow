/**
 * UI 偏好的本地存储：只存列宽、行密度与当前角色，不存任何业务数据。
 *
 * - `tableflow.ui.columnWidths.v1`：`{ [tableId]: { [fieldId]: px } }`
 * - `tableflow.ui.density.v1`：`"comfortable" | "compact"`
 * - `tableflow.ui.role.v1`：`"systems" | "dev" | "test" | "all"`
 *
 * localStorage 不可用、内容损坏、越界或超限时一律静默降级，绝不阻塞渲染。
 */

import { DEFAULT_ROLE, isRoleId, type RoleId } from "./roles";

export type Density = "comfortable" | "compact";

export const COLUMN_WIDTHS_KEY = "tableflow.ui.columnWidths.v1";
export const DENSITY_KEY = "tableflow.ui.density.v1";
export const ROLE_KEY = "tableflow.ui.role.v1";
export const MIN_COLUMN_WIDTH = 48;
export const MAX_COLUMN_WIDTH = 600;
export const MAX_WIDTH_ENTRIES = 200;

export type ColumnWidths = Record<string, number>;
type WidthStore = Record<string, ColumnWidths>;

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

function clampWidth(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  const rounded = Math.round(value);
  if (rounded < MIN_COLUMN_WIDTH) {
    return MIN_COLUMN_WIDTH;
  }
  if (rounded > MAX_COLUMN_WIDTH) {
    return MAX_COLUMN_WIDTH;
  }
  return rounded;
}

function sanitizeWidths(raw: unknown): ColumnWidths {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return {};
  }
  const widths: ColumnWidths = {};
  for (const [fieldId, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!fieldId) {
      continue;
    }
    const width = clampWidth(value);
    if (width !== null) {
      widths[fieldId] = width;
    }
  }
  return widths;
}

function sanitizeStore(raw: unknown): WidthStore {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return {};
  }
  const store: WidthStore = {};
  for (const [tableId, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!tableId || !value || typeof value !== "object" || Array.isArray(value)) {
      continue;
    }
    const widths = sanitizeWidths(value);
    if (Object.keys(widths).length > 0) {
      store[tableId] = widths;
    }
  }
  return store;
}

function readStore(): WidthStore {
  const storage = getStorage();
  if (!storage) {
    return {};
  }
  try {
    const raw = storage.getItem(COLUMN_WIDTHS_KEY);
    if (!raw) {
      return {};
    }
    return sanitizeStore(JSON.parse(raw));
  } catch {
    return {};
  }
}

function writeStore(store: WidthStore): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(COLUMN_WIDTHS_KEY, JSON.stringify(store));
  } catch {
    // 隐私模式 / 配额超限：静默降级。
  }
}

function trimStore(store: WidthStore): WidthStore {
  const tableIds = Object.keys(store);
  if (tableIds.length <= MAX_WIDTH_ENTRIES) {
    return store;
  }
  const trimmed: WidthStore = {};
  for (const tableId of tableIds.slice(tableIds.length - MAX_WIDTH_ENTRIES)) {
    trimmed[tableId] = store[tableId];
  }
  return trimmed;
}

/** 读取某张表的列宽记忆；非法条目被忽略。 */
export function readColumnWidths(tableId: string): ColumnWidths {
  return readStore()[tableId] ?? {};
}

/** 写入某张表的列宽；写前净化，并把该表移到最近使用位置。 */
export function writeColumnWidths(tableId: string, widths: ColumnWidths): void {
  const clean = sanitizeWidths(widths);
  const store = readStore();
  delete store[tableId];
  if (Object.keys(clean).length > 0) {
    store[tableId] = clean;
  }
  writeStore(trimStore(store));
}

/** 清除某张表的列宽记忆。 */
export function clearColumnWidths(tableId: string): void {
  const store = readStore();
  if (tableId in store) {
    delete store[tableId];
    writeStore(store);
  }
}

/** 读取行密度；非法或缺失回退舒适档。 */
export function readDensity(): Density {
  const storage = getStorage();
  if (!storage) {
    return "comfortable";
  }
  try {
    return storage.getItem(DENSITY_KEY) === "compact" ? "compact" : "comfortable";
  } catch {
    return "comfortable";
  }
}

/** 写入行密度；写失败静默降级。 */
export function writeDensity(density: Density): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(DENSITY_KEY, density === "compact" ? "compact" : "comfortable");
  } catch {
    // 忽略写入失败。
  }
}

/** 读取上次选择的角色；缺失或非法回退「全局」。 */
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

/** 最大列宽：自动列宽不会超过该值；默认 320，可选档位。 */
export const MAX_COLUMN_WIDTH_KEY = "tableflow.ui.maxColumnWidth.v1";
export const MAX_COLUMN_WIDTH_DEFAULT = 320;
export const MAX_COLUMN_WIDTH_OPTIONS = [200, 240, 280, 320, 400] as const;

/** 读取最大列宽；非法值回退默认。 */
export function readMaxColumnWidth(): number {
  const storage = getStorage();
  if (!storage) {
    return MAX_COLUMN_WIDTH_DEFAULT;
  }
  try {
    const raw = Number(storage.getItem(MAX_COLUMN_WIDTH_KEY));
    return (MAX_COLUMN_WIDTH_OPTIONS as readonly number[]).includes(raw)
      ? raw
      : MAX_COLUMN_WIDTH_DEFAULT;
  } catch {
    return MAX_COLUMN_WIDTH_DEFAULT;
  }
}

/** 写入最大列宽；写失败静默降级。 */
export function writeMaxColumnWidth(value: number): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    const next = (MAX_COLUMN_WIDTH_OPTIONS as readonly number[]).includes(value)
      ? value
      : MAX_COLUMN_WIDTH_DEFAULT;
    storage.setItem(MAX_COLUMN_WIDTH_KEY, String(next));
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
