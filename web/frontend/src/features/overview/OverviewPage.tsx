import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { client } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useUser } from "@/providers/UserProvider";
import type {
  Action,
  DailyGoal,
  DayBlock,
  Overview,
  Session,
  TopError,
  WeeklyPoint,
} from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Skeleton } from "@/components/ui/Skeleton";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "夜深了";
  if (h < 11) return "早上好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

function todayLabel(): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
}

function ErrorBanner({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-card border border-coral/30 bg-coral/[0.08] px-4 py-3">
      <span className="text-sm text-coral">数据加载失败</span>
      <Button variant="secondary" onClick={onRetry}>
        重试
      </Button>
    </div>
  );
}

function GreetingRow() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-sm text-text3">
          {greeting()} · {todayLabel()}
        </p>
        <h1 className="mt-1 text-2xl font-medium text-text1">今天练什么？</h1>
      </div>
      <Button variant="primary" onClick={() => navigate("/train")}>
        开始训练
      </Button>
    </div>
  );
}

function TrainingTrack({ days }: { days: DayBlock[] }) {
  return (
    <div className="mt-6 border-t border-line1 pt-4">
      <span className="text-xs uppercase tracking-[0.12em] text-text3">
        近 7 天
      </span>
      <div className="mt-3 flex gap-2">
        {days.map((d) => (
          <div
            key={d.date}
            className="flex flex-1 flex-col items-center gap-1.5"
          >
            <div
              className={cn(
                "h-6 w-full rounded-[6px]",
                d.reps > 0 ? "bg-accent" : "bg-surface2",
              )}
            />
            <span className="text-[10px] text-text3">{d.date}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Hero({ data }: { data?: Overview }) {
  const target = data?.daily_goal_target ?? null;
  const done = data?.daily_goal_done ?? 0;
  const pct =
    target && target > 0 ? Math.min(100, Math.round((done / target) * 100)) : 0;
  const remaining = target ? Math.max(0, target - done) : 0;

  const diff =
    data && data.yesterday_reps > 0 ? data.today_reps - data.yesterday_reps : null;

  return (
    <Card className="h-full" bodyClassName="flex h-full flex-col">
      {!data ? (
        <>
          <Skeleton className="h-4 w-20" />
          <Skeleton className="mt-4 h-[100px] w-48" />
          <Skeleton className="mt-6 flex-1" />
        </>
      ) : (
        <>
          <span className="text-xs uppercase tracking-[0.12em] text-text3">
            今日完成
          </span>
          <div className="font-num mt-2 text-[clamp(80px,9vw,140px)] leading-none text-text1">
            {data.today_reps}
          </div>

          <div className="mt-4 flex items-center gap-6">
            {target ? (
              <>
                <ProgressRing value={pct} size={96} label="目标" />
                <div className="text-sm">
                  {remaining > 0 ? (
                    <p className="text-text2">还差 {remaining} 次</p>
                  ) : (
                    <p className="text-mint">已达成今日目标</p>
                  )}
                  {diff !== null && (
                    <p
                      className={cn(
                        "mt-1 font-mono text-[13px]",
                        diff >= 0 ? "text-mint" : "text-coral",
                      )}
                    >
                      较昨日 {diff >= 0 ? "+" : ""}
                      {diff}
                    </p>
                  )}
                </div>
              </>
            ) : (
              <Link
                to="/settings"
                className="flex h-[96px] w-[96px] flex-col items-center justify-center rounded-full border-2 border-dashed border-line2 text-center text-xs leading-tight text-text3 transition-colors hover:border-accent"
              >
                未设置目标
                <br />
                去设置
              </Link>
            )}
          </div>

          <TrainingTrack days={data.last_7_days} />
        </>
      )}
    </Card>
  );
}

function ActionGlyph() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="rgb(var(--accent-rgb))"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="5" r="2.5" />
      <path d="M12 7.5V14" />
      <path d="M12 10l-4-1.5" />
      <path d="M12 10l4-1.5" />
      <path d="M12 14l-4 4" />
      <path d="M12 14l4 4" />
    </svg>
  );
}

function QuickStart({ actions }: { actions?: Action[] }) {
  return (
    <Card title="快速开始" subtitle="选择动作进入训练" className="h-full">
      {!actions ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {actions.map((a) => (
              <Link
                key={a.id}
                to={`/train/${a.id}`}
                className="flex flex-col rounded-[12px] border border-line1 bg-surface2 p-4 transition-colors duration-[120ms] hover:border-accent"
              >
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-[10px] bg-surface3">
                  <ActionGlyph />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-medium text-text1">
                    {a.name}
                  </span>
                  <Badge tone={a.camera_side === "side" ? "cyan" : "amber"}>
                    {a.camera_side === "side" ? "侧方" : "正面"}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-text3">{a.signal}</p>
                <p className="mt-0.5 text-xs text-text3">
                  {a.rule_count} 条规则 · {a.thresholds}
                </p>
              </Link>
            ))}
          </div>
          <p className="mt-4 text-xs text-text3">
            没有摄像头？用演示数据回放（后续支持）。
          </p>
        </>
      )}
    </Card>
  );
}

function WeeklyTrend({ data }: { data?: WeeklyPoint[] }) {
  return (
    <Card title="本周趋势" subtitle="近 8 周完成次数" className="h-full">
      {!data ? (
        <Skeleton className="h-[220px]" />
      ) : data.length === 0 ? (
        <EmptyState title="还没有训练记录" description="完成一次训练后这里会显示趋势。" />
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgb(var(--line-1-rgb))"
              vertical={false}
            />
            <XAxis
              dataKey="week_start"
              tick={{ fill: "#6C7686", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#6C7686", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{
                background: "#151922",
                border: "1px solid #232833",
                borderRadius: 10,
                fontSize: 12,
              }}
              labelStyle={{ color: "#A3ACBA" }}
              itemStyle={{ color: "#F5F7FA" }}
              labelFormatter={(label) => `周起始 ${label}`}
              formatter={(value) => `${value} 次`}
            />
            <Bar
              dataKey="reps"
              fill="url(#trendGrad)"
              radius={[4, 4, 0, 0]}
              maxBarSize={28}
            />
            <defs>
              <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#D6FF3F" stopOpacity={1} />
                <stop offset="100%" stopColor="#D6FF3F" stopOpacity={0} />
              </linearGradient>
            </defs>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

function GoalsAndErrors({
  goals,
  errors,
}: {
  goals?: DailyGoal[];
  errors?: TopError[];
}) {
  return (
    <div className="flex h-full flex-col gap-4">
      <Card title="目标进度" subtitle="今日最多显示 3 项">
        {!goals ? (
          <div className="space-y-3">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : goals.length === 0 ? (
          <p className="text-sm text-text3">还没有设置目标。</p>
        ) : (
          goals.slice(0, 3).map((g) => {
            const p =
              g.target > 0
                ? Math.min(100, Math.round((g.done / g.target) * 100))
                : 0;
            return (
              <div key={g.action_id} className="mb-3 last:mb-0">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text1">{g.action_name}</span>
                  <span className="font-mono text-text3">
                    {g.done}/{g.target}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface2">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${p}%` }}
                  />
                </div>
              </div>
            );
          })
        )}
      </Card>

      <Card title="最常犯的错" subtitle="近 30 天 top 3">
        {!errors ? (
          <div className="space-y-3">
            <Skeleton className="h-7" />
            <Skeleton className="h-7" />
            <Skeleton className="h-7" />
          </div>
        ) : errors.length === 0 ? (
          <p className="text-sm text-text3">动作很标准，暂无常见错误。</p>
        ) : (
          errors.slice(0, 3).map((e, i) => (
            <Link
              key={i}
              to="/data?tab=errors"
              className="flex items-center justify-between gap-3 rounded-[8px] px-2 py-2 text-sm transition-colors hover:bg-surface2"
            >
              <span className="truncate text-text1">
                {i + 1}. {e.tip}
              </span>
              <span className="shrink-0 font-mono text-coral">{e.count}</span>
            </Link>
          ))
        )}
      </Card>
    </div>
  );
}

function RecentSessions({ sessions }: { sessions?: Session[] }) {
  return (
    <Card title="最近训练" subtitle="最近 5 次" className="h-full">
      {!sessions ? (
        <Skeleton className="h-[200px]" />
      ) : sessions.length === 0 ? (
        <EmptyState title="还没有训练记录" description="完成一次训练后这里会显示记录。" />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.08em] text-text3">
              <th className="pb-2 font-medium">时间</th>
              <th className="pb-2 font-medium">动作</th>
              <th className="pb-2 text-right font-medium">次数</th>
              <th className="pb-2 text-right font-medium">评分</th>
              <th className="pb-2 text-right font-medium">错误</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr
                key={i}
                className="border-t border-line1 transition-colors hover:bg-surface2/50"
              >
                <td className="py-2.5 font-mono text-text2">{s.time}</td>
                <td className="py-2.5 text-text1">{s.action_name}</td>
                <td className="py-2.5 text-right font-num text-text1">
                  {s.reps}
                </td>
                <td className="py-2.5 text-right font-num text-text1">
                  {s.score ?? "—"}
                </td>
                <td className="py-2.5 text-right font-num text-coral">
                  {s.errors}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export function OverviewPage() {
  const { activeUserId } = useUser();
  const overview = useQuery({
    queryKey: ["overview", activeUserId],
    queryFn: () => client.getOverview(activeUserId),
  });
  const actions = useQuery({
    queryKey: ["actions"],
    queryFn: client.getActions,
  });

  return (
    <div className="flex flex-col gap-6">
      <GreetingRow />

      {overview.isError && <ErrorBanner onRetry={() => overview.refetch()} />}
      {actions.isError && <ErrorBanner onRetry={() => actions.refetch()} />}

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-5">
          <Hero data={overview.data} />
        </div>
        <div className="col-span-12 lg:col-span-7">
          <QuickStart actions={actions.data} />
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8">
          <WeeklyTrend data={overview.data?.weekly_trend} />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <GoalsAndErrors
            goals={overview.data?.goals}
            errors={overview.data?.top_errors}
          />
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8">
          <RecentSessions sessions={overview.data?.recent_sessions} />
        </div>
      </div>

      <p className="text-center text-xs text-text3">
        数据来自本地 data/users，视频帧不落盘。
      </p>
    </div>
  );
}