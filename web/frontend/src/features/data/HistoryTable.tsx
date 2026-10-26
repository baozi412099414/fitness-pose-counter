import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDuration, gradeOf, gradeTone } from "@/lib/format";
import type { HistoryRecord } from "@/lib/types";

export const HISTORY_PAGE_SIZE = 10;

interface HistoryTableProps {
  items?: HistoryRecord[];
  total: number;
  page: number;
  onPageChange: (page: number) => void;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onSelect: (record: HistoryRecord) => void;
  onExport: () => void;
  isExporting: boolean;
  filtered: boolean;
}

export function HistoryTable({
  items,
  total,
  page,
  onPageChange,
  isLoading,
  isError,
  onRetry,
  onSelect,
  onExport,
  isExporting,
  filtered,
}: HistoryTableProps) {
  const pageCount = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE));

  let body: ReactNode;
  if (isError) {
    body = <ErrorBanner message="历史记录加载失败" onRetry={onRetry} />;
  } else if (isLoading && !items) {
    body = (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    );
  } else if (!items || items.length === 0) {
    body = (
      <EmptyState
        title="暂无训练记录"
        description={
          filtered
            ? "当前筛选条件下没有匹配的记录，试试调整动作或清除错误筛选。"
            : "完成一次训练后，这里会显示历史记录。"
        }
      />
    );
  } else {
    body = (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.08em] text-text3">
              <th className="pb-2 pr-3 font-medium">时间</th>
              <th className="pb-2 pr-3 font-medium">动作</th>
              <th className="pb-2 pr-3 text-right font-medium">次数</th>
              <th className="pb-2 pr-3 text-right font-medium">组数</th>
              <th className="pb-2 pr-3 font-medium">评分</th>
              <th className="pb-2 pr-3 text-right font-medium">时长</th>
              <th className="pb-2 font-medium">错误</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => {
              const grade = gradeOf(r.score);
              return (
                <tr
                  key={r.id}
                  onClick={() => onSelect(r)}
                  className="cursor-pointer border-t border-line1 transition-colors hover:bg-surface2/50"
                >
                  <td className="whitespace-nowrap py-2.5 pr-3 font-mono text-text2">
                    {r.time}
                  </td>
                  <td className="whitespace-nowrap py-2.5 pr-3 text-text1">
                    {r.action_name}
                  </td>
                  <td className="py-2.5 pr-3 text-right font-num text-text1">
                    {r.reps}
                  </td>
                  <td className="py-2.5 pr-3 text-right font-num text-text1">
                    {r.sets}
                  </td>
                  <td className="py-2.5 pr-3">
                    {r.score == null ? (
                      <span className="text-text3">—</span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5">
                        <span className="font-num text-text1">{r.score}</span>
                        {grade && (
                          <Badge tone={gradeTone(grade)}>{grade}</Badge>
                        )}
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-2.5 pr-3 text-right text-xs text-text2">
                    {formatDuration(r.duration)}
                  </td>
                  <td className="py-2.5">
                    {r.errors.length === 0 ? (
                      <span className="text-text3">—</span>
                    ) : (
                      <div className="flex flex-wrap items-center gap-1">
                        {r.errors.slice(0, 2).map((tip) => (
                          <Badge key={tip} tone="coral">
                            {tip.length > 8 ? `${tip.slice(0, 8)}…` : tip}
                          </Badge>
                        ))}
                        {r.errors.length > 2 && (
                          <Badge tone="neutral">
                            +{r.errors.length - 2}
                          </Badge>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <Card
      title="训练历史"
      subtitle={`共 ${total} 条记录`}
      className="h-full"
      actions={
        <Button
          variant="secondary"
          onClick={onExport}
          disabled={isExporting || total === 0}
          className="h-8 px-3 text-xs"
        >
          <Download size={14} />
          {isExporting ? "导出中…" : "导出 CSV"}
        </Button>
      }
    >
      {body}

      {!isError && total > 0 && (
        <div className="mt-4 flex items-center justify-between border-t border-line1 pt-3">
          <span className="text-xs text-text3">
            第 {page} / {pageCount} 页 · 共 {total} 条
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="h-8 px-3 text-xs"
            >
              <ChevronLeft size={14} />
              上一页
            </Button>
            <Button
              variant="secondary"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= pageCount}
              className="h-8 px-3 text-xs"
            >
              下一页
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}