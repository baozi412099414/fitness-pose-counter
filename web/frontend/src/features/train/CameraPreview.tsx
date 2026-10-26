import { useEffect, useRef } from "react";

export function CameraPreview({
  active,
  onError,
  onVideoReady,
}: {
  active: boolean;
  onError: (message: string) => void;
  /** 把 <video> 暴露给父组件，供 live 模式按 12fps 抓帧发送 */
  onVideoReady?: (video: HTMLVideoElement | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const onVideoReadyRef = useRef(onVideoReady);
  onVideoReadyRef.current = onVideoReady;

  useEffect(() => {
    onVideoReadyRef.current?.(videoRef.current);
    return () => onVideoReadyRef.current?.(null);
  }, []);

  useEffect(() => {
    if (!active) return;
    let stream: MediaStream | null = null;
    let cancelled = false;

    if (!navigator.mediaDevices?.getUserMedia) {
      onErrorRef.current("当前浏览器不支持摄像头，请改用回放模式");
      return;
    }

    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: "user", width: 1280, height: 720 },
        audio: false,
      })
      .then((next) => {
        if (cancelled) {
          next.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = next;
        if (videoRef.current) videoRef.current.srcObject = next;
      })
      .catch(() => {
        onErrorRef.current("无法访问摄像头，请检查权限，或切到回放模式");
      });

    return () => {
      cancelled = true;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [active]);

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      className="h-full w-full -scale-x-100 object-cover"
    />
  );
}
