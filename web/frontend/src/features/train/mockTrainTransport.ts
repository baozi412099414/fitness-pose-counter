import { gradeOf } from "@/lib/format";
import { checksForSample, loadSample } from "./samples";
import type { TrainTransport, TrainStartConfig } from "./trainTransport";
import type { LoadedSample, TrainFrame, TrainSummary } from "./types";

const TICK_MS = 66;

/**
 * mock 传输层：把原 useTrainSession 内的回放/演示计时逻辑原样搬进来，
 * 通过 TrainTransport 接口对外输出，行为与改造前完全一致。
 */
export function createMockTrainTransport(): TrainTransport {
  let cfg: TrainStartConfig | null = null;
  let loaded: LoadedSample | null = null;
  let setNo = 1;
  let runId = 0;
  let trainingStarted = 0;
  let startedAt = 0;
  let lastFrame: TrainFrame | null = null;

  let timer: number | null = null;
  let restTimer: number | null = null;
  let calibTimer: number | null = null;

  const t: TrainTransport = {
    onPhase: null,
    onFrame: null,
    onSet: null,
    onRestTick: null,
    onSummary: null,
    onError: null,
    sendFrame: () => {},
    start,
    stop,
    skipRest,
    reset,
    dispose,
  };

  function clearTimer() {
    if (timer != null) {
      window.clearInterval(timer);
      timer = null;
    }
  }
  function clearRest() {
    if (restTimer != null) {
      window.clearInterval(restTimer);
      restTimer = null;
    }
  }
  function clearCalib() {
    if (calibTimer != null) {
      window.clearTimeout(calibTimer);
      calibTimer = null;
    }
  }

  function finish(reps: number, durationSec: number) {
    const sample = cfg!.sample;
    const summary: TrainSummary = {
      reps,
      score: sample.score,
      grade: gradeOf(sample.score) ?? "待改进",
      durationSec: Math.max(1, Math.round(durationSec)),
      errors: sample.errors,
    };
    t.onSummary?.(summary);
    t.onPhase?.("finished");
  }

  function beginReplay(set: number) {
    clearTimer();
    const myRun = ++runId;
    startedAt = 0;
    const sample = cfg!.sample;
    setNo = set;
    t.onPhase?.("calibrating");
    t.onSet?.(set);

    void (async () => {
      try {
        if (!loaded || loaded.id !== sample.id) {
          loaded = await loadSample(sample);
        }
        // 等待期间用户可能已经取消/重开，过期任务直接丢弃
        if (myRun !== runId) return;
        const data = loaded;
        t.onPhase?.("running");
        startedAt = performance.now();

        timer = window.setInterval(() => {
          const elapsed = (performance.now() - startedAt) / 1000;
          const progress = Math.min(1, elapsed / data.duration);
          const idx = Math.min(
            data.frames.length - 1,
            Math.floor(progress * data.frames.length),
          );
          const total = sample.count;
          const count = progress >= 1 ? total : Math.floor(progress * total);
          const cycle = (progress * total) % 1;

          const frame: TrainFrame = {
            frameId: idx,
            count,
            stage: cycle < 0.5 ? "down" : "up",
            cycleProgress: cycle,
            score: progress > 0.02 ? sample.score : null,
            grade: progress > 0.02 ? gradeOf(sample.score) : null,
            checks: checksForSample(sample),
            tip: progress > 0.08 ? (sample.errors[0] ?? null) : null,
            landmarks: data.frames[idx] ?? [],
            person: true,
          };
          lastFrame = frame;
          t.onFrame?.(frame);

          if (progress >= 1) {
            clearTimer();
            if (set < cfg!.sets) {
              beginRest(set);
            } else {
              finish(total * set, data.duration * set);
            }
          }
        }, TICK_MS);
      } catch {
        if (myRun !== runId) return;
        t.onError?.("回放样本加载失败，请换一个样本或刷新重试");
        t.onPhase?.("idle");
      }
    })();
  }

  function beginRest(completedSet: number) {
    t.onPhase?.("resting");
    let left = cfg!.restSeconds;
    t.onRestTick?.(left);
    clearRest();
    restTimer = window.setInterval(() => {
      left -= 1;
      if (left <= 0) {
        clearRest();
        beginReplay(completedSet + 1);
      } else {
        t.onRestTick?.(left);
      }
    }, 1000);
  }

  function start(config: TrainStartConfig) {
    cfg = config;
    clearRest();
    clearCalib();
    clearTimer();
    runId += 1;
    trainingStarted = performance.now();
    startedAt = 0;
    lastFrame = null;
    setNo = 1;

    if (config.mode === "live") {
      loaded = null;
      t.onPhase?.("calibrating");
      calibTimer = window.setTimeout(() => {
        t.onPhase?.("running");
        const frame: TrainFrame = {
          frameId: 0,
          count: 0,
          stage: "up",
          cycleProgress: 0,
          score: null,
          grade: null,
          checks: checksForSample(config.sample),
          tip: "演示模式：实时识别需后端 /ws/train 接入",
          landmarks: [],
          person: false,
        };
        lastFrame = frame;
        t.onFrame?.(frame);
      }, 1600);
    } else {
      beginReplay(1);
    }
  }

  function stop() {
    clearRest();
    clearCalib();
    clearTimer();
    runId += 1;
    if (cfg?.mode === "live" || !startedAt) {
      t.onPhase?.("idle");
      return;
    }
    const sample = cfg!.sample;
    const current = lastFrame;
    const completed = (setNo - 1) * sample.count + (current?.count ?? 0);
    const seconds = trainingStarted
      ? (performance.now() - trainingStarted) / 1000
      : 0;
    finish(completed, seconds);
  }

  function skipRest() {
    clearRest();
    beginReplay(setNo + 1);
  }

  function reset() {
    clearRest();
    clearCalib();
    clearTimer();
    runId += 1;
    t.onPhase?.("idle");
  }

  function dispose() {
    clearRest();
    clearCalib();
    clearTimer();
    runId += 1;
  }

  return t;
}