import { cn } from "@/lib/cn";

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

export function Switch({
  checked,
  onChange,
  label,
  disabled,
  id,
  className,
}: SwitchProps) {
  return (
    <button
      type="button"
      id={id}
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "group inline-flex items-center gap-2.5 disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
    >
      <span
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors duration-[120ms] ease-form",
          checked ? "border-accent/40 bg-accent/20" : "border-line1 bg-surface2",
        )}
      >
        <span
          className={cn(
            "absolute left-0.5 h-3.5 w-3.5 rounded-full transition-transform duration-[120ms] ease-form",
            checked ? "translate-x-4 bg-accent" : "translate-x-0 bg-text3",
          )}
        />
      </span>
      {label && (
        <span className="text-sm text-text2 transition-colors group-hover:text-text1">
          {label}
        </span>
      )}
    </button>
  );
}