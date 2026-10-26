import type { HistoryRecord, HistoryResult } from "@/lib/types";
import { formatDuration, gradeOf, gradeTone } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";

function ErrorChips({ errors }: { errors: string[] }) {
  if (errors.length === 0) {
    return <span className="text-xs text-text3">—</span>;
  }
  return (
    <div className="flex flex-wrap items-center gap-1">
      {errors.slice(0, 2).map((tip) => (
        <Badge key={tip} tone="coral">
          {tip.length > 8 ? `${tip.slice(0, 8)}…` : tip}
        </Badge>
      ))}
      {errors.length > 2 && (
        <Badge tone="neutral">+{errors.length - 2}</Badge>
      )}
    </div>
  );
}

export function HistoryTable({
  data,
  loading,
  isError,
  onRetry,
  onSelect,
  page,
  pageSize,
  onPageChange,
}: {
  data?: HistoryResult;
  loading: boolean;
  isError: boolean;
  onRetry: () => void;
  onSelect: (record: HistoryRecord) => void;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <Card
      title="历史记录"
      subtitle={loading ? "加载中…" : `时间范围内共 ${total} 条`}
      className="h-full"
    >
      {isError ? (
        <ErrorBanner onRetry={onRetry} />
      ) : loading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-11" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="还没有训练记录"
          description="换个时间范围或动作筛选试试，或者先完成一次训练。"
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.08em] text-text3">
                  <th className="pb-2 font-medium">时间</th>
                  <th className="pb-2 font-medium">动作</th>
                  <th className="pb-2 text-right font-medium">次数</th>
                  <th className="pb-2 text-right font-medium">组数</th>
                  <th className="pb-2 font-medium">评分</th>
                  <th className="pb-2 text-right font-medium">时长</th>
                  <th className="pb-2 font-medium">错误</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => {
                  const grade = gradeOf(r.score);
                  return (
                    <tr
                      key={r.id}
                      tabIndex={0}
                      onClick={() => onSelect(r)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(r);
                        }
                      }}
                      className="cursor-pointer border-t border-line1 outline-none transition-colors hover:bg-surface2/50 focus-visible:bg-surface2/50"
                    >
                      <td className="whitespace-nowrap py-2.5 font-mono text-text2">
                        {r.time}
                      </td>
                      <td className="whitespace-nowrap py-2.5 text-text1">
                        {r.action_name}
                      </td>
                      <td className="py-2.5 text-right font-num text-text1">
                        {r.reps}
                      </td>
                      <td className="py-2.5 text-right font-num text-text2">
                        {r.sets}
                      </td>
                      <td className="py-2.5">
                        {r.score == null ? (
                          <span className="text-text3">—</span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="font-num text-text1">
                              {r.score}
                            </span>
                            {grade && (
                              <Badge tone={gradeTone(grade)}>{grade}</Badge>
                            )}
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap py-2.5 text-right text-xs text-text2">
                        {formatDuration(r.duration)}
                      </td>
                      <td className="py-2.5">
                        <ErrorChips errors={r.errors} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-text3">
            <span>
              第 {page + 1} / {totalPages} 页 · 共 {total} 条
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                className="h-8 px-3 text-xs"
                disabled={page <= 0}
                onClick={() => onPageChange(page - 1)}
              >
                上一页
              </Button>
              <Button
                variant="secondary"
                className="h-8 px-3 text-xs"
                disabled={page + 1 >= totalPages}
                onClick={() => onPageChange(page + 1)}
              >
                下一页
              </Button>
            </div>
          </div>
        </>
      )}
    </Card>
  );
}
