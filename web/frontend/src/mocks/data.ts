import type { Action, Health, Overview, User } from "@/lib/types";

/**
 * 演示数据。字段与后端 API 契约保持一致，
 * 后续接入真实 /api/* 时，用这里的数据结构做对照即可，不改组件。
 */
export const MOCK_ACTIONS: Action[] = [
  {
    id: "squat",
    name: "深蹲",
    camera_side: "side",
    signal: "左膝角",
    rule_count: 7,
    thresholds: "计数 140°~155°",
  },
  {
    id: "pushup",
    name: "俯卧撑",
    camera_side: "side",
    signal: "左肘角",
    rule_count: 7,
    thresholds: "计数 140°~160°",
  },
  {
    id: "jumping_jack",
    name: "开合跳",
    camera_side: "front",
    signal: "肩角 + 脚距",
    rule_count: 4,
    thresholds: "3 条件 AND",
  },
];

export const MOCK_USERS: User[] = [
  { id: "default", name: "默认用户", initials: "默" },
  { id: "tester", name: "测试用户", initials: "测" },
];

export const MOCK_OVERVIEW: Overview = {
  today_reps: 128,
  yesterday_reps: 96,
  daily_goal_target: 150,
  daily_goal_done: 128,
  last_7_days: [
    { date: "10-19", reps: 0 },
    { date: "10-20", reps: 62 },
    { date: "10-21", reps: 84 },
    { date: "10-22", reps: 0 },
    { date: "10-23", reps: 120 },
    { date: "10-24", reps: 96 },
    { date: "10-25", reps: 128 },
  ],
  weekly_trend: [
    { week_start: "09-01", reps: 180 },
    { week_start: "09-08", reps: 240 },
    { week_start: "09-15", reps: 210 },
    { week_start: "09-22", reps: 360 },
    { week_start: "09-29", reps: 300 },
    { week_start: "10-06", reps: 420 },
    { week_start: "10-13", reps: 390 },
    { week_start: "10-20", reps: 490 },
  ],
  goals: [
    { action_id: "squat", action_name: "深蹲", target: 50, done: 30 },
    { action_id: "pushup", action_name: "俯卧撑", target: 40, done: 40 },
    { action_id: "jumping_jack", action_name: "开合跳", target: 60, done: 58 },
  ],
  top_errors: [
    { tip: "蹲得不够深", count: 12 },
    { tip: "站起时腿没伸直", count: 8 },
    { tip: "双脚张开不足", count: 5 },
  ],
  recent_sessions: [
    { time: "10-25 21:40", action_id: "squat", action_name: "深蹲", reps: 40, score: 86, errors: 3 },
    { time: "10-25 08:12", action_id: "pushup", action_name: "俯卧撑", reps: 32, score: 78, errors: 5 },
    { time: "10-24 21:05", action_id: "jumping_jack", action_name: "开合跳", reps: 56, score: 91, errors: 1 },
    { time: "10-23 21:32", action_id: "squat", action_name: "深蹲", reps: 36, score: 74, errors: 6 },
    { time: "10-21 08:20", action_id: "pushup", action_name: "俯卧撑", reps: 28, score: 69, errors: 8 },
  ],
};

export const MOCK_HEALTH: Health = { ok: true, mode: "mock" };