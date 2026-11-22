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

/** 版本进度灯组：六个灯，颜色对应四态，悬停给出节点名与状态。 */
export function ProgressLights({ stages, values }: ProgressLightsProps) {
  return (
    <span className="stage-lights" role="img" aria-label="版本进度六节点">
      {stages.map((stage, index) => {
        const raw = values[index];
        const state = typeof raw === "string" ? raw : "todo";
        const tone = STATE_TONE[state] ?? "todo";
        const label = STATE_LABEL[state] ?? state;
        return (
          <span
            key={stage.id}
            className={`stage-light stage-light-${tone}`}
            data-tip={`${stage.name}：${label}`}
            aria-label={`${stage.name}：${label}`}
            tabIndex={0}
          />
        );
      })}
    </span>
  );
}
