import { useEffect, useRef, useState } from "react";

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
      media.removeEventListener?.("devicechange", onDeviceChange);
      stream?.getTracks().forEach((track) => track.stop());
      activeIdRef.current = null;
    };
  }, [active, deviceId]);

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      className={`h-full w-full object-cover ${mirrored ? "-scale-x-100" : ""}`}
    />
  );
}
