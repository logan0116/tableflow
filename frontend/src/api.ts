import type { Project, TableResponse } from "./types";

const TIMEOUT_MS = 5000;

async function getJson<T>(url: string): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, { cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(body?.detail ?? `请求失败（${response.status}）`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("请求超时，请重试");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export function fetchProjects(): Promise<Project[]> {
  return getJson<{ projects: Project[] }>("/api/projects").then((data) => data.projects);
}

export function fetchTable(projectId: string): Promise<TableResponse> {
  return getJson<TableResponse>(`/api/projects/${encodeURIComponent(projectId)}/table`);
}
