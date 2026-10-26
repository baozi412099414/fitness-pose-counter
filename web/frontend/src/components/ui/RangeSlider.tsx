import { useEffect, useRef, type PointerEvent as ReactPointerEvent } from "react";
import { cn } from "@/lib/cn";

export interface RangeSliderProps {
  min: number;
  max: number;
  step: number;
  lo: number;
  hi: number;
  onChange: (lo: number, hi: number) => void;
  unit?: string;
  /** lo = 先变小（进入在左）；hi = 先变大（进入在右），决定手柄标签与箭头 */
  first?: "lo" | "hi";
  className?: string;
}

/**
 * 双滑块阈值选择器：两个手柄之间的区间用荧光绿填充并标注「迟滞区」。
 * 手柄标签（进入动作 / 计 1 次）随方向 first 交换，箭头跟着变。
 */
export function RangeSlider({
  min,
  max,
  step,
  lo,
  hi,
  onChange,
  unit = "",
  first = "lo",
  className,
}: RangeSliderProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<null | "lo" | "hi">(null);
  const latest = useRef({ lo, hi, min, max, step, onChange });
  latest.current = { lo, hi, min, max, step, onChange };

  useEffect(() => {
    const move = (e: globalThis.PointerEvent) => {
      const which = dragging.current;
      const track = trackRef.current;
      if (!which || !track) return;
      const rect = track.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      const { min, max, step, lo, hi, onChange } = latest.current;
      const raw = min + ratio * (max - min);
      const p = step.toString().split(".")[1]?.length ?? 0;
      const v = Number(Math.min(max, Math.max(min, raw)).toFixed(p));
      if (which === "lo") onChange(Math.min(v, hi - step), hi);
      else onChange(lo, Math.max(v, lo + step));
    };
    const up = () => {
      dragging.current = null;
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, []);

  const loPct = ((lo - min) / (max - min)) * 100;
  const hiPct = ((hi - min) / (max - min)) * 100;
  const decimals = step < 1 ? 2 : 0;
  const fmt = (v: number) => v.toFixed(decimals);

  const enterIsLo = first === "lo";
  const leftLabel = enterIsLo ? "进入动作" : "计 1 次";
  const rightLabel = enterIsLo ? "计 1 次" : "进入动作";

  const startDrag =
    (which: "lo" | "hi") => (e: ReactPointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
      dragging.current = which;
    };

  return (
    <div className={cn("select-none", className)}>
      <div className="mb-1.5 flex items-center justify-between text-[11px] text-text3">
        <span>
          {fmt(min)}
          {unit}
        </span>
        <span>
          {fmt(max)}
          {unit}
        </span>
      </div>

      <div ref={trackRef} className="relative h-7 touch-none">
        <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-full bg-surface2" />
        <div
          className="absolute top-1/2 h-3 -translate-y-1/2 rounded-full border border-accent/30 bg-accent/10"
          style={{ left: `${loPct}%`, width: `${hiPct - loPct}%` }}
        />
        {hiPct - loPct > 10 && (
          <span
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded bg-accent/15 px-1.5 text-[10px] leading-4 text-accent"
            style={{ left: `${(loPct + hiPct) / 2}%` }}
          >
            迟滞区
          </span>
        )}

        <div
          role="slider"
          tabIndex={0}
          aria-label={leftLabel}
          onPointerDown={startDrag("lo")}
          className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 cursor-grab rounded-full border-2 border-accent bg-surface1 shadow-md active:cursor-grabbing"
          style={{ left: `${loPct}%` }}
        />
        <div
          role="slider"
          tabIndex={0}
          aria-label={rightLabel}
          onPointerDown={startDrag("hi")}
          className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 cursor-grab rounded-full border-2 border-accent bg-surface1 shadow-md active:cursor-grabbing"
          style={{ left: `${hiPct}%` }}
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="flex flex-col rounded-[10px] border border-line1 bg-surface2 px-3 py-2">
          <span className="text-[11px] text-text3">↓ {leftLabel}</span>
          <span className="font-num text-lg leading-none text-text1 tabular-nums">
            {fmt(lo)}
            <span className="ml-1 text-xs text-text3">{unit}</span>
          </span>
        </div>
        <div className="flex flex-col items-end rounded-[10px] border border-line1 bg-surface2 px-3 py-2">
          <span className="text-[11px] text-text3">↑ {rightLabel}</span>
          <span className="font-num text-lg leading-none text-text1 tabular-nums">
            {fmt(hi)}
            <span className="ml-1 text-xs text-text3">{unit}</span>
          </span>
        </div>
      </div>
    </div>
  );
}