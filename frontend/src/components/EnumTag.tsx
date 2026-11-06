import type { CSSProperties } from "react";

import type { FieldColor, FieldOption, Tone } from "../types";

const TONES: readonly Tone[] = ["neutral", "info", "success", "warning", "danger"];
const TONE_SET = new Set<string>(TONES);

export function normalizeTone(tone: unknown): Tone {
  return typeof tone === "string" && TONE_SET.has(tone) ? (tone as Tone) : "neutral";
}

function safeColor(value: unknown): string | null {
  if (typeof value !== "string" || value.trim() === "") {
    return null;
  }
  try {
    if (typeof CSS !== "undefined" && typeof CSS.supports === "function") {
      return CSS.supports("color", value) ? value : null;
    }
  } catch {
    return null;
  }
  return null;
}

function colorStyle(color: FieldColor | null | undefined): CSSProperties | undefined {
  const bg = safeColor(color?.bg);
  const fg = safeColor(color?.fg);
  if (!bg && !fg) {
    return undefined;
  }
  const style: CSSProperties = {};
  if (bg) {
    style.backgroundColor = bg;
  }
  if (fg) {
    style.color = fg;
  }
  return style;
}

interface EnumTagProps {
  option?: FieldOption | null;
  /** 选项缺失时展示的原值（不报错）。 */
  fallback: string;
}

/** 状态标签：颜色只由数据里的 tone / color 决定，前端不硬编码任何业务值。 */
export function EnumTag({ option, fallback }: EnumTagProps) {
  const tone = normalizeTone(option?.tone);
  return (
    <span
      className={`enum-tag enum-tone-${tone}`}
      style={colorStyle(option?.color)}
      data-tone={tone}
    >
      {option?.label ?? fallback}
    </span>
  );
}
