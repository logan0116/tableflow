"""fd_system 模板：表名、列名、类型、顺序的唯一定义。

两个项目（fd_system、tableflow）都用这一份模板，保证结构完全一致。
表 id 与字段 id 是全局主键，按项目前缀生成；列名/类型/顺序/选项不随项目变化。
"""

from __future__ import annotations


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
                (fid("v-ver"), "版本号", "text", None),
                (fid("v-date"), "发布时间", "datetime", None),
                (fid("v-status"), "发布状态", "enum", [
                    {"value": "released", "label": "已发布"},
                    {"value": "planned", "label": "计划中"},
                    {"value": "dropped", "label": "已废弃"},
                ]),
                (fid("v-indep"), "需求关联（独立）", "relation", {"table_id": tid("indep")}),
                (fid("v-dep"), "需求关联（依赖）", "relation", {"table_id": tid("dep")}),
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
                (fid("i-id"), "编号", "text", None),
                (fid("i-clause"), "条款", "text", None),
                (fid("i-dir"), "规格目录", "text", None),
                (fid("i-scenes"), "场景数", "number", None),
                (fid("i-tasks"), "任务总数", "number", None),
                (fid("i-status"), "状态", "text", None),
                (fid("i-constitution"), "speckit-constitution状态", "text", None),
                (fid("i-specify"), "speckit-specify状态", "text", None),
                (fid("i-plan"), "speckit-plan状态", "text", None),
                (fid("i-task"), "speckit-task状态", "text", None),
                (fid("i-implement"), "speckit-implement状态", "text", None),
            ],
        },
        {
            "id": tid("dep"),
            "name": "依赖变更需求",
            "order": 3,
            "fields": [
                (fid("d-id"), "编号", "text", None),
                (fid("d-clause"), "条款", "text", None),
                (fid("d-spec"), "依赖规格", "text", None),
                (fid("d-indep"), "关联的独立规格需求", "relation", {"table_id": tid("indep")}),
                (fid("d-impact"), "影响面", "text", None),
                (fid("d-regress"), "回归状态", "text", None),
                (fid("d-status"), "状态", "text", None),
                (fid("d-version"), "所属版本", "relation", {"table_id": tid("ver")}),
            ],
        },
    ]
