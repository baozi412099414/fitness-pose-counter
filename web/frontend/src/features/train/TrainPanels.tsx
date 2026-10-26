import { ArrowRight, Check, RotateCcw, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatDuration, gradeTone } from "@/lib/format";
import type { Grade } from "@/lib/types";
import type { TrainCheckState, TrainSummary } from "./types";

const GRADE_COLOR: Record<Grade, string> = {
  优秀: "#45E0A8",
  良好: "#6FE3FF",
  及格: "#FFB454",
  待改进: "#FF6B5C",
};

export function ScoreRing({
  score,
  grade,
}: {
  score: number | null;
  grade: Grade | null;
}) {
  const value = score ?? 0;
  const color = grade ? GRADE_COLOR[grade] : "#3A4150";
  const circumference = 2 * Math.PI * 44;
  const dash = (value / 100) * circumference;

  return (
    <div className="relative flex h-[132px] w-[132px] items-center justify-center">
      <svg viewBox="0 0 120 120" className="h-[120px] w-[120px] -rotate-90">
        <circle
          cx="60"
          cy="60"
          r="44"
          fill="none"
          stroke="#232833"
          strokeWidth="8"
        />
        <circle
          cx="60"
          cy="60"
          r="44"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-num text-3xl leading-none text-text1">
          {score == null ? "—" : score}
        </span>
        {grade ? (
          <Badge tone={gradeTone(grade)} className="mt-1">
            {grade}
          </Badge>
        ) : (
          <span className="mt-1 text-[11px] text-text3">待评分</span>
        )}
      </div>
    </div>
  );
}

export function ChecksPanel({
  checks,
  pending,
}: {
  checks: TrainCheckState[];
  pending: boolean;
}) {
  return (
    <ul className="flex flex-col gap-2">
      {checks.map((check) => (
        <li
          key={check.key}
          className="flex items-center justify-between gap-3 rounded-[8px] border border-line1 bg-surface2/40 px-3 py-2"
        >
          <span className="text-sm text-text2">{check.label}</span>
          {pending ? (
            <span className="text-xs text-text3">—</span>
          ) : check.ok ? (
            <Check size={16} className="text-mint" />
          ) : (
            <X size={16} className="text-coral" />
          )}
        </li>
      ))}
    </ul>
  );
}

export function SummaryPanel({
  summary,
  onRestart,
  onBack,
}: {
  summary: TrainSummary;
  onRestart: () => void;
  onBack: () => void;
}) {
  return (
    <Card title="本次训练" subtitle="训练汇总">
      <div className="flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-4">
          <span className="font-num text-5xl leading-none text-text1">
            {summary.score}
          </span>
          <Badge tone={gradeTone(summary.grade)}>{summary.grade}</Badge>
        </div>

        <div className="flex gap-6 text-sm">
          <div>
            <p className="text-xs text-text3">完成次数</p>
            <p className="mt-1 font-num text-xl text-text1">
              {summary.reps}
            </p>
          </div>
          <div>
            <p className="text-xs text-text3">用时</p>
            <p className="mt-1 text-text1">
              {formatDuration(summary.durationSec)}
            </p>
          </div>
        </div>

        <div className="ml-auto flex gap-2">
          <Button onClick={onRestart}>
            <RotateCcw size={15} /> 再来一次
          </Button>
          <Button variant="secondary" onClick={onBack}>
            查看数据 <ArrowRight size={15} />
          </Button>
        </div>
      </div>

      {summary.errors.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {summary.errors.map((error, i) => (
            <Badge key={`${error}-${i}`} tone="coral">
              {error}
            </Badge>
          ))}
        </div>
      )}
    </Card>
  );
}
