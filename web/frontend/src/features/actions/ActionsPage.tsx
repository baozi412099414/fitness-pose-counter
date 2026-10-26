import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { Action, ActionValidationResult } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ActionCard } from "./ActionCard";

function ErrorBanner({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-card border border-coral/30 bg-coral/[0.08] px-4 py-3">
      <span className="text-sm text-coral">动作库加载失败</span>
      <Button variant="secondary" onClick={onRetry}>
        重试
      </Button>
    </div>
  );
}

/** 统计条：一排细指标，不用大卡片 */
function StatStrip({ actions }: { actions: Action[] }) {
  const passed = actions.filter((a) => a.validation.error_count === 0).length;
  const builtin = actions.filter((a) => a.builtin).length;
  const items = [
    { label: "动作数", value: actions.length },
    { label: "校验通过", value: passed },
    { label: "内置动作", value: builtin },
  ];
  return (
    <div className="flex divide-x divide-line1 rounded-card border border-line1 bg-surface1">
      {items.map((it, i) => (
        <div key={it.label} className={i === 0 ? "px-5 py-3" : "px-5 py-3"}>
          <span className="text-xs uppercase tracking-[0.12em] text-text3">
            {it.label}
          </span>
          <span className="font-num ml-2 text-2xl text-text1">{it.value}</span>
        </div>
      ))}
    </div>
  );
}

function ValidationDrawerContent({
  data,
  isLoading,
  isError,
  onRetry,
  onJump,
}: {
  data?: ActionValidationResult[];
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onJump: (id: string) => void;
}) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
    );
  }
  if (isError) {
    return (
      <div className="flex flex-col gap-3 py-4 text-sm text-coral">
        校验失败
        <Button variant="secondary" onClick={onRetry}>
          重试
        </Button>
      </div>
    );
  }
  if (!data || data.length === 0) {
    return <p className="text-sm text-text3">没有需要校验的配置。</p>;
  }
  return (
    <div className="flex flex-col gap-4">
      {data.map((r) => (
        <div key={r.action_id} className="rounded-[10px] border border-line1 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <button
                type="button"
                onClick={() => onJump(r.action_id)}
                className="block truncate text-sm font-medium text-text1 hover:text-accent"
              >
                {r.action_name}
              </button>
              <span className="font-mono text-xs text-text3">{r.file_path}</span>
            </div>
            {r.ok ? (
              <Badge tone="mint">通过</Badge>
            ) : (
              <Badge tone="coral">{r.errors.length} 错误</Badge>
            )}
          </div>

          {r.errors.length > 0 && (
            <ul className="mt-2 space-y-1">
              {r.errors.map((e, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => onJump(r.action_id)}
                    className="block w-full rounded-[6px] px-2 py-1 text-left text-xs text-coral hover:bg-coral/10"
                  >
                    ✖ {e}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {r.warnings.length > 0 && (
            <ul className="mt-1 space-y-1">
              {r.warnings.map((w, i) => (
                <li key={i} className="px-2 py-1 text-xs text-amber">
                  ⚠ {w}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

export function ActionsPage() {
  const navigate = useNavigate();
  const [validateOpen, setValidateOpen] = useState(false);

  const actions = useQuery({
    queryKey: ["actions"],
    queryFn: client.getActions,
  });

  const validate = useQuery({
    queryKey: ["validate-actions"],
    queryFn: client.validateActions,
    enabled: validateOpen,
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-medium text-text1">动作库</h1>
          <p className="mt-1 text-sm text-text3">
            动作判定全部来自 configs/ · 新增动作不需要改代码
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => setValidateOpen(true)}>
            校验全部配置
          </Button>
          <Button variant="primary" onClick={() => navigate("/actions/new")}>
            新建动作
          </Button>
        </div>
      </div>

      {actions.isError && (
        <ErrorBanner onRetry={() => actions.refetch()} />
      )}

      {actions.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 min-[1440px]:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : actions.data && actions.data.length > 0 ? (
        <>
          <StatStrip actions={actions.data} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 min-[1440px]:grid-cols-3">
            {actions.data.map((a) => (
              <ActionCard key={a.id} action={a} />
            ))}
          </div>
        </>
      ) : (
        <EmptyState
          title="还没有动作"
          description="新建一个动作后，这里会出现一张卡片。"
          action={
            <Button variant="primary" onClick={() => navigate("/actions/new")}>
              新建动作
            </Button>
          }
        />
      )}

      <Drawer
        open={validateOpen}
        onClose={() => setValidateOpen(false)}
        title="配置校验"
      >
        <ValidationDrawerContent
          data={validate.data}
          isLoading={validate.isLoading}
          isError={validate.isError}
          onRetry={() => validate.refetch()}
          onJump={(id) => {
            setValidateOpen(false);
            navigate(`/actions/${id}`);
          }}
        />
      </Drawer>
    </div>
  );
}