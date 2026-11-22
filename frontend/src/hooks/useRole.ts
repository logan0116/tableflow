import { useCallback, useState } from "react";

import { isRoleId, type RoleId } from "../roles";
import { readRole, writeRole } from "../ui-prefs";

/** 角色视图：默认全局，选择结果持久化到 localStorage；非法值静默回退。 */
export function useRole(): [RoleId, (role: RoleId) => void] {
  const [role, setRoleState] = useState<RoleId>(() => readRole());

  const setRole = useCallback((next: RoleId) => {
    const value: RoleId = isRoleId(next) ? next : "all";
    setRoleState(value);
    writeRole(value);
  }, []);

  return [role, setRole];
}
