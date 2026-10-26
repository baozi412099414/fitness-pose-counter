/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 实时训练传输层：mock（默认，本地计时 + 回放）| live（WebSocket /ws/train） */
  readonly VITE_TRAIN_MODE?: "mock" | "live";
}