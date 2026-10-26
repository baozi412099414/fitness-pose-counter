import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-[10px] bg-surface2 px-3 text-sm text-text1 " +
          "border border-line1 placeholder:text-text3 " +
          "focus:border-accent focus:outline-none transition-colors duration-[120ms] ease-form",
        className,
      )}
      {...props}
    />
  );
});