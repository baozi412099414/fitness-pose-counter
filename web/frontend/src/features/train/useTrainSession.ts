import { useCallback, useEffect, useRef, useState } from "react";
import { getTrainTransport } from "./transport";
import type { TrainTransport } from "./trainTransport";
import type {
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
  userName: string;
}

/**
 * 训练会话 hook：只对接 TrainTransport 接口并镜像其事件到 React 状态，
 * 不再内联任何计时 / 回放 / 判定逻辑。导出签名与改造前一致，页面组件不变。
 */
export function useTrainSession(options: Options) {
  const optsRef = useRef(options);
  optsRef.current = options;

  const [phase, setPhase] = useState<TrainPhase>("idle");
  const [frame, setFrame] = useState<TrainFrame | null>(null);
  const [summary, setSummary] = useState<TrainSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSet, setCurrentSet] = useState(1);
  const [restLeft, setRestLeft] = useState(0);

  const transportRef = useRef<TrainTransport | null>(null);
  if (transportRef.current == null) {
    transportRef.current = getTrainTransport();
  }

  useEffect(() => {
    const transport = transportRef.current!;

    transport.onPhase = (next) => {
      if (next === "idle") {
        setFrame(null);
        setSummary(null);
        setCurrentSet(1);
        setRestLeft(0);
      }
      setPhase(next);
    };
    transport.onFrame = setFrame;
    transport.onSet = setCurrentSet;
    transport.onRestTick = setRestLeft;
    transport.onSummary = setSummary;
    transport.onError = setError;

    return () => {
      transport.dispose();
    };
  }, []);

  const start = useCallback(() => {
    setFrame(null);
    setSummary(null);
    setError(null);
    setCurrentSet(1);
    setRestLeft(0);
    transportRef.current!.start({
      mode: optsRef.current.mode,
      sample: optsRef.current.sample,
      sets: optsRef.current.sets,
      restSeconds: optsRef.current.restSeconds,
      userName: optsRef.current.userName,
    });
  }, []);

  const sendFrame = useCallback((frameId: number, image: string) => {
    transportRef.current!.sendFrame(frameId, image);
  }, []);

  const stop = useCallback(() => {
    transportRef.current!.stop();
  }, []);

  const skipRest = useCallback(() => {
    transportRef.current!.skipRest();
  }, []);

  const reset = useCallback(() => {
    setError(null);
    transportRef.current!.reset();
  }, []);

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
    sendFrame,
  };
}