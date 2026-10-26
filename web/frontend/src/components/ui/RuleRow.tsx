import { cn } from "@/lib/cn";

export type RuleRowState = "fail" | "pass" | "invisible" | "unchecked";

interface Meta {
  dot: string;
  value: string;
  bar: string;
  label: string;
}

const META: Record<RuleRowState, Meta> = {
  fail: {
    dot: "bg-coral",
    value: "text-coral",
    bar: "bg-coral",
    label: "未达标",
  },
  pass: {
    dot: "bg-mint",
    value: "text-mint",
    bar: "bg-mint",
    label: "达标",
  },
  invisible: {
    dot: "bg-text3",
    value: "text-text3",
    bar: "bg-surface3",
    label: "不可见",
  },
  unchecked: {
    dot: "bg-line2",
    value: "text-text3",
    bar: "bg-surface3",
    label: "未参与判定",
  },
};

export interface RuleRowProps {
  name: string;
  value: string;
  limit: string;
  state: RuleRowState;
  progress: number; // 0~1
  className?: string;
}

export function RuleRow({
  name,
  value,
  limit,
  state,
  progress,
  className,
}: RuleRowProps) {
  const meta = META[state];
  const clamped = Math.min(1, Math.max(0, progress));

  return (
    <div
      className={cn("flex flex-col gap-2 rounded-[10px] bg-surface2 px-3.5 py-3", className)}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
          <span className="truncate text-sm text-text1">{name}</span>
        </div>
        <div className="flex shrink-0 items-baseline gap-1.5 font-mono text-[13px]">
          <span className={cn(meta.value)}>{value}</span>
          <span className="text-text3">{limit}</span>
        </div>
      </div>
      <div className="flex items-center gap-2.5">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface1">
          <div
            className={cn("h-full rounded-full", meta.bar)}
            style={{ width: `${clamped * 100}%` }}
          />
        </div>
        <span className="w-16 shrink-0 text-right text-xs text-text3">
          {meta.label}
        </span>
      </div>
    </div>
  );
}