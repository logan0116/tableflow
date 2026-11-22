import type { TableSummary } from "./types";

/**
 * 角色视图（022）：角色只决定「表导航显示哪些表」和「用哪套角色色」，
 * 不是权限边界——人侧仍是只读 GET，隐藏的表仍可经 relation 弹层读取。
 */
export type RoleId = "systems" | "dev" | "test" | "all";

/** board@4 的表语义键，来自契约的 `<前缀>-ver|indep|dep|case|run|bug`。 */
export type TableSemanticKey = "ver" | "indep" | "dep" | "case" | "run" | "bug";

export interface RoleDefinition {
  id: RoleId;
  label: string;
  /** null 表示不按角色过滤（全局）。 */
  tables: readonly TableSemanticKey[] | null;
}

/**
 * 四角色与可见表：
 * - 系统工程：版本、独立规格需求、依赖变更需求（版本需求设计节点所需的范围）
 * - 软件开发：再加缺陷（开发修复与回归的工作面）
 * - 软件测试：版本、测试用例、依赖变更需求、缺陷（回归结论 change.regress 归测试域，证据来自测试执行）
 * - 全局：不过滤
 */
export const ROLES: readonly RoleDefinition[] = [
  { id: "systems", label: "系统工程", tables: ["ver", "indep", "dep"] },
  { id: "dev", label: "软件开发", tables: ["ver", "indep", "dep", "bug"] },
  { id: "test", label: "软件测试", tables: ["ver", "case", "dep", "bug"] },
  { id: "all", label: "全局", tables: null },
];

export const DEFAULT_ROLE: RoleId = "all";

const ROLE_IDS = new Set<string>(ROLES.map((role) => role.id));

export function isRoleId(value: unknown): value is RoleId {
  return typeof value === "string" && ROLE_IDS.has(value);
}

export function roleDefinition(role: RoleId): RoleDefinition {
  return ROLES.find((item) => item.id === role) ?? ROLES[ROLES.length - 1];
}

/**
 * 从表 id 取契约语义键（`<前缀>-ver` 等）。取不到（自定义表）返回 null，
 * 这类表对所有角色保留，避免角色过滤把不属于六表合同的表静默吞掉。
 */
export function tableSemanticKey(tableId: string): TableSemanticKey | null {
  const match = /-(ver|indep|dep|case|run|bug)$/.exec(tableId);
  return match ? (match[1] as TableSemanticKey) : null;
}

/**
 * 当前角色可见的表：按角色声明里的语义键顺序输出，未知语义键的表追加在后。
 * 顺序只影响导航排列（例如测试角色把「测试用例」排在「依赖变更需求」前），
 * 不改变接口返回或表内容。
 */
export function visibleTablesForRole(
  tables: TableSummary[],
  role: RoleId,
): TableSummary[] {
  const definition = roleDefinition(role);
  if (!definition.tables) {
    return tables;
  }
  const byKey = new Map<TableSemanticKey, TableSummary[]>();
  const unknown: TableSummary[] = [];
  for (const table of tables) {
    const key = tableSemanticKey(table.id);
    if (key === null) {
      unknown.push(table);
      continue;
    }
    const bucket = byKey.get(key);
    if (bucket) {
      bucket.push(table);
    } else {
      byKey.set(key, [table]);
    }
  }
  const visible: TableSummary[] = [];
  for (const key of definition.tables) {
    const bucket = byKey.get(key);
    if (bucket) {
      visible.push(...bucket);
    }
  }
  visible.push(...unknown);
  return visible;
}

/** 角色切换或项目加载后的默认表：当前角色可见表里的第一张。 */
export function firstVisibleTableId(
  tables: TableSummary[],
  role: RoleId,
): string | null {
  return visibleTablesForRole(tables, role)[0]?.id ?? null;
}
