// ─────────────────────────────────────────────────────────────
// /ws/train 的 WebSocket 消息契约（对齐 docs Prompt C §6 + 附录 A）。
//
// 本文件是前端与后端（Prompt C 负责人）之间的接口契约：
// - 字段名以「服务端实际收发」的 JSON 键为准，勿在联调前随意改名；
// - 前端不重写计数 / 判定 / 评分算法，只消费这些消息并渲染。
// ─────────────────────────────────────────────────────────────

/** 客户端 → 服务端 */
export type ClientMessage =
  | {
      type: "start";
      action_id: string;
      user: string;
      sets: number;
      reps_per_set: number;
      rest_seconds: number;
    }
  | {
      type: "frame";
      frame_id: number;
      image: string; // data:image/jpeg;base64,...
    }
  | {
      type: "start_replay";
      sample_id: string;
      action_id: string;
      record_history: boolean;
    }
  | { type: "reset" }
  | { type: "stop" };

/** 动作是否处于激活阶段（供 UI 推断「下蹲/起身」等展示） */
export type Stage = "ready" | "active";

/** 单条质量判定项（附录 A A.1） */
export interface CheckItem {
  name: string;
  tip: string;
  value: number | null;
  limit: number | null;
  ok: boolean;
  visible: boolean;
  checked: boolean;
  priority: number;
  score: number | null;
}

/** 单个骨架关键点（37 归一化坐标，v=0 表示缺失） */
export interface Landmark {
  x: number; // 0~1
  y: number; // 0~1
  z: number;
  v: number; // visibility 0~1；0 = 缺失
}

export interface SetStatus {
  current_set: number;
  total_sets: number;
  reps_in_set: number;
  reps_per_set: number;
  total_reps: number;
  rest_remaining: number;
  finished: boolean;
}

export interface CalibrationStatus {
  status: "idle" | "sampling" | "done" | "skipped";
  baseline: number | null;
  progress: number; // 0~1
}

export interface TrainMetrics {
  fps: number;
  latency_ms: number;
  infer_ms: number;
  dropped?: boolean;
}

export interface ReadyMessage {
  type: "ready";
  session_id: string;
  mode: "camera" | "replay";
  action: { id: string; name: string; camera_side: string };
  calibration: { needed: boolean };
}

/** 每个 tick 的实时状态（附录 A StateMessage） */
export interface StateMessage {
  type: "state";
  seq: number;
  frame_id: number | null;
  ts: number;
  count: number;
  stage: Stage;
  signal: number | null;
  /** 各条件/主信号实测值；单条件一个，多条件必须全给 */
  values: Array<number | null> | null;
  cycle_progress: number;
  score: number | null;
  /** 服务端等级：优秀 / 良好 / 及格 / 待改进 / — */
  grade: string;
  checks: CheckItem[];
  hits: CheckItem[];
  landmarks: Landmark[]; // 33 个
  person: boolean;
  calibration: CalibrationStatus;
  sets: SetStatus;
  metrics: TrainMetrics;
}

export type ServerEventName =
  | "set_done"
  | "rest_start"
  | "rest_end"
  | "all_done"
  | "calibrated";

export interface EventMessage {
  type: "event";
  event: ServerEventName;
  set: number;
  total_sets: number;
  seconds: number;
  baseline: number | null;
  tip: string | null;
}

export interface SummaryMessage {
  type: "summary";
  action: string;
  action_name: string;
  reps: number;
  score: number | null;
  grade: string;
  duration_sec: number;
  errors: Record<string, number>;
  error_tips: Record<string, string>;
  person_rate: number;
  detection_rate: number;
  saved: boolean;
  goal: unknown;
}

export type ErrorCode = "NO_PERSON" | "MODEL_ERROR" | "BAD_FRAME" | "BUSY";

export interface ErrorMessage {
  type: "error";
  code: ErrorCode;
  message: string;
}

/** 服务端 → 客户端消息联合类型 */
export type ServerMessage =
  | ReadyMessage
  | StateMessage
  | EventMessage
  | SummaryMessage
  | ErrorMessage;