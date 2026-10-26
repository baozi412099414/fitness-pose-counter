import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-dashed border-line2 bg-surface1/40 px-6 py-12 text-center",
        className,
      )}
    >
      {/* 线框示意图形 */}
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-[14px] border border-line1">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="rgb(var(--text-3-rgb))"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="3" y="3" width="18" height="18" rx="4" />
          <path d="M3 9h18" />
          <path d="M9 21V9" />
        </svg>
      </div>
      <p className="text-base text-text1">{title}</p>
      {description && (
        <p className="mt-1.5 max-w-sm text-[13px] text-text3">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}