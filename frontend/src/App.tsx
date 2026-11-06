import { useEffect, useRef, useState, type ReactNode } from "react";

import { fetchProjects, fetchTable, fetchTables } from "./api";
import { DataTable } from "./components/DataTable";
import { EmptyState } from "./components/EmptyState";
import { ProjectSwitcher } from "./components/ProjectSwitcher";
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

  const retry = () => setReloadKey((key) => key + 1);
  const hasColumnWidths = Object.keys(widths).length > 0;

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
                  density={density}
                  onDensityChange={setDensity}
                  onResetColumnWidths={resetWidths}
                  canResetColumnWidths={hasColumnWidths}
                />
                <DataTable
                  key={tableState.table.table.id}
                  tableId={tableState.table.table.id}
                  fields={tableState.table.fields}
                  rows={tableState.table.rows}
                  density={density}
                  columnWidths={widths}
                  onColumnWidthsChange={setWidths}
                  onOpenRelation={(targetTableId, rowId) =>
                    setModal({ tableId: targetTableId, rowId })
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
      <h1>只读状态看板</h1>
      {content}

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
