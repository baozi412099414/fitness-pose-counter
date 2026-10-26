import type { Grade } from "@/lib/types";

export type ActionKey = "squat" | "pushup" | "jumping_jack";
export type TrainMode = "replay" | "live";
export type TrainPhase =
  | "idle"
  | "calibrating"
  | "running"
  | "resting"
  | "finished";

export interface LandmarkPoint {
  index: number;
  x: number; // 0..1
  y: number; // 0..1
}

export interface TrainCheckState {
  key: string;
  label: string;
  ok: boolean;
}

export interface TrainFrame {
  frameId: number;
  count: number;
  stage: "down" | "up";
  cycleProgress: number;
  score: number | null;
  grade: Grade | null;
  checks: TrainCheckState[];
  tip: string | null;
  landmarks: LandmarkPoint[];
  person: boolean;
}

export interface TrainSummary {
  reps: number;
  score: number;
  grade: Grade;
  durationSec: number;
  errors: string[];
}

export interface SampleMeta {
  id: string;
  file: string;
  action: ActionKey;
  caseLabel: string;
  count: number;
  score: number;
  errors: string[];
}

export interface LoadedSample {
  id: string;
  fps: number;
  duration: number;
  frames: LandmarkPoint[][];
}
