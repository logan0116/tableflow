import { useEffect, useState } from "react";

import { fetchRow } from "../api";
import type { Field, RowDetailResponse } from "../types";
import { Cell } from "./Cell";

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
          <div className="state">加载中…</div>
        ) : state.status === "error" ? (
          <div className="state">关联已失效：{state.message}</div>
        ) : (
          <table>
            <thead>
              <tr>
                {state.detail.fields.map((field: Field) => (
                  <th key={field.id}>{field.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {state.detail.fields.map((field: Field) => (
                  <td key={field.id}>
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
