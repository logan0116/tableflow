import type { Project } from "../types";

interface ProjectNavProps {
  projects: Project[] | null;
  currentId: string | null;
  onSelect: (projectId: string) => void;
  /** 项目列表读取失败时的原因；成功或加载中时为空。 */
  error?: string | null;
}

/** 左侧竖排项目导航：当前项目带选中态，项目多时由侧栏自身滚动。 */
export function ProjectNav({ projects, currentId, onSelect, error = null }: ProjectNavProps) {
  return (
    <nav className="project-nav" aria-label="项目导航">
      <span className="nav-label">项目</span>
      {projects === null ? (
        <span className="nav-placeholder" title={error ?? undefined}>
          {error ? "项目加载失败" : "加载中…"}
        </span>
      ) : projects.length === 0 ? (
        <span className="nav-placeholder">暂无项目</span>
      ) : (
        projects.map((project) => (
          <button
            key={project.id}
            type="button"
            aria-current={project.id === currentId ? "page" : undefined}
            title={project.name}
            onClick={() => onSelect(project.id)}
          >
            {project.name}
          </button>
        ))
      )}
    </nav>
  );
}
