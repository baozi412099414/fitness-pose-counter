import { createLiveTrainTransport } from "./liveTrainTransport";
import { createMockTrainTransport } from "./mockTrainTransport";
import type { TrainTransport } from "./trainTransport";
import type { TrainMode } from "./types";

/**
 * 训练传输层工厂。
 *
 * 默认按**页面模式**选：
 * - 「实时」→ WebSocket `/ws/train`（真摄像头 + 后端 MediaPipe 判定）；
 * - 「回放」→ 本地 mock（离线也能演示，不依赖后端）。
 *
 * `VITE_TRAIN_MODE` 仍然可以强制覆盖，两个取值：
 * - `"live"`：两种模式都走后端（回放走 `start_replay`，需要后端在）；
 * - `"mock"`：两种模式都走本地假数据（纯看 UI 时用）。
 *
 * 切换只影响传输层，useTrainSession 与页面组件不变。
 */
export function getTrainTransport(mode: TrainMode): TrainTransport {
  const forced = import.meta.env.VITE_TRAIN_MODE;
  if (forced === "live") return createLiveTrainTransport();
  if (forced === "mock") return createMockTrainTransport();
  return mode === "live" ? createLiveTrainTransport() : createMockTrainTransport();
}
