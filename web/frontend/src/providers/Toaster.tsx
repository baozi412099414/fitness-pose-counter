import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { BadgeTone } from "@/components/ui/Badge";
import { Toast } from "@/components/ui/Toast";

interface ToastItem {
  id: number;
  message: ReactNode;
  tone: BadgeTone;
}

interface ToastApi {
  push: (message: ReactNode, tone?: BadgeTone) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast 必须在 <Toaster> 内使用");
  }
  return ctx;
}

export function Toaster({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: ReactNode, tone: BadgeTone = "neutral") => {
      const id = ++idRef.current;
      setItems((prev) => [...prev, { id, message, tone }]);
    },
    [],
  );

  const api = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-5 top-5 z-[100] flex flex-col gap-3">
        {items.map((t) => (
          <Toast
            key={t.id}
            message={t.message}
            tone={t.tone}
            onDismiss={() => dismiss(t.id)}
            className="static"
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}