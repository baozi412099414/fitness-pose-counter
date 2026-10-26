import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface FieldProps {
  label?: ReactNode;
  help?: ReactNode;
  error?: ReactNode;
  htmlFor?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}

export function Field({
  label,
  help,
  error,
  htmlFor,
  required,
  className,
  children,
}: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {label && (
        <label
          htmlFor={htmlFor}
          className="text-xs font-medium uppercase tracking-[0.12em] text-text2"
        >
          {label}
          {required && <span className="ml-1 text-coral">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-coral">{error}</p>
      ) : help ? (
        <p className="text-xs text-text3">{help}</p>
      ) : null}
    </div>
  );
}