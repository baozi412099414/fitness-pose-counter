import type {
  Action,
  ActionDetail,
  ActionValidationResult,
  CounterSpec,
  CreateUserInput,
  DailyGoal,
  Health,
  NewActionDraft,
  Overview,
  QualityRule,
  SaveError,
  SaveResult,
  User,
  UserOpResult,
} from "@/lib/types";
import {
  isValidId,
  RATIO_SIGNALS,
  signalKindOf,
  signalShortLabel,
  thresholdSummary,
} from "@/features/actions/humanize";

/**
 * 演示数据。字段与后端 API 契约保持一致，
 * 后续接入真实 /api/* 时，用这里的数据结构做对照即可，不改组件。
 *
 * 动作摘要（getActionSummaries()）从详情（MOCK_ACTION_DETAILS）派生，单一数据源。
 */

// ── 动作详情（faithful 镜像 configs/*.json） ──────────────────────
export const MOCK_ACTION_DETAILS: ActionDetail[] = [
  {
    id: "squat",
    name: "深蹲",
    camera_side: "侧",
    calibrate: true,
    builtin: true,
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
    builtin: true,
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
    builtin: true,
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
    builtin: d.builtin,
    validation: {
      ok: d.validation.ok,
      error_count: d.validation.errors.length,
      warning_count: d.validation.warnings.length,
    },
  };
}

/** 摘要随 store 实时派生（新建动作后 op 到最新列表） */
export function getActionSummaries(): Action[] {
  return MOCK_ACTION_DETAILS.map(toSummary);
}

export function getValidationResults(): ActionValidationResult[] {
  return MOCK_ACTION_DETAILS.map((d) => ({
    action_id: d.id,
    action_name: d.name,
    file_path: d.file_path,
    ok: d.validation.ok,
    errors: d.validation.errors,
    warnings: d.validation.warnings,
  }));
}

// ─────────────────────────────────────────────────────────────
// 新建动作（mock「后端」）：镜像 action_editor.build_action_config +
// validate_config 的一致性检查。本轮不落盘 configs/*.json。
// ─────────────────────────────────────────────────────────────

function buildCounter(draft: NewActionDraft): CounterSpec {
  const counter: CounterSpec = {
    signal: draft.signal,
    points: draft.points,
    lo: draft.lo,
    hi: draft.hi,
    first: draft.first,
    enter_hold: draft.enter_hold,
    exit_hold: draft.exit_hold,
    min_active_duration: draft.min_active_duration,
    min_interval: draft.min_interval,
    cycles_per_rep: draft.cycles_per_rep,
  };
  // 距离类信号必须有归一化基准，默认肩宽
  if (RATIO_SIGNALS.has(draft.signal)) counter.unit_points = [11, 12];
  return counter;
}

function buildQuality(draft: NewActionDraft): QualityRule[] {
  const rules: QualityRule[] = [];
  const firstLo = draft.first === "lo";
  if (draft.depth.enabled) {
    rules.push({
      name: "not_enough_range",
      check: firstLo ? "valley_max" : "peak_min",
      ...(firstLo
        ? { max: draft.depth.threshold }
        : { min: draft.depth.threshold }),
      when: "on_rep",
      priority: draft.depth.priority,
      tip: draft.depth.tip,
    });
  }
  if (draft.straight.enabled) {
    rules.push({
      name: "not_returned",
      check: firstLo ? "peak_min" : "valley_max",
      ...(firstLo
        ? { min: draft.straight.threshold }
        : { max: draft.straight.threshold }),
      when: "on_rep",
      priority: draft.straight.priority,
      tip: draft.straight.tip,
    });
  }
  return rules;
}

/** 一致性校验（镜像 validate_config 的核心约束 + 幅度方向一致性） */
function validateDraft(draft: NewActionDraft, existing: Set<string>): SaveError[] {
  const errors: SaveError[] = [];
  if (!draft.name.trim()) {
    errors.push({ field: "name", message: "动作名称不能为空" });
  }
  if (!isValidId(draft.id)) {
    errors.push({ field: "id", message: "ID 只能包含字母、数字、下划线" });
  } else if (existing.has(draft.id)) {
    errors.push({ field: "id", message: `ID「${draft.id}」已存在，请换一个` });
  }

  if (draft.points.length === 3 && draft.signal !== "angle") {
    errors.push({ field: "signal", message: "三点部位只能用「关节角度」信号" });
  } else if (draft.points.length === 2 && draft.signal === "angle") {
    errors.push({ field: "signal", message: "两点部位不能选「关节角度」信号" });
  }
  if (draft.lo >= draft.hi) {
    errors.push({
      field: "signal.lo",
      message: `lo(${draft.lo}) 必须小于 hi(${draft.hi})，否则迟滞区不成立`,
    });
  }

  // 幅度/回位阈值方向一致性：进入值越「深」，回位值越「回到起始」。
  // 先变小（first=lo）：幅度必须 ≤ 进入(lo)；先变大（first=hi）：幅度必须 ≥ 进入(hi)。
  const firstLo = draft.first === "lo";
  if (draft.depth.enabled) {
    const bad = firstLo
      ? draft.depth.threshold > draft.lo
      : draft.depth.threshold < draft.hi;
    if (bad) {
      errors.push({
        field: "quality.0.threshold",
        message: firstLo
          ? `「幅度不够」阈值(${draft.depth.threshold}) 必须 ≤ 进入阈值(${draft.lo})，否则永远不触发`
          : `「幅度不够」阈值(${draft.depth.threshold}) 必须 ≥ 进入阈值(${draft.hi})，否则永远不触发`,
      });
    }
  }
  if (draft.straight.enabled) {
    const bad = firstLo
      ? draft.straight.threshold < draft.hi
      : draft.straight.threshold > draft.lo;
    if (bad) {
      errors.push({
        field: "quality.1.threshold",
        message: firstLo
          ? `「没回到起始」阈值(${draft.straight.threshold}) 必须 ≥ 计一次阈值(${draft.hi})，否则永远不触发`
          : `「没回到起始」阈值(${draft.straight.threshold}) 必须 ≤ 计一次阈值(${draft.lo})，否则永远不触发`,
      });
    }
  }
  return errors;
}

export function createAction(draft: NewActionDraft): SaveResult {
  const existing = new Set(MOCK_ACTION_DETAILS.map((d) => d.id));
  const errors = validateDraft(draft, existing);
  if (errors.length > 0) {
    return { ok: false, errors, warnings: [] };
  }

  const warnings: string[] = [];
  if (
    [31, 32].some((p) => draft.points.includes(p)) &&
    !["侧", "侧面"].includes(draft.camera_side)
  ) {
    warnings.push("用到了脚尖关键点（31/32），建议机位设为侧面");
  }

  const detail: ActionDetail = {
    id: draft.id,
    name: draft.name,
    camera_side: draft.camera_side,
    calibrate: draft.calibrate,
    builtin: false,
    counter: buildCounter(draft),
    quality: buildQuality(draft),
    file_path: `configs/${draft.id}.json`,
    last_validated_at: null,
    validation: { ok: true, errors: [], warnings },
  };
  // 本轮 mock：不写 configs/*.json，直接进内存 store，列表/详情立即可见
  MOCK_ACTION_DETAILS.push(detail);
  return { ok: true, errors: [], warnings, detail };
}

// ─────────────────────────────────────────────────────────────
// 用户（可变 store）：新建用户仅本次会话有效，刷新后回到初始快照。
// ─────────────────────────────────────────────────────────────

export const MOCK_USERS: User[] = [
  {
    id: "default",
    name: "默认用户",
    initials: "默",
    created_at: "2026-09-01",
    height: 176,
    weight: 68,
    total_sessions: 128,
    today_sessions: 42,
    badge: "坚持之星",
  },
  {
    id: "tester",
    name: "测试用户",
    initials: "测",
    created_at: "2026-10-18",
    height: null,
    weight: null,
    total_sessions: 0,
    today_sessions: 0,
    badge: null,
  },
];

function generateUserId(name: string): string {
  const existing = new Set(MOCK_USERS.map((u) => u.id));
  // ASCII 且非纯数字可直接作为 id；否则退化为带时间戳的 user_ 前缀
  const base =
    /^[0-9a-zA-Z_]+$/.test(name) && !/^\d+$/.test(name)
      ? name
      : `user_${Date.now().toString(36)}${Math.floor(Math.random() * 36).toString(36)}`;
  if (!existing.has(base)) return base;
  let i = 2;
  while (existing.has(`${base}_${i}`)) i += 1;
  return `${base}_${i}`;
}

/** 每次返回新数组引用，保证 React Query invalidate 后能重渲染 */
export function getUsersSnapshot(): User[] {
  return [...MOCK_USERS];
}

export function createUser(input: CreateUserInput): UserOpResult {
  const name = input.name.trim();
  if (!name) {
    return { ok: false, errors: [{ field: "name", message: "用户名不能为空" }] };
  }
  if (MOCK_USERS.some((u) => u.name === name)) {
    return {
      ok: false,
      errors: [{ field: "name", message: `用户名「${name}」已存在` }],
    };
  }
  const user: User = {
    id: generateUserId(name),
    name,
    initials: name[0] ?? "?",
    created_at: new Date().toISOString().slice(0, 10),
    height: input.height ?? null,
    weight: input.weight ?? null,
    total_sessions: 0,
    today_sessions: 0,
    badge: null,
  };
  MOCK_USERS.push(user);
  return { ok: true, errors: [], user };
}

export function deleteUser(id: string): { ok: boolean; errors: SaveError[] } {
  if (MOCK_USERS.length <= 1) {
    return { ok: false, errors: [{ message: "至少保留一个用户，无法删除" }] };
  }
  const idx = MOCK_USERS.findIndex((u) => u.id === id);
  if (idx < 0) {
    return { ok: false, errors: [{ message: "用户不存在或已被删除" }] };
  }
  MOCK_USERS.splice(idx, 1);
  return { ok: true, errors: [] };
}

// ─────────────────────────────────────────────────────────────
// 每日目标（可变 store）：单一数据源，总览目标环由它求和派生。
// ─────────────────────────────────────────────────────────────

const MOCK_GOALS: DailyGoal[] = [
  { action_id: "squat", action_name: "深蹲", target: 50, done: 30 },
  { action_id: "pushup", action_name: "俯卧撑", target: 40, done: 40 },
  { action_id: "jumping_jack", action_name: "开合跳", target: 60, done: 58 },
];

export function setGoal(action_id: string, target: number): void {
  if (target <= 0) {
    clearGoal(action_id);
    return;
  }
  const existing = MOCK_GOALS.find((g) => g.action_id === action_id);
  if (existing) {
    existing.target = target;
  } else {
    const a = MOCK_ACTION_DETAILS.find((d) => d.id === action_id);
    MOCK_GOALS.push({ action_id, action_name: a?.name ?? action_id, target, done: 0 });
  }
}

export function clearGoal(action_id: string): void {
  const idx = MOCK_GOALS.findIndex((g) => g.action_id === action_id);
  if (idx >= 0) MOCK_GOALS.splice(idx, 1);
}

// ─────────────────────────────────────────────────────────────
// 总览：静态部分 + 按目标求和派生 daily_goal_target / daily_goal_done
// ─────────────────────────────────────────────────────────────

type OverviewBase = Omit<
  Overview,
  "daily_goal_target" | "daily_goal_done" | "goals"
>;

const MOCK_OVERVIEW_BASE: OverviewBase = {
  today_reps: 128,
  yesterday_reps: 96,
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

/** 每次返回新对象 + goals 逐项拷贝（daily_goal_target/done 由 goals 求和派生） */
export function getOverviewData(): Overview {
  const goals = MOCK_GOALS.map((g) => ({ ...g }));
  const daily_goal_target = goals.reduce((sum, g) => sum + g.target, 0);
  const daily_goal_done = goals.reduce((sum, g) => sum + g.done, 0);
  return {
    ...MOCK_OVERVIEW_BASE,
    goals,
    daily_goal_target,
    daily_goal_done,
  };
}

export const MOCK_HEALTH: Health = {
  ok: true,
  mode: "mock",
  version: "0.1.0",
  python_version: "3.11",
  mediapipe_version: "0.10.35",
  model: "pose_landmarker_lite.task",
  device: "CPU",
  data_dir: "data/users",
  configs_dir: "configs",
  backend_url: "http://127.0.0.1:8000",
};