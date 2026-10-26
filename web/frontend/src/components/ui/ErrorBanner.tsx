import { Button } from "@/components/ui/Button";

export interface ErrorBannerProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorBanner({ message = "数据加载失败", onRetry }: ErrorBannerProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-card border border-coral/30 bg-coral/[0.08] px-4 py-3">
      <span className="text-sm text-coral">{message}</span>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          重试
        </Button>
      )}
    </div>
  );
}