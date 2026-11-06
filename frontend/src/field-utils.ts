import type {
  ComputedOptions,
  Field,
  FieldOption,
  FieldOptions,
  NumberOptions,
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
