import { Check } from "lucide-react";
import type { TopError } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

export function ErrorRanking({
  errors,
  loading,
  activeError,
  onSelect,
}: {
  errors?: TopError[];
  loading: boolean;
  activeError?: string;
  onSelect: (tip: string) => void;
}) {
  return (
    <Card
      title="最常犯的错"
      subtitle="点击一条可筛选下方历史记录"
      className="h-full"
    >
      {loading ? (
        <div className="space-y-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i}>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="mt-2 h-2 w-full" />
            </div>
          ))}
        </div>
      ) : !errors || errors.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-mint/15 text-mint">
            <Check size={18} />
          </span>
          <p className="text-sm text-text2">最近没有检测到动作变形</p>
          <p className="text-xs text-text3">保持标准动作，继续加油。</p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {errors.slice(0, 8).map((e) => {
            const max = errors[0]?.count || 1;
            const pct = Math.max(4, Math.round((e.count / max) * 100));
            const active = activeError === e.tip;
            return (
              <button
                key={e.tip}
                type="button"
                onClick={() => onSelect(e.tip)}
                className={cn(
                  "block w-full rounded-[8px] px-2 py-1.5 text-left transition-colors",
                  active ? "bg-surface2" : "hover:bg-surface2/60",
                )}
              >
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate text-text1">{e.tip}</span>
                  <span className="shrink-0 font-mono text-coral">
                    {e.count}
                  </span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface2">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-coral to-coral/40"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
