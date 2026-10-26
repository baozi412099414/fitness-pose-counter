import type { Overview } from "@/lib/types";
import { gradeTone } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";

function Cell({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-surface1 px-5 py-4">
      <div className="text-xs uppercase tracking-[0.12em] text-text3">
        {label}
      </div>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

function NumberValue({ value, unit }: { value: number; unit: string }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className="font-num text-3xl leading-none text-text1">{value}</span>
      <span className="text-xs text-text3">{unit}</span>
    </span>
  );
}

export function KpiBar({
  data,
  loading,
  days,
}: {
  data?: Overview;
  loading: boolean;
  days: number;
}) {
  if (loading || !data) {
    return (
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line1 bg-line1 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-surface1 px-5 py-4">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="mt-2 h-7 w-24" />
            <Skeleton className="mt-2 h-2 w-20" />
          </div>
        ))}
      </div>
    );
  }

  const target = data.daily_goal_target ?? 0;
  const today = data.today_reps;
  const pct = target > 0 ? Math.min(100, Math.round((today / target) * 100)) : 0;
  const grade = data.avg_score_grade;

  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line1 bg-line1 lg:grid-cols-4">
      <Cell label="今日完成">
        <NumberValue value={today} unit="次" />
        {target > 0 ? (
          <div className="mt-2">
            <div className="h-1 overflow-hidden rounded-full bg-surface2">
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-text3">
              目标 {target} 次 · {pct}%
            </p>
          </div>
        ) : (
          <p className="mt-2 text-[11px] text-text3">未设置目标</p>
        )}
      </Cell>

      <Cell label="本周总次数">
        <NumberValue value={data.week_reps} unit="次" />
        <p className="mt-2 text-[11px] text-text3">
          {data.week_sessions} 次训练
        </p>
      </Cell>

      <Cell label="平均评分">
        {data.avg_score == null ? (
          <span className="font-num text-3xl leading-none text-text3">—</span>
        ) : (
          <span className="flex items-baseline gap-2">
            <span className="font-num text-3xl leading-none text-text1">
              {data.avg_score}
            </span>
            <span className="text-xs text-text3">分</span>
            {grade && <Badge tone={gradeTone(grade)}>{grade}</Badge>}
          </span>
        )}
        <p className="mt-2 text-[11px] text-text3">
          {data.avg_score == null ? "暂无评分" : `近 ${days} 天已完成动作`}
        </p>
      </Cell>

      <Cell label="累计训练">
        <NumberValue value={data.total_sessions} unit="次" />
        <p className="mt-2 text-[11px] text-text3">全部历史训练</p>
      </Cell>
    </div>
  );
}
