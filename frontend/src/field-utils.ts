import type {
  ComputedOptions,
  Field,
  FieldOption,
  FieldOptions,
  NumberOptions,
  Row,
} from "./types";

/** 取出 options 的对象形态；数组（历史 enum 取值表）与 null 返回 null。 */
export function optionObject<T extends object>(options: FieldOptions): T | null {
  if (!options || Array.isArray(options) || typeof options !== "object") {
    return null;
  }
  return options as T;
}

/** enum 取值表：兼容 002 的 `options.items[]` 与历史的 `options[]`。 */
export function enumItems(field: Field): FieldOption[] {
  if (Array.isArray(field.options)) {
    return field.options.filter(
      (item): item is FieldOption =>
        Boolean(item) && typeof item === "object" && "value" in item,
    );
  }
  const items = optionObject<{ items?: unknown }>(field.options)?.items;
  return Array.isArray(items)
    ? items.filter(
        (item): item is FieldOption =>
          Boolean(item) && typeof item === "object" && "value" in item,
      )
    : [];
}

/** 计算字段的 kind；非计算字段返回 null。 */
export function computedKind(field: Field): ComputedOptions["kind"] | null {
  if (field.type !== "computed") {
    return null;
  }
  const kind = optionObject<ComputedOptions>(field.options)?.kind;
  return kind ?? null;
}

/** 右对齐 + 等宽数字的列：number 字段，以及产出数字的 count/percent/sum 计算字段。 */
export function isNumericField(field: Field): boolean {
  if (field.type === "number") {
    return true;
  }
  const kind = computedKind(field);
  return kind === "count" || kind === "percent" || kind === "sum";
}

/** 数字格式化配置（002 US4）。 */
export function numberOptions(field: Field): NumberOptions | null {
  return field.type === "number" ? optionObject<NumberOptions>(field.options) : null;
}

/** 默认列宽下限 / 上限（用户拖拽范围仍为 004 的 48–600）。 */
const DEFAULT_WIDTH_MIN = 88;
const DEFAULT_WIDTH_MAX = 320;
const FIRST_COLUMN_EXTRA = 16;
/** 表头左右内边距 12px×2 + 省略号与字距预留 16px。 */
const HEADER_PADDING = 40;

const CJK = /[\u3000-\u9fff\uf900-\ufaff\uff00-\uffef]/;

/**
 * 表头文字宽度估算：中文按 1 字宽（14px）、西文按 0.57 字宽（8px）。
 * 只做字符近似，不用 canvas 或 DOM 测量（宪法原则 IV）。
 */
export function estimateHeaderWidth(name: string): number {
  let px = 0;
  for (const ch of name) {
    px += CJK.test(ch) ? 14 : 8;
  }
  return px + HEADER_PADDING;
}

/** 单元格左右内边距与省略号预留（与 styles.css 的 cell padding 对齐）。 */
const CELL_PADDING = 32;

/** 文本宽度估算：中文 14px、西文 8px，与表头同口径，不做 DOM 测量。 */
export function estimateTextWidth(text: string): number {
  let px = 0;
  for (const ch of text) {
    px += CJK.test(ch) ? 14 : 8;
  }
  return px;
}

/** 某列可见内容所需的最小宽度（含内边距）；全空返回 0。 */
export function contentMinWidth(field: Field, rows: Row[]): number {
  let max = 0;
  for (const row of rows) {
    const text = displayText(field, row.values[field.id]);
    if (!text) {
      continue;
    }
    const width = estimateTextWidth(text) + CELL_PADDING;
    if (width > max) {
      max = width;
    }
  }
  return max;
}

/**
 * 默认列宽：min(内容最小宽, 最大列宽上限)。
 *
 * 028 起不再按字段类型基础宽放大——内容短就窄，超过上限才省略。
 * `maxWidth` 由工具栏的最大列宽设置传入（默认 320）。
 */
export function defaultColumnWidth(
  field: Field,
  isFirst: boolean,
  rows: Row[] = [],
  maxWidth: number = DEFAULT_WIDTH_MAX,
): number {
  const headerWidth = estimateHeaderWidth(field.name);
  const content = contentMinWidth(field, rows);
  const wanted = Math.max(headerWidth, content) + (isFirst ? FIRST_COLUMN_EXTRA : 0);
  const upper = Math.max(DEFAULT_WIDTH_MIN, Math.min(maxWidth, DEFAULT_WIDTH_MAX));
  return Math.min(upper, Math.max(DEFAULT_WIDTH_MIN, wanted));
}

/** 单元格的显示文本（供筛选匹配用，与渲染保持一致）。 */
export function displayText(field: Field, value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join("、");
  }
  if (field.type === "enum") {
    const option = enumItems(field).find((item) => item.value === value);
    return option?.label ?? String(value);
  }
  if (field.type === "datetime") {
    const date = new Date(String(value));
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    const pad = (n: number) => String(n).padStart(2, "0");
    const ymd = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
    return String(value).includes("T")
      ? `${ymd} ${pad(date.getHours())}:${pad(date.getMinutes())}`
      : ymd;
  }
  return String(value);
}
