#!/usr/bin/env python3
"""核对 styles.css 的结构色对比度是否满足 005-ui-visual 的 SC-001。

用法：python3 scripts/contrast_check.py [styles.css 路径]
退出码：0 全部达标；1 有未达标项。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_CSS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "styles.css"

# (变量名, 中文名, 最低对比度)
TARGETS = [
    ("--color-border", "容器边框", 1.50),
    ("--color-border-soft", "行分隔线", 1.25),
    ("--color-header", "表头带", 1.12),
    ("--color-hover", "悬停底", 1.15),
    ("--color-zebra", "斑马纹", 1.04),
]

WHITE = "#ffffff"


def relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"只支持 #rrggbb：{hex_color}")
    channels = []
    for i in (0, 2, 4):
        c = int(value[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def read_variables(css_path: Path) -> dict[str, str]:
    text = css_path.read_text(encoding="utf-8")
    return {
        name: value
        for name, value in re.findall(r"(--color-[a-z-]+)\s*:\s*(#[0-9a-fA-F]{6})", text)
    }


def main() -> int:
    css_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSS
    if not css_path.exists():
        print(f"找不到样式文件：{css_path}")
        return 1

    variables = read_variables(css_path)
    failures = 0
    print(f"样式文件：{css_path}")
    for name, label, minimum in TARGETS:
        color = variables.get(name)
        if color is None:
            print(f"  [缺失] {label:6s} {name} 未定义")
            failures += 1
            continue
        ratio = contrast_ratio(color, WHITE)
        ok = ratio >= minimum
        print(
            f"  [{'OK' if ok else 'FAIL'}] {label:6s} {name}={color} "
            f"对白底 {ratio:.3f}:1（要求 ≥{minimum:.2f}）"
        )
        if not ok:
            failures += 1

    print("结论：" + ("全部达标" if failures == 0 else f"{failures} 项未达标"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
