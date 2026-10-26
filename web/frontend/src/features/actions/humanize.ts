import type {
  ActionDetail,
  CounterCondition,
  CounterSpec,
  QualityRule,
  WhenValue,
} from "@/lib/types";

/**
 * 把 backend 的内部字段名翻译成人话。
 * 这些映射来自 action_editor.py（SIGNALS / CHECKS / WHENS）与
 * validate_config.py（LANDMARK_NAMES / SIGNAL_ARITY），保持一一对应，
 * 避免详情页直接甩 JSON 字段名。
 */

export const LANDMARK_NAMES: Record<number, string> = {
  0: "鼻子",
  2: "左眼",
  5: "右眼",
  7: "左耳",
  8: "右耳",
  9: "嘴左",
  10: "嘴右",
  11: "左肩",
  12: "右肩",
  13: "左肘",
  14: "右肘",
  15: "左腕",
  16: "右腕",
  17: "左手小指",
  18: "右手小指",
  19: "左手食指",
  20: "右手食指",
  21: "左手拇指",
  22: "右手拇指",
  23: "左髋",
  24: "右髋",
  25: "左膝",
  26: "右膝",
  27: "左踝",
  28: "右踝",
  29: "左脚跟",
  30: "右脚跟",
  31: "左脚尖",
  32: "右脚尖",
};

const SIGNALS: Record<string, string> = {
  angle: "关节角度",
  tilt: "倾斜角度",
  tilts: "倾斜角度（带方向）",
  distance: "两点距离",
  dx: "水平距离",
  dxs: "水平距离（分前后）",
  dy: "竖直距离",
  angle_pair_diff: "左右夹角差",
  segment_angle_diff: "线段方向差",
};

const SIGNAL_KIND_SHORT: Record<string, string> = {
  angle: "关节角度",
  tilt: "倾斜",
  tilts: "倾斜",
  distance: "两点距离",
  dx: "水平距离",
  dxs: "水平距离",
  dy: "竖直距离",
  angle_pair_diff: "夹角差",
  segment_angle_diff: "线段差",
};

const DEGREE_SIGNALS = new Set([
  "angle",
  "tilt",
  "tilts",
  "angle_pair_diff",
  "segment_angle_diff",
]);

// 三点组合（顶点在中间，顺序敏感）→ 人话
const ANGLE_PART_NAMES: Record<string, string> = {
  "11,13,15": "左肘角（肩-肘-腕）",
  "12,14,16": "右肘角（肩-肘-腕）",
  "23,25,27": "左膝角（髋-膝-踝）",
  "24,26,28": "右膝角（髋-膝-踝）",
  "13,11,23": "左肩角（肘-肩-髋）",
  "14,12,24": "右肩角（肘-肩-髋）",
  "11,23,25": "左髋角（肩-髋-膝）",
  "12,24,26": "右髋角（肩-髋-膝）",
  "25,27,31": "左踝角（膝-踝-趾）",
  "26,28,32": "右踝角（膝-踝-趾）",
};

// 两点组合（顺序不敏感，按数值排序做 key）→ 人话
const PAIR_PART_NAMES: Record<string, string> = {
  "11,12": "左右肩（肩宽）",
  "23,24": "左右髋（髋宽）",
  "25,26": "左右膝（膝距）",
  "27,28": "左右脚踝（脚距）",
  "25,27": "左小腿（膝-踝）",
  "27,31": "左脚掌（踝-尖）",
  "11,23": "左躯干（肩-髋）",
  "23,25": "左大腿（髋-膝）",
  "11,13": "左上臂（肩-肘）",
  "13,15": "左前臂（肘-腕）",
  "11,15": "左腕-左肩",
  "12,16": "右腕-右肩",
  "23,27": "左腿全长（髋-踝）",
};

// 距离类信号的「通用」名（不带左右），用于多条件合并摘要
const PAIR_GENERIC: Record<string, string> = {
  "11,12": "肩宽",
  "23,24": "髋宽",
  "25,26": "膝距",
  "27,28": "脚距",
  "11,15": "腕肩距",
  "12,16": "腕肩距",
};

const keyOf = (points: number[]) => points.join(",");
const sortedKeyOf = (points: number[]) => [...points].sort((a, b) => a - b).join(",");

export function signalLabel(signal: string): string {
  return SIGNALS[signal] ?? signal;
}

export function signalKindLabel(signal?: string): string {
  return (signal && SIGNAL_KIND_SHORT[signal]) || "信号";
}

/** 单位：角度类 → °，距离类 → ×肩宽（×） */
export function unitOf(signal?: string): string {
  return signal && DEGREE_SIGNALS.has(signal) ? "°" : "×";
}

export function whenLabel(when?: WhenValue | string): string {
  switch (when) {
    case "any":
      return "全程实时";
    case "ready":
      return "准备姿势时";
    case "active":
      return "动作过程中";
    case "on_rep":
      return "做完那一下";
    default:
      return "全程";
  }
}

export function directionLabel(dir?: "lo" | "hi" | string): string {
  return dir === "hi" ? "先变大（举手类）" : "先变小（下蹲类）";
}

export function priorityLabel(priority?: number): string {
  if (priority == null) return "—";
  if (priority >= 80) return "高";
  if (priority >= 60) return "中";
  return "低";
}

function partFull(points: number[]): string | undefined {
  return (
    ANGLE_PART_NAMES[keyOf(points)] ?? PAIR_PART_NAMES[sortedKeyOf(points)]
  );
}

/** 测量部位人话：优先命中的预设名，否则回退「关键点 23/25/27」 */
export function partLabel(points?: number[]): string {
  if (!points || points.length === 0) return "—";
  const hit = partFull(points);
  return hit ?? `关键点 ${points.join("/")}`;
}

/** 简短名（去掉括号），如「左膝角」 */
export function partShortLabel(points?: number[]): string {
  if (!points || points.length === 0) return "—";
  const hit = partFull(points);
  if (hit) return hit.split("（")[0];
  return `关键点${points.join("/")}`;
}

/** 关键点编号 + 中文名，如「23(左髋) · 25(左膝) · 27(左踝)」 */
export function pointsLabel(points?: number[]): string {
  if (!points || points.length === 0) return "—";
  return points
    .map((i) => `${i}(${LANDMARK_NAMES[i] ?? "?"})`)
    .join(" · ");
}

/** 多条件下单条条件的通用名（去左右），如「肩角」「脚距」 */
function multiPartShort(cond: CounterCondition): string {
  const key = sortedKeyOf(cond.points);
  if (DEGREE_SIGNALS.has(cond.signal)) {
    return partShortLabel(cond.points).replace(/^(左|右)/, "");
  }
  return PAIR_GENERIC[key] ?? partShortLabel(cond.points).replace(/^(左|右)/, "");
}

/** 列表卡片 / 快速开始用的简短信号名 */
export function signalShortLabel(d: ActionDetail): string {
  const c = d.counter;
  if (!c.conditions) return partShortLabel(c.points);
  const names = c.conditions.map(multiPartShort);
  return [...new Set(names)].join(" + ");
}

/** 列表卡片的阈值摘要：单信号「140° ↓ · 155° ↑」；多条件「3 条件 AND · 75°/…」 */
export function thresholdSummary(d: ActionDetail): string {
  const c = d.counter;
  if (c.conditions) {
    const parts = c.conditions
      .map((cond) => `${cond.on}${unitOf(cond.signal)}`)
      .filter((v, i, arr) => arr.indexOf(v) === i);
    return `${c.conditions.length} 条件 AND · ${parts.join(" / ")}`;
  }
  const u = unitOf(c.signal);
  const loFirst = c.first !== "hi";
  const enterVal = loFirst ? c.lo : c.hi;
  const countVal = loFirst ? c.hi : c.lo;
  const enterArrow = loFirst ? "↓" : "↑";
  const countArrow = loFirst ? "↑" : "↓";
  return `${enterVal}${u} ${enterArrow} · ${countVal}${u} ${countArrow}`;
}

/** 列表卡片的信号类型标签：多条件 → 「多条件」，否则用信号短名 */
export function signalKindOf(d: ActionDetail): string {
  if (d.counter.conditions) return "多条件";
  return signalKindLabel(d.counter.signal);
}

function measureNoun(signal?: string): string {
  switch (signal) {
    case "angle":
    case "tilt":
    case "tilts":
      return "角度";
    case "angle_pair_diff":
      return "夹角差";
    case "segment_angle_diff":
      return "方向差";
    case "distance":
    case "dx":
    case "dxs":
    case "dy":
      return "距离";
    default:
      return "数值";
  }
}

/**
 * 质量规则判据 → 一句话（如「本轮最小角度 ≤ 105°」）。
 * fallbackSignal：规则自身没写 signal 时，继承计数信号（例如深蹲的
 * not_deep_enough 用的是计数膝角）。不传会导致单位从「°」错成「×」。
 */
export function checkSentence(
  rule: QualityRule,
  fallbackSignal?: string,
): string {
  const sig = rule.signal ?? fallbackSignal;
  const u = unitOf(sig);
  const noun = measureNoun(sig);
  switch (rule.check) {
    case "collinear":
      return `三点共线度 ≥ ${rule.min_angle ?? "—"}°`;
    case "angle_min":
      return `角度 ≥ ${rule.min ?? "—"}${u}`;
    case "angle_max":
      return `角度 ≤ ${rule.max ?? "—"}${u}`;
    case "valley_max":
      return `本轮最小${noun} ≤ ${rule.max ?? "—"}${u}`;
    case "valley_min":
      return `本轮最小${noun} ≥ ${rule.min ?? "—"}${u}`;
    case "peak_max":
      return `本轮最大${noun} ≤ ${rule.max ?? "—"}${u}`;
    case "peak_min":
      return `本轮最大${noun} ≥ ${rule.min ?? "—"}${u}`;
    case "min":
      return `≥ ${rule.min ?? "—"}${u}`;
    case "max":
      return `≤ ${rule.max ?? "—"}${u}`;
    default:
      return rule.check;
  }
}

/** 单信号下：进入阈值 / 计一次阈值，各带方向箭头 */
export function counterThresholds(c: CounterSpec): {
  enter: string;
  count: string;
} {
  if (c.conditions) return { enter: "—", count: "—" };
  const u = unitOf(c.signal);
  const loFirst = c.first !== "hi";
  const enter = loFirst
    ? `${c.lo}${u} ↓`
    : `${c.hi}${u} ↑`;
  const count = loFirst
    ? `${c.hi}${u} ↑`
    : `${c.lo}${u} ↓`;
  return { enter, count };
}

/** 多条件下单条条件的进入阈值 / 计一次阈值 */
export function conditionThresholds(cond: CounterCondition): {
  enter: string;
  count: string;
} {
  const u = unitOf(cond.signal);
  const up = cond.direction === "hi";
  return {
    enter: up ? `${cond.on}${u} ↑` : `${cond.on}${u} ↓`,
    count: up ? `${cond.off}${u} ↓` : `${cond.off}${u} ↑`,
  };
}

// ─────────────────────────────────────────────────────────────
// 新建动作向导：部位目录 / 信号目录 / 阈值量程 / id 生成
// 映射来自 action_editor.py（ANGLE_PARTS / PAIR_PARTS / SIGNALS）
// -------------------------------------------------------------

export interface PartOption {
  label: string;
  points: number[];
  /** 3 = 三点夹角（仅 angle）；2 = 两点（tilt/tilts/distance/dx/dxs/dy） */
  arity: 3 | 2;
}

/** 三点组合：只能量关节角度（order 敏感，中间是顶点） */
export const ANGLE_PARTS: PartOption[] = [
  { label: "左肘角（肩-肘-腕）", points: [11, 13, 15], arity: 3 },
  { label: "右肘角（肩-肘-腕）", points: [12, 14, 16], arity: 3 },
  { label: "左膝角（髋-膝-踝）", points: [23, 25, 27], arity: 3 },
  { label: "右膝角（髋-膝-踝）", points: [24, 26, 28], arity: 3 },
  { label: "左肩角（肘-肩-髋）", points: [13, 11, 23], arity: 3 },
  { label: "右肩角（肘-肩-髋）", points: [14, 12, 24], arity: 3 },
  { label: "左髋角（肩-髋-膝）", points: [11, 23, 25], arity: 3 },
  { label: "右髋角（肩-髋-膝）", points: [12, 24, 26], arity: 3 },
  { label: "左踝角（膝-踝-趾）", points: [25, 27, 31], arity: 3 },
  { label: "右踝角（膝-踝-趾）", points: [26, 28, 32], arity: 3 },
  { label: "躯干-左大腿夹角", points: [11, 23, 25], arity: 3 },
  { label: "躯干-右大腿夹角", points: [12, 24, 26], arity: 3 },
];

/** 两点组合：量距离/水平差/竖直差/倾角（order 对 dxs/tilts 有意义） */
export const PAIR_PARTS: PartOption[] = [
  { label: "左右肩（肩宽）", points: [11, 12], arity: 2 },
  { label: "左右髋（髋宽）", points: [23, 24], arity: 2 },
  { label: "左右膝（膝距）", points: [25, 26], arity: 2 },
  { label: "左右脚踝（脚距）", points: [27, 28], arity: 2 },
  { label: "左脚踝→左膝（小腿）", points: [27, 25], arity: 2 },
  { label: "左脚踝→左脚尖（脚掌）", points: [27, 31], arity: 2 },
  { label: "左肩→左髋（躯干）", points: [11, 23], arity: 2 },
  { label: "左髋→左膝（大腿）", points: [23, 25], arity: 2 },
  { label: "左肩→左肘（上臂）", points: [11, 13], arity: 2 },
  { label: "左肘→左腕（前臂）", points: [13, 15], arity: 2 },
  { label: "左手腕→左肩", points: [15, 11], arity: 2 },
  { label: "右手腕→右肩", points: [16, 12], arity: 2 },
  { label: "左脚踝→左髋（腿全长）", points: [27, 23], arity: 2 },
];

/** 距离类信号：归一化基准（unit_points 默认肩宽） */
export const RATIO_SIGNALS = new Set(["distance", "dx", "dxs", "dy"]);

/** 信号类型：三点只 angle；两点只这几种（按 SIGNALS 顺序给出） */
export const THREE_POINT_SIGNALS = ["angle"];
export const TWO_POINT_SIGNALS = ["tilt", "tilts", "distance", "dx", "dxs", "dy"];

export function signalsForPointCount(n: number): string[] {
  if (n === 3) return THREE_POINT_SIGNALS;
  if (n === 2) return TWO_POINT_SIGNALS;
  return [];
}

export const SIGNAL_HINTS: Record<string, string> = {
  angle: "三点夹角，最稳，优先用",
  tilt: "两点连线偏离竖直方向多少度",
  tilts: "带方向，能分「偏前/偏后」",
  distance: "两点直线距离（按肩宽归一）",
  dx: "两点水平方向差多少",
  dxs: "带符号水平差（分前后）",
  dy: "两点竖直方向差多少",
};

/** 阈值量程：角度 0~180（步长 1），距离 0~3.0（步长 0.05） */
export function thresholdRange(signal: string): {
  min: number;
  max: number;
  step: number;
} {
  return RATIO_SIGNALS.has(signal)
    ? { min: 0, max: 3, step: 0.05 }
    : { min: 0, max: 180, step: 1 };
}

/** 信号默认阈值：角度 120/150、距离 0.8/1.2 */
export function defaultThresholds(signal: string): { lo: number; hi: number } {
  return RATIO_SIGNALS.has(signal)
    ? { lo: 0.8, hi: 1.2 }
    : { lo: 120, hi: 150 };
}

const ID_RE = /^[0-9a-zA-Z_]+$/;

/** id 只允许字母/数字/下划线（镜像 validate_config 的文件名约束） */
export function isValidId(id: string): boolean {
  return ID_RE.test(id);
}

/**
 * 从中文名生成合法 id（镜像 action_editor.slugify_id）：
 * 保留英数、其余并成下划线；纯中文/空/纯数字 → 通用前缀 action，
 * 冲突时按 action_2 / action_3 … 递增。
 */
export function slugifyId(name: string, existing: readonly string[]): string {
  const existingSet = new Set(existing);
  let base = (name || "")
    .trim()
    .replace(/[^0-9a-zA-Z_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  if (!base || /^\d+$/.test(base)) base = "action";
  if (!existingSet.has(base)) return base;
  let i = 2;
  while (existingSet.has(`${base}_${i}`)) i += 1;
  return `${base}_${i}`;
}