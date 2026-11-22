import type { TableSummary } from "./types";

/**
 * 表级 kind（board@4）：只有 board 表进表导航，detail 表只经 relation 弹层展示。
 *
 * 缺失 kind 时按 board 处理——board@3 的接口没有这个字段，兼容期不能让导航整片消失。
 * 这里只读服务端元数据，不按表名/表 id 猜测（宪法原则 III）。
 */
export function isBoardTable(table: TableSummary): boolean {
  return table.kind !== "detail";
}

/** 表导航可见的表：过滤掉 detail 表，保持接口返回的顺序。 */
export function boardTables(tables: TableSummary[]): TableSummary[] {
  return tables.filter(isBoardTable);
}

/** 表导航当前选中项：只允许落在 board 表上；没有 board 表时返回 null。 */
export function firstBoardTableId(tables: TableSummary[]): string | null {
  return boardTables(tables)[0]?.id ?? null;
}
