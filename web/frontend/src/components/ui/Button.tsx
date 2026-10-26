import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const base =
  "inline-flex items-center justify-center gap-2 h-10 px-4 rounded-[10px] text-sm font-medium " +
  "transition-colors duration-[120ms] ease-form select-none whitespace-nowrap " +
  "disabled:opacity-40 disabled:cursor-not-allowed";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-accentInk hover:brightness-105 active:brightness-95",
  secondary:
    "bg-transparent text-text1 border border-line1 hover:border-line2 hover:bg-surface2",
  ghost: "bg-transparent text-text2 hover:text-text1 hover:bg-surface2",
  danger: "bg-coral text-bg0 hover:brightness-105 active:brightness-95",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button({ variant = "primary", className, ...props }, ref) {
    return (
      <button
        ref={ref}
        className={cn(base, variants[variant], className)}
        {...props}
        type={props.type ?? "button"}
      />
    );
  },
);