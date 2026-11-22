"""demo 模板：表名、列名、类型、顺序的唯一定义。

board@4（019）：六张表（ver / indep / dep / case / run / bug），不设测试计划表。
表 id 与字段 id 是全局主键，按项目前缀生成；列名/类型/顺序/选项不随项目变化。
`build_tables` 的产物必须能通过 `backend/scripts/check_board.py --template`（差异 0）。

board@4 相对 board@3：
- 版本表 15 → 26 字段：六个四态节点、`六节点是否全部完成`、`测试用例`（→run）、
  用例总数/已完成用例数/用例是否完成；两个 Bug 字段改名；发布条件从第 3 位移到第 10 位。
- 闸门从 4 个降到 2 个：只剩 `六节点是否全部完成`、`发布条件`；三个展示布尔不再打 gate。
- 新增 case（8 字段，board，用例是规格场景的派生投影）与 run（9 字段，detail，
  用例执行情况，不进表导航，只经版本行 relation 弹层展示）。
- 关系链：ver→indep/dep/bug/run、run→case、case→indep、dep→indep、bug→indep；
  relation 一律带 display_field，按目标角色的完成判据带 status_field（指向 case 的关系不给）。
"""


from __future__ import annotations

THREE_STATE = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
]

FOUR_STATE = THREE_STATE + [{"value": "na", "label": "不适用", "tone": "neutral"}]

# board@4 六节点四态：没有 na；failed 不是终态，返工后改回 doing。
VERSION_STAGE = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
    {"value": "failed", "label": "失败", "tone": "danger"},
]

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

RUN_STATE = [
    {"value": "todo", "label": "待执行", "tone": "neutral"},
    {"value": "done", "label": "已执行", "tone": "success"},
]

RUN_RESULT = [
    {"value": "pass", "label": "通过", "tone": "success"},
    {"value": "fail", "label": "失败", "tone": "danger"},
    {"value": "blocked", "label": "阻塞", "tone": "warning"},
    {"value": "skip", "label": "跳过", "tone": "info"},
]

CASE_PRIORITY = [
    {"value": "P0", "label": "高", "tone": "danger"},
    {"value": "P1", "label": "中", "tone": "warning"},
    {"value": "P2", "label": "低", "tone": "neutral"},
]

YES_NO = {"true_label": "是", "false_label": "否"}


def build_tables(table_prefix: str, field_prefix: str) -> list[dict]:
    """生成六张表的定义。field_prefix 为空时字段 id 形如 v-ver，否则 tf-v-ver。"""

    def tid(key: str) -> str:
        return f"{table_prefix}-{key}"

    def fid(key: str) -> str:
        return f"{field_prefix}-{key}" if field_prefix else key

    # 关联弹层：第二列是目标表可读文本列，第三列是目标表完成判据（case 无完成判据）。
    relation_columns = {
        "indep": (fid("i-clause"), fid("i-acceptance")),
        "dep": (fid("d-clause"), fid("d-regress")),
        "bug": (fid("b-title"), fid("b-status")),
        "case": (fid("c-name"), None),
        "run": (fid("r-case_no"), fid("r-state")),
    }

    def rel(target: str, *, required: bool = False) -> dict:
        display, status = relation_columns[target]
        options: dict = {
            "table_id": tid(target),
            "display_field": display,
            "constraints": {"relation_must_exist": True},
        }
        if required:
            options["constraints"]["required"] = True
        if status is not None:
            options["status_field"] = status
        return options

    stage_fields = [
        (fid("v-stage-plan"), "版本需求设计"),
        (fid("v-stage-test-design"), "测试设计"),
        (fid("v-stage-dev"), "开发"),
        (fid("v-stage-dev-accept"), "开发验收"),
        (fid("v-stage-test"), "测试"),
        (fid("v-stage-test-accept"), "测试验收"),
    ]

    return [
        {
            "id": tid("ver"),
            "name": "版本管理",
            "order": 1,
            "kind": "board",
            "fields": [
                (fid("v-ver"), "版本号", "text", {"constraints": {"required": True}}),
                (fid("v-date"), "发布时间", "datetime", {"with_time": False}),
                *[
                    (field_id, name, "enum", {"items": VERSION_STAGE, "constraints": {"required": True}})
                    for field_id, name in stage_fields
                ],
                (fid("v-stage-done"), "六节点是否全部完成", "computed", {
                    "kind": "and",
                    "conditions": [
                        {"field_id": field_id, "equals": "done"}
                        for field_id, _ in stage_fields
                    ],
                    "gate": True,
                    **YES_NO,
                }),
                (fid("v-cond"), "发布条件", "computed", {
                    "kind": "and",
                    "conditions": [
                        {"field_id": fid("v-stage-done"), "equals": True},
                    ],
                    "gate": True,
                    **YES_NO,
                }),
                (fid("v-status"), "发布状态", "enum", {
                    "items": RELEASE_STATUS, "constraints": {"required": True}}),
                (fid("v-indep"), "独立需求管理", "relation", rel("indep")),
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
                    **YES_NO,
                }),
                (fid("v-dep"), "依赖需求管理", "relation", rel("dep")),
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
                    **YES_NO,
                }),
                (fid("v-runs"), "测试用例", "relation", rel("run")),
                (fid("v-case-total"), "用例总数", "computed", {
                    "kind": "count",
                    "source": fid("v-runs"),
                }),
                (fid("v-case-done-count"), "已完成用例数", "computed", {
                    "kind": "count",
                    "source": fid("v-runs"),
                    "where": {"field_id": fid("r-state"), "equals": "done"},
                }),
                (fid("v-case-done"), "用例是否完成", "computed", {
                    "kind": "rollup",
                    "source": fid("v-runs"),
                    "field_id": fid("r-state"),
                    "aggregate": "all",
                    "equals": "done",
                    **YES_NO,
                }),
                (fid("v-bug"), "Bug管理", "relation", rel("bug")),
                (fid("v-bug-ratio"), "Bug已修复/总数", "computed", {
                    "kind": "ratio",
                    "source": fid("v-bug"),
                    "where": {"field_id": fid("b-status"), "equals": "closed"},
                }),
                (fid("v-bug-clear"), "Bug是否清空", "computed", {
                    "kind": "rollup",
                    "source": fid("v-bug"),
                    "field_id": fid("b-status"),
                    "aggregate": "all",
                    "equals": "closed",
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
            "kind": "board",
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
            "kind": "board",
            "fields": [
                (fid("d-id"), "编号", "text", {"constraints": {"required": True}}),
                (fid("d-clause"), "条款", "text", {"constraints": {"required": True}}),
                (fid("d-indep"), "关联的独立规格需求", "relation", rel("indep", required=True)),
                (fid("d-impact"), "影响面", "text", {"constraints": {"required": True}}),
                (fid("d-regress"), "回归状态", "enum", {
                    "items": REGRESS_STATUS, "constraints": {"required": True}}),
                (fid("d-evidence"), "证据", "text", None),
                (fid("d-rest"), "剩余事项", "text", None),
                (fid("d-spec-revision"), "规格修订", "enum", {"items": SPEC_REVISION}),
                (fid("d-owner"), "负责人", "text", None),
            ],
        },
        {
            "id": tid("case"),
            "name": "测试用例",
            "order": 4,
            "kind": "board",
            "fields": [
                (fid("c-id"), "用例号", "text", {"constraints": {"required": True}}),
                (fid("c-name"), "用例名", "text", {"constraints": {"required": True}}),
                (fid("c-indep"), "来源规格", "relation", rel("indep", required=True)),
                (fid("c-precondition"), "前置条件", "text", None),
                (fid("c-steps"), "操作步骤", "text", None),
                (fid("c-expect"), "预期结果", "text", None),
                (fid("c-priority"), "优先级", "enum", {"items": CASE_PRIORITY}),
                (fid("c-owner"), "负责人", "text", None),
            ],
        },
        {
            "id": tid("run"),
            "name": "用例执行情况",
            "order": 5,
            "kind": "detail",
            "fields": [
                (fid("r-id"), "执行编号", "text", {"constraints": {"required": True}}),
                (fid("r-case_no"), "用例号", "text", {"constraints": {"required": True}}),
                (fid("r-case"), "用例", "relation", rel("case", required=True)),
                (fid("r-state"), "执行状态", "enum", {
                    "items": RUN_STATE, "constraints": {"required": True}}),
                (fid("r-result"), "执行结果", "enum", {"items": RUN_RESULT}),
                (fid("r-evidence"), "证据", "text", None),
                (fid("r-executed_at"), "执行时间", "datetime", {"with_time": True}),
                (fid("r-executor"), "执行人", "text", None),
                (fid("r-note"), "备注", "text", None),
            ],
        },
        {
            "id": tid("bug"),
            "name": "缺陷",
            "order": 6,
            "kind": "board",
            "fields": [
                (fid("b-id"), "编号", "text", {"constraints": {"required": True}}),
                (fid("b-title"), "标题", "text", {"constraints": {"required": True}}),
                (fid("b-status"), "状态", "enum", {
                    "items": BUG_STATUS, "constraints": {"required": True}}),
                (fid("b-severity"), "严重度", "enum", {
                    "items": BUG_SEVERITY, "constraints": {"required": True}}),
                (fid("b-source"), "来源", "enum", {
                    "items": BUG_SOURCE, "constraints": {"required": True}}),
                (fid("b-indep"), "关联规格", "relation", rel("indep")),
                (fid("b-found-ver"), "发现版本号", "text", None),
                (fid("b-evidence"), "证据", "text", None),
                (fid("b-rest"), "剩余事项", "text", None),
                (fid("b-ms"), "MS用例号", "text", None),
                (fid("b-owner"), "负责人", "text", None),
            ],
        },
    ]
