export type EmptyKind =
  | "loading"
  | "no-projects"
  | "no-tables"
  | "no-rows"
  | "no-fields"
  | "error";

const COPY: Record<Exclude<EmptyKind, "error">, { title: string; hint?: string }> = {
  loading: { title: "加载中…" },
  "no-projects": { title: "暂无项目", hint: "先创建项目，再来看板查看数据。" },
  "no-tables": { title: "暂无表格", hint: "当前项目下还没有任何表格。" },
  "no-rows": { title: "暂无数据", hint: "这张表还没有数据行。" },
  "no-fields": { title: "暂无字段", hint: "当前表没有可见字段。" },
};

interface EmptyStateProps {
  kind: EmptyKind;
  /** 仅错误态使用的具体原因。 */
  message?: string | null;
  onRetry?: () => void;
  /** 嵌在表格单元格里时使用紧凑排版。 */
  compact?: boolean;
}

/**
 * 六种互斥状态统一展示：加载中 / 暂无项目 / 暂无表格 / 暂无数据 / 暂无字段 / 读取失败。
 * 只有「读取失败」提供重试按钮，空状态不提供。
 */
export function EmptyState({ kind, message, onRetry, compact = false }: EmptyStateProps) {
  const isError = kind === "error";
  const copy = isError
    ? { title: "读取失败", hint: message ?? "数据读取失败，请稍后重试。" }
    : COPY[kind];

  return (
    <div
      className={`empty-state empty-state-${kind}${compact ? " empty-state-compact" : ""}`}
      role={isError ? "alert" : "status"}
    >
      <p className="empty-state-title">{copy.title}</p>
      {copy.hint ? <p className="empty-state-hint">{copy.hint}</p> : null}
      {isError && onRetry ? (
        <button type="button" className="empty-state-retry" onClick={onRetry}>
          重试
        </button>
      ) : null}
    </div>
  );
}
