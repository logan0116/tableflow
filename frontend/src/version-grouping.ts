import type { Field } from "./types";

/**
 * 版本表的界面合并分组（026）。
 *
 * 只按字段名识别，不硬编码项目前缀；任一组的字段不齐时整表不合并，
 * 退回 board@4 的原始列（宁可多列，不要半合并）。
 */
export type VersionGroupKind = "lights" | "group";

export interface VersionGroup {
  key: string;
  header: string;
  kind: VersionGroupKind;
  fieldIds: string[];
  /** lights：六个节点的字段 id（顺序即灯序）。 */
  stageFieldIds?: string[];
  /** group：关联字段 id，用于打开弹层。 */
  relationFieldId?: string;
  /** group：已完成/总数 字段 id。 */
  ratioFieldId?: string;
  /** group：是否完成 字段 id。 */
  statusFieldId?: string;
}

const LIGHTS = ["版本需求设计", "测试设计", "开发", "开发验收", "测试", "测试验收"];
const LIGHTS_SUM = "六节点是否全部完成";

const GROUPS: Array<{ key: string; header: string; names: [string, string, string] }> = [
  { key: "ver-indep", header: "独立需求", names: ["独立需求管理", "独立需求已完成/总数", "独立需求是否完成"] },
  { key: "ver-dep", header: "依赖需求", names: ["依赖需求管理", "依赖需求已完成/总数", "依赖需求是否完成"] },
  { key: "ver-case", header: "测试", names: ["测试用例", "用例总数", "用例是否完成"] },
  { key: "ver-bug", header: "Bug", names: ["Bug管理", "Bug已修复/总数", "Bug是否清空"] },
];

/** 用例组的「已完成」不是 ratio 文本，而是单独的计数字段。 */
const CASE_DONE_NAME = "已完成用例数";

function findByName(fields: Field[], name: string): Field | undefined {
  return fields.find((field) => field.name === name);
}

/**
 * 返回版本表的合并分组；不是版本表或字段不齐时返回 null。
 *
 * 只有六节点齐全且至少一组三列齐全才合并，避免把普通表误伤。
 */
export function versionGroups(fields: Field[]): VersionGroup[] | null {
  const stages = LIGHTS.map((name) => findByName(fields, name));
  if (stages.some((field) => !field)) {
    return null;
  }
  const sum = findByName(fields, LIGHTS_SUM);
  if (!sum) {
    return null;
  }

  const groups: VersionGroup[] = [
    {
      key: "ver-lights",
      header: "版本进度",
      kind: "lights",
      fieldIds: [...stages.map((field) => field!.id), sum.id],
      stageFieldIds: stages.map((field) => field!.id),
    },
  ];

  for (const definition of GROUPS) {
    const relation = findByName(fields, definition.names[0]);
    const ratio = findByName(fields, definition.names[1]);
    const status = findByName(fields, definition.names[2]);
    if (!relation || !ratio || !status) {
      continue;
    }
    const ids = [relation.id, ratio.id, status.id];
    if (definition.key === "ver-case") {
      const done = findByName(fields, CASE_DONE_NAME);
      if (done) {
        ids.push(done.id);
      }
    }
    groups.push({
      key: definition.key,
      header: definition.header,
      kind: "group",
      fieldIds: ids,
      relationFieldId: relation.id,
      ratioFieldId: ratio.id,
      statusFieldId: status.id,
    });
  }

  return groups.length > 1 ? groups : null;
}

/** 某个字段属于哪个分组（用于在列顺序里定位合并列）。 */
export function groupOfField(groups: VersionGroup[], fieldId: string): VersionGroup | null {
  for (const group of groups) {
    if (group.fieldIds.includes(fieldId)) {
      return group;
    }
  }
  return null;
}
