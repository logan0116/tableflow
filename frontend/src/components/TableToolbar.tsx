import type { Density } from "../ui-prefs";

interface TableToolbarProps {
  density: Density;
  onDensityChange: (density: Density) => void;
  onResetColumnWidths: () => void;
  canResetColumnWidths: boolean;
}

/** 表格工具栏：行密度两档切换 + 重置列宽。 */
export function TableToolbar({
  density,
  onDensityChange,
  onResetColumnWidths,
  canResetColumnWidths,
}: TableToolbarProps) {
  return (
    <div className="table-toolbar" role="toolbar" aria-label="表格显示设置">
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
