#!/usr/bin/env python3
"""把 tableflow 自身的改进需求（TF-01..TF-21）灌进 tf 项目的「独立规格需求」表。

用法：后端跑起来后执行
    backend/.venv/bin/python data/load_backlog.py
"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"
HEADERS = {"X-Agent-Id": "agent-tableflow"}
TABLE = "tf-indep"

# (编号, 名称, 优先级说明)
ITEMS = [
    ("TF-01", "单向关联：版本表为唯一挂载点，依赖需求表删除「所属版本」", "P0 结构"),
    ("TF-02", "行 id 采用业务编号（UD-01 / 7.0.1），关联标签可读", "P0 结构"),
    ("TF-03", "状态类字段全部 enum 化（发布/回归/依赖/speckit 五态）", "P0 结构"),
    ("TF-04", "独立规格需求补齐 speckit-clarify/analyze/checklist 与宪法版本、验收状态、负责人、优先级", "P1 字段"),
    ("TF-05", "依赖变更需求补：依赖类型、触发来源、回归用例数/通过数、阻塞发布、完成判据、负责人", "P1 字段"),
    ("TF-06", "enum 支持状态色（tone 存 options，前端不硬编码业务值）", "P1 字段"),
    ("TF-07", "数字/日期格式：小数位、百分比、单位；日期显式声明仅日期或含时间", "P2 字段"),
    ("TF-08", "字段级约束：必填、取值范围、枚举、关联目标存在性由写接口校验", "P1 字段"),
    ("TF-09", "计算字段类型：count / percent / sum / rollup / and（写侧计算、结果落库）", "P1 计算"),
    ("TF-10", "版本「开发进度」= 关联需求的 speckit-implement 完成比例", "P1 计算"),
    ("TF-11", "版本「Bug已清空」= 数字字段 + 归零判定，允许手工覆盖", "P1 计算"),
    ("TF-12", "「发布条件」= 多条件 AND（实现完成 + 回归通过 + Bug=0 + 文档完成）", "P1 计算"),
    ("TF-13", "计算字段刷新：Agent 写入后重算并落库，重算失败返回 failed", "P1 计算"),
    ("TF-14", "enum 状态色标签（按 tone 显示底色与文字色）", "P2 界面"),
    ("TF-15", "数字列右对齐 + 等宽数字", "P2 界面"),
    ("TF-16", "首列 sticky + 横向滚动阴影", "P2 界面"),
    ("TF-17", "列宽记忆（localStorage 存 UI 偏好，不碰业务数据）", "P2 界面"),
    ("TF-18", "加载骨架与空状态优化（区分空项目/空表/加载中）", "P2 界面"),
    ("TF-19", "行密度两档（紧凑/舒适）+ 斑马纹", "P2 界面"),
    ("TF-20", "人经 Agent 改状态的入口（人只读不变，写操作仍由 Agent 落审计）", "P1 交互"),
    ("TF-21", "业务级变更记录（谁/何时/字段/旧值/新值），区别于技术审计", "P1 治理"),
]


def call(method: str, path: str, body: dict | None = None) -> dict:
    response = httpx.request(method, f"{BASE}{path}", json=body, headers=HEADERS, timeout=10)
    data = response.json()
    if data.get("result") != "success":
        print(f"  ! {method} {path} → {response.status_code} {data}")
    return data


def main() -> int:
    for item_id, name, _priority in ITEMS:
        call("POST", f"/api/agent/tables/{TABLE}/rows", {
            "id": item_id,
            "values": {
                "tf-i-id": item_id,
                "tf-i-clause": name,
                "tf-i-status": "待办",
            },
        })
    print(f"完成：{len(ITEMS)} 条改进需求写入 {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
