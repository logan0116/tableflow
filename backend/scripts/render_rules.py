#!/usr/bin/env python3
"""从 `tableflow.rules` 生成规则文档（040）。

引擎里的规则清单是唯一来源，本文档由脚本生成，不允许手改：

    python3 backend/scripts/render_rules.py           # 写入 specs/019-test-contract/rules.md
    python3 backend/scripts/render_rules.py --check   # 只比对，不一致时退出码 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from tableflow.rules import RULES  # noqa: E402

TARGET = REPO_ROOT / "specs" / "019-test-contract" / "rules.md"

HEADER = """# 看板规则清单

本文件由 `backend/scripts/render_rules.py` 从 `backend/src/tableflow/rules.py` 生成，
**不要手改**。新增或修改规则时改代码，再重新生成本文件；`--check` 会把它纳入回归。

契约 YAML 能表达的（字段类型、枚举取值、计算字段）不在这里；这里只收
**契约写不下、必须在写入期或技能流程里判定的规则**。

- `engine`：写入期拦截，任何写入路径都绕不过
- `skill`：只在技能流程里校验

规则号会出现在所有拒绝信息里，照着规则号就能查到含义、判定式与反例。
"""


def render() -> str:
    lines = [HEADER, "", f"共 {len(RULES)} 条。", ""]
    by_since: dict[str, list] = {}
    for rule in RULES:
        by_since.setdefault(rule.since, []).append(rule)
    for since in sorted(by_since):
        lines.append(f"## 需求 {since}")
        lines.append("")
        for rule in by_since[since]:
            lines.append(f"### {rule.id} {rule.title}")
            lines.append("")
            lines.append(f"- **含义**：{rule.meaning}")
            lines.append(f"- **判定式**：`{rule.expr}`")
            lines.append(f"- **实现位置**：`{rule.impl}`")
            lines.append(f"- **反例**：{rule.counterexample}")
            lines.append(f"- **执行方**：{rule.enforced}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只比对，不写")
    args = parser.parse_args()

    text = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != text:
            print(f"[rules] {TARGET} 与规则清单不一致，请重新生成", file=sys.stderr)
            return 1
        print(f"[rules] {TARGET} 与规则清单一致（{len(RULES)} 条）")
        return 0

    TARGET.write_text(text, encoding="utf-8")
    print(f"[rules] 已生成 {TARGET}（{len(RULES)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
