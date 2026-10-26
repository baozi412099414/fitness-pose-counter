import type { NewActionDraft, SaveError } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import { thresholdRange, unitOf } from "../humanize";

interface Props {
  draft: NewActionDraft;
  onChange: (patch: Partial<NewActionDraft>) => void;
  errors: SaveError[];
}

interface RuleCardProps {
  title: string;
  desc: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  threshold: number;
  onThreshold: (v: number) => void;
  tip: string;
  onTip: (v: string) => void;
  priority: number;
  onPriority: (v: number) => void;
  error?: string;
  unit: string;
  step: number;
}

function RuleCard({
  title,
  desc,
  enabled,
  onToggle,
  threshold,
  onThreshold,
  tip,
  onTip,
  priority,
  onPriority,
  error,
  unit,
  step,
}: RuleCardProps) {
  return (
    <div className="rounded-card border border-line1 bg-surface1">
      <div className="flex items-center justify-between gap-4 border-b border-line1 px-5 py-4">
        <div>
          <div className="text-sm font-medium text-text1">{title}</div>
          <div className="mt-0.5 text-xs text-text3">{desc}</div>
        </div>
        <Switch checked={enabled} onChange={onToggle} label={enabled ? "启用" : "关闭"} />
      </div>
      {enabled && (
        <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2">
          <Field label={`阈值（${unit}）`} error={error}>
            <Input
              type="number"
              step={step}
              value={threshold}
              onChange={(e) => {
                const n = e.target.valueAsNumber;
                if (!Number.isNaN(n)) onThreshold(n);
              }}
            />
          </Field>
          <Field label="优先级" help="越高越优先播报">
            <Select
              value={String(priority)}
              onChange={(e) => onPriority(Number(e.target.value))}
            >
              <option value="80">高优先</option>
              <option value="60">中优先</option>
              <option value="40">低优先</option>
            </Select>
          </Field>
          <Field label="提示语" className="sm:col-span-2">
            <Input value={tip} onChange={(e) => onTip(e.target.value)} />
          </Field>
        </div>
      )}
    </div>
  );
}

export function QualityRulesStep({ draft, onChange, errors }: Props) {
  const err = (f: string) => errors.find((e) => e.field === f)?.message;
  const unit = unitOf(draft.signal);
  const step = thresholdRange(draft.signal).step;
  const firstLo = draft.first === "lo";

  const setDepth = (patch: Partial<NewActionDraft["depth"]>) =>
    onChange({ depth: { ...draft.depth, ...patch } });
  const setStraight = (patch: Partial<NewActionDraft["straight"]>) =>
    onChange({ straight: { ...draft.straight, ...patch } });

  const ruleCount = (draft.depth.enabled ? 1 : 0) + (draft.straight.enabled ? 1 : 0);

  return (
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-12 flex flex-col gap-4 lg:col-span-8">
        <RuleCard
          title="动作幅度不够"
          desc={
            firstLo
              ? "先变小：本轮最小角度 ≤ 阈值才算到位"
              : "先变大：本轮最大角度 ≥ 阈值才算到位"
          }
          enabled={draft.depth.enabled}
          onToggle={(v) => setDepth({ enabled: v })}
          threshold={draft.depth.threshold}
          onThreshold={(v) => setDepth({ threshold: v })}
          tip={draft.depth.tip}
          onTip={(v) => setDepth({ tip: v })}
          priority={draft.depth.priority}
          onPriority={(v) => setDepth({ priority: v })}
          error={err("quality.0.threshold")}
          unit={unit}
          step={step}
        />
        <RuleCard
          title="没回到起始位置"
          desc={
            firstLo
              ? "先变小：本轮最大角度 ≥ 阈值才算站直"
              : "先变大：本轮最小角度 ≤ 阈值才算放下"
          }
          enabled={draft.straight.enabled}
          onToggle={(v) => setStraight({ enabled: v })}
          threshold={draft.straight.threshold}
          onThreshold={(v) => setStraight({ threshold: v })}
          tip={draft.straight.tip}
          onTip={(v) => setStraight({ tip: v })}
          priority={draft.straight.priority}
          onPriority={(v) => setStraight({ priority: v })}
          error={err("quality.1.threshold")}
          unit={unit}
          step={step}
        />

        <p className="text-xs text-text3">
          更多规则可在保存后直接编辑配置 JSON；网页版先覆盖这两个最常用模板。
        </p>
      </div>

      <div className="col-span-12 lg:col-span-4">
        <Card title="预览" subtitle="质量规则（可选，可为 0 条）">
          <p className="text-sm text-text2">
            将生成 <span className="font-num text-text1">{ruleCount}</span> 条规则
          </p>
        </Card>
      </div>
    </div>
  );
}