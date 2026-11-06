import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo } from "react";

import type { Field, Row } from "../types";
import { Cell } from "./Cell";

interface DataTableProps {
  fields: Field[];
  rows: Row[];
  onOpenRelation?: (tableId: string, rowId: string) => void;
}

export function DataTable({ fields, rows, onOpenRelation }: DataTableProps) {
  const columns = useMemo<ColumnDef<Row>[]>(
    () =>
      fields.map((field) => ({
        id: field.id,
        header: field.name,
        accessorFn: (row: Row) => row.values[field.id],
        cell: (context) => (
          <Cell
            field={field}
            value={context.getValue()}
            onOpenRelation={onOpenRelation}
          />
        ),
      })),
    [fields, onOpenRelation],
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="table-wrap">
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.length === 0 ? (
            <tr>
              <td className="empty" colSpan={Math.max(fields.length, 1)}>
                暂无数据
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
