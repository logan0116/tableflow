import { useEffect, useRef, useState, type ReactNode, useMemo } from "react";

import { fetchProjects, fetchTable, fetchTables } from "./api";
import { displayText } from "./field-utils";
import { DataTable } from "./components/DataTable";
import { EmptyState } from "./components/EmptyState";
import { ProjectSwitcher } from "./components/ProjectSwitcher";
import { RelationListModal } from "./components/RelationListModal";
import { RelationModal } from "./components/RelationModal";
import { TableTabs } from "./components/TableTabs";
import { TableToolbar } from "./components/TableToolbar";
import { InlineSkeleton, TableSkeleton } from "./components/TableSkeleton";
import { useColumnWidths } from "./hooks/useColumnWidths";
import { useDensity } from "./hooks/useDensity";
import type { Project, TableResponse, TableSummary } from "./types";

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
  const [reloadKey, setReloadKey] = useState(0);
  const [modal, setModal] = useState<{ tableId: string; rowId: string } | null>(null);
  const [relationList, setRelationList] = useState<{ tableId: string; rowIds: string[] } | null>(null);
  const [filter, setFilter] = useState("");

  const [density, setDensity] = useDensity();
  const { widths, setWidths, resetWidths } = useColumnWidths(tableId);

  const seq = useRef(0);
  const lastFieldCount = useRef(DEFAULT_SKELETON_COLUMNS);

  useEffect(() => {
    let cancelled = false;
    setProjectsError(null);
    fetchProjects()
      .then((list) => {
        if (cancelled) {
          return;
        }
        setProjects(list);
        setProjectId((previous) => previous ?? list[0]?.id ?? null);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setProjectsError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!projectId) {
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
  }, [projectId, reloadKey]);

  useEffect(() => {
    if (!tableId) {
      return;
    }
    const current = ++seq.current;
    setFilter("");
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
  }, [tableId, reloadKey]);

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

  const retry = () => setReloadKey((key) => key + 1);
  const hasColumnWidths = Object.keys(widths).length > 0;

  const currentProject = projects?.find((project) => project.id === projectId) ?? null;
  const currentTable = tables?.find((table) => table.id === tableId) ?? null;
  const totalRows = tableState.status === "ready" ? tableState.table.rows.length : null;
  const isFiltering = filter.trim().length > 0;

  let content: ReactNode;
  if (projectsError) {
    content = <EmptyState kind="error" message={projectsError} onRetry={retry} />;
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
        <ProjectSwitcher projects={projects} currentId={projectId} onSelect={setProjectId} />

        {tablesError ? (
          <EmptyState kind="error" message={tablesError} onRetry={retry} />
        ) : tables === null ? (
          <div className="state">
            <InlineSkeleton />
          </div>
        ) : tables.length === 0 ? (
          <EmptyState kind="no-tables" />
        ) : (
          <>
            <TableTabs tables={tables} currentId={tableId} onSelect={setTableId} />
            {tableState.status === "loading" ? (
              <TableSkeleton columns={lastFieldCount.current} />
            ) : tableState.status === "error" ? (
              <EmptyState kind="error" message={tableState.message} onRetry={retry} />
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
                  onOpenRelationList={(targetTableId, rowIds) =>
                    setRelationList({ tableId: targetTableId, rowIds })
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
    <main className="app">
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
        {totalRows !== null && totalRows > 0 ? (
          <span className="page-count">
            {isFiltering ? `${filteredRows.length} / ${totalRows} 条` : `共 ${totalRows} 条`}
          </span>
        ) : null}
      </header>
      {content}

      {relationList ? (
        <RelationListModal
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
    </main>
  );
}
