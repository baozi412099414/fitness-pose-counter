import type {
  Action,
  ActionDetail,
  ActionValidationResult,
  Health,
  Overview,
  User,
} from "@/lib/types";
import {
  signalKindOf,
  signalShortLabel,
  thresholdSummary,
} from "@/features/actions/humanize";

/**
 * 演示数据。字段与后端 API 契约保持一致，
 * 后续接入真实 /api/* 时，用这里的数据结构做对照即可，不改组件。
 *
 * 动作摘要（MOCK_ACTIONS）从详情（MOCK_ACTION_DETAILS）派生，单一数据源。
 */

// ── 动作详情（faithful 镜像 configs/*.json） ──────────────────────
export const MOCK_ACTION_DETAILS: ActionDetail[] = [
  {
    id: "squat",
    name: "深蹲",
    camera_side: "侧",
    calibrate: true,
    counter: {
      signal: "angle",
      points: [23, 25, 27],
      lo: 140,
      hi: 155,
      first: "lo",
      min_interval: 0.4,
      enter_hold: 0.06,
      exit_hold: 0.06,
      min_active_duration: 0.25,
    },
    quality: [
      { name: "not_deep_enough", check: "valley_max", max: 105, when: "on_rep", priority: 70, tip: "蹲得不够深，大腿接近与地面平行", ideal: 90 },
      { name: "right_not_deep_enough", signal: "angle", points: [24, 26, 28], check: "valley_max", max: 105, when: "on_rep", priority: 70, tip: "右腿下蹲幅度不足", ideal: 90 },
      { name: "not_standing_straight", check: "peak_min", min: 160, when: "on_rep", priority: 50, tip: "站起时腿没伸直", ideal: 172 },
      { name: "right_not_standing_straight", signal: "angle", points: [24, 26, 28], check: "peak_min", min: 155, when: "on_rep", priority: 50, tip: "站起时右腿没伸直", ideal: 168 },
      { name: "knee_over_toe", signal: "tilt", points: [25, 27], check: "peak_max", max: 45, ideal: 33, when: "any", priority: 70, confirm_frames: 4, tip: "小腿前倾太多，膝盖明显前移了 —— 试着把髋部向后坐（像坐椅子那样）" },
      { name: "torso_shin_mismatch", signal: "segment_angle_diff", points: [11, 23, 25, 27], check: "peak_max", max: 60, when: "on_rep", priority: 80, tip: "躯干与小腿角度严重失配，动作变形明显", ideal: 40 },
      { name: "torso_lean_excessive", signal: "tilt", points: [23, 11], check: "peak_max", max: 45, when: "on_rep", priority: 80, tip: "上身前倾太多，挺胸并保持核心稳定", ideal: 20 },
    ],
    file_path: "configs/squat.json",
    last_validated_at: null,
    validation: { ok: true, errors: [], warnings: [] },
  },
  {
    id: "pushup",
    name: "俯卧撑",
    camera_side: "侧",
    calibrate: true,
    counter: {
      signal: "angle",
      points: [11, 13, 15],
      lo: 140,
      hi: 160,
      first: "lo",
      min_interval: 0.35,
      enter_hold: 0.06,
      exit_hold: 0.06,
      min_active_duration: 0.25,
    },
    quality: [
      { name: "low_back", check: "collinear", points: [11, 23, 27], min_angle: 160, confirm_frames: 3, priority: 100, tip: "收紧核心，头肩髋踝保持一条直线", ideal: 172 },
      { name: "right_body_line", signal: "angle", points: [12, 24, 28], check: "angle_min", min: 160, confirm_frames: 3, priority: 100, tip: "收紧核心，身体保持一条直线", ideal: 172 },
      { name: "not_low_enough", check: "valley_max", max: 105, when: "on_rep", priority: 80, tip: "下压不够深，胸口再贴近地面", ideal: 88 },
      { name: "right_not_low_enough", signal: "angle", points: [12, 14, 16], check: "valley_max", max: 105, when: "on_rep", priority: 80, tip: "右臂下压不够深", ideal: 88 },
      { name: "arm_not_straight", check: "peak_min", min: 155, when: "on_rep", priority: 60, tip: "撑起时手臂没伸直", ideal: 168 },
      { name: "right_arm_not_straight", signal: "angle", points: [12, 14, 16], check: "peak_min", min: 155, when: "on_rep", priority: 60, tip: "撑起时右臂没伸直", ideal: 168 },
      { name: "arm_asymmetry", signal: "angle_pair_diff", points: [11, 13, 15, 12, 14, 16], check: "peak_max", max: 35, when: "on_rep", priority: 70, tip: "两侧手臂不同步，保持同时下压和撑起", ideal: 8 },
    ],
    file_path: "configs/pushup.json",
    last_validated_at: null,
    validation: { ok: true, errors: [], warnings: [] },
  },
  {
    id: "jumping_jack",
    name: "开合跳",
    camera_side: "正",
    calibrate: false,
    counter: {
      conditions: [
        { signal: "angle", points: [13, 11, 23], direction: "hi", on: 75, off: 45 },
        { signal: "angle", points: [14, 12, 24], direction: "hi", on: 75, off: 45 },
        { signal: "dx", points: [27, 28], unit_points: [11, 12], direction: "hi", on: 0.95, off: 0.75 },
      ],
      min_interval: 0.4,
      enter_hold: 0.06,
      exit_hold: 0.06,
      min_active_duration: 0.2,
    },
    quality: [
      { name: "hand_not_up", check: "peak_min", min: 140, when: "on_rep", priority: 70, tip: "左手再举高一点，举过头顶", ideal: 168 },
      { name: "right_hand_not_up", signal: "angle", points: [14, 12, 24], check: "peak_min", min: 140, when: "on_rep", priority: 70, tip: "右手再举高一点，举过头顶", ideal: 168 },
      { name: "legs_not_apart", signal: "dx", points: [27, 28], unit_points: [11, 12], check: "peak_min", min: 1.2, when: "on_rep", priority: 60, tip: "腿没张开，跳开一点", ideal: 1.9 },
      { name: "arm_asymmetry", signal: "angle_pair_diff", points: [13, 11, 23, 14, 12, 24], check: "peak_max", max: 35, when: "on_rep", priority: 80, tip: "双臂不同步，尽量同时举起", ideal: 8 },
    ],
    file_path: "configs/jumping_jack.json",
    last_validated_at: null,
    validation: { ok: true, errors: [], warnings: [] },
  },
];

/** 详情 → 列表摘要（单一数据源） */
function toSummary(d: ActionDetail): Action {
  return {
    id: d.id,
    name: d.name,
    camera_side: d.camera_side === "正" ? "front" : "side",
    signal: signalShortLabel(d),
    signal_kind: signalKindOf(d),
    rule_count: d.quality.length,
    thresholds: thresholdSummary(d),
    builtin: true,
    validation: {
      ok: d.validation.ok,
      error_count: d.validation.errors.length,
      warning_count: d.validation.warnings.length,
    },
  };
}

export const MOCK_ACTIONS: Action[] = MOCK_ACTION_DETAILS.map(toSummary);

export const MOCK_VALIDATION_RESULTS: ActionValidationResult[] =
  MOCK_ACTION_DETAILS.map((d) => ({
    action_id: d.id,
    action_name: d.name,
    file_path: d.file_path,
    ok: d.validation.ok,
    errors: d.validation.errors,
    warnings: d.validation.warnings,
  }));

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