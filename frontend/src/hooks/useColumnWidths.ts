import type { ColumnSizingState } from "@tanstack/react-table";
import { useCallback, useEffect, useRef, useState } from "react";

import { clearColumnWidths, readColumnWidths, writeColumnWidths } from "../ui-prefs";

const PERSIST_DEBOUNCE_MS = 300;

interface UseColumnWidthsResult {
  widths: ColumnSizingState;
  setWidths: (next: ColumnSizingState) => void;
  resetWidths: () => void;
}

/**
 * 列宽记忆：按「表 + 字段」读写 localStorage，拖动时只更新内存，
 * 300ms 后再落盘；切换表格时重新读取。只存列宽，不存业务数据。
 */
export function useColumnWidths(tableId: string | null): UseColumnWidthsResult {
  const [widths, setWidthsState] = useState<ColumnSizingState>(() =>
    tableId ? readColumnWidths(tableId) : {},
  );
  const timer = useRef<number | null>(null);
  const activeTable = useRef<string | null>(tableId);

  const clearTimer = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => {
    activeTable.current = tableId;
    clearTimer();
    setWidthsState(tableId ? readColumnWidths(tableId) : {});
  }, [tableId, clearTimer]);

  const setWidths = useCallback(
    (next: ColumnSizingState) => {
      setWidthsState(next);
      const currentTable = activeTable.current;
      if (!currentTable) {
        return;
      }
      clearTimer();
      timer.current = window.setTimeout(() => {
        timer.current = null;
        writeColumnWidths(currentTable, next);
      }, PERSIST_DEBOUNCE_MS);
    },
    [clearTimer],
  );

  const resetWidths = useCallback(() => {
    clearTimer();
    setWidthsState({});
    if (activeTable.current) {
      clearColumnWidths(activeTable.current);
    }
  }, [clearTimer]);

  useEffect(() => clearTimer, [clearTimer]);

  return { widths, setWidths, resetWidths };
}
