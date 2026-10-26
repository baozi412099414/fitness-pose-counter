import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * 基于原生 <dialog> + showModal()：自带 ESC 关闭、焦点锁定、70% 黑遮罩。
 */
export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  className,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={titleId}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto w-[min(560px,calc(100vw-48px))] rounded-dialog border border-line1 bg-surface1 p-0 text-text1 shadow-2xl backdrop:bg-black/70",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-line1 px-5 py-4">
        <h2 id={titleId} className="text-base font-medium text-text1">
          {title}
        </h2>
        <button
          type="button"
          aria-label="关闭"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-[10px] text-text2 transition-colors hover:bg-surface2 hover:text-text1"
        >
          <X size={16} />
        </button>
      </div>
      <div className="px-5 py-4">{children}</div>
      {footer && (
        <div className="flex justify-end gap-2 border-t border-line1 px-5 py-4">
          {footer}
        </div>
      )}
    </dialog>
  );
}