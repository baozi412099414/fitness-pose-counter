import { createLiveTrainTransport } from "./liveTrainTransport";
import { createMockTrainTransport } from "./mockTrainTransport";
import type { TrainTransport } from "./trainTransport";

/**
 * 训练传输层工厂。
 *
 * VITE_TRAIN_MODE 取值：
 * - "mock"（默认）：本地计时 + samples 回放，行为与后端接入前一致；
 * - "live"：WebSocket /ws/train（Prompt C 后端就绪后切换）。
 *
 * 切换只影响传输层，useTrainSession 与页面组件不变。
 */
export function getTrainTransport(): TrainTransport {
  if (import.meta.env.VITE_TRAIN_MODE === "live") {
    return createLiveTrainTransport();
  }
  return createMockTrainTransport();
}