import type {
  SampleMeta,
  TrainFrame,
  TrainPhase,
  TrainSummary,
} from "./types";

/** 一次训练会话的启动参数（UI 侧形状，与传输实现无关） */
export interface TrainStartConfig {
  mode: "replay" | "live";
  sample: SampleMeta;
  sets: number;
  /** 每组目标次数（live 用它决定一组什么时候算做完；回放由样本长度决定） */
  repsPerSet: number;
  restSeconds: number;
  /** 当前用户显示名，live 的 start 消息需要写入 data/users/<用户名> */
  userName: string;
}

/**
 * 训练传输层抽象。
 *
 * mock 实现（mockTrainTransport）用本地计时 + samples 回放；
 * live 实现（liveTrainTransport）走 WebSocket /ws/train。
 * useTrainSession 只依赖本接口，不感知具体实现，因此接入后端时只换传输层。
 */
export interface TrainTransport {
  /** 开始一次训练会话 */
  start(config: TrainStartConfig): void;
  /** 中途结束（replay 会产出 summary，live/未开始则回 idle） */
  stop(): void;
  /** 跳过当前组间休息，直接进入下一组 */
  skipRest(): void;
  /** 回到 idle，丢弃当前会话 */
  reset(): void;
  /** 释放资源（清理定时器 / 关闭连接） */
  dispose(): void;
  /** 发送一帧图像（仅 live 模式使用，mock 忽略） */
  sendFrame(frameId: number, image: string): void;

  // 传输层 → 调用方（useTrainSession）的事件回调
  onPhase: ((phase: TrainPhase) => void) | null;
  onFrame: ((frame: TrainFrame) => void) | null;
  onSet: ((no: number) => void) | null;
  onRestTick: ((secondsLeft: number) => void) | null;
  onSummary: ((summary: TrainSummary) => void) | null;
  onError: ((message: string) => void) | null;
}