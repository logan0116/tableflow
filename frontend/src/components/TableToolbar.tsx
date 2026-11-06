import type { Density } from "../ui-prefs";

interface TableToolbarProps {
  filter: string;
  onFilterChange: (value: string) => void;
  totalRows: number;
  shownRows: number;
  density: Density;
  onDensityChange: (density: Density) => void;
  onResetColumnWidths: () => void;
  canResetColumnWidths: boolean;
}

/** 表格工具栏：行密度两档切换 + 重置列宽。 */
export function TableToolbar({
  filter,
  onFilterChange,
  totalRows,
  shownRows,
  density,
  onDensityChange,
  onResetColumnWidths,
  canResetColumnWidths,
}: TableToolbarProps) {
  return (
    <div className="table-toolbar" role="toolbar" aria-label="表格显示设置">
      <div className="filter-box">
        <input
          type="search"
          value={filter}
          placeholder="筛选：输入关键字，跨所有列匹配"
          aria-label="筛选条目"
          onChange={(event) => onFilterChange(event.target.value)}
        />
        {filter ? (
          <button type="button" className="filter-clear" onClick={() => onFilterChange("")}>
            清除
          </button>
        ) : null}
        <span className="filter-count">
          {filter ? `${shownRows}/${totalRows} 条` : `共 ${totalRows} 条`}
        </span>
      </div>
      <div className="density-toggle" role="group" aria-label="行密度">
        <span className="toolbar-label">行密度</span>
        <button
          type="button"
          aria-pressed={density === "comfortable"}
          onClick={() => onDensityChange("comfortable")}
        >
          舒适
        </button>
        <button
          type="button"
          aria-pressed={density === "compact"}
          onClick={() => onDensityChange("compact")}
        >
          紧凑
        </button>
      </div>
      <button
        type="button"
        className="toolbar-reset"
        onClick={onResetColumnWidths}
        disabled={!canResetColumnWidths}
        title={canResetColumnWidths ? "清除当前表的列宽记忆" : "当前表还没有列宽记忆"}
      >
        重置列宽
      </button>
    </div>
  );
}
