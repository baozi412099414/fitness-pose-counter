import { useEffect, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";

const VIDEO_BASE = { width: 1280, height: 720 } as const;

/** 只有拿到摄像头权限后，enumerateDevices 才会返回设备名（label） */
async function listCameras(): Promise<MediaDeviceInfo[]> {
  try {
    const all = await navigator.mediaDevices.enumerateDevices();
    return all.filter((device) => device.kind === "videoinput");
  } catch {
    return [];
  }
}

export function CameraPreview({
  active,
  deviceId,
  onError,
  onDevices,
  onVideoReady,
  onMirror,
}: {
  active: boolean;
  /** 指定摄像头（如 iPhone）；为空时交给浏览器挑默认摄像头 */
  deviceId?: string | null;
  onError: (message: string) => void;
  /** 画面是否镜像（前置/笔记本摄像头为 true）——骨架叠加层要跟着一起镜像 */
  onMirror?: (mirrored: boolean) => void;
  /** 授权后回传可用摄像头列表，以及此刻真正在用的 deviceId */
  onDevices?: (devices: MediaDeviceInfo[], activeId: string | null) => void;
  /** 把 <video> 暴露给父组件，供 live 模式按 12fps 抓帧发送 */
  onVideoReady?: (video: HTMLVideoElement | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [mirrored, setMirrored] = useState(true);
  // 「设备连上了但一直没画面」：连续互通相机最常见的问题（手机锁屏/被占用/掉线）。
  // 不检测的话用户只看到一块黑屏，完全不知道下一步该干嘛。
  const [stalled, setStalled] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const activeIdRef = useRef<string | null>(null);

  // 回调放 ref 里，避免父组件每次渲染都触发重新开流
  const callbacks = useRef({ onError, onDevices, onVideoReady, onMirror });
  callbacks.current = { onError, onDevices, onVideoReady, onMirror };

  useEffect(() => {
    callbacks.current.onVideoReady?.(videoRef.current);
    return () => callbacks.current.onVideoReady?.(null);
  }, []);

  useEffect(() => {
    if (!active) return;
    const media = navigator.mediaDevices;
    if (!media?.getUserMedia) {
      callbacks.current.onError("当前浏览器不支持摄像头，请改用回放模式");
      return;
    }

    let cancelled = false;
    let stream: MediaStream | null = null;
    setStalled(false);
    const stallTimer = window.setTimeout(() => {
      const video = videoRef.current;
      if (!video || video.videoWidth === 0) setStalled(true);
    }, 3000);

    const publishDevices = async () => {
      const devices = await listCameras();
      if (!cancelled) callbacks.current.onDevices?.(devices, activeIdRef.current);
    };

    const apply = async (constraints: MediaStreamConstraints) => {
      const next = await media.getUserMedia(constraints);
      if (cancelled) {
        next.getTracks().forEach((track) => track.stop());
        return;
      }
      stream?.getTracks().forEach((track) => track.stop());
      stream = next;
      if (videoRef.current) videoRef.current.srcObject = next;
      const settings = next.getVideoTracks()[0]?.getSettings?.() ?? {};
      activeIdRef.current = settings.deviceId ?? null;
      // 设备被拔掉 / 手机休眠：轨道会 ended，画面就黑了
      next.getVideoTracks()[0]?.addEventListener("ended", () => {
        if (!cancelled) setStalled(true);
      });
      // 手机后置摄像头不镜像，前置/笔记本摄像头镜像（自拍视角更自然）
      const nextMirror = settings.facingMode !== "environment";
      setMirrored(nextMirror);
      callbacks.current.onMirror?.(nextMirror);
      await publishDevices();
    };

    const start = async () => {
      try {
        if (deviceId) {
          try {
            await apply({
              video: { deviceId: { exact: deviceId }, ...VIDEO_BASE },
              audio: false,
            });
            return;
          } catch {
            if (cancelled) return;
            // 设备被拔掉 / 被别的 App 占用：退回默认，别整块黑屏
            callbacks.current.onError(
              "选中的摄像头打不开（可能已断开或被其他程序占用），已切回默认摄像头",
            );
          }
        }
        await apply({
          video: { facingMode: "user", ...VIDEO_BASE },
          audio: false,
        });
      } catch {
        if (!cancelled) {
          callbacks.current.onError(
            "无法访问摄像头，请检查浏览器权限，或切到回放模式",
          );
        }
      }
    };

    void start();

    // iPhone 插拔 / 连续互通相机上线时刷新设备列表
    const onDeviceChange = () => {
      void publishDevices();
    };
    media.addEventListener?.("devicechange", onDeviceChange);

    return () => {
      cancelled = true;
      window.clearTimeout(stallTimer);
      media.removeEventListener?.("devicechange", onDeviceChange);
      stream?.getTracks().forEach((track) => track.stop());
      activeIdRef.current = null;
    };
  }, [active, deviceId, attempt]);

  return (
    <div className="relative h-full w-full">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        onLoadedData={() => setStalled(false)}
        className={`h-full w-full object-cover ${mirrored ? "-scale-x-100" : ""}`}
      />
      {stalled && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80 px-6 text-center">
          <p className="text-sm text-coral">摄像头已连接，但一直没有画面</p>
          <p className="max-w-sm text-xs leading-relaxed text-text3">
            如果是 iPhone 连续互通相机：确认手机亮屏、没被别的 App 占用、数据线插好；
            也可以在左侧「摄像头」里换成 Mac 自带摄像头。
          </p>
          <Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>
            <RotateCcw size={14} /> 重新连接
          </Button>
        </div>
      )}
    </div>
  );
}
