import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ScoreTrendPoint } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";

const TOOLTIP_STYLE = {
  background: "#151922",
  border: "1px solid #232833",
  borderRadius: 10,
  fontSize: 12,
} as const;

export function ScoreTrendChart({
  data,
  loading,
  days,
}: {
  data?: ScoreTrendPoint[];
  loading: boolean;
  days: number;
}) {
  const subtitle = `近 ${days} 天 · 无记录的天断开`;

  if (loading) {
    return (
      <Card title="评分趋势" subtitle={subtitle}>
        <Skeleton className="h-[240px]" />
      </Card>
    );
  }

  const hasScore = !!data?.some((p) => p.score != null);
  if (!data || data.length === 0 || !hasScore) {
    return (
      <Card title="评分趋势" subtitle={subtitle}>
        <EmptyState
          title="暂无评分记录"
          description="完成一次带评分的动作后，这里会出现曲线。"
        />
      </Card>
    );
  }

  return (
    <Card title="评分趋势" subtitle={subtitle}>
      <div className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#1B202A" />
            <XAxis
              dataKey="date"
              tick={{ fill: "#6C7686", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              minTickGap={16}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 60, 75, 90, 100]}
              tick={{ fill: "#6C7686", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={36}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: "#A3ACBA" }}
              itemStyle={{ color: "#F5F7FA" }}
              labelFormatter={(label) => `日期 ${label}`}
              formatter={(value) =>
                value == null ? "无记录" : [`${value} 分`, "评分"]
              }
            />
            <ReferenceLine y={60} stroke="#3A4150" strokeDasharray="3 3" />
            <ReferenceLine y={75} stroke="#3A4150" strokeDasharray="3 3" />
            <ReferenceLine y={90} stroke="#3A4150" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#6FE3FF"
              strokeWidth={2}
              dot={{ r: 2.5, fill: "#6FE3FF", strokeWidth: 0 }}
              activeDot={{ r: 4 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-right text-[11px] text-text3">
        参考线 60 / 75 / 90 分
      </p>
    </Card>
  );
}
