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
