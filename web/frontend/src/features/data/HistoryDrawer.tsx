import type { HistoryRecord } from "@/lib/types";
import { formatDuration, gradeOf, gradeTone } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Drawer";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.12em] text-text3">{label}</dt>
      <dd className="mt-1 text-sm text-text1">{value}</dd>
    </div>
  );
}

export function HistoryDrawer({
  record,
  onClose,
}: {
  record: HistoryRecord | null;
  onClose: () => void;
}) {
  const grade = gradeOf(record?.score);

  return (
    <Drawer open={!!record} onClose={onClose} title="训练详情">
      {record && (
        <div className="flex flex-col gap-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-medium text-text1">
                {record.action_name}
              </h3>
              <p className="mt-1 font-mono text-xs text-text3">{record.time}</p>
            </div>
            {record.score == null ? (
              <Badge tone="neutral">无评分</Badge>
            ) : (
              <div className="text-right">
                <p className="font-num text-3xl leading-none text-text1">
                  {record.score}
                </p>
                {grade && (
                  <Badge tone={gradeTone(grade)} className="mt-1">
                    {grade}
                  </Badge>
                )}
              </div>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-5">
            <Field label="次数" value={`${record.reps} 次`} />
            <Field label="组数" value={`${record.sets} 组`} />
            <Field label="时长" value={formatDuration(record.duration)} />
            <Field label="动作 ID" value={<code className="font-mono text-[13px]">{record.action_id}</code>} />
          </dl>

          <div>
            <h4 className="text-xs uppercase tracking-[0.12em] text-text3">
              错误明细
            </h4>
            {record.errors.length === 0 ? (
              <p className="mt-2 text-sm text-mint">本次未记录到错误。</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {record.errors.map((tip, i) => (
                  <li
                    key={`${tip}-${i}`}
                    className="flex items-start gap-2 rounded-[8px] border border-coral/20 bg-coral/[0.06] px-3 py-2 text-sm text-text1"
                  >
                    <span className="mt-0.5 font-mono text-xs text-coral">
                      {i + 1}
                    </span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h4 className="text-xs uppercase tracking-[0.12em] text-text3">
              评分说明
            </h4>
            <p className="mt-2 rounded-[8px] border border-line1 bg-surface2/40 px-3 py-2.5 text-sm leading-relaxed text-text2">
              {record.score == null
                ? "本次没有评分（关键点未拍全或未完成一次动作）。"
                : `本次仅保存总分 ${record.score} 分（${grade ?? "—"}）；逐条评分明细需后端回传 checks，当前 Mock 未提供，因此不展示逐项扣分。`}
            </p>
          </div>
        </div>
      )}
    </Drawer>
  );
}
