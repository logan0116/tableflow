import { useEffect, useRef, useState } from "react";

import { fetchProjects, fetchTable, fetchTables } from "./api";
import { DataTable } from "./components/DataTable";
import { ProjectSwitcher } from "./components/ProjectSwitcher";
import { RelationModal } from "./components/RelationModal";
import { TableTabs } from "./components/TableTabs";
import type { Project, TableResponse, TableSummary } from "./types";

type TableState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; table: TableResponse };

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

  const seq = useRef(0);

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

  return (
    <main className="app">
      <h1>只读状态看板</h1>

      {projectsError ? (
        <div className="state">
          <p>读取项目列表失败：{projectsError}</p>
          <button type="button" onClick={retry}>
            重试
          </button>
        </div>
      ) : projects === null ? (
        <div className="state">加载中…</div>
      ) : projects.length === 0 ? (
        <div className="state">暂无项目</div>
      ) : (
        <>
          <ProjectSwitcher projects={projects} currentId={projectId} onSelect={setProjectId} />

          {tablesError ? (
            <div className="state">
              <p>读取表格列表失败：{tablesError}</p>
              <button type="button" onClick={retry}>
                重试
              </button>
            </div>
          ) : tables === null ? (
            <div className="state">加载中…</div>
          ) : tables.length === 0 ? (
            <div className="state">暂无表格</div>
          ) : (
            <>
              <TableTabs tables={tables} currentId={tableId} onSelect={setTableId} />
              {tableState.status === "loading" ? (
                <div className="state">加载中…</div>
              ) : tableState.status === "error" ? (
                <div className="state">
                  <p>读取数据失败：{tableState.message}</p>
                  <button type="button" onClick={retry}>
                    重试
                  </button>
                </div>
              ) : (
                <DataTable
                  fields={tableState.table.fields}
                  rows={tableState.table.rows}
                  onOpenRelation={(targetTableId, rowId) =>
                    setModal({ tableId: targetTableId, rowId })
                  }
                />
              )}
            </>
          )}
        </>
      )}

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
