import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnSizingState,
} from "@tanstack/react-table";
import { useMemo, type CSSProperties } from "react";

import { isNumericField } from "../field-utils";
import type { Field, Row } from "../types";
import type { Density } from "../ui-prefs";
import { Cell } from "./Cell";
import { EmptyState } from "./EmptyState";

const DEFAULT_COLUMN_WIDTH = 110;
const FIRST_COLUMN_WIDTH = 140;
const MIN_COLUMN_WIDTH = 48;
const MAX_COLUMN_WIDTH = 600;

interface DataTableProps {
  tableId: string;
  fields: Field[];
  rows: Row[];
  density: Density;
  columnWidths: ColumnSizingState;
  onColumnWidthsChange: (next: ColumnSizingState) => void;
  onOpenRelation?: (tableId: string, rowId: string) => void;
  onOpenRelationList?: (tableId: string, rowIds: string[]) => void;
}

export function DataTable({
  tableId,
  fields,
  rows,
  density,
  columnWidths,
  onColumnWidthsChange,
  onOpenRelation,
  onOpenRelationList,
}: DataTableProps) {
  const visibleFields = useMemo(
    () => fields.filter((field) => field.visible !== 0),
    [fields],
  );

  const fieldById = useMemo(() => {
    const map = new Map<string, Field>();
    for (const field of visibleFields) {
      map.set(field.id, field);
    }
    return map;
  }, [visibleFields]);

  const firstFieldId = visibleFields[0]?.id ?? null;

  const columns = useMemo<ColumnDef<Row>[]>(
    () =>
      visibleFields.map((field, index) => ({
        id: field.id,
        header: field.name,
        accessorFn: (row: Row) => row.values[field.id],
        size: index === 0 ? FIRST_COLUMN_WIDTH : DEFAULT_COLUMN_WIDTH,
        minSize: MIN_COLUMN_WIDTH,
        maxSize: MAX_COLUMN_WIDTH,
        cell: (context) => (
          <Cell
            field={field}
            value={context.getValue()}
            truncate
            onOpenRelation={onOpenRelation}
            onOpenRelationList={onOpenRelationList}
          />
        ),
      })),
    [visibleFields, onOpenRelation, onOpenRelationList],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { columnSizing: columnWidths },
    onColumnSizingChange: (updater) => {
      const next =
        typeof updater === "function" ? updater(columnWidths) : updater;
      // 只保留当前表仍存在的字段，避免已删除字段的列宽被反复写回存储。
      const sanitized: ColumnSizingState = {};
      for (const field of visibleFields) {
        const value = next[field.id];
        if (typeof value === "number" && Number.isFinite(value)) {
          sanitized[field.id] = value;
        }
      }
      onColumnWidthsChange(sanitized);
    },
    columnResizeMode: "onChange",
    enableColumnResizing: true,
    getRowId: (row) => row.id,
    getCoreRowModel: getCoreRowModel(),
    defaultColumn: {
      minSize: MIN_COLUMN_WIDTH,
      maxSize: MAX_COLUMN_WIDTH,
      size: DEFAULT_COLUMN_WIDTH,
    },
  });

  const totalWidth = table.getTotalSize();
  const isEmpty = table.getRowModel().rows.length === 0;
  const firstColumnWidth = firstFieldId
    ? (table.getColumn(firstFieldId)?.getSize() ?? FIRST_COLUMN_WIDTH)
    : FIRST_COLUMN_WIDTH;
  const frameStyle = {
    "--first-col-width": `${firstColumnWidth}px`,
  } as CSSProperties;

  return (
    <div
      className="table-frame"
      style={frameStyle}
      data-density={density}
      data-table-id={tableId}
    >
      <div className="table-wrap">
        <table style={{ width: totalWidth, minWidth: "100%" }}>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const field = fieldById.get(header.id);
                  const classes = ["th-cell"];
                  if (header.id === firstFieldId) {
                    classes.push("is-first");
                  }
                  if (field && isNumericField(field)) {
                    classes.push("th-number");
                  }
                  return (
                    <th
                      key={header.id}
                      className={classes.join(" ")}
                      style={{ width: header.getSize() }}
                    >
                      <span className="th-label">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </span>
                      {header.column.getCanResize() ? (
                        <span
                          className={`col-resizer${header.column.getIsResizing() ? " is-resizing" : ""}`}
                          role="separator"
                          aria-orientation="vertical"
                          aria-label={`调整「${field?.name ?? header.id}」列宽`}
                          onMouseDown={header.getResizeHandler()}
                          onTouchStart={header.getResizeHandler()}
                        />
                      ) : null}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isEmpty ? (
              <tr>
                <td className="empty-cell" colSpan={Math.max(visibleFields.length, 1)}>
                  <EmptyState kind="no-rows" compact />
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => {
                    const field = fieldById.get(cell.column.id);
                    const classes: string[] = [];
                    if (cell.column.id === firstFieldId) {
                      classes.push("is-first");
                    }
                    if (field && isNumericField(field)) {
                      classes.push("cell-number");
                    }
                    return (
                      <td key={cell.id} className={classes.join(" ") || undefined}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <span className="scroll-hint scroll-hint-left" aria-hidden="true" />
      <span className="scroll-hint scroll-hint-right" aria-hidden="true" />
    </div>
  );
}
