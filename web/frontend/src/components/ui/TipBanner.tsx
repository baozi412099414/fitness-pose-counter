import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TipBannerProps {
  children: ReactNode;
  className?: string;
}

/**
 * 训练中的动作提示：左侧 3px coral 竖条 + 8% 深红底，一次只显示一条。
 */
export function TipBanner({ children, className }: TipBannerProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-l-[3px] border-coral bg-coral/[0.08] px-4 py-3",
        className,
      )}
    >
      <span className="text-lg leading-snug text-text1">{children}</span>
    </div>
  );
}