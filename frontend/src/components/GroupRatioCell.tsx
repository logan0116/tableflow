import type { Field, Row } from "../types";

interface GroupRatioCellProps {
  /** 关联字段（点击弹层用）。 */
  relationField: Field;
  /** 已完成/总数 文本，如 `7/7`。 */
  ratio: unknown;
  /** 是否完成（布尔）。 */
  done: unknown;
  row: Row;
  onOpen?: (tableId: string, rowIds: string[], field: Field) => void;
}

/**
 * 合并后的关联组单元格：显示「已完成/总数」，点击复用关系弹层看清单。
 *
 * 空集显示 `0/0` 且仍可点（026 US2-AS3）——点了看空清单，而不是死格。
 */
export function GroupRatioCell({ relationField, ratio, done, row, onOpen }: GroupRatioCellProps) {
  const text = typeof ratio === "string" && ratio ? ratio : "0/0";
  const ids = Array.isArray(row.values[relationField.id])
    ? (row.values[relationField.id] as unknown[]).map(String)
    : [];
  const target = (relationField.options as { table_id?: string } | null)?.table_id;
  const ok = done === true;
  const title = `${text}${ids.length ? ` · ${ids.length} 条` : " · 暂无关联条目"}`;

  return (
    <button
      type="button"
      className={`group-ratio${ok ? " is-done" : ""}`}
      title={title}
      aria-label={`${relationField.name} ${text}`}
      onClick={() => {
        if (target && onOpen) {
          onOpen(target, ids, relationField);
        }
      }}
    >
      {text}
    </button>
  );
}
