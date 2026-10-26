import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import type { BadgeTone } from "./Badge";

const bars: Record<BadgeTone, string> = {
  neutral: "bg-line2",
  accent: "bg-accent",
  mint: "bg-mint",
  amber: "bg-amber",
  coral: "bg-coral",
  cyan: "bg-cyan",
};

export interface ToastProps {
  message: ReactNode;
  tone?: BadgeTone;
  onDismiss: () => void;
  duration?: number;
  className?: string;
}

/**
 * 右上角 Toast，默认 3s 消失。
 * 注意：训练过程中不要用 toast 报动作错误（改用 TipBanner）。
 */
export function Toast({
  message,
  tone = "neutral",
  onDismiss,
  duration = 3000,
  className,
}: ToastProps) {
  useEffect(() => {
    const t = setTimeout(onDismiss, duration);
    return () => clearTimeout(t);
  }, [onDismiss, duration]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "fixed right-5 top-5 z-50 flex items-center gap-3 rounded-card border border-line1 bg-surface1 py-3 pl-4 pr-2 shadow-xl",
        className,
      )}
    >
      <span className={cn("h-4 w-1 rounded-full", bars[tone])} />
      <span className="text-sm text-text1">{message}</span>
      <button
        type="button"
        aria-label="关闭"
        onClick={onDismiss}
        className="flex h-7 w-7 items-center justify-center rounded-[6px] text-text3 transition-colors hover:bg-surface2 hover:text-text1"
      >
        <X size={14} />
      </button>
    </div>
  );
}