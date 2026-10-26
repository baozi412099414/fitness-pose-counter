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
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";
import type { WeeklyPoint } from "@/lib/types";

interface WeeklyBarChartProps {
  data?: WeeklyPoint[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

const tooltipStyle = {
  background: "#151922",
  border: "1px solid #232833",
  borderRadius: 10,
  fontSize: 12,
} as const;

export function WeeklyBarChart({
  data,
  isLoading,
  isError,
  onRetry,
}: WeeklyBarChartProps) {
  const avg =
    data && data.length > 0
      ? Math.round((data.reduce((s, d) => s + d.reps, 0) / data.length) * 10) / 10
      : 0;

  return (
    <Card
      title="周训练趋势"
      subtitle="近 8 周完成次数 · 虚线为均值"
      className="h-full"
    >
      {isLoading ? (
        <Skeleton className="h-[240px]" />
      ) : isError ? (
        <ErrorBanner message="趋势加载失败" onRetry={onRetry} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="暂无周趋势" description="完成训练后这里会显示趋势。" />
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#232833"
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
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#A3ACBA" }}
              itemStyle={{ color: "#F5F7FA" }}
              labelFormatter={(label) => `周起始 ${label}`}
              formatter={(value) => [`${value} 次`, "次数"]}
            />
            <ReferenceLine
              y={avg}
              stroke="#6C7686"
              strokeDasharray="4 4"
              label={{
                value: `均值 ${avg}`,
                fill: "#6C7686",
                fontSize: 11,
                position: "insideTopRight",
              }}
            />
            <Bar
              dataKey="reps"
              fill="#D6FF3F"
              radius={[4, 4, 0, 0]}
              maxBarSize={28}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}