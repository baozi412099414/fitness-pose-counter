import type { NewActionDraft, SaveError } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { RangeSlider } from "@/components/ui/RangeSlider";
import { SkeletonFigure } from "../SkeletonFigure";
import {
  ANGLE_PARTS,
  PAIR_PARTS,
  RATIO_SIGNALS,
  SIGNAL_HINTS,
  defaultThresholds,
  partLabel,
  pointsLabel,
  signalLabel,
  signalsForPointCount,
  thresholdRange,
  unitOf,
  TWO_POINT_SIGNALS,
} from "../humanize";

interface Props {
  draft: NewActionDraft;
  onChange: (patch: Partial<NewActionDraft>) => void;
  errors: SaveError[];
}

const ALL_PARTS = [...ANGLE_PARTS, ...PAIR_PARTS];

export function SignalStep({ draft, onChange, errors }: Props) {
  const err = (f: string) => errors.find((e) => e.field === f)?.message;

  const range = thresholdRange(draft.signal);
  const unit = unitOf(draft.signal);
  const dec = range.step < 1 ? 2 : 0;
  const clamp = (v: number, lo: number, hi: number) =>
    Number(Math.min(hi, Math.max(lo, v)).toFixed(dec));

  const setLo = (v: number) => onChange({ lo: clamp(v, range.min, draft.hi - range.step) });
  const setHi = (v: number) => onChange({ hi: clamp(v, draft.lo + range.step, range.max) });

  const enter = draft.first === "lo" ? draft.lo : draft.hi;
  const count = draft.first === "lo" ? draft.hi : draft.lo;
  const enterArrow = draft.first === "lo" ? "↓" : "↑";
  const countArrow = draft.first === "lo" ? "↑" : "↓";

  const setEnter = (v: number) => (draft.first === "lo" ? setLo(v) : setHi(v));
  const setCount = (v: number) => (draft.first === "lo" ? setHi(v) : setLo(v));

  const pickPart = (label: string) => {
    const opt = ALL_PARTS.find((p) => p.label === label);
    if (!opt) return;
    const signal =
      opt.arity === 3
        ? "angle"
        : TWO_POINT_SIGNALS.includes(draft.signal)
          ? draft.signal
          : "tilt";
    const th = defaultThresholds(signal);
    onChange({ points: opt.points, signal, lo: th.lo, hi: th.hi });
  };

  const pickSignal = (signal: string) => {
    if (RATIO_SIGNALS.has(signal) !== RATIO_SIGNALS.has(draft.signal)) {
      const th = defaultThresholds(signal);
      onChange({ signal, lo: th.lo, hi: th.hi });
    } else {
      onChange({ signal });
    }
  };

  const addNum = (e: React.ChangeEvent<HTMLInputElement>, set: (n: number) => void) => {
    const n = e.target.valueAsNumber;
    if (!Number.isNaN(n)) set(n);
  };

  const currentPart = ALL_PARTS.find(
    (p) => p.points.length === draft.points.length && p.points.every((x, i) => x === draft.points[i]),
  );

  return (
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-12 flex flex-col gap-5 lg:col-span-8">
        <Field label="测量部位" required error={err("signal")} help="选「左膝角」会自动填 23/25/27">
          <Select value={currentPart?.label ?? ""} onChange={(e) => pickPart(e.target.value)}>
            <option value="" disabled>
              选择部位…
            </option>
            <optgroup label="三点组合（量角度）">
              {ANGLE_PARTS.map((p) => (
                <option key={p.label} value={p.label}>
                  {p.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="两点组合（量距离 / 倾角）">
              {PAIR_PARTS.map((p) => (
                <option key={p.label} value={p.label}>
                  {p.label}
                </option>
              ))}
            </optgroup>
          </Select>
        </Field>

        <Field
          label="信号类型"
          required
          help={SIGNAL_HINTS[draft.signal]}
        >
          <Select value={draft.signal} onChange={(e) => pickSignal(e.target.value)}>
            {signalsForPointCount(draft.points.length).map((s) => (
              <option key={s} value={s}>
                {signalLabel(s)}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="方向" required>
          <div className="grid grid-cols-2 gap-3">
            {(
              [
                { v: "lo", t: "信号先变小", d: "下蹲类：蹲下去再站起" },
                { v: "hi", t: "信号先变大", d: "举手类：抬起来再放下" },
              ] as const
            ).map((o) => (
              <button
                key={o.v}
                type="button"
                onClick={() => onChange({ first: o.v })}
                className={cn(
                  "rounded-[10px] border p-3 text-left transition-colors",
                  draft.first === o.v
                    ? "border-accent bg-accent/10"
                    : "border-line1 hover:border-line2",
                )}
              >
                <span className="text-sm text-text1">{o.t}</span>
                <span className="mt-0.5 block text-xs text-text3">{o.d}</span>
              </button>
            ))}
          </div>
        </Field>

        <Field
          label="阈值"
          error={err("signal.lo")}
          help="中间荧光绿区间为「迟滞区」，两端都不会反复翻转"
        >
          <div className="rounded-[12px] border border-line1 bg-surface1/40 p-4">
            <RangeSlider
              min={range.min}
              max={range.max}
              step={range.step}
              lo={draft.lo}
              hi={draft.hi}
              first={draft.first}
              unit={unit}
              onChange={(lo, hi) => onChange({ lo, hi })}
            />
          </div>
        </Field>

        <Field
          label="数值输入"
          help={`与滑块双向绑定 · 单位：${unit === "°" ? "度" : "倍肩宽（×）"}`}
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label={`进入动作 ${enterArrow}`}>
              <Input
                type="number"
                step={range.step}
                min={range.min}
                max={range.max}
                value={enter}
                onChange={(e) => addNum(e, setEnter)}
              />
            </Field>
            <Field label={`计 1 次 ${countArrow}`}>
              <Input
                type="number"
                step={range.step}
                min={range.min}
                max={range.max}
                value={count}
                onChange={(e) => addNum(e, setCount)}
              />
            </Field>
          </div>
        </Field>

        <details className="rounded-[12px] border border-line1 bg-surface1/40 px-4 py-3">
          <summary className="cursor-pointer select-none text-sm text-text2">
            高级参数（推荐值，一般不用改）
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {(
              [
                { k: "min_interval", t: "最小计数间隔", s: 0.05 },
                { k: "enter_hold", t: "进入确认时长", s: 0.01 },
                { k: "exit_hold", t: "退出确认时长", s: 0.01 },
                { k: "min_active_duration", t: "最短动作时长", s: 0.01 },
              ] as const
            ).map((it) => (
              <Field key={it.k} label={it.t}>
                <Input
                  type="number"
                  step={it.s}
                  min={0}
                  value={draft[it.k]}
                  onChange={(e) => {
                    const n = e.target.valueAsNumber;
                    if (!Number.isNaN(n)) onChange({ [it.k]: n });
                  }}
                />
              </Field>
            ))}
          </div>
        </details>
      </div>

      <div className="col-span-12 lg:col-span-4">
        <Card title="静态示意" subtitle="高亮当前选中的关键点">
          <SkeletonFigure
            counterPoints={draft.points}
            rulePoints={[]}
            className="mx-auto w-full max-w-[240px]"
          />
          <div className="mt-3 space-y-1 text-sm text-text2">
            <p>
              {partLabel(draft.points)} · {signalLabel(draft.signal)}
            </p>
            <p className="font-mono text-xs text-text3">{pointsLabel(draft.points)}</p>
            <p className="font-mono text-xs text-accent">
              进入 {enter}
              {unit} {enterArrow} · 计一次 {count}
              {unit} {countArrow}
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}