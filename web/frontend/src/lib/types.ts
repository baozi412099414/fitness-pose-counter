export type CameraSide = "side" | "front";

export interface Action {
  id: string;
  name: string;
  camera_side: CameraSide;
  signal: string;
  rule_count: number;
  thresholds: string;
}

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