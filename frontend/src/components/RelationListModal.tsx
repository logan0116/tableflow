import { useEffect, useState } from "react";

import { fetchTable } from "../api";
import { displayText, enumItems } from "../field-utils";
import type { Field, Row } from "../types";
import { EnumTag } from "./EnumTag";

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

const TITLE_NAMES = ["标题", "条款", "名称", "姓名", "设备", "任务"];
const STATUS_NAMES = ["状态", "发布状态", "回归状态"];

function pickTitleField(fields: Field[]): Field | null {
  for (const name of TITLE_NAMES) {
    const hit = fields.find((field) => field.name === name);
    if (hit) {
      return hit;
    }
  }
  // 退而求其次：第一个不是“编号”的文本字段
  return fields.find((field) => field.type === "text" && !/编号|id/i.test(field.name)) ?? null;
}

function pickStatusField(fields: Field[]): Field | null {
  for (const name of STATUS_NAMES) {
    const hit = fields.find((field) => field.name === name);
    if (hit) {
      return hit;
    }
  }
  return fields.find((field) => field.type === "enum") ?? null;
}

/** 关联条目列表：编号 + 标题 + 状态，点一行看明细。 */
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
          <table className="relation-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>标题</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {rowIds.map((rowId) => {
                const row = state.rows.get(rowId);
                const titleField = pickTitleField(state.fields);
                const statusField = pickStatusField(state.fields);
                const title = row && titleField ? displayText(titleField, row.values[titleField.id]) : "";
                const statusValue = row && statusField ? row.values[statusField.id] : null;
                const statusOption =
                  statusField && statusValue != null
                    ? enumItems(statusField).find((item) => item.value === statusValue) ?? null
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
                    <td>{row ? title : "关联已失效"}</td>
                    <td>
                      {row && statusField && statusValue != null ? (
                        <EnumTag option={statusOption} fallback={displayText(statusField, statusValue)} />
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
