export type CameraSide = "side" | "front";

// ─────────────────────────────────────────────────────────────
// 动作库：列表摘要（Action） + 详情（ActionDetail）
// ─────────────────────────────────────────────────────────────

/** 列表卡片上的校验状态（只带计数，不带原文） */
export interface ActionValidationStatus {
  ok: boolean;
  error_count: number;
  warning_count: number;
}

export interface Action {
  id: string;
  name: string;
  camera_side: CameraSide;
  /** 简短信号名，如「左膝角」/「肩角 + 脚距」 */
  signal: string;
  /** 信号类型标签：关节角度 / 多条件 */
  signal_kind: string;
  rule_count: number;
  /** 阈值摘要，如「140° ↓ · 155° ↑」 */
  thresholds: string;
  builtin: boolean;
  validation: ActionValidationStatus;
}

export type WhenValue = "any" | "ready" | "active" | "on_rep";

/** 质量规则（faithful 镜像 backend configs/*.json 的 quality[] 项） */
export interface QualityRule {
  name: string;
  check: string;
  signal?: string;
  points?: number[];
  unit_points?: number[];
  min?: number;
  max?: number;
  min_angle?: number;
  on?: number;
  off?: number;
  when?: WhenValue;
  priority?: number;
  tip?: string;
  ideal?: number;
  confirm_frames?: number;
}

/** 多条件 AND 模式下的单条降级条件 */
export interface CounterCondition {
  signal: string;
  points: number[];
  unit_points?: number[];
  direction: "hi" | "lo";
  on: number;
  off: number;
}

/** 计数配置：单信号（signal/points/lo/hi/first）或多条件（conditions[]） */
export interface CounterSpec {
  signal?: string;
  points?: number[];
  lo?: number;
  hi?: number;
  first?: "lo" | "hi";
  conditions?: CounterCondition[];
  min_interval?: number;
  enter_hold?: number;
  exit_hold?: number;
  min_active_duration?: number;
  cycles_per_rep?: number;
}

/** 完整校验结果（错误/警告原文，展示时原样呈现，不改写） */
export interface ActionValidation {
  ok: boolean;
  errors: string[];
  warnings: string[];
}

/** 动作详情：镜像 backend 的一份动作配置 + 前端运行时元信息 */
export interface ActionDetail {
  id: string;
  name: string;
  /** 原始机位：侧 / 正（与 backend 一致） */
  camera_side: string;
  calibrate: boolean;
  counter: CounterSpec;
  quality: QualityRule[];
  /** 前端元信息（不参与「原始 JSON」序列化） */
  file_path: string;
  last_validated_at: string | null;
  validation: ActionValidation;
}

/** 校验全部接口的单文件结果 */
export interface ActionValidationResult {
  action_id: string;
  action_name: string;
  file_path: string;
  ok: boolean;
  errors: string[];
  warnings: string[];
}

// ─────────────────────────────────────────────────────────────
// 其余业务类型（用户 / 健康 / 总览等）
// ─────────────────────────────────────────────────────────────

export interface User {
  id: string;
  name: string;
  initials: string;
}

export interface Health {
  ok: boolean;
  mode: "mock" | "live";
}

export interface DailyGoal {
  action_id: string;
  action_name: string;
  target: number;
  done: number;
}

/** 训练轨道单日方块 */
export interface DayBlock {
  date: string; // YYYY-MM-DD
  reps: number;
}

/** 本周趋势柱状图（周汇总，与日轨道分开） */
export interface WeeklyPoint {
  week_start: string; // YYYY-MM-DD
  reps: number;
}

export interface TopError {
  tip: string;
  count: number;
}

export interface Session {
  time: string;
  action_id: string;
  action_name: string;
  reps: number;
  score: number | null;
  errors: number;
}

export interface Overview {
  today_reps: number;
  yesterday_reps: number;
  daily_goal_target: number | null;
  daily_goal_done: number;
  last_7_days: DayBlock[];
  weekly_trend: WeeklyPoint[];
  goals: DailyGoal[];
  top_errors: TopError[];
  recent_sessions: Session[];
}