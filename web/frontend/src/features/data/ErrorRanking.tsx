import { Check } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import type { TopError } from "@/lib/types";

interface ErrorRankingProps {
  data?: TopError[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  activeError?: string;
  onSelect: (tip: string) => void;
}

export function ErrorRanking({
  data,
  isLoading,
  isError,
  onRetry,
  activeError,
  onSelect,
}: ErrorRankingProps) {
  return (
    <Card title="错误排行" subtitle="按出现次数排序 · 点击筛选" className="h-full">
      {isLoading ? (
        <div className="space-y-5">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-8" />
          ))}
        </div>
      ) : isError ? (
        <ErrorBanner message="错误排行加载失败" onRetry={onRetry} />
      ) : !data || data.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-mint/10">
            <Check size={22} className="text-mint" />
          </div>
          <p className="text-sm text-text2">动作很标准，暂无常见错误</p>
        </div>
      ) : (
        <ParetoList data={data} activeError={activeError} onSelect={onSelect} />
      )}
    </Card>
  );
}

function ParetoList({
  data,
  activeError,
  onSelect,
}: {
  data: TopError[];
  activeError?: string;
  onSelect: (tip: string) => void;
}) {
  const max = data[0]?.count ?? 1;
  const total = data.reduce((s, d) => s + d.count, 0);
  let cum = 0;

  return (
    <ul className={cn("flex flex-col gap-1")}>
      {data.map((e, i) => {
        cum += e.count;
        const cumPct = total > 0 ? Math.round((cum / total) * 100) : 0;
        const isActive = activeError === e.tip;
        return (
          <li key={e.tip}>
            <button
              type="button"
              onClick={() => onSelect(e.tip)}
              className={cn(
                "w-full rounded-[10px] px-3 py-2.5 text-left transition-colors hover:bg-surface2",
                isActive && "bg-surface2 ring-1 ring-accent/40",
              )}
            >
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-xs text-text3">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate text-sm text-text1">
                  {e.tip}
                </span>
                <span className="shrink-0 font-mono text-sm text-coral">
                  {e.count}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2 pl-[18px]">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface2">
                  <div
                    className="h-full rounded-full bg-coral/80"
                    style={{ width: `${(e.count / max) * 100}%` }}
                  />
                </div>
                <span className="w-11 text-right font-mono text-[11px] text-text3">
                  {cumPct}%
                </span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}