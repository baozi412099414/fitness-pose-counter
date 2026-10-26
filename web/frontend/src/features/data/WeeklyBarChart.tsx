import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { WeeklyPoint } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";

const TOOLTIP_STYLE = {
  background: "#151922",
  border: "1px solid #232833",
  borderRadius: 10,
  fontSize: 12,
} as const;

export function WeeklyBarChart({
  data,
  loading,
}: {
  data?: WeeklyPoint[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card title="每周训练量" subtitle="近 8 周 · 虚线为平均值">
        <Skeleton className="h-[240px]" />
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card title="每周训练量" subtitle="近 8 周 · 虚线为平均值">
        <EmptyState
          title="还没有训练记录"
          description="完成一次训练后，这里会出现每周训练量。"
        />
      </Card>
    );
  }

  const avg = Math.round(
    data.reduce((sum, p) => sum + p.reps, 0) / data.length,
  );

  return (
    <Card title="每周训练量" subtitle="近 8 周 · 虚线为平均值">
      <div className="h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#1B202A" />
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
              width={44}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: "#A3ACBA" }}
              itemStyle={{ color: "#F5F7FA" }}
              labelFormatter={(label) => `周起始 ${label}`}
              formatter={(value) => [`${value} 次`, "训练量"]}
            />
            <ReferenceLine y={avg} stroke="#6C7686" strokeDasharray="4 4" />
            <Bar
              dataKey="reps"
              fill="#D6FF3F"
              radius={[3, 3, 0, 0]}
              maxBarSize={36}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-right text-[11px] text-text3">
        平均 {avg} 次 / 周
      </p>
    </Card>
  );
}
