import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { Action, DailyGoal } from "@/lib/types";
import { useToast } from "@/providers/Toaster";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { NumberStepper } from "@/components/ui/NumberStepper";
import { Skeleton } from "@/components/ui/Skeleton";

function GoalRow({ action, goal }: { action: Action; goal?: DailyGoal }) {
  const [value, setValue] = useState(goal?.target ?? 0);
  const [dirty, setDirty] = useState(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  // 服务端目标变化（保存/清除后 refetch）时同步本地输入
  useEffect(() => {
    setValue(goal?.target ?? 0);
    setDirty(false);
  }, [goal?.target]);

  const save = useMutation({
    mutationFn: (target: number) => client.setGoal(action.id, target),
    onSuccess: (_d, target) => {
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      toast.push(
        target > 0 ? `已保存「${action.name}」目标 ${target} 次` : `已清除「${action.name}」目标`,
        "mint",
      );
      setDirty(false);
    },
    onError: () => toast.push(`「${action.name}」保存失败`, "coral"),
  });

  const clear = useMutation({
    mutationFn: () => client.clearGoal(action.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      toast.push(`已清除「${action.name}」目标`, "neutral");
    },
    onError: () => toast.push(`「${action.name}」清除失败`, "coral"),
  });

  const hasTarget = value > 0;
  const done = goal?.done ?? 0;
  const pct = hasTarget ? Math.min(100, Math.round((done / value) * 100)) : 0;
  const busy = save.isPending || clear.isPending;

  return (
    <div className="flex flex-col gap-3 border-b border-line1 py-4 last:border-0 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-surface2 text-text1">
          {action.name[0]}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text1">{action.name}</p>
          <p className="text-xs text-text3">今日已完成 {done}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {hasTarget ? (
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface2">
            <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
        ) : (
          <span className="text-xs text-text3">未设置目标</span>
        )}
        <NumberStepper
          value={value}
          onChange={(v) => {
            setValue(v);
            setDirty(true);
          }}
          min={0}
          max={999}
          unit="次"
        />
        {goal && (
          <Button
            variant="ghost"
            className="text-coral hover:bg-coral/10 hover:text-coral"
            onClick={() => clear.mutate()}
            disabled={busy}
          >
            清除
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={() => save.mutate(value)}
          disabled={busy || !dirty}
        >
          {save.isPending ? "处理中…" : "保存"}
        </Button>
      </div>
    </div>
  );
}

export function GoalsSection() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => client.getOverview() });
  const actions = useQuery({ queryKey: ["actions"], queryFn: client.getActions });

  const loading = overview.isLoading || actions.isLoading;
  const error = overview.isError || actions.isError;

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <ErrorBanner
          onRetry={() => {
            overview.refetch();
            actions.refetch();
          }}
        />
      )}

      <Card title="每日目标" subtitle="为每个动作设置今日次数目标；设为 0 视为未设置">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        ) : actions.data && actions.data.length === 0 ? (
          <p className="text-sm text-text3">动作库为空，先去动作库新建动作。</p>
        ) : (
          actions.data?.map((a) => (
            <GoalRow
              key={a.id}
              action={a}
              goal={overview.data?.goals.find((g) => g.action_id === a.id)}
            />
          ))
        )}
      </Card>

      <p className="text-xs text-text3">保存后总览的目标环会同步更新（按各动作目标求和派生）。</p>
    </div>
  );
}