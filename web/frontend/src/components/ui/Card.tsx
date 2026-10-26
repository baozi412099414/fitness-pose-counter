import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export function Card({
  title,
  subtitle,
  actions,
  className,
  bodyClassName,
  children,
}: CardProps) {
  return (
    <section
      className={cn(
        "rounded-card border border-line1 bg-surface1",
        className,
      )}
    >
      {(title || subtitle || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-line1 px-5 py-4">
          <div className="flex flex-col gap-1">
            {title && (
              <h3 className="text-base font-medium text-text1">{title}</h3>
            )}
            {subtitle && (
              <p className="text-[13px] text-text3">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}