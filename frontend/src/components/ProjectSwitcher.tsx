import type { Project } from "../types";

interface ProjectSwitcherProps {
  projects: Project[];
  currentId: string | null;
  onSelect: (projectId: string) => void;
}

export function ProjectSwitcher({ projects, currentId, onSelect }: ProjectSwitcherProps) {
  return (
    <div className="switcher" role="group" aria-label="项目切换">
      {projects.map((project) => (
        <button
          key={project.id}
          type="button"
          aria-pressed={project.id === currentId}
          onClick={() => onSelect(project.id)}
        >
          {project.name}
        </button>
      ))}
    </div>
  );
}
