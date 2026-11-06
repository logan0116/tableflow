"""fd_system 模板：表名、列名、类型、顺序的唯一定义。

两个项目（fd_system、tableflow）都用这一份模板，保证结构完全一致。
表 id 与字段 id 是全局主键，按项目前缀生成；列名/类型/顺序/选项不随项目变化。

v0.3.0（002）：
- 依赖变更需求表删除「所属版本」（d-version）：版本管理表是唯一关联挂载点。
- enum 选项带 tone（neutral/info/success/warning/danger），颜色由数据决定。
- number/datetime 显式声明格式，字段可声明 constraints。
- 独立规格需求补齐 speckit-clarify/analyze/checklist 三态与治理字段。
"""

from __future__ import annotations

THREE_STATE = [
    {"value": "todo", "label": "未开始", "tone": "neutral"},
    {"value": "doing", "label": "进行中", "tone": "info"},
    {"value": "done", "label": "完成", "tone": "success"},
]

RELEASE_STATUS = [
    {"value": "released", "label": "已发布", "tone": "success"},
    {"value": "planned", "label": "计划中", "tone": "info"},
    {"value": "dropped", "label": "已废弃", "tone": "neutral"},
]

ACCEPTANCE_STATUS = [
    {"value": "pending", "label": "未验收", "tone": "neutral"},
    {"value": "accepted", "label": "已验收", "tone": "success"},
    {"value": "rejected", "label": "不通过", "tone": "danger"},
]

PRIORITIES = [
    {"value": "P0", "label": "P0", "tone": "danger"},
    {"value": "P1", "label": "P1", "tone": "warning"},
    {"value": "P2", "label": "P2", "tone": "info"},
    {"value": "P3", "label": "P3", "tone": "neutral"},
]


def build_tables(table_prefix: str, field_prefix: str) -> list[dict]:
    """生成三张表的定义。field_prefix 为空时字段 id 形如 v-ver，否则 tf-v-ver。"""

    def tid(key: str) -> str:
        return f"{table_prefix}-{key}"

    def fid(key: str) -> str:
        return f"{field_prefix}-{key}" if field_prefix else key

    return [
        {
            "id": tid("ver"),
            "name": "版本管理",
            "order": 1,
            "fields": [
                (fid("v-ver"), "版本号", "text", {"constraints": {"required": True}}),
                (fid("v-date"), "发布时间", "datetime", {"with_time": False}),
                (fid("v-status"), "发布状态", "enum", RELEASE_STATUS),
                (fid("v-indep"), "需求关联（独立）", "relation", {
                    "table_id": tid("indep"),
                    "constraints": {"relation_must_exist": True},
                }),
                (fid("v-dep"), "需求关联（依赖）", "relation", {
                    "table_id": tid("dep"),
                    "constraints": {"relation_must_exist": True},
                }),
                (fid("v-dev"), "开发进度", "text", None),
                (fid("v-test"), "测试进度", "text", None),
                (fid("v-bug"), "Bug已清空", "text", None),
                (fid("v-doc"), "文档状态", "text", None),
                (fid("v-cond"), "发布条件", "text", None),
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
                (fid("i-clause"), "条款", "text", None),
                (fid("i-dir"), "规格目录", "text", None),
                (fid("i-scenes"), "场景数", "number", {"decimals": 0, "constraints": {"min": 0}}),
                (fid("i-tasks"), "任务总数", "number", {"decimals": 0, "constraints": {"min": 0}}),
                (fid("i-status"), "状态", "text", None),
                (fid("i-constitution"), "speckit-constitution状态", "text", None),
                (fid("i-specify"), "speckit-specify状态", "text", None),
                (fid("i-plan"), "speckit-plan状态", "text", None),
                (fid("i-task"), "speckit-task状态", "text", None),
                (fid("i-implement"), "speckit-implement状态", "text", None),
                (fid("i-clarify"), "speckit-clarify状态", "enum", THREE_STATE),
                (fid("i-analyze"), "speckit-analyze状态", "enum", THREE_STATE),
                (fid("i-checklist"), "speckit-checklist状态", "enum", THREE_STATE),
                (fid("i-constitution-version"), "宪法版本", "text", None),
                (fid("i-acceptance"), "验收状态", "enum", ACCEPTANCE_STATUS),
                (fid("i-owner"), "负责人", "text", None),
                (fid("i-priority"), "优先级", "enum", PRIORITIES),
            ],
        },
        {
            "id": tid("dep"),
            "name": "依赖变更需求",
            "order": 3,
            "fields": [
                (fid("d-id"), "编号", "text", {"constraints": {"required": True}}),
                (fid("d-clause"), "条款", "text", None),
                (fid("d-spec"), "依赖规格", "text", None),
                (fid("d-indep"), "关联的独立规格需求", "relation", {
                    "table_id": tid("indep"),
                    "constraints": {"relation_must_exist": True},
                }),
                (fid("d-impact"), "影响面", "text", None),
                (fid("d-regress"), "回归状态", "text", None),
                (fid("d-status"), "状态", "text", None),
                # v0.3.0：删除「所属版本」（d-version），依赖变更需求表不再挂载反向关联。
            ],
        },
    ]
