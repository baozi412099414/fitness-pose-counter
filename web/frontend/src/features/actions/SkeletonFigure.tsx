import { LANDMARK_NAMES } from "./humanize";

/**
 * 静态人体骨架示意（MediaPipe Pose 33 点，近似坐标，非真实比例）。
 * 骨骼线统一暗色，关键点分层高亮：
 *   · 计数关键点（counterPoints）→ 荧光绿实心 + 编号
 *   · 质量判定点（rulePoints）→ 青色小点
 * 其余关节点不点亮。
 */

// 33 点近似归一化坐标（x: 0~1 左→右，y: 0~1 上→下，正面站姿）
const XY: Record<number, [number, number]> = {
  0: [0.5, 0.12],
  2: [0.46, 0.11],
  5: [0.54, 0.11],
  7: [0.43, 0.13],
  8: [0.57, 0.13],
  9: [0.48, 0.15],
  10: [0.52, 0.15],
  11: [0.42, 0.30],
  12: [0.58, 0.30],
  13: [0.33, 0.45],
  14: [0.67, 0.45],
  15: [0.26, 0.60],
  16: [0.74, 0.60],
  17: [0.25, 0.62],
  18: [0.75, 0.62],
  19: [0.24, 0.60],
  20: [0.76, 0.60],
  21: [0.23, 0.58],
  22: [0.77, 0.58],
  23: [0.45, 0.52],
  24: [0.55, 0.52],
  25: [0.44, 0.72],
  26: [0.56, 0.72],
  27: [0.43, 0.90],
  28: [0.57, 0.90],
  29: [0.42, 0.93],
  30: [0.58, 0.93],
  31: [0.47, 0.90],
  32: [0.53, 0.90],
};

const BONES: [number, number][] = [
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
  [11, 23],
  [12, 24],
  [23, 24],
  [23, 25],
  [25, 27],
  [24, 26],
  [26, 28],
  [27, 29],
  [28, 30],
  [27, 31],
  [28, 32],
];

const W = 100;
const H = 100;

export interface SkeletonFigureProps {
  counterPoints: number[];
  rulePoints: number[];
  className?: string;
}

function px(x: number) {
  return x * W;
}
function py(y: number) {
  return y * H;
}

export function SkeletonFigure({
  counterPoints,
  rulePoints,
  className,
}: SkeletonFigureProps) {
  const counterSet = new Set(counterPoints);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={className}
      role="img"
      aria-label="人体骨架示意"
    >
      {/* 头 */}
      <circle
        cx={px(0.5)}
        cy={py(0.12)}
        r="7"
        fill="none"
        stroke="rgb(var(--line-2-rgb))"
        strokeWidth="1.5"
      />

      {/* 骨骼线 */}
      {BONES.map(([a, b]) => {
        const pa = XY[a];
        const pb = XY[b];
        if (!pa || !pb) return null;
        return (
          <line
            key={`${a}-${b}`}
            x1={px(pa[0])}
            y1={py(pa[1])}
            x2={px(pb[0])}
            y2={py(pb[1])}
            stroke="rgb(var(--line-1-rgb))"
            strokeWidth="1.5"
          />
        );
      })}

      {/* 质量判定点：青色小点 */}
      {rulePoints.map((i) => {
        const p = XY[i];
        if (!p || counterSet.has(i)) return null;
        return (
          <circle
            key={`r-${i}`}
            cx={px(p[0])}
            cy={py(p[1])}
            r="2.4"
            fill="rgb(var(--cyan-rgb))"
          />
        );
      })}

      {/* 计数关键点：荧光绿实心 + 编号（点多时只显示编号，避免标签互相压住） */}
      {counterPoints.map((i) => {
        const p = XY[i];
        if (!p) return null;
        const isRight = p[0] > 0.5;
        const label =
          counterPoints.length <= 4
            ? `${i} ${LANDMARK_NAMES[i] ?? ""}`.trim()
            : String(i);
        return (
          <g key={`c-${i}`}>
            <circle
              cx={px(p[0])}
              cy={py(p[1])}
              r="4"
              fill="rgb(var(--accent-rgb))"
              stroke="rgb(var(--bg-0-rgb))"
              strokeWidth="1"
            />
            <text
              x={px(p[0]) + (isRight ? -6 : 6)}
              y={py(p[1]) - 4}
              fontSize="7"
              textAnchor={isRight ? "end" : "start"}
              fill="rgb(var(--accent-rgb))"
            >
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}