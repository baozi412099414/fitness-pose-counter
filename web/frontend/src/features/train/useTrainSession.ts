import { useCallback, useEffect, useRef, useState } from "react";
import { gradeOf } from "@/lib/format";
import { checksForSample, loadSample } from "./samples";
import type {
  LoadedSample,
  SampleMeta,
  TrainFrame,
  TrainMode,
  TrainPhase,
  TrainSummary,
} from "./types";

interface Options {
  mode: TrainMode;
  sample: SampleMeta;
  sets: number;
  restSeconds: number;
}

const TICK_MS = 66;

export function useTrainSession(options: Options) {
  const optsRef = useRef(options);
  optsRef.current = options;

  const [phase, setPhase] = useState<TrainPhase>("idle");
  const [frame, setFrame] = useState<TrainFrame | null>(null);
  const [summary, setSummary] = useState<TrainSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSet, setCurrentSet] = useState(1);
  const [restLeft, setRestLeft] = useState(0);

  const timerRef = useRef<number | null>(null);
  const calibRef = useRef<number | null>(null);
  const loadedRef = useRef<LoadedSample | null>(null);
  const runIdRef = useRef(0);
  const trainingStartedRef = useRef(0);
  const startedAtRef = useRef(0);
  const setRef = useRef(1);
  const frameRef = useRef<TrainFrame | null>(null);
  frameRef.current = frame;

  const clearTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const clearCalib = useCallback(() => {
    if (calibRef.current != null) {
      window.clearTimeout(calibRef.current);
      calibRef.current = null;
    }
  }, []);

  useEffect(
    () => () => {
      clearTimer();
      clearCalib();
    },
    [clearTimer, clearCalib],
  );

  const finish = useCallback((reps: number, durationSec: number) => {
    const sample = optsRef.current.sample;
    setSummary({
      reps,
      score: sample.score,
      grade: gradeOf(sample.score) ?? "待改进",
      durationSec: Math.max(1, Math.round(durationSec)),
      errors: sample.errors,
    });
    setPhase("finished");
  }, []);

  const beginReplay = useCallback(
    async (setNo: number) => {
      clearTimer();
      const runId = ++runIdRef.current;
      startedAtRef.current = 0;
      const { sample } = optsRef.current;
      setError(null);
      setSummary(null);
      setFrame(null);
      setPhase("calibrating");
      setCurrentSet(setNo);
      setRestLeft(0);
      setRef.current = setNo;

      try {
        if (!loadedRef.current || loadedRef.current.id !== sample.id) {
          loadedRef.current = await loadSample(sample);
        }
        // 等待期间用户可能已经取消/重开，过期任务直接丢弃
        if (runId !== runIdRef.current) return;
        const loaded = loadedRef.current;
        setPhase("running");
        startedAtRef.current = performance.now();

        timerRef.current = window.setInterval(() => {
          const elapsed = (performance.now() - startedAtRef.current) / 1000;
          const progress = Math.min(1, elapsed / loaded.duration);
          const idx = Math.min(
            loaded.frames.length - 1,
            Math.floor(progress * loaded.frames.length),
          );
          const total = sample.count;
          const count = progress >= 1 ? total : Math.floor(progress * total);
          const cycle = (progress * total) % 1;

          setFrame({
            frameId: idx,
            count,
            stage: cycle < 0.5 ? "down" : "up",
            cycleProgress: cycle,
            score: progress > 0.02 ? sample.score : null,
            grade: progress > 0.02 ? gradeOf(sample.score) : null,
            checks: checksForSample(sample),
            tip: progress > 0.08 ? (sample.errors[0] ?? null) : null,
            landmarks: loaded.frames[idx] ?? [],
            person: true,
          });

          if (progress >= 1) {
            clearTimer();
            if (setNo < optsRef.current.sets) {
              setPhase("resting");
              setRestLeft(optsRef.current.restSeconds);
            } else {
              finish(total * setNo, loaded.duration * setNo);
            }
          }
        }, TICK_MS);
      } catch {
        if (runId !== runIdRef.current) return;
        setError("回放样本加载失败，请换一个样本或刷新重试");
        setPhase("idle");
      }
    },
    [clearTimer, finish],
  );

  const start = useCallback(() => {
    clearCalib();
    clearTimer();
    runIdRef.current += 1;
    trainingStartedRef.current = performance.now();
    startedAtRef.current = 0;
    setFrame(null);
    setSummary(null);
    setError(null);
    setCurrentSet(1);
    setRestLeft(0);
    setRef.current = 1;

    if (optsRef.current.mode === "live") {
      loadedRef.current = null;
      setPhase("calibrating");
      calibRef.current = window.setTimeout(() => {
        setPhase("running");
        setFrame({
          frameId: 0,
          count: 0,
          stage: "up",
          cycleProgress: 0,
          score: null,
          grade: null,
          checks: checksForSample(optsRef.current.sample),
          tip: "演示模式：实时识别需后端 /ws/train 接入",
          landmarks: [],
          person: false,
        });
      }, 1600);
    } else {
      void beginReplay(1);
    }
  }, [beginReplay, clearCalib, clearTimer]);

  const stop = useCallback(() => {
    clearTimer();
    clearCalib();
    runIdRef.current += 1;
    if (optsRef.current.mode === "live" || !startedAtRef.current) {
      setFrame(null);
      setSummary(null);
      setPhase("idle");
      return;
    }
    const sample = optsRef.current.sample;
    const current = frameRef.current;
    const completed =
      (setRef.current - 1) * sample.count + (current?.count ?? 0);
    const seconds = trainingStartedRef.current
      ? (performance.now() - trainingStartedRef.current) / 1000
      : 0;
    finish(completed, seconds);
  }, [clearCalib, clearTimer, finish]);

  const skipRest = useCallback(() => {
    void beginReplay(setRef.current + 1);
  }, [beginReplay]);

  const reset = useCallback(() => {
    clearTimer();
    clearCalib();
    runIdRef.current += 1;
    setPhase("idle");
    setFrame(null);
    setSummary(null);
    setError(null);
    setCurrentSet(1);
    setRestLeft(0);
    setRef.current = 1;
  }, [clearCalib, clearTimer]);

  useEffect(() => {
    if (phase !== "resting") return;
    if (restLeft <= 0) {
      void beginReplay(setRef.current + 1);
      return;
    }
    const t = window.setTimeout(() => setRestLeft((v) => v - 1), 1000);
    return () => window.clearTimeout(t);
  }, [phase, restLeft, beginReplay]);

  return {
    phase,
    frame,
    summary,
    error,
    currentSet,
    restLeft,
    start,
    stop,
    skipRest,
    reset,
  };
}
