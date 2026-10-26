import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type BadgeTone = "neutral" | "accent" | "mint" | "amber" | "coral" | "cyan";

const tones: Record<BadgeTone, string> = {
  neutral: "bg-surface2 text-text2 border-line1",
  accent: "bg-accent/10 text-accent border-accent/30",
  mint: "bg-mint/10 text-mint border-mint/30",
  amber: "bg-amber/10 text-amber border-amber/30",
  coral: "bg-coral/10 text-coral border-coral/30",
  cyan: "bg-cyan/10 text-cyan border-cyan/30",
};

export interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs leading-5",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}