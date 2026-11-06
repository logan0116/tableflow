export interface FieldOption {
  value: string;
  label: string;
}

export interface Field {
  id: string;
  name: string;
  type: string;
  options: unknown;
  order: number;
}

export interface Row {
  id: string;
  values: Record<string, unknown>;
}

export interface Project {
  id: string;
  name: string;
}

export interface TableSummary {
  id: string;
  name: string;
  order: number;
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
