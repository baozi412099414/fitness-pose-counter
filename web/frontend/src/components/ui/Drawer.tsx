import { useEffect, useId, useRef, type ReactNode } from "react";
import { motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  side?: "right" | "left";
  className?: string;
}

/**
 * 基于原生 <dialog> + showModal() 的侧滑抽屉：ESC 关闭、焦点锁定。
 */
export function Drawer({
  open,
  onClose,
  title,
  children,
  side = "right",
  className,
}: DrawerProps) {
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
        "max-h-none h-full w-[min(420px,100vw)] bg-surface1 p-0 text-text1 backdrop:bg-black/70",
        side === "right" ? "ml-auto mr-0" : "ml-0 mr-auto",
        "rounded-none",
        className,
      )}
    >
      <motion.div
        initial={{ x: side === "right" ? 32 : -32, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
        className="flex h-full flex-col"
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
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </motion.div>
    </dialog>
  );
}