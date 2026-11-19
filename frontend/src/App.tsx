import { useEffect, useRef, useState, type ReactNode, useMemo } from "react";

import { fetchProjects, fetchTable, fetchTables } from "./api";
import { displayText } from "./field-utils";
import { DataTable } from "./components/DataTable";
import { EmptyState } from "./components/EmptyState";
import { ProjectNav } from "./components/ProjectNav";
import { RelationListModal } from "./components/RelationListModal";
import { RelationModal } from "./components/RelationModal";
import { TableTabs } from "./components/TableTabs";
import { TableToolbar } from "./components/TableToolbar";
import { InlineSkeleton, TableSkeleton } from "./components/TableSkeleton";
import { useColumnWidths } from "./hooks/useColumnWidths";
import { useDensity } from "./hooks/useDensity";
import type { Field, Project, TableResponse, TableSummary } from "./types";

type TableState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; table: TableResponse };

const DEFAULT_SKELETON_COLUMNS = 6;

export default function App() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);

  const [tables, setTables] = useState<TableSummary[] | null>(null);
  const [tablesError, setTablesError] = useState<string | null>(null);
  const [tableId, setTableId] = useState<string | null>(null);

  const [tableState, setTableState] = useState<TableState>({ status: "loading" });
  const [refreshing, setRefreshing] = useState(false);
  const [modal, setModal] = useState<{ tableId: string; rowId: string } | null>(null);
  const [relationList, setRelationList] = useState<{
    tableId: string;
    rowIds: string[];
    field: Field;
  } | null>(null);
  const [filter, setFilter] = useState("");

  const [density, setDensity] = useDensity();
  const { widths, setWidths, resetWidths } = useColumnWidths(tableId);

  const seq = useRef(0);
  const lastFieldCount = useRef(DEFAULT_SKELETON_COLUMNS);
  /** 刷新令牌：导航会自增以作废进行中的刷新，避免旧结果覆盖新选中项。 */
  const refreshToken = useRef(0);
  const projectIdRef = useRef<string | null>(null);
  const tableIdRef = useRef<string | null>(null);

  useEffect(() => {
    projectIdRef.current = projectId;
  }, [projectId]);

  useEffect(() => {
    tableIdRef.current = tableId;
  }, [tableId]);

  useEffect(() => {
    let cancelled = false;
    setProjectsError(null);
    fetchProjects()
      .then((list) => {
        if (cancelled) {
          return;
        }
        setProjects(list);
        setProjectId(list[0]?.id ?? null);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setProjectsError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!projectId) {
      setTables(null);
      setTableId(null);
      return;
    }
    let cancelled = false;
    setTables(null);
    setTablesError(null);
    setTableId(null);
    fetchTables(projectId)
      .then((list) => {
        if (cancelled) {
          return;
        }
        setTables(list);
        setTableId(list[0]?.id ?? null);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setTablesError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    setFilter("");
    if (!tableId) {
      return;
    }
    const current = ++seq.current;
    setTableState({ status: "loading" });
    fetchTable(tableId)
      .then((table) => {
        if (current === seq.current) {
          lastFieldCount.current = table.fields.length || DEFAULT_SKELETON_COLUMNS;
          setTableState({ status: "ready", table });
        }
      })
      .catch((error: Error) => {
        if (current === seq.current) {
          setTableState({ status: "error", message: error.message });
        }
      });
  }, [tableId]);

  /**
   * 全部重拉：项目 → 当前项目表格 → 当前表格数据。
   * 直接保留旧内容直到新结果返回（不闪骨架），并保留当前项目、表格与筛选词。
   */
  const refreshAll = async () => {
    const token = ++refreshToken.current;
    setRefreshing(true);
    let stage: "projects" | "tables" | "table" = "projects";
    try {
      const list = await fetchProjects();
      if (token !== refreshToken.current) {
        return;
      }
      setProjects(list);
      setProjectsError(null);

      const activeProject = projectIdRef.current;
      const nextProject =
        activeProject && list.some((project) => project.id === activeProject)
          ? activeProject
          : list[0]?.id ?? null;
      if (nextProject !== activeProject) {
        setProjectId(nextProject);
        return;
      }
      if (!nextProject) {
        setTables([]);
        setTableId(null);
        return;
      }

      stage = "tables";
      const nextTables = await fetchTables(nextProject);
      if (token !== refreshToken.current) {
        return;
      }
      setTables(nextTables);
      setTablesError(null);

      const activeTable = tableIdRef.current;
      const nextTableId =
        activeTable && nextTables.some((table) => table.id === activeTable)
          ? activeTable
          : nextTables[0]?.id ?? null;
      if (nextTableId !== activeTable) {
        setTableId(nextTableId);
        return;
      }
      if (!nextTableId) {
        return;
      }

      stage = "table";
      const table = await fetchTable(nextTableId);
      if (token !== refreshToken.current) {
        return;
      }
      lastFieldCount.current = table.fields.length || DEFAULT_SKELETON_COLUMNS;
      setTableState({ status: "ready", table });
    } catch (error) {
      if (token !== refreshToken.current) {
        return;
      }
      const message = error instanceof Error ? error.message : "刷新失败，请重试";
      if (stage === "projects") {
        setProjectsError(message);
      } else if (stage === "tables") {
        setTablesError(message);
      } else {
        setTableState({ status: "error", message });
      }
    } finally {
      if (token === refreshToken.current) {
        setRefreshing(false);
      }
    }
  };

  /** 导航即作废进行中的刷新，保证后发起的选中项优先。 */
  const selectProject = (nextId: string) => {
    refreshToken.current += 1;
    setRefreshing(false);
    setProjectsError(null);
    setProjectId(nextId);
  };

  const selectTable = (nextId: string) => {
    refreshToken.current += 1;
    setRefreshing(false);
    setTableId(nextId);
  };

  const filteredRows = useMemo(() => {
    if (tableState.status !== "ready") {
      return [];
    }
    const rows = tableState.table.rows;
    const keyword = filter.trim().toLowerCase();
    if (!keyword) {
      return rows;
    }
    const fields = tableState.table.fields;
    return rows.filter((row) =>
      fields.some((field) =>
        displayText(field, row.values[field.id]).toLowerCase().includes(keyword),
      ),
    );
  }, [tableState, filter]);

  const hasColumnWidths = Object.keys(widths).length > 0;

  const currentProject = projects?.find((project) => project.id === projectId) ?? null;
  const currentTable = tables?.find((table) => table.id === tableId) ?? null;
  const totalRows = tableState.status === "ready" ? tableState.table.rows.length : null;
  const isFiltering = filter.trim().length > 0;

  let content: ReactNode;
  if (projectsError) {
    content = <EmptyState kind="error" message={projectsError} onRetry={refreshAll} />;
  } else if (projects === null) {
    content = (
      <div className="state">
        <InlineSkeleton />
      </div>
    );
  } else if (projects.length === 0) {
    content = <EmptyState kind="no-projects" />;
  } else {
    content = (
      <>
        {tablesError ? (
          <EmptyState kind="error" message={tablesError} onRetry={refreshAll} />
        ) : tables === null ? (
          <div className="state">
            <InlineSkeleton />
          </div>
        ) : tables.length === 0 ? (
          <EmptyState kind="no-tables" />
        ) : (
          <>
            <TableTabs tables={tables} currentId={tableId} onSelect={selectTable} />
            {tableState.status === "loading" ? (
              <TableSkeleton columns={lastFieldCount.current} />
            ) : tableState.status === "error" ? (
              <EmptyState kind="error" message={tableState.message} onRetry={refreshAll} />
            ) : tableState.table.fields.length === 0 ? (
              <EmptyState kind="no-fields" />
            ) : (
              <>
                <TableToolbar
                  filter={filter}
                  onFilterChange={setFilter}
                  totalRows={tableState.table.rows.length}
                  shownRows={filteredRows.length}
                  density={density}
                  onDensityChange={setDensity}
                  onResetColumnWidths={resetWidths}
                  canResetColumnWidths={hasColumnWidths}
                />
                <DataTable
                  key={tableState.table.table.id}
                  tableId={tableState.table.table.id}
                  fields={tableState.table.fields}
                  rows={filteredRows}
                  density={density}
                  columnWidths={widths}
                  onColumnWidthsChange={setWidths}
                  onOpenRelation={(targetTableId, rowId) =>
                    setModal({ tableId: targetTableId, rowId })
                  }
                  onOpenRelationList={(targetTableId, rowIds, sourceField) =>
                    setRelationList({ tableId: targetTableId, rowIds, field: sourceField })
                  }
                />
              </>
            )}
          </>
        )}
      </>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-name">TableFlow</span>
          <span className="brand-note">只读看板</span>
        </div>
        <ProjectNav
          projects={projects}
          currentId={projectId}
          onSelect={selectProject}
          error={projectsError}
        />
      </aside>

      <main className="app-main">
        <header className="page-header">
          <h1>
            {currentProject ? (
              <>
                <span className="crumb-project">{currentProject.name}</span>
                {currentTable ? (
                  <>
                    <span className="crumb-sep">›</span>
                    <span className="crumb-table">{currentTable.name}</span>
                  </>
                ) : null}
              </>
            ) : (
              <span className="crumb-table">只读状态看板</span>
            )}
          </h1>
          <div className="header-actions">
            {totalRows !== null && totalRows > 0 ? (
              <span className="page-count">
                {isFiltering ? `${filteredRows.length} / ${totalRows} 条` : `共 ${totalRows} 条`}
              </span>
            ) : null}
            <button
              type="button"
              className={`refresh-button${refreshing ? " is-loading" : ""}`}
              onClick={refreshAll}
              disabled={refreshing}
              aria-busy={refreshing}
              title="重新拉取项目、表格与当前表数据"
            >
              <span className="refresh-icon" aria-hidden="true">
                ⟳
              </span>
              {refreshing ? "刷新中" : "刷新"}
            </button>
          </div>
        </header>
        {content}
      </main>

      {relationList ? (
        <RelationListModal
          field={relationList.field}
          tableId={relationList.tableId}
          rowIds={relationList.rowIds}
          onClose={() => setRelationList(null)}
          onPick={(rowId) => {
            setRelationList(null);
            setModal({ tableId: relationList.tableId, rowId });
          }}
        />
      ) : null}

      {modal ? (
        <RelationModal
          tableId={modal.tableId}
          rowId={modal.rowId}
          onClose={() => setModal(null)}
        />
      ) : null}
    </div>
  );
}
