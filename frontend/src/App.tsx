import { useEffect, useRef, useState } from "react";

import { fetchProjects, fetchTable } from "./api";
import { DataTable } from "./components/DataTable";
import { ProjectSwitcher } from "./components/ProjectSwitcher";
import type { Project, TableResponse } from "./types";

type TableState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; table: TableResponse };

export default function App() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [tableState, setTableState] = useState<TableState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const requestSeq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setProjectsError(null);
    fetchProjects()
      .then((list) => {
        if (cancelled) {
          return;
        }
        setProjects(list);
        setCurrentId((previous) => previous ?? list[0]?.id ?? null);
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
    if (!currentId) {
      return;
    }
    const seq = ++requestSeq.current;
    setTableState({ status: "loading" });
    fetchTable(currentId)
      .then((table) => {
        if (seq === requestSeq.current) {
          setTableState({ status: "ready", table });
        }
      })
      .catch((error: Error) => {
        if (seq === requestSeq.current) {
          setTableState({ status: "error", message: error.message });
        }
      });
  }, [currentId, reloadKey]);

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
          <ProjectSwitcher
            projects={projects}
            currentId={currentId}
            onSelect={setCurrentId}
          />
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
            <DataTable fields={tableState.table.fields} rows={tableState.table.rows} />
          )}
        </>
      )}
    </main>
  );
}
