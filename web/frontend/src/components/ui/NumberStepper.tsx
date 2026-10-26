import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/cn";

export interface NumberStepperProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  className?: string;
}

export function NumberStepper({
  value,
  onChange,
  min = -Infinity,
  max = Infinity,
  step = 1,
  unit,
  className,
}: NumberStepperProps) {
  const clamp = (n: number) => Math.min(max, Math.max(min, n));

  const dec = () => onChange(clamp(round(value - step)));
  const inc = () => onChange(clamp(round(value + step)));

  function round(n: number) {
    const p = String(step).split(".")[1]?.length ?? 0;
    return Number(n.toFixed(p));
  }

  const btn =
    "flex h-10 w-10 items-center justify-center text-text2 hover:text-text1 " +
    "hover:bg-surface3 disabled:opacity-30 transition-colors duration-[120ms] ease-form";

  return (
    <div
      className={cn(
        "inline-flex items-stretch overflow-hidden rounded-[10px] border border-line1 bg-surface2",
        className,
      )}
    >
      <button
        type="button"
        aria-label="减少"
        className={btn}
        onClick={dec}
        disabled={value <= min}
      >
        <Minus size={15} />
      </button>
      <div className="flex min-w-[72px] items-center justify-center border-x border-line1 px-2">
        <span className="font-num text-lg leading-none text-text1 tabular-nums">
          {value}
        </span>
        {unit && (
          <span className="ml-1 text-xs text-text3">{unit}</span>
        )}
      </div>
      <button
        type="button"
        aria-label="增加"
        className={btn}
        onClick={inc}
        disabled={value >= max}
      >
        <Plus size={15} />
      </button>
    </div>
  );
}