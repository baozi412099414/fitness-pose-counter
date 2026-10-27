import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Camera,
  Play,
  RotateCcw,
  SkipForward,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Select } from "@/components/ui/Select";
import { cn } from "@/lib/cn";
import { useUser } from "@/providers/UserProvider";
import { CameraPreview } from "./CameraPreview";
import { SkeletonCanvas } from "./SkeletonCanvas";
import { ChecksPanel, ScoreRing, SummaryPanel } from "./TrainPanels";
import {
  ACTION_META,
  DEFAULT_SAMPLE,
  SAMPLES,
  checksForSample,
  isActionKey,
} from "./samples";
import { useTrainSession } from "./useTrainSession";
import type { ActionKey, TrainMode } from "./types";

const REST_SECONDS = 30;

/** 每组次数的预设（网页端演示用，够覆盖常见组次） */
const REPS_OPTIONS = [5, 8, 10, 12, 15, 20, 30];
/** 组间休息预设（秒），0 = 不休息 */
const REST_OPTIONS = [0, 10, 15, 20, 30, 45, 60, 90];

/** 连续互通相机的设备名里带 iPhone / iPad / Continuity，中文系统是「iPhone 的相机」 */
const PHONE_CAMERA = /iphone|ipad|continuity|手机/i;

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="rounded border border-line1 bg-surface2 px-1.5 py-0.5 font-mono text-[10px] text-text2">
      {children}
    </kbd>
  );
}

export function TrainPage() {
  const navigate = useNavigate();
  const { currentUser } = useUser();
  const { id } = useParams();
  const action: ActionKey = isActionKey(id) ? id : "squat";
  const actionSamples = SAMPLES.filter((sample) => sample.action === action);

  const [sampleId, setSampleId] = useState(DEFAULT_SAMPLE[action]);
  const [mode, setMode] = useState<TrainMode>("replay");
  const [sets, setSets] = useState(1);
  const [repsPerSet, setRepsPerSet] = useState(10);
  const [restSeconds, setRestSeconds] = useState(REST_SECONDS);
  const [voice, setVoice] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [showExit, setShowExit] = useState(false);
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([]);
  const [cameraMirrored, setCameraMirrored] = useState(true);
  const [activeCameraId, setActiveCameraId] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState<string>(() => {
    try {
      return localStorage.getItem("formlab.cameraId") ?? "";
    } catch {
      return "";
    }
  });

  useEffect(() => {
    setSampleId(DEFAULT_SAMPLE[action]);
  }, [action]);

  const sample = useMemo(
    () =>
      SAMPLES.find((item) => item.id === sampleId) ??
      SAMPLES.find((item) => item.action === action)!,
    [sampleId, action],
  );

  const session = useTrainSession({
    mode,
    sample,
    sets,
    repsPerSet,
    restSeconds,
    userName: currentUser?.name ?? "默认用户",
  });
  const { phase, frame, summary, error, currentSet, restLeft } = session;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const handleVideoReady = useCallback(
    (video: HTMLVideoElement | null) => {
      videoRef.current = video;
    },
    [],
  );

  // 摄像头列表来自 CameraPreview（拿到权限后 label 才可读）。
  // 第一次拿到列表时若存在 iPhone 摄像头，自动切过去——演示时不用手动挑。
  const handleDevices = useCallback(
    (devices: MediaDeviceInfo[], activeId: string | null) => {
      setCameras(devices);
      setActiveCameraId(activeId);
      setCameraId((current) => {
        if (current) return current;
        const phone = devices.find((device) => PHONE_CAMERA.test(device.label));
        return phone && phone.deviceId !== activeId ? phone.deviceId : current;
      });
    },
    [],
  );

  const pickCamera = (deviceId: string) => {
    setCameraId(deviceId);
    try {
      localStorage.setItem("formlab.cameraId", deviceId);
    } catch {
      // 隐私模式下 localStorage 可能不可写，忽略即可
    }
  };

  const savedCameraAvailable = cameras.some(
    (device) => device.deviceId === cameraId,
  );
  // 列表还没出来时先让浏览器用默认摄像头，等 enumerateDevices 回来再切到指定设备
  const appliedCameraId =
    cameras.length > 0 && savedCameraAvailable ? cameraId : undefined;
  const cameraValue = savedCameraAvailable ? cameraId : (activeCameraId ?? "");
  const phoneCamera = cameras.find((device) => PHONE_CAMERA.test(device.label));
  const cameraHint =
    cameras.length === 0
      ? "打开实时并允许摄像头后，这里会列出可用设备（含 iPhone）。"
      : phoneCamera
        ? "已检测到 iPhone 摄像头：保持 iPhone 解锁、靠近 Mac、开启「连续互通相机」。"
        : "没检测到 iPhone：确认 iPhone 已解锁、与 Mac 同一 Apple ID，并在设置里开启「连续互通相机」。";

  // live 模式：从 camera 按 12fps 抓 640px JPEG 帧发给 /ws/train。
  // ⚠ 校准阶段也要发帧：后端的站立基线是靠这些帧采出来的，
  //   只在 running 阶段发会死锁（不校准完就进不了 running）。
  useEffect(() => {
    if (mode !== "live") return;
    if (
      phase !== "running" &&
      phase !== "calibrating" &&
      phase !== "resting"
    ) {
      return;
    }
    const video = videoRef.current;
    if (!video) return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    let frameId = 0;
    let cancelled = false;
    let timer = 0;

    const tick = () => {
      if (cancelled) return;
      if (video.readyState >= 2 && video.videoWidth > 0) {
        const scale = 640 / Math.max(video.videoWidth, video.videoHeight);
        canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
        canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
        ctx?.drawImage(video, 0, 0, canvas.width, canvas.height);
        session.sendFrame(++frameId, canvas.toDataURL("image/jpeg", 0.72));
      }
      timer = window.setTimeout(tick, 1000 / 12);
    };

    timer = window.setTimeout(tick, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [mode, phase, session.sendFrame]);
  const busy =
    phase === "calibrating" || phase === "running" || phase === "resting";

  const count = frame?.count ?? 0;
  useEffect(() => {
    if (!voice || count <= 0) return;
    if (!("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(`第 ${count} 次`);
    utterance.lang = "zh-CN";
    utterance.rate = 1.1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, [voice, count]);

  const actionsRef = useRef({ start: session.start, stop: session.stop });
  actionsRef.current = { start: session.start, stop: session.stop };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      ) {
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        if (phase === "idle" || phase === "finished") navigate("/");
        else setShowExit(true);
      } else if (
        (event.key === "Enter" || event.key === " ") &&
        phase === "idle"
      ) {
        event.preventDefault();
        actionsRef.current.start();
      } else if (
        event.key.toLowerCase() === "r" &&
        phase !== "idle"
      ) {
        event.preventDefault();
        actionsRef.current.start();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, navigate]);

  const changeMode = (next: TrainMode) => {
    session.reset();
    setMode(next);
    setCameraError(null);
  };

  const requestExit = () => {
    if (phase === "idle" || phase === "finished") navigate("/");
    else setShowExit(true);
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/")}
            aria-label="返回总览"
            className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-line1 text-text2 transition-colors hover:bg-surface2 hover:text-text1"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-2xl font-medium text-text1">
              训练 · {ACTION_META[action].name}
            </h1>
            <p className="mt-0.5 text-sm text-text3">
              {ACTION_META[action].hint}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-[10px] border border-line1 bg-surface1 p-0.5">
            {(["replay", "live"] as const).map((item) => (
              <button
                key={item}
                type="button"
                disabled={busy}
                onClick={() => changeMode(item)}
                className={cn(
                  "rounded-[8px] px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40",
                  mode === item
                    ? "bg-surface2 text-text1"
                    : "text-text2 hover:text-text1",
                )}
              >
                {item === "replay" ? "回放" : "实时"}
              </button>
            ))}
          </div>
          <Button variant="secondary" onClick={requestExit}>
            <Square size={14} /> 结束
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <aside className="order-2 col-span-12 lg:order-1 lg:col-span-2">
          <Card title="训练设置" className="h-full">
            <div className="flex flex-col gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.12em] text-text3">
                  动作
                </p>
                <p className="mt-1 text-lg text-text1">
                  {ACTION_META[action].name}
                </p>
                <p className="mt-0.5 text-xs text-text3">
                  {ACTION_META[action].hint}
                </p>
              </div>

              <label className="flex flex-col gap-1">
                <span className="text-xs uppercase tracking-[0.12em] text-text3">
                  回放样本
                </span>
                <Select
                  value={sample.id}
                  disabled={busy || mode !== "replay"}
                  onChange={(event) => setSampleId(event.target.value)}
                >
                  {actionSamples.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.caseLabel}
                    </option>
                  ))}
                </Select>
              </label>

              {mode === "live" && (
                <label className="flex flex-col gap-1">
                  <span className="text-xs uppercase tracking-[0.12em] text-text3">
                    摄像头
                  </span>
                  <Select
                    value={cameraValue}
                    title={cameraHint}
                    disabled={busy || cameras.length === 0}
                    onChange={(event) => pickCamera(event.target.value)}
                  >
                    {cameras.length === 0 && (
                      <option value="">未检测到摄像头</option>
                    )}
                    {cameras.map((device, index) => (
                      <option key={device.deviceId || index} value={device.deviceId}>
                        {device.label || `摄像头 ${index + 1}`}
                      </option>
                    ))}
                  </Select>
                  <span className="text-[11px] leading-relaxed text-text3">
                    {cameraHint}
                  </span>
                </label>
              )}

              <label className="flex flex-col gap-1">
                <span className="text-xs uppercase tracking-[0.12em] text-text3">
                  组数
                </span>
                <Select
                  value={String(sets)}
                  disabled={busy}
                  onChange={(event) => setSets(Number(event.target.value))}
                >
                  {[1, 2, 3].map((value) => (
                    <option key={value} value={String(value)}>
                      {value} 组
                    </option>
                  ))}
                </Select>
              </label>

              <div className="flex flex-col gap-2 text-sm">
                <label className="flex flex-col gap-1">
                  <span className="text-xs uppercase tracking-[0.12em] text-text3">
                    每组次数
                  </span>
                  {mode === "live" ? (
                    <Select
                      value={String(repsPerSet)}
                      disabled={busy}
                      onChange={(event) => setRepsPerSet(Number(event.target.value))}
                    >
                      {REPS_OPTIONS.map((value) => (
                        <option key={value} value={String(value)}>
                          {value} 次
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <div className="flex h-10 items-center justify-between rounded-[10px] border border-line1 bg-surface2/40 px-3">
                      <span className="text-[11px] text-text3">回放样本长度</span>
                      <span className="font-num text-text1">{sample.count} 次</span>
                    </div>
                  )}
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs uppercase tracking-[0.12em] text-text3">
                    组间休息
                  </span>
                  <Select
                    value={String(restSeconds)}
                    disabled={busy}
                    onChange={(event) => setRestSeconds(Number(event.target.value))}
                  >
                    {REST_OPTIONS.map((value) => (
                      <option key={value} value={String(value)}>
                        {value === 0 ? "不休息" : `${value} 秒`}
                      </option>
                    ))}
                  </Select>
                </label>
              </div>

              <Button
                variant="secondary"
                className="w-full justify-start"
                onClick={() => setVoice((value) => !value)}
              >
                {voice ? <Volume2 size={15} /> : <VolumeX size={15} />}
                语音播报 {voice ? "开" : "关"}
              </Button>

              {mode === "live" && (
                <p className="text-xs leading-relaxed text-text3">
                  实时模式的帧会发给本地 `/ws/train`（MediaPipe + pose_logic 判定），
                  开跑前确认后端已启动：`python -m uvicorn web.backend.app:app --port 8000`。
                </p>
              )}
              {mode === "replay" && (
                <p className="text-xs leading-relaxed text-text3">
                  回放数据来自 `samples/*.json`（合成动作），计数与评分复现
                  README 基准。
                </p>
              )}
            </div>
          </Card>
        </aside>

        <section className="order-1 col-span-12 lg:order-2 lg:col-span-7">
          <div className="relative aspect-video overflow-hidden rounded-card border border-line1 bg-[#07090c]">
            {mode === "live" ? (
              <>
                <CameraPreview
                  active
                  deviceId={appliedCameraId}
                  onError={setCameraError}
                  onDevices={handleDevices}
                  onVideoReady={handleVideoReady}
                  onMirror={setCameraMirrored}
                />
                {frame?.person && frame.landmarks.length > 0 && (
                  <div
                    className={cn(
                      "pointer-events-none absolute inset-0",
                      cameraMirrored && "-scale-x-100",
                    )}
                  >
                    <SkeletonCanvas landmarks={frame.landmarks} />
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,#121722_0%,#07090c_70%)]" />
                {frame && frame.landmarks.length > 0 && (
                  <SkeletonCanvas landmarks={frame.landmarks} />
                )}
              </>
            )}

            <div className="absolute left-4 top-4 flex items-center gap-2">
              <Badge tone="accent">{ACTION_META[action].name}</Badge>
              <Badge tone="neutral">
                {mode === "replay" ? "回放" : "实时"}
              </Badge>
            </div>

            {phase === "running" && frame && mode === "replay" && (
              <div className="absolute right-4 top-4 text-right">
                <p className="text-[10px] uppercase tracking-[0.16em] text-text3">
                  次数
                </p>
                <p className="font-num text-5xl leading-none text-text1">
                  {frame.count}
                </p>
                <p className="text-xs text-text3">/ {sample.count}</p>
              </div>
            )}

            {phase === "idle" && !(mode === "live" && cameraError) && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/45 px-6 text-center backdrop-blur-[1px]">
                <p className="text-sm text-text2">
                  {mode === "replay"
                    ? "回放样本，复现 README 的计数与评分"
                    : "实时预览；点开始后先站直 2 秒量基线，再开始做动作"}
                </p>
                <Button onClick={session.start}>
                  <Play size={16} /> 开始训练
                </Button>
                <p className="text-[11px] text-text3">Enter / Space 开始</p>
              </div>
            )}

            {phase === "calibrating" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/55 backdrop-blur-[1px]">
                <div className="flex h-12 w-12 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-accent">
                  <Camera size={20} />
                </div>
                <p className="text-sm text-text1">
                  {mode === "replay" ? "正在准备回放…" : "正在量站立基线…"}
                </p>
                <p className="max-w-xs text-center text-xs leading-relaxed text-text3">
                  {mode === "replay"
                    ? "加载样本关键点…"
                    : "站直、别动，让全身进画面 —— 这 2 秒在量你站着时关节的角度，后面的判定门槛会按它来定"}
                </p>
                <div className="h-1 w-40 overflow-hidden rounded-full bg-surface2">
                  <div
                    className="h-full rounded-full bg-accent transition-[width] duration-200"
                    style={{
                      width: `${Math.round((frame?.calibration?.progress ?? 0.15) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {phase === "resting" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/60 backdrop-blur-[2px]">
                <p className="text-[11px] uppercase tracking-[0.2em] text-text3">
                  组间休息
                </p>
                <p className="font-num text-7xl leading-none text-accent">
                  {restLeft}
                </p>
                <p className="text-xs text-text3">
                  第 {currentSet} / {sets} 组完成
                </p>
                <Button
                  variant="secondary"
                  className="mt-2"
                  disabled={mode === "live"}
                  title={mode === "live" ? "待后端支持" : undefined}
                  onClick={session.skipRest}
                >
                  <SkipForward size={15} /> 跳过休息
                </Button>
                {mode === "live" && (
                  <p className="text-[11px] text-text3">跳过休息待后端支持</p>
                )}
              </div>
            )}

            {phase === "running" && frame && mode === "replay" && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-line1 bg-black/55 px-4 py-1.5 text-xs text-text2 backdrop-blur">
                {frame.stage === "down"
                  ? ACTION_META[action].down
                  : ACTION_META[action].up}
                <span className="mx-2 text-line2">·</span>
                {Math.round(frame.cycleProgress * 100)}%
              </div>
            )}

            {mode === "live" && phase === "running" && (
              <div
                className={cn(
                  "absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border px-4 py-1.5 text-xs backdrop-blur",
                  frame?.person
                    ? "border-mint/30 bg-mint/10 text-mint"
                    : "border-amber/30 bg-amber/10 text-amber",
                )}
              >
                {frame?.person
                  ? `实时识别中 · 当前 ${frame.signal != null ? `${Math.round(frame.signal)}°` : "—"}`
                  : "请站到画面里"}
              </div>
            )}

            {mode === "live" && cameraError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/70 px-6 text-center">
                <p className="text-sm text-coral">{cameraError}</p>
                <Button
                  variant="secondary"
                  onClick={() => changeMode("replay")}
                >
                  切到回放模式
                </Button>
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {phase === "idle" && (
                <Button onClick={session.start}>
                  <Play size={15} /> 开始训练
                </Button>
              )}
              {phase === "calibrating" && (
                <Button variant="secondary" onClick={session.stop}>
                  <Square size={15} /> 取消
                </Button>
              )}
              {phase === "running" && (
                <Button variant="secondary" onClick={session.stop}>
                  <Square size={15} /> 结束训练
                </Button>
              )}
              {phase === "resting" && (
                <Button
                  disabled={mode === "live"}
                  title={mode === "live" ? "待后端支持" : undefined}
                  onClick={session.skipRest}
                >
                  <SkipForward size={15} /> 跳过休息
                </Button>
              )}
              {phase === "finished" && (
                <Button onClick={session.start}>
                  <RotateCcw size={15} /> 再来一次
                </Button>
              )}
              {(phase === "running" || phase === "resting") && (
                <Button variant="ghost" onClick={session.start}>
                  <RotateCcw size={15} /> 重新开始
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-text3">
              <Kbd>Enter</Kbd> 开始 <Kbd>R</Kbd> 重开 <Kbd>Esc</Kbd> 退出
            </div>
          </div>

          {phase === "finished" && summary && (
            <div className="mt-4">
              <SummaryPanel
                summary={summary}
                onRestart={session.start}
                onBack={() => navigate("/data")}
              />
            </div>
          )}

          {error && (
            <p className="mt-3 rounded-[10px] border border-coral/30 bg-coral/[0.06] px-3 py-2 text-sm text-coral">
              {error}
            </p>
          )}
        </section>

        <aside className="order-3 col-span-12 lg:col-span-3">
          <div className="flex flex-col gap-4">
            <Card title="实时评分" bodyClassName="flex flex-col items-center">
              <ScoreRing
                score={frame?.score ?? null}
                grade={frame?.grade ?? null}
              />
              <p className="mt-3 text-center text-xs text-text3">
                {mode === "live"
                  ? "评分在本轮动作完成时结算"
                  : "评分来自回放样本基准值"}
              </p>
            </Card>

            <Card
              title="判定项"
              subtitle={phase === "idle" ? "开始后逐项判定" : "实时判定"}
            >
              <ChecksPanel
                checks={
                  frame?.checks?.length ? frame.checks : checksForSample(sample)
                }
                pending={!frame || phase === "idle" || !frame.person}
              />
            </Card>

            {(cameraError || frame?.tip) && (
              <div className="rounded-card border border-coral/30 bg-coral/[0.06] px-4 py-3 text-sm text-coral">
                {cameraError ?? frame?.tip}
              </div>
            )}
          </div>
        </aside>
      </div>

      <Dialog
        open={showExit}
        onClose={() => setShowExit(false)}
        title="结束训练"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setShowExit(false)}
            >
              继续训练
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setShowExit(false);
                session.stop();
              }}
            >
              结束训练
            </Button>
          </>
        }
      >
        <p className="text-sm text-text2">
          结束后会生成本次训练汇总；已完成的计数会保留。
        </p>
      </Dialog>
    </div>
  );
}
