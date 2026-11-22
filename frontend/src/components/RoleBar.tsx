import { roleDefinition, ROLES, type RoleId } from "../roles";

interface RoleBarProps {
  role: RoleId;
  onSelect: (role: RoleId) => void;
}

/**
 * 顶部通栏角色切换（022 方案 C）：角色名常显、四个入口、当前角色实心高亮。
 * 颜色全部由 html[data-role] 上的 CSS 变量驱动，组件只负责选中态。
 */
export function RoleBar({ role, onSelect }: RoleBarProps) {
  const current = roleDefinition(role);

  return (
    <header className="role-bar" aria-label="角色切换">
      <div className="role-bar-current">
        当前角色 <b>{current.label}</b>
      </div>
      <span className="role-bar-hint">以该角色查看</span>
      <div className="role-switch" role="group" aria-label="选择角色">
        {ROLES.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-pressed={item.id === role}
            onClick={() => onSelect(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </header>
  );
}
