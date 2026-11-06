/**
 * UI 偏好的本地存储：只存列宽与行密度，不存任何业务数据。
 *
 * - `tableflow.ui.columnWidths.v1`：`{ [tableId]: { [fieldId]: px } }`
 * - `tableflow.ui.density.v1`：`"comfortable" | "compact"`
 *
 * localStorage 不可用、内容损坏、越界或超限时一律静默降级，绝不阻塞渲染。
 */

export type Density = "comfortable" | "compact";

export const COLUMN_WIDTHS_KEY = "tableflow.ui.columnWidths.v1";
export const DENSITY_KEY = "tableflow.ui.density.v1";
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
