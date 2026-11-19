"""fd_system 模板：表名、列名、类型、顺序的唯一定义。

两个项目（fd_system、tableflow）都用这一份模板，保证结构完全一致。
表 id 与字段 id 是全局主键，按项目前缀生成；列名/类型/顺序/选项不随项目变化。

v0.3.0（002）：
- 依赖变更需求表删除「所属版本」（d-version）：版本管理表是唯一关联挂载点。
- enum 选项带 tone（neutral/info/success/warning/danger），颜色由数据决定。
- number/datetime 显式声明格式，字段可声明 constraints。
- 独立规格需求补齐 speckit-clarify/analyze/checklist 三态与治理字段。

v0.6.5（DEP-05-BR）：
- 按 board@3 重写：版本表 15 字段（三比率 + 三布尔 + 发布条件），删掉开发进度/测试进度/
  未清Bug数/Bug已清空/回归通过/文档状态/场景总数/任务总数与旧字段名「需求关联（独立/依赖）」。
- 独立需求表 16 字段：stage 各阶段统一 todo/doing/done/na（implement 无 na 且必填），
  删掉旧的「状态」「优先级」。
- 依赖需求表 9 字段（补 证据/剩余事项/规格修订/负责人，删「依赖规格」「状态」），回归状态无 na。
- 新增缺陷表 11 字段（一行=一个缺陷），关系方向 ver→bug（Bug管理），缺陷的发现版本号是文本。
- relation 一律带 display_field / status_field，状态列指向该表的完成判据字段。
"""


from __future__ import annotations

THREE_STATE = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
]

FOUR_STATE = THREE_STATE + [{"value": "na", "label": "不适用", "tone": "neutral"}]

RELEASE_STATUS = [
    {"value": "planned", "label": "计划中", "tone": "info"},
    {"value": "released", "label": "已发布", "tone": "success"},
    {"value": "dropped", "label": "已废弃", "tone": "neutral"},
]

REGRESS_STATUS = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "passed", "label": "通过", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]

ACCEPTANCE_STATUS = [
    {"value": "pending", "label": "未验收", "tone": "neutral"},
    {"value": "accepted", "label": "已验收", "tone": "success"},
    {"value": "rejected", "label": "不通过", "tone": "danger"},
]

SPEC_REVISION = [
    {"value": "not_needed", "label": "无需修订", "tone": "neutral"},
    {"value": "pending", "label": "待修订", "tone": "warning"},
    {"value": "done", "label": "已修订", "tone": "success"},
]

BUG_STATUS = [
    {"value": "open", "label": "待修", "tone": "danger"},
    {"value": "fixing", "label": "修复中", "tone": "warning"},
    {"value": "verifying", "label": "已修待验", "tone": "info"},
    {"value": "closed", "label": "已关闭", "tone": "success"},
]

BUG_SEVERITY = [
    {"value": "blocker", "label": "阻断", "tone": "danger"},
    {"value": "critical", "label": "严重", "tone": "warning"},
    {"value": "major", "label": "一般", "tone": "info"},
    {"value": "minor", "label": "轻微", "tone": "neutral"},
]

BUG_SOURCE = [
    {"value": "ms_case", "label": "用例执行", "tone": "info"},
    {"value": "manual", "label": "人工确认", "tone": "warning"},
    {"value": "prod", "label": "线上发现", "tone": "danger"},
    {"value": "review", "label": "评审发现", "tone": "neutral"},
]

YES_NO = {"true_label": "是", "false_label": "否"}


def build_tables(table_prefix: str, field_prefix: str) -> list[dict]:
    """生成四张表的定义。field_prefix 为空时字段 id 形如 v-ver，否则 tf-v-ver。"""

    def tid(key: str) -> str:
        return f"{table_prefix}-{key}"

    def fid(key: str) -> str:
        return f"{field_prefix}-{key}" if field_prefix else key

    def rel(key: str, target: str) -> dict:
        return {
            "table_id": tid(target),
            "display_field": fid({"indep": "i", "dep": "d", "bug": "b"}[target] + "-clause")
            if target != "bug"
            else fid("b-title"),
            "status_field": fid(
                {"indep": "i-acceptance", "dep": "d-regress", "bug": "b-status"}[target]
            ),
            "constraints": {"relation_must_exist": True},
        }

    return [
        {
            "id": tid("ver"),
            "name": "版本管理",
            "order": 1,
            "fields": [
                (fid("v-ver"), "版本号", "text", {"constraints": {"required": True}}),
                (fid("v-date"), "发布时间", "datetime", {"with_time": False}),
                (fid("v-cond"), "发布条件", "computed", {
                    "kind": "and",
                    "conditions": [
                        {"field_id": fid("v-spec-done"), "equals": True},
                        {"field_id": fid("v-change-done"), "equals": True},
                        {"field_id": fid("v-bug-clear"), "equals": True},
                    ],
                    "gate": True,
                    **YES_NO,
                }),
                (fid("v-status"), "发布状态", "enum", {
                    "items": RELEASE_STATUS, "constraints": {"required": True}}),
                (fid("v-indep"), "独立需求管理", "relation", rel("v", "indep")),
                (fid("v-spec-ratio"), "独立需求已完成/总数", "computed", {
                    "kind": "ratio",
                    "source": fid("v-indep"),
                    "where": {"field_id": fid("i-acceptance"), "equals": "accepted"},
                }),
                (fid("v-spec-done"), "独立需求是否完成", "computed", {
                    "kind": "rollup",
                    "source": fid("v-indep"),
                    "field_id": fid("i-acceptance"),
                    "aggregate": "all",
                    "equals": "accepted",
                    "gate": True,
                    **YES_NO,
                }),
                (fid("v-dep"), "依赖需求管理", "relation", rel("v", "dep")),
                (fid("v-change-ratio"), "依赖需求已完成/总数", "computed", {
                    "kind": "ratio",
                    "source": fid("v-dep"),
                    "where": {"field_id": fid("d-regress"), "equals": "passed"},
                }),
                (fid("v-change-done"), "依赖需求是否完成", "computed", {
                    "kind": "rollup",
                    "source": fid("v-dep"),
                    "field_id": fid("d-regress"),
                    "aggregate": "all",
                    "equals": "passed",
                    "gate": True,
                    **YES_NO,
                }),
                (fid("v-bug"), "Bug管理", "relation", rel("v", "bug")),
                (fid("v-bug-ratio"), "上一版本Bug已修复/总数", "computed", {
                    "kind": "ratio",
                    "source": fid("v-bug"),
                    "where": {"field_id": fid("b-status"), "equals": "closed"},
                }),
                (fid("v-bug-clear"), "上一版本Bug是否清空", "computed", {
                    "kind": "rollup",
                    "source": fid("v-bug"),
                    "field_id": fid("b-status"),
                    "aggregate": "all",
                    "equals": "closed",
                    "gate": True,
                    **YES_NO,
                }),
                (fid("v-owner"), "负责人", "text", None),
                (fid("v-note"), "变更说明", "text", None),
            ],
        },
        {
            "id": tid("indep"),
            "name": "独立规格需求",
            "order": 2,
            "fields": [
                (fid("i-id"), "编号", "text", {"constraints": {"required": True}}),
                (fid("i-clause"), "条款", "text", {"constraints": {"required": True}}),
                (fid("i-dir"), "规格目录", "text", None),
                (fid("i-scenes"), "场景数", "number", {"decimals": 0, "constraints": {"min": 0}}),
                (fid("i-tasks"), "任务总数", "number", {"decimals": 0, "constraints": {"min": 0}}),
                (fid("i-constitution"), "speckit-constitution状态", "enum", {"items": FOUR_STATE}),
                (fid("i-specify"), "speckit-specify状态", "enum", {"items": FOUR_STATE}),
                (fid("i-plan"), "speckit-plan状态", "enum", {"items": FOUR_STATE}),
                (fid("i-task"), "speckit-task状态", "enum", {"items": FOUR_STATE}),
                (fid("i-implement"), "speckit-implement状态", "enum", {
                    "items": THREE_STATE, "constraints": {"required": True}}),
                (fid("i-clarify"), "speckit-clarify状态", "enum", {"items": FOUR_STATE}),
                (fid("i-analyze"), "speckit-analyze状态", "enum", {"items": FOUR_STATE}),
                (fid("i-checklist"), "speckit-checklist状态", "enum", {"items": FOUR_STATE}),
                (fid("i-constitution-version"), "宪法版本", "text", None),
                (fid("i-acceptance"), "验收状态", "enum", {
                    "items": ACCEPTANCE_STATUS, "constraints": {"required": True}}),
                (fid("i-owner"), "负责人", "text", None),
            ],
        },
        {
            "id": tid("dep"),
            "name": "依赖变更需求",
            "order": 3,
            "fields": [
                (fid("d-id"), "编号", "text", {"constraints": {"required": True}}),
                (fid("d-clause"), "条款", "text", {"constraints": {"required": True}}),
                (fid("d-indep"), "关联的独立规格需求", "relation", rel("d", "indep")),
                (fid("d-impact"), "影响面", "text", None),
                (fid("d-regress"), "回归状态", "enum", {
                    "items": REGRESS_STATUS, "constraints": {"required": True}}),
                (fid("d-evidence"), "证据", "text", None),
                (fid("d-rest"), "剩余事项", "text", None),
                (fid("d-spec-revision"), "规格修订", "enum", {"items": SPEC_REVISION}),
                (fid("d-owner"), "负责人", "text", None),
            ],
        },
        {
            "id": tid("bug"),
            "name": "缺陷",
            "order": 4,
            "fields": [
                (fid("b-id"), "编号", "text", {"constraints": {"required": True}}),
                (fid("b-title"), "标题", "text", {"constraints": {"required": True}}),
                (fid("b-status"), "状态", "enum", {
                    "items": BUG_STATUS, "constraints": {"required": True}}),
                (fid("b-severity"), "严重度", "enum", {
                    "items": BUG_SEVERITY, "constraints": {"required": True}}),
                (fid("b-source"), "来源", "enum", {
                    "items": BUG_SOURCE, "constraints": {"required": True}}),
                (fid("b-indep"), "关联规格", "relation", rel("b", "indep")),
                (fid("b-found-ver"), "发现版本号", "text", None),
                (fid("b-evidence"), "证据", "text", None),
                (fid("b-rest"), "剩余事项", "text", None),
                (fid("b-ms"), "MS用例号", "text", None),
                (fid("b-owner"), "负责人", "text", None),
            ],
        },
    ]
