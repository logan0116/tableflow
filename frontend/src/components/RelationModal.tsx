import { useEffect, useState } from "react";

import { fetchRow } from "../api";
import { isNumericField } from "../field-utils";
import type { Field, RowDetailResponse } from "../types";
import { Cell } from "./Cell";
import { EmptyState } from "./EmptyState";
import { TableSkeleton } from "./TableSkeleton";

interface RelationModalProps {
  tableId: string;
  rowId: string;
  onClose: () => void;
}

type ModalState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; detail: RowDetailResponse };

export function RelationModal({ tableId, rowId, onClose }: RelationModalProps) {
  const [state, setState] = useState<ModalState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetchRow(tableId, rowId)
      .then((detail) => {
        if (!cancelled) {
          setState({ status: "ready", detail });
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState({ status: "error", message: error.message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tableId, rowId]);

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>关联明细 · {rowId}</h2>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </header>
        {state.status === "loading" ? (
          <TableSkeleton columns={4} rows={3} />
        ) : state.status === "error" ? (
          <EmptyState kind="error" message={`关联已失效：${state.message}`} />
        ) : (
          <table>
            <thead>
              <tr>
                {state.detail.fields.map((field: Field) => (
                  <th
                    key={field.id}
                    className={isNumericField(field) ? "th-number" : undefined}
                  >
                    {field.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {state.detail.fields.map((field: Field) => (
                  <td
                    key={field.id}
                    className={isNumericField(field) ? "cell-number" : undefined}
                  >
                    <Cell field={field} value={state.detail.row.values[field.id]} />
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
