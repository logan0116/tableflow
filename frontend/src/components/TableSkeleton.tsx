interface TableSkeletonProps {
  /** 占位列数；未知时给一个合理默认值。 */
  columns?: number;
  rows?: number;
}

const DEFAULT_COLUMNS = 6;
const DEFAULT_ROWS = 8;

/** 与真实表格同构的加载骨架：1 行表头 + 8 行占位。 */
export function TableSkeleton({ columns = DEFAULT_COLUMNS, rows = DEFAULT_ROWS }: TableSkeletonProps) {
  const columnCount = Math.max(1, Math.min(columns, 24));
  const rowCount = Math.max(1, Math.min(rows, 20));

  return (
    <div className="table-skeleton" role="status" aria-live="polite">
      <span className="sr-only">加载中…</span>
      <div className="table-skeleton-head" aria-hidden="true">
        {Array.from({ length: columnCount }, (_, index) => (
          <span key={`head-${index}`} className="skeleton-block skeleton-head" />
        ))}
      </div>
      <div className="table-skeleton-body" aria-hidden="true">
        {Array.from({ length: rowCount }, (_, rowIndex) => (
          <div key={`row-${rowIndex}`} className="table-skeleton-row">
            {Array.from({ length: columnCount }, (_, columnIndex) => (
              <span key={`cell-${rowIndex}-${columnIndex}`} className="skeleton-block" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** 项目/表格切换区的轻量占位条，避免整页闪白。 */
export function InlineSkeleton({ width = 96 }: { width?: number }) {
  return (
    <span className="skeleton-inline" aria-hidden="true">
      <span className="skeleton-block" style={{ width }} />
      <span className="skeleton-block" style={{ width: width * 0.75 }} />
      <span className="skeleton-block" style={{ width: width * 0.6 }} />
    </span>
  );
}
