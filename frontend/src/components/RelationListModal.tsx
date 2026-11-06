import { useEffect, useState } from "react";

import { fetchTable } from "../api";
import type { Field, Row } from "../types";

interface RelationListModalProps {
  tableId: string;
  rowIds: string[];
  onPick: (rowId: string) => void;
  onClose: () => void;
}

type ListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; rows: Map<string, Row>; fields: Field[] };

function labelFor(row: Row | undefined, fields: Field[]): string | null {
  if (!row) {
    return null;
  }
  const textField = fields.find((field) => field.type === "text");
  if (!textField) {
    return null;
  }
  const value = row.values[textField.id];
  return typeof value === "string" && value ? value : null;
}

/** 关联条目列表：点单元格先看列表，再点某条看明细。 */
export function RelationListModal({ tableId, rowIds, onPick, onClose }: RelationListModalProps) {
  const [state, setState] = useState<ListState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetchTable(tableId)
      .then((table) => {
        if (cancelled) {
          return;
        }
        const map = new Map(table.rows.map((row) => [row.id, row]));
        setState({ status: "ready", rows: map, fields: table.fields });
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState({ status: "error", message: error.message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tableId]);

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>关联条目 · {rowIds.length} 项</h2>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </header>

        {state.status === "loading" ? (
          <div className="state">加载中…</div>
        ) : state.status === "error" ? (
          <div className="state">读取关联表失败：{state.message}</div>
        ) : (
          <ul className="relation-list">
            {rowIds.map((rowId) => {
              const row = state.rows.get(rowId);
              const label = labelFor(row, state.fields);
              return (
                <li key={rowId}>
                  <button type="button" onClick={() => onPick(rowId)} disabled={!row}>
                    <span className="relation-id">{rowId}</span>
                    {label ? <span className="relation-label">{label}</span> : null}
                    {row ? null : <span className="relation-missing">关联已失效</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
