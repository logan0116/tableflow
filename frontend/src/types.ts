export type FieldType = "text" | "number" | "datetime" | "enum";

export interface FieldOption {
  value: string;
  label: string;
}

export interface Field {
  id: string;
  name: string;
  type: string;
  options: FieldOption[] | null;
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

export interface TableResponse {
  project: Project;
  fields: Field[];
  rows: Row[];
}
