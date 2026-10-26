import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";
import { gradeTone } from "@/lib/format";
import type { Overview } from "@/lib/types";

interface KpiBarProps {
  data?: Overview;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

function Tile({
  label,
  value,
  footer,
}: {
  label: string;
  value: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <Card bodyClassName="flex h-full flex-col justify-between gap-3">
      <span className="text-xs uppercase tracking-[0.12em] text-text3">
        {label}
      </span>
      <span className="font-num text-[40px] leading-none text-text1">
        {value}
      </span>
      <div className="flex min-h-5 items-center">{footer ?? null}</div>
    </Card>
  );
}

export function KpiBar({ data, isLoading, isError, onRetry }: KpiBarProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className="h-full">
            <Skeleton className="h-20" />
          </Card>
        ))}
      </div>
    );
  }

  if (isError) {
    return <ErrorBanner message="汇总数据加载失败" onRetry={onRetry} />;
  }

  const d = data!;
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Tile label="本周训练次数" value={d.week_reps} />
      <Tile label="本周训练场次" value={d.week_sessions} />
      <Tile
        label="累计训练"
        value={d.total_sessions}
        footer={<span className="text-[13px] text-text3">全量累计</span>}
      />
      <Tile
        label="平均评分"
        value={d.avg_score ?? "—"}
        footer={
          d.avg_score_grade ? (
            <Badge tone={gradeTone(d.avg_score_grade)}>
              {d.avg_score_grade}
            </Badge>
          ) : (
            <span className="text-[13px] text-text3">近 14 天</span>
          )
        }
      />
    </div>
  );
}