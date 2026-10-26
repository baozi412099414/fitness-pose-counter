import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Drawer";
import { formatDuration, gradeOf, gradeTone } from "@/lib/format";
import type { Grade, HistoryRecord } from "@/lib/types";

interface HistoryDrawerProps {
  record: HistoryRecord | null;
  onClose: () => void;
}

const SCORE_NOTES: Record<Grade, string> = {
  优秀: "动作标准、节奏稳定，继续保持。",
  良好: "整体完成度不错，仍有小幅可优化空间。",
  及格: "基本完成动作，注意改善动作质量。",
  待改进: "动作质量有较大提升空间，建议放慢节奏并对照提示纠正。",
};

function Info({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-[10px] border border-line1 bg-surface2 px-3 py-3">
      <p className="text-xs text-text3">{label}</p>
      <p className="mt-1 font-num text-xl leading-none text-text1">{value}</p>
    </div>
  );
}

export function HistoryDrawer({ record, onClose }: HistoryDrawerProps) {
  const grade = gradeOf(record?.score ?? null);

  return (
    <Drawer
      open={!!record}
      onClose={onClose}
      title={record ? `${record.action_name} · ${record.time}` : ""}
    >
      {record && (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-3 gap-3">
            <Info label="次数" value={record.reps} />
            <Info label="组数" value={record.sets} />
            <Info label="时长" value={formatDuration(record.duration)} />
          </div>

          <div className="rounded-[12px] border border-line1 bg-surface2 p-4">
            <span className="text-xs uppercase tracking-[0.12em] text-text3">
              评分
            </span>
            <div className="mt-2 flex items-center gap-3">
              <span className="font-num text-4xl leading-none text-text1">
                {record.score ?? "—"}
              </span>
              {grade && <Badge tone={gradeTone(grade)}>{grade}</Badge>}
            </div>
            <p className="mt-3 text-sm text-text2">
              {record.score == null
                ? "该次训练未记录评分。"
                : SCORE_NOTES[grade!]}
            </p>
          </div>

          <div>
            <span className="text-xs uppercase tracking-[0.12em] text-text3">
              错误明细
            </span>
            {record.errors.length === 0 ? (
              <div className="mt-3 flex items-center gap-2 rounded-[10px] border border-mint/30 bg-mint/[0.08] px-3 py-3">
                <Check size={16} className="text-mint" />
                <span className="text-sm text-mint">本轮无错误</span>
              </div>
            ) : (
              <ul className="mt-3 flex flex-col gap-2">
                {record.errors.map((e, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2.5 rounded-[10px] border border-coral/30 bg-coral/[0.06] px-3 py-2.5"
                  >
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-coral" />
                    <span className="text-sm text-text1">{e}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}