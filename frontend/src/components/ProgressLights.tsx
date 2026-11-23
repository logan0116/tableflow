import { useState } from "react";
import type { Field } from "../types";

interface ProgressLightsProps {
  /** 六个节点字段（顺序即灯序）。 */
  stages: Field[];
  /** 每个节点的当前取值（与 stages 同序）。 */
  values: unknown[];
}

const STATE_LABEL: Record<string, string> = {
  todo: "未开始",
  doing: "进行中",
  done: "已完成",
  failed: "失败",
};

const STATE_TONE: Record<string, string> = {
  todo: "todo",
  doing: "doing",
  done: "done",
  failed: "failed",
};

/**
 * 版本进度灯组：六个灯，颜色对应四态，悬停显示「节点名：状态」。
 *
 * 提示用 fixed 定位渲染在灯组末尾——表格容器是 `overflow: auto`，
 * 用伪元素向上弹会被裁掉一半（v0.7.2 报的缺陷）。fixed 不受容器裁剪。
 */
export function ProgressLights({ stages, values }: ProgressLightsProps) {
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null);

  return (
    <span className="stage-lights" role="img" aria-label="版本进度六节点">
      {stages.map((stage, index) => {
        const raw = values[index];
        const state = typeof raw === "string" ? raw : "todo";
        const tone = STATE_TONE[state] ?? "todo";
        const label = STATE_LABEL[state] ?? state;
        const text = `${stage.name}：${label}`;
        return (
          <span
            key={stage.id}
            className={`stage-light stage-light-${tone}`}
            aria-label={text}
            tabIndex={0}
            onMouseEnter={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              setTip({ text, x: rect.left + rect.width / 2, y: rect.top });
            }}
            onMouseLeave={() => setTip(null)}
            onFocus={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              setTip({ text, x: rect.left + rect.width / 2, y: rect.top });
            }}
            onBlur={() => setTip(null)}
          />
        );
      })}
      {tip ? (
        <span className="stage-tip" style={{ left: tip.x, top: tip.y }} role="tooltip">
          {tip.text}
        </span>
      ) : null}
    </span>
  );
}
