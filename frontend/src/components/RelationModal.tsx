import { useEffect, useState } from "react";

import { fetchRow } from "../api";
import { displayText } from "../field-utils";
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

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        // 只认直接按在遮罩上的关闭，避免弹层内拖选文本到外面误关。
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal modal-wide" role="dialog" aria-modal="true" aria-label={`关联明细 ${rowId}`}>
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
          <div className="kv-grid">
            {state.detail.fields.map((field: Field) => {
              const value = state.detail.row.values[field.id];
              const text = displayText(field, value);
              return (
                <div className="kv-item" key={field.id}>
                  <span className="kv-label">{field.name}</span>
                  <div className="kv-value">
                    {text === "" ? (
                      <span className="kv-empty">—</span>
                    ) : (
                      <Cell field={field} value={value} />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
