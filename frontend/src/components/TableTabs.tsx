import type { TableSummary } from "../types";

interface TableTabsProps {
  tables: TableSummary[];
  currentId: string | null;
  onSelect: (tableId: string) => void;
}

export function TableTabs({ tables, currentId, onSelect }: TableTabsProps) {
  return (
    <div className="tabs" role="tablist" aria-label="表格切换">
      {tables.map((table) => (
        <button
          key={table.id}
          type="button"
          role="tab"
          aria-selected={table.id === currentId}
          onClick={() => onSelect(table.id)}
        >
          {table.name}
        </button>
      ))}
    </div>
  );
}
