export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export interface FieldColor {
  bg?: string;
  fg?: string;
}

export interface FieldOption {
  value: string;
  label: string;
  tone?: Tone | string;
  color?: FieldColor | null;
}

export interface FieldConstraints {
  required?: boolean;
  min?: number;
  max?: number;
  enum_strict?: boolean;
  relation_must_exist?: boolean;
}

export interface EnumOptions {
  items?: FieldOption[];
  constraints?: FieldConstraints;
  human_request?: boolean;
}

export interface NumberOptions {
  decimals?: number;
  percent?: boolean;
  unit?: string;
  constraints?: FieldConstraints;
}

export interface DatetimeOptions {
  with_time?: boolean;
  constraints?: FieldConstraints;
}

export interface RelationOptions {
  table_id?: string;
  /** 关联条目列表里用作「名称」列的字段 id（目标表字段）。缺失时只显示编号列。 */
  display_field?: string;
  /** 关联条目列表里用作「状态」列的字段 id（目标表字段）。缺失时不显示状态列。 */
  status_field?: string;
  /** 关联条目列表里用作「结果」列的字段 id（目标表字段）。缺失时不显示结果列（043）。 */
  result_field?: string;
  constraints?: FieldConstraints;
}

export interface ComputedOptions {
  kind?: "count" | "percent" | "sum" | "rollup" | "and" | "ratio";
  allow_override?: boolean;
  constraints?: FieldConstraints;
}

/**
 * 字段 options 的联合类型。
 *
 * 002 起统一为对象（enum 的取值表在 `options.items`）；早期样例把 enum 的取值表
 * 直接存成数组，前端读侧同时兼容两种形态，避免历史数据导致整张表读失败。
 */
export type FieldOptions =
  | FieldOption[]
  | EnumOptions
  | NumberOptions
  | DatetimeOptions
  | RelationOptions
  | ComputedOptions
  | null;

export interface Field {
  id: string;
  name: string;
  type: string;
  options: FieldOptions;
  order: number;
  visible?: number;
}

export interface Row {
  id: string;
  values: Record<string, unknown>;
}

export interface Project {
  id: string;
  name: string;
}

/**
 * 表级 kind（board@4）：board 进表导航，detail 不进导航但仍可被 relation 弹层读取。
 * 旧接口/旧库没有该字段时按 board 兼容（board@3 行为不变）。
 */
export type TableKind = "board" | "detail";

export interface TableSummary {
  id: string;
  name: string;
  order: number;
  kind?: TableKind;
}

export interface TableResponse {
  project: Project;
  table: TableSummary;
  fields: Field[];
  rows: Row[];
}

export interface RowDetailResponse {
  table: TableSummary;
  fields: Field[];
  row: Row;
}
