import { gradeOf } from "@/lib/format";
import type { Grade } from "@/lib/types";
import type {
  CheckItem,
  ErrorMessage,
  EventMessage,
  Landmark,
  ServerMessage,
  StateMessage,
  SummaryMessage,
} from "./contract";
import type { TrainTransport, TrainStartConfig } from "./trainTransport";
import type {
  LandmarkPoint,
  TrainCheckState,
  TrainFrame,
  TrainSummary,
} from "./types";

const WS_URL = "/ws/train";
const USER = "演示用户";

function toGrade(
  grade: string | null | undefined,
  score: number | null | undefined,
): Grade | null {
  if (grade === "优秀" || grade === "良好" || grade === "及格" || grade === "待改进") {
    return grade;
  }
  return gradeOf(score);
}

function mapChecks(checks: CheckItem[]): TrainCheckState[] {
  return checks.map((check) => ({
    key: check.name || check.tip,
    label: check.name || check.tip,
    ok: check.ok,
  }));
}

function mapLandmarks(landmarks: Landmark[]): LandmarkPoint[] {
  const out: LandmarkPoint[] = [];
  for (let i = 0; i < landmarks.length; i++) {
    const lm = landmarks[i];
    if (lm.v > 0) out.push({ index: i, x: lm.x, y: lm.y });
  }
  return out;
}

function mapState(s: StateMessage): TrainFrame {
  return {
    frameId: s.frame_id ?? 0,
    count: s.count,
    // WS 的 stage 是「动作是否激活」，与 UI 的「下蹲/起身」是两个概念；
    // 联调前先用 cycle_progress 粗略推断，接入 C 后再按真实语义收敛。
    stage: s.stage === "active" ? (s.cycle_progress < 0.5 ? "down" : "up") : "up",
    cycleProgress: s.cycle_progress,
    score: s.score,
    grade: toGrade(s.grade, s.score),
    checks: mapChecks(s.checks),
    tip: s.hits?.[0]?.tip ?? (s.person ? null : "请让全身入镜"),
    landmarks: mapLandmarks(s.landmarks),
    person: s.person,
  };
}

function mapSummary(s: SummaryMessage): TrainSummary {
  const errorTips = Object.values(s.error_tips ?? {});
  return {
    reps: s.reps,
    score: s.score ?? 0,
    grade: toGrade(s.grade, s.score) ?? "待改进",
    durationSec: Math.max(1, Math.round(s.duration_sec)),
    errors: errorTips.length ? errorTips : Object.keys(s.errors ?? {}),
  };
}

function mapError(msg: ErrorMessage): string {
  return msg.message;
}

/**
 * live 传输层：WebSocket /ws/train 客户端。
 *
 * 仅当 VITE_TRAIN_MODE=live 时使用。后端未启动时，连接失败会通过
 * onError + onPhase("idle") 给出可恢复错误态，绝不白屏/卡死。
 * 消息字段对齐 contract.ts（Prompt C / 附录 A），接入 C 后无需改 UI。
 */
export function createLiveTrainTransport(): TrainTransport {
  let ws: WebSocket | null = null;
  let closed = false;

  const transport: TrainTransport = {
    onPhase: null,
    onFrame: null,
    onSet: null,
    onRestTick: null,
    onSummary: null,
    onError: null,

    start(config: TrainStartConfig) {
      closed = false;
      transport.onPhase?.("calibrating");

      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        if (closed) return;
        if (config.mode === "replay") {
          ws?.send(
            JSON.stringify({
              type: "start_replay",
              sample_id: config.sample.id,
              action_id: config.sample.action,
              record_history: false,
            }),
          );
        } else {
          ws?.send(
            JSON.stringify({
              type: "start",
              action_id: config.sample.action,
              user: USER,
              sets: config.sets,
              reps_per_set: config.sample.count,
              rest_seconds: config.restSeconds,
            }),
          );
        }
      };

      ws.onmessage = (ev) => {
        let msg: ServerMessage;
        try {
          msg = JSON.parse(ev.data as string) as ServerMessage;
        } catch {
          return;
        }
        handleMessage(msg);
      };

      ws.onerror = () => {
        // 交由 onclose 统一处理，避免重复回调。
      };

      ws.onclose = () => {
        if (closed) return;
        transport.onError?.(
          "无法连接 /ws/train，请确认后端已启动，或切回回放模式",
        );
        transport.onPhase?.("idle");
      };
    },

    sendFrame(frameId: number, image: string) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "frame", frame_id: frameId, image }));
      }
    },

    skipRest() {
      // 契约（Prompt C §6）暂无 skip_rest 客户端消息；接入 C 后按需补充。
    },

    stop() {
      // TODO(接入 C 后)：服务端收到 stop 会回 summary；当前先通知后断连，
      // 联调时若需要保留 summary，则改为等待服务端 summary 再 close。
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));
      }
      closed = true;
      close();
    },

    reset() {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "reset" }));
      }
      closed = true;
      close();
      transport.onPhase?.("idle");
    },

    dispose() {
      closed = true;
      close();
    },
  };

  function close() {
    if (ws) {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      try {
        ws.close();
      } catch {
        // 忽略关闭异常
      }
      ws = null;
    }
  }

  function handleMessage(msg: ServerMessage) {
    switch (msg.type) {
      case "ready":
        transport.onPhase?.(
          msg.calibration?.needed && msg.mode === "camera"
            ? "calibrating"
            : "running",
        );
        break;
      case "state":
        transport.onFrame?.(mapState(msg));
        break;
      case "event":
        handleEvent(msg);
        break;
      case "summary":
        transport.onSummary?.(mapSummary(msg));
        transport.onPhase?.("finished");
        break;
      case "error":
        transport.onError?.(mapError(msg));
        if (msg.code === "BUSY" || msg.code === "MODEL_ERROR") {
          transport.onPhase?.("idle");
        }
        break;
    }
  }

  function handleEvent(msg: EventMessage) {
    switch (msg.event) {
      case "calibrated":
      case "rest_end":
        transport.onPhase?.("running");
        break;
      case "rest_start":
        transport.onPhase?.("resting");
        if (msg.seconds > 0) transport.onRestTick?.(msg.seconds);
        break;
      case "set_done":
        transport.onSet?.(msg.set);
        break;
      case "all_done":
        // 结算 summary 由服务端紧随其后推送
        break;
    }
  }

  return transport;
}