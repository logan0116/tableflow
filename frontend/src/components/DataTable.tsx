import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo, type CSSProperties } from "react";

import { defaultColumnWidth, isNumericField } from "../field-utils";
import { groupOfField, versionGroups } from "../version-grouping";
import type { Field, Row } from "../types";
import { Cell } from "./Cell";
import { GroupRatioCell } from "./GroupRatioCell";
import { ProgressLights } from "./ProgressLights";
import { EmptyState } from "./EmptyState";

const MIN_COLUMN_WIDTH = 48;
const MAX_COLUMN_WIDTH = 600;
const FALLBACK_COLUMN_WIDTH = 168;

interface DataTableProps {
  tableId: string;
  fields: Field[];
  rows: Row[];
  onOpenRelation?: (tableId: string, rowId: string) => void;
  onOpenRelationList?: (tableId: string, rowIds: string[], field: Field) => void;
}

export function DataTable({
  tableId,
  fields,
  rows,
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

  const groups = useMemo(() => versionGroups(visibleFields), [visibleFields]);

  const columns = useMemo<ColumnDef<Row>[]>(() => {
    const plain = (field: Field, index: number): ColumnDef<Row> => ({
      id: field.id,
      header: field.name,
      accessorFn: (row: Row) => row.values[field.id],
      size: defaultColumnWidth(field, index === 0, rows),
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
    });

    if (!groups) {
      return visibleFields.map((field, index) => plain(field, index));
    }

    const emitted = new Set<string>();
    const out: ColumnDef<Row>[] = [];
    visibleFields.forEach((field, index) => {
      const group = groupOfField(groups, field.id);
      if (!group) {
        out.push(plain(field, index));
        return;
      }
      if (emitted.has(group.key)) {
        return;
      }
      emitted.add(group.key);
      if (group.kind === "lights") {
        const stages = (group.stageFieldIds ?? [])
          .map((id) => fieldById.get(id))
          .filter((item): item is Field => Boolean(item));
        out.push({
          id: group.key,
          header: group.header,
          accessorFn: (row: Row) => row.values[stages[0]?.id ?? ""],
          size: 132,
          minSize: MIN_COLUMN_WIDTH,
          maxSize: MAX_COLUMN_WIDTH,
          cell: (context) => (
            <ProgressLights
              stages={stages}
              values={stages.map((stage) => context.row.original.values[stage.id])}
            />
          ),
        });
        return;
      }
      const relationField = fieldById.get(group.relationFieldId ?? "");
      const ratioField = fieldById.get(group.ratioFieldId ?? "");
      const statusField = fieldById.get(group.statusFieldId ?? "");
      const doneCountField = fieldById.get(group.doneCountFieldId ?? "");
      if (!relationField) {
        out.push(plain(field, index));
        return;
      }
      out.push({
        id: group.key,
        header: group.header,
        accessorFn: (row: Row) => row.values[ratioField?.id ?? relationField.id],
        size: 104,
        minSize: MIN_COLUMN_WIDTH,
        maxSize: MAX_COLUMN_WIDTH,
        cell: (context) => (
          <GroupRatioCell
            relationField={relationField}
            ratio={
              ratioField
                ? doneCountField
                  // 用例组：已完成与总数是两个数字字段，拼成 "7/7"（v0.8.5 显示 0/0 的根因）
                  ? `${context.row.original.values[doneCountField.id] ?? 0}/${
                      context.row.original.values[ratioField.id] ?? 0
                    }`
                  : context.row.original.values[ratioField.id]
                : undefined
            }
            done={statusField ? context.row.original.values[statusField.id] : undefined}
            row={context.row.original}
            onOpen={onOpenRelationList}
          />
        ),
      });
    });
    return out;
  }, [visibleFields, groups, fieldById, rows, onOpenRelation, onOpenRelationList]);

  const table = useReactTable({
    data: rows,
    columns,
    enableColumnResizing: false,
    getRowId: (row) => row.id,
    getCoreRowModel: getCoreRowModel(),
    defaultColumn: {
      minSize: MIN_COLUMN_WIDTH,
      maxSize: MAX_COLUMN_WIDTH,
      size: FALLBACK_COLUMN_WIDTH,
    },
  });

  const totalWidth = table.getTotalSize();
  const isEmpty = table.getRowModel().rows.length === 0;
  const firstColumnWidth = firstFieldId
    ? (table.getColumn(firstFieldId)?.getSize() ?? FALLBACK_COLUMN_WIDTH)
    : FALLBACK_COLUMN_WIDTH;
  const frameStyle = {
    "--first-col-width": `${firstColumnWidth}px`,
  } as CSSProperties;

  return (
    <div
      className="table-frame"
      style={frameStyle}
      data-density="comfortable"
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
                      <span className="th-label" title={field?.name}>
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
