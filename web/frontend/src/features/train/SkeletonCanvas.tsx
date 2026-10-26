import { useEffect, useRef } from "react";
import type { LandmarkPoint } from "./types";

/** MediaPipe Pose 33 点中常用的躯干/四肢连线 */
const CONNECTIONS: [number, number][] = [
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
  [11, 23],
  [12, 24],
  [23, 24],
  [23, 25],
  [25, 27],
  [24, 26],
  [26, 28],
  [27, 29],
  [29, 31],
  [28, 30],
  [30, 32],
  [27, 31],
  [28, 32],
];

export function SkeletonCanvas({
  landmarks,
}: {
  landmarks: LandmarkPoint[];
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const width = wrap.clientWidth || 640;
    const height = wrap.clientHeight || 360;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // 背景网格
    ctx.strokeStyle = "rgba(255,255,255,0.035)";
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 48) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 48) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const byIndex = new Map(landmarks.map((p) => [p.index, p]));
    const lineWidth = Math.max(2, width / 320);
    const jointRadius = Math.max(2.5, width / 260);

    ctx.lineCap = "round";
    for (const [a, b] of CONNECTIONS) {
      const pa = byIndex.get(a);
      const pb = byIndex.get(b);
      if (!pa || !pb) continue;
      ctx.beginPath();
      ctx.moveTo(pa.x * width, pa.y * height);
      ctx.lineTo(pb.x * width, pb.y * height);
      ctx.strokeStyle = "rgba(111,227,255,0.82)";
      ctx.lineWidth = lineWidth;
      ctx.shadowColor = "rgba(111,227,255,0.55)";
      ctx.shadowBlur = 10;
      ctx.stroke();
    }

    ctx.shadowBlur = 0;
    for (const point of landmarks) {
      ctx.beginPath();
      ctx.arc(
        point.x * width,
        point.y * height,
        jointRadius,
        0,
        Math.PI * 2,
      );
      ctx.fillStyle = "#D6FF3F";
      ctx.shadowColor = "rgba(214,255,63,0.75)";
      ctx.shadowBlur = 8;
      ctx.fill();
    }
    ctx.shadowBlur = 0;
  }, [landmarks]);

  return (
    <div ref={wrapRef} className="absolute inset-0">
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  );
}
