import type { Field } from "../types";

interface CellProps {
  field: Field;
  value: unknown;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function formatDateTime(raw: string): string {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  const ymd = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  if (!raw.includes("T")) {
    return ymd;
  }
  return `${ymd} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function Cell({ field, value }: CellProps) {
  if (value === null || value === undefined || value === "") {
    return <span />;
  }

  switch (field.type) {
    case "number":
      return <span>{String(value)}</span>;
    case "datetime":
      return <span>{formatDateTime(String(value))}</span>;
    case "enum": {
      const option = field.options?.find((item) => item.value === value);
      return <span>{option?.label ?? String(value)}</span>;
    }
    case "text":
    default:
      return <span>{String(value)}</span>;
  }
}
