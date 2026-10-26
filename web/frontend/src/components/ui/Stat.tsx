import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface StatProps {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  deltaTone?: "mint" | "coral";
  hint?: ReactNode;
  className?: string;
}

export function Stat({
  label,
  value,
  delta,
  deltaTone = "mint",
  hint,
  className,
}: StatProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-xs uppercase tracking-[0.12em] text-text3">
        {label}
      </span>
      <span className="font-num text-[48px] leading-none text-text1">
        {value}
      </span>
      {delta && (
        <span
          className={cn(
            "font-mono text-[13px]",
            deltaTone === "mint" ? "text-mint" : "text-coral",
          )}
        >
          {delta}
        </span>
      )}
      {hint && <span className="text-[13px] text-text3">{hint}</span>}
    </div>
  );
}