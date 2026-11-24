import type { Field } from "./types";

/**
 * 版本表的界面合并分组（026）。
 *
 * 字段按 id 语义后缀识别（如 `-v-indep`、`-stage-plan`），后缀认不出时才回退字段名；
 * 后端改字段显示名不会让进度灯与关联列静默降级。任一组的字段不齐时整表不合并，
 * 退回原始列（宁可多列，不要半合并）。
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
  /** group：单独的「已完成」计数字段 id（用例组的 ratio 不是文本，需要拼）。 */
  doneCountFieldId?: string;
  /** group：是否完成 字段 id。 */
  statusFieldId?: string;
}

const LIGHTS: Array<{ suffix: string; name: string }> = [
  { suffix: "-stage-plan", name: "版本需求设计" },
  { suffix: "-stage-test-design", name: "测试设计" },
  { suffix: "-stage-dev", name: "开发" },
  { suffix: "-stage-dev-accept", name: "开发验收" },
  { suffix: "-stage-test", name: "测试" },
  { suffix: "-stage-test-accept", name: "测试验收" },
];
const LIGHTS_SUM = { suffix: "-stage-done", name: "六节点是否全部完成" };

const GROUPS: Array<{
  key: string;
  header: string;
  fields: Array<{ suffix: string; name: string }>;
  done?: { suffix: string; name: string };
}> = [
  {
    key: "ver-indep",
    header: "独立需求",
    fields: [
      { suffix: "-v-indep", name: "独立需求管理" },
      { suffix: "-v-spec-ratio", name: "独立需求已完成/总数" },
      { suffix: "-v-spec-done", name: "独立需求是否完成" },
    ],
  },
  {
    key: "ver-dep",
    header: "依赖需求",
    fields: [
      { suffix: "-v-dep", name: "依赖需求管理" },
      { suffix: "-v-change-ratio", name: "依赖需求已完成/总数" },
      { suffix: "-v-change-done", name: "依赖需求是否完成" },
    ],
  },
  {
    key: "ver-case",
    header: "测试",
    fields: [
      { suffix: "-v-runs", name: "测试用例" },
      { suffix: "-v-case-total", name: "用例总数" },
      { suffix: "-v-case-done", name: "用例是否完成" },
    ],
    done: { suffix: "-v-case-done-count", name: "已完成用例数" },
  },
  {
    key: "ver-bug",
    header: "Bug",
    fields: [
      { suffix: "-v-bug", name: "Bug管理" },
      { suffix: "-v-bug-ratio", name: "Bug已修复/总数" },
      { suffix: "-v-bug-clear", name: "Bug是否清空" },
    ],
  },
];

function findField(fields: Field[], suffix: string, name: string): Field | undefined {
  return (
    fields.find((field) => field.id.endsWith(suffix)) ??
    fields.find((field) => field.name === name)
  );
}

/**
 * 返回版本表的合并分组；不是版本表或字段不齐时返回 null。
 *
 * 只有六节点齐全且至少一组三列齐全才合并，避免把普通表误伤。
 */
export function versionGroups(fields: Field[]): VersionGroup[] | null {
  const stages = LIGHTS.map((item) => findField(fields, item.suffix, item.name));
  if (stages.some((field) => !field)) {
    return null;
  }
  const sum = findField(fields, LIGHTS_SUM.suffix, LIGHTS_SUM.name);
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
    const [relationDef, ratioDef, statusDef] = definition.fields;
    const relation = findField(fields, relationDef.suffix, relationDef.name);
    const ratio = findField(fields, ratioDef.suffix, ratioDef.name);
    const status = findField(fields, statusDef.suffix, statusDef.name);
    if (!relation || !ratio || !status) {
      continue;
    }
    const ids = [relation.id, ratio.id, status.id];
    if (definition.done) {
      const done = findField(fields, definition.done.suffix, definition.done.name);
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
      ...(definition.done
        ? {
            doneCountFieldId: findField(
              fields,
              definition.done.suffix,
              definition.done.name,
            )?.id,
          }
        : {}),
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
