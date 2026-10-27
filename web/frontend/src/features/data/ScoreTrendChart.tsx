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
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ScoreTrendPoint } from "@/lib/types";

interface ScoreTrendChartProps {
  data?: ScoreTrendPoint[];
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

export function ScoreTrendChart({
  data,
  isLoading,
  isError,
  onRetry,
}: ScoreTrendChartProps) {
  return (
    <Card
      title="评分趋势"
      subtitle="近 14 天平均评分 · 断点为无记录"
      className="h-full"
    >
      {isLoading ? (
        <Skeleton className="h-[240px]" />
      ) : isError ? (
        <ErrorBanner message="评分趋势加载失败" onRetry={onRetry} />
      ) : !data ||
        data.length === 0 ||
        data.every((point) => point.score == null) ? (
        <EmptyState title="暂无评分" description="完成训练后这里会显示评分趋势。" />
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart
            data={data}
            margin={{ top: 12, right: 16, left: 0, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#232833"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: "#6C7686", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 20, 40, 60, 80, 100]}
              tick={{ fill: "#6C7686", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={34}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#A3ACBA" }}
              itemStyle={{ color: "#F5F7FA" }}
              formatter={(value) =>
                value == null ? "无记录" : `${value} 分`
              }
            />
            <ReferenceLine
              y={90}
              stroke="#45E0A8"
              strokeDasharray="4 4"
              label={{ value: "优秀", fill: "#45E0A8", fontSize: 11, position: "insideTopRight" }}
            />
            <ReferenceLine
              y={75}
              stroke="#6FE3FF"
              strokeDasharray="4 4"
              label={{ value: "良好", fill: "#6FE3FF", fontSize: 11, position: "insideTopRight" }}
            />
            <ReferenceLine
              y={60}
              stroke="#FFB454"
              strokeDasharray="4 4"
              label={{ value: "及格", fill: "#FFB454", fontSize: 11, position: "insideTopRight" }}
            />
            <Line
              type="linear"
              dataKey="score"
              stroke="#6FE3FF"
              strokeWidth={2}
              dot={{ r: 3, fill: "#6FE3FF", strokeWidth: 0 }}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}