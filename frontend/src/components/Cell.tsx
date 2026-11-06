import type { Field, FieldOption } from "../types";

interface CellProps {
  field: Field;
  value: unknown;
  onOpenRelation?: (tableId: string, rowId: string) => void;
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

function enumOptions(field: Field): FieldOption[] {
  return Array.isArray(field.options) ? (field.options as FieldOption[]) : [];
}

export function Cell({ field, value, onOpenRelation }: CellProps) {
  if (value === null || value === undefined || value === "") {
    return <span />;
  }

  switch (field.type) {
    case "number":
      return <span className="cell-nowrap">{String(value)}</span>;
    case "datetime":
      return <span>{formatDateTime(String(value))}</span>;
    case "enum": {
      const option = enumOptions(field).find((item) => item.value === value);
      return <span className="cell-nowrap">{option?.label ?? String(value)}</span>;
    }
    case "relation": {
      const ids = Array.isArray(value) ? value.map(String) : [];
      if (ids.length === 0) {
        return <span />;
      }
      const target = (field.options as { table_id?: string } | null)?.table_id;
      return (
        <span className="cell-nowrap">
          {ids.map((id, index) => (
            <span key={id}>
              {index > 0 ? "、" : ""}
              <button
                type="button"
                className="relation-link"
                onClick={() => {
                  if (target) {
                    onOpenRelation?.(target, id);
                  }
                }}
              >
                {id}
              </button>
            </span>
          ))}
        </span>
      );
    }
    case "text":
    default: {
      const text = String(value);
      const compact = text.length <= 12 || /^[\w\-./]+$/.test(text);
      return <span className={compact ? "cell-nowrap" : undefined}>{text}</span>;
    }
  }
}
