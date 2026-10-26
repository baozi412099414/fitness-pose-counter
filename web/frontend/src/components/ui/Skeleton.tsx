import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-skeleton rounded-[10px] bg-surface2",
        className,
      )}
    />
  );
}