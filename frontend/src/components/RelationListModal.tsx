import { useEffect, useState } from "react";

import { fetchTable } from "../api";
import { displayText, enumItems, optionObject } from "../field-utils";
import type { Field, RelationOptions, Row } from "../types";
import { EnumTag } from "./EnumTag";

interface RelationListModalProps {
  /** 源 relation 字段：显示列由它的 options.display_field / status_field 决定。 */
  field: Field;
  tableId: string;
  rowIds: string[];
  onPick: (rowId: string) => void;
  onClose: () => void;
}

type ListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; rows: Map<string, Row>; fields: Field[] };

/** 按 relation 字段的配置解析显示列；不按字段名猜测（宪法原则 III）。 */
function resolveColumns(field: Field, fields: Field[]) {
  const options = optionObject<RelationOptions>(field.options);
  const byId = new Map(fields.map((item) => [item.id, item]));
  return {
    display: options?.display_field ? byId.get(options.display_field) ?? null : null,
    status: options?.status_field ? byId.get(options.status_field) ?? null : null,
  };
}

/** 关联条目列表：编号 + 配置的名称列 + 配置的状态列，点一行看明细。 */
export function RelationListModal({ field, tableId, rowIds, onPick, onClose }: RelationListModalProps) {
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
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label="关联条目">
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
          (() => {
            const { display, status } = resolveColumns(field, state.fields);
            const isEnumStatus = status?.type === "enum";
            return (
              <table className="relation-table">
                <thead>
                  <tr>
                    <th>编号</th>
                    {display ? <th>{display.name}</th> : null}
                    {status ? <th>{status.name}</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {rowIds.map((rowId) => {
                    const row = state.rows.get(rowId);
                    const displayValue =
                      row && display ? displayText(display, row.values[display.id]) : "";
                    const statusValue = row && status ? row.values[status.id] : null;
                    const statusOption =
                      status && isEnumStatus && statusValue != null
                        ? enumItems(status).find((item) => item.value === statusValue) ?? null
                        : null;

                    return (
                      <tr
                        key={rowId}
                        className={row ? "relation-row" : "relation-row is-missing"}
                        onClick={() => {
                          if (row) {
                            onPick(rowId);
                          }
                        }}
                      >
                        <td className="relation-id">{rowId}</td>
                        {display ? (
                          <td>{row ? displayValue || "—" : "关联已失效"}</td>
                        ) : null}
                        {status ? (
                          <td>
                            {row && statusValue != null && isEnumStatus ? (
                              <EnumTag
                                option={statusOption}
                                fallback={displayText(status, statusValue)}
                              />
                            ) : row && statusValue != null ? (
                              displayText(status, statusValue)
                            ) : null}
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            );
          })()
        )}
      </div>
    </div>
  );
}
