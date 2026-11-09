import type { DatetimeOptions, Field, FieldOption, RelationOptions } from "../types";
import { enumItems, isNumericField, numberOptions, optionObject } from "../field-utils";
import { EnumTag } from "./EnumTag";

interface CellProps {
  field: Field;
  value: unknown;
  /** 主表单元格：单行截断，全文进 title；明细弹层不传，保持换行全文。 */
  truncate?: boolean;
  onOpenRelation?: (tableId: string, rowId: string) => void;
  onOpenRelationList?: (tableId: string, rowIds: string[], field: Field) => void;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function formatDateTime(raw: string, withTime: boolean | undefined): string {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  const ymd = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const includeTime = withTime ?? raw.includes("T");
  return includeTime ? `${ymd} ${pad(date.getHours())}:${pad(date.getMinutes())}` : ymd;
}

function formatNumber(value: unknown, field: Field): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  const options = numberOptions(field);
  const decimals =
    typeof options?.decimals === "number" &&
    Number.isInteger(options.decimals) &&
    options.decimals >= 0 &&
    options.decimals <= 6
      ? options.decimals
      : null;
  const normalized = Object.is(numeric, -0) ? 0 : numeric;
  const text = decimals === null ? String(normalized) : normalized.toFixed(decimals);
  if (options?.percent) {
    return `${text}%`;
  }
  const unit = typeof options?.unit === "string" ? options.unit.trim() : "";
  return unit ? `${text} ${unit}` : text;
}

function findOption(field: Field, value: unknown): FieldOption | undefined {
  return enumItems(field).find((item) => item.value === value);
}

function isBlank(value: unknown): boolean {
  return value === null || value === undefined || value === "";
}

export function Cell({ field, value, truncate, onOpenRelation, onOpenRelationList }: CellProps) {
  const blank = isBlank(value);

  // 数字列（number 与产出数字的计算字段）始终右对齐占位，空值也不破坏列宽。
  if (isNumericField(field)) {
    return <span className="cell-number">{blank ? "" : formatNumber(value, field)}</span>;
  }

  if (blank) {
    return <span />;
  }

  if (typeof value === "boolean") {
    return (
      <EnumTag
        option={{
          value: String(value),
          label: value ? "是" : "否",
          tone: value ? "success" : "neutral",
        }}
        fallback={String(value)}
      />
    );
  }

  switch (field.type) {
    case "datetime": {
      const options = optionObject<DatetimeOptions>(field.options);
      const text = formatDateTime(String(value), options?.with_time);
      return (
        <span className={truncate ? "cell-text" : undefined} title={truncate ? text : undefined}>
          {text}
        </span>
      );
    }
    case "enum": {
      const option = findOption(field, value);
      return (
        <span className="cell-nowrap">
          <EnumTag option={option} fallback={String(value)} />
        </span>
      );
    }
    case "relation": {
      const ids = Array.isArray(value) ? value.map(String) : [];
      if (ids.length === 0) {
        return <span />;
      }
      const target = optionObject<RelationOptions>(field.options)?.table_id;
      return (
        <button
          type="button"
          className="relation-link cell-nowrap"
          title={ids.join("、")}
          onClick={() => {
            if (!target) {
              return;
            }
            if (onOpenRelationList) {
              onOpenRelationList(target, ids, field);
            } else {
              onOpenRelation?.(target, ids[0]);
            }
          }}
        >
          {ids.length === 1 ? ids[0] : `${ids[0]} +${ids.length - 1}`}
        </button>
      );
    }
    case "text":
    default: {
      const text = String(value);
      if (truncate) {
        // 主表：单行 + 省略号，行高不随文本长度变化；全文靠 title 与明细弹层。
        return (
          <span className="cell-text" title={text}>
            {text}
          </span>
        );
      }
      const compact = text.length <= 12 || /^[\w\-./]+$/.test(text);
      return <span className={compact ? "cell-nowrap" : undefined}>{text}</span>;
    }
  }
}
