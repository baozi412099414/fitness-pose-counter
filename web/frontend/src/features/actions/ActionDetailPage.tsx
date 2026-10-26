import { useMemo, useRef } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Copy, Play } from "lucide-react";
import { client } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { ActionDetail, CounterCondition } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { TipBanner } from "@/components/ui/TipBanner";
import { useToast } from "@/providers/Toaster";
import { SkeletonFigure } from "./SkeletonFigure";
import {
  checkSentence,
  conditionThresholds,
  counterThresholds,
  directionLabel,
  partLabel,
  pointsLabel,
  priorityLabel,
  signalLabel,
  whenLabel,
} from "./humanize";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.08em] text-text3">{label}</dt>
      <dd className="mt-0.5 text-sm text-text1">{children}</dd>
    </div>
  );
}

function SignalBlock({
  signal,
  points,
  enter,
  count,
  direction,
}: {
  signal: string;
  points: number[];
  enter: string;
  count: string;
  direction: string;
}) {
  return (
    <div className="py-4">
      <div className="text-sm font-medium text-text1">
        信号 · {signalLabel(signal)}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3">
        <Field label="测量部位">{partLabel(points)}</Field>
        <Field label="进入阈值">{enter}</Field>
        <Field label="计一次阈值">{count}</Field>
        <Field label="方向">{direction}</Field>
      </dl>
      <p className="mt-2 font-mono text-xs text-text3">{pointsLabel(points)}</p>
    </div>
  );
}

function PublicParams({ detail }: { detail: ActionDetail }) {
  const c = detail.counter;
  return (
    <div className="border-t border-line1 py-4">
      <div className="text-sm font-medium text-text1">公共参数</div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3">
        <Field label="最小计数间隔">{c.min_interval ?? 0.4}s</Field>
        <Field label="确认时长">
          进入 {c.enter_hold ?? 0.06}s · 退出 {c.exit_hold ?? 0.06}s
        </Field>
        <Field label="循环次数">{c.cycles_per_rep ?? 1} 次</Field>
        <Field label="校准开关">
          {detail.calibrate ? "开 · 只对角度变小类有效" : "关"}
        </Field>
      </dl>
    </div>
  );
}

function LogicSection({ detail }: { detail: ActionDetail }) {
  const c = detail.counter;
  return (
    <Card title="判定逻辑" subtitle="规则已翻译成人话，便于核对照 JSON">
      <div className="divide-y divide-line1">
        {c.conditions
          ? c.conditions.map((cond: CounterCondition, i: number) => {
              const t = conditionThresholds(cond);
              return (
                <SignalBlock
                  key={i}
                  signal={cond.signal}
                  points={cond.points}
                  enter={t.enter}
                  count={t.count}
                  direction={directionLabel(cond.direction)}
                />
              );
            })
          : (() => {
              const t = counterThresholds(c);
              return (
                <SignalBlock
                  signal={c.signal ?? "—"}
                  points={c.points ?? []}
                  enter={t.enter}
                  count={t.count}
                  direction={directionLabel(c.first)}
                />
              );
            })()}
        <PublicParams detail={detail} />
      </div>
    </Card>
  );
}

function QualitySection({ detail }: { detail: ActionDetail }) {
  const rules = useMemo(
    () => [...detail.quality].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0)),
    [detail.quality],
  );
  // 没写 signal 的规则继承计数信号（多条件时取第一条）
  const fallbackSignal =
    detail.counter.signal ?? detail.counter.conditions?.[0]?.signal;

  return (
    <Card title="质量规则" subtitle={`${rules.length} 条 · 按优先级降序`}>
      {rules.length === 0 ? (
        <p className="text-sm text-text3">该动作没有配置质量规则。</p>
      ) : (
        <div className="divide-y divide-line1">
          {rules.map((r, i) => {
            const p = r.priority ?? 0;
            const tone = p >= 80 ? "coral" : p >= 60 ? "amber" : "neutral";
            return (
              <div key={i} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm text-text1">{r.tip ?? r.name}</span>
                  <Badge tone={tone} className="shrink-0">
                    {priorityLabel(r.priority)}优先
                  </Badge>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-xs text-text2">
                  <span>时机 · {whenLabel(r.when)}</span>
                  <span className="font-mono">{checkSentence(r, fallbackSignal)}</span>
                  {r.ideal != null && (
                    <span className="text-text3">满分 {r.ideal}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export function ActionDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const jsonRef = useRef<HTMLDetailsElement>(null);

  const action = useQuery({
    queryKey: ["action", id],
    queryFn: () => client.getAction(id),
  });

  if (action.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8">
            <Skeleton className="h-64" />
            <Skeleton className="mt-6 h-72" />
          </div>
          <div className="col-span-12 lg:col-span-4">
            <Skeleton className="h-80" />
          </div>
        </div>
      </div>
    );
  }

  if (action.isError) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-card border border-coral/30 bg-coral/[0.08] px-4 py-3">
          <span className="text-sm text-coral">动作详情加载失败</span>
          <Button variant="secondary" onClick={() => action.refetch()}>
            重试
          </Button>
        </div>
      </div>
    );
  }

  const detail = action.data;

  if (!detail) {
    return (
      <EmptyState
        title="找不到这个动作"
        description={`没有 id 为「${id}」的动作配置。`}
        action={
          <Button variant="secondary" onClick={() => navigate("/actions")}>
            返回动作库
          </Button>
        }
      />
    );
  }

  const c = detail.counter;
  const counterPoints = c.conditions
    ? [...new Set(c.conditions.flatMap((x) => x.points))]
    : [...new Set(c.points ?? [])];
  const rulePoints = [
    ...new Set(detail.quality.flatMap((r) => r.points ?? [])),
  ].filter((p) => !counterPoints.includes(p));

  const raw = {
    id: detail.id,
    name: detail.name,
    camera_side: detail.camera_side,
    calibrate: detail.calibrate,
    counter: detail.counter,
    quality: detail.quality,
  };
  const json = JSON.stringify(raw, null, 2);

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(json);
      toast.push("已复制配置 JSON", "accent");
    } catch {
      toast.push("复制失败", "coral");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 顶部 */}
      <div>
        <Link
          to="/actions"
          className="inline-flex items-center gap-1.5 text-sm text-text3 transition-colors hover:text-text1"
        >
          <ArrowLeft size={15} />
          动作库
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-medium text-text1">{detail.name}</h1>
          <span className="font-mono text-sm text-text3">{detail.id}</span>
          {detail.validation.ok ? (
            <Badge tone="mint">校验通过</Badge>
          ) : (
            <Badge tone="coral">{detail.validation.errors.length} 错误</Badge>
          )}
          <div className="ml-auto flex gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                jsonRef.current?.scrollIntoView({ behavior: "smooth" });
                if (jsonRef.current) jsonRef.current.open = true;
              }}
            >
              查看 JSON
            </Button>
            <Button
              variant="primary"
              disabled={!detail.validation.ok}
              onClick={() => navigate(`/train/${detail.id}`)}
            >
              <Play size={16} />
              用这个动作训练
            </Button>
          </div>
        </div>
      </div>

      {/* 校验错误提示条 */}
      {detail.validation.errors.length > 0 && (
        <TipBanner className="rounded-card">
          <div className="flex flex-col gap-1">
            <span className="text-sm text-coral">
              配置存在 {detail.validation.errors.length} 个错误，暂时无法用于训练：
            </span>
            <ul className="list-inside list-disc text-sm text-text2">
              {detail.validation.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        </TipBanner>
      )}

      <div className="grid grid-cols-12 gap-6">
        {/* 左栏 */}
        <div className="col-span-12 flex flex-col gap-6 lg:col-span-8">
          <LogicSection detail={detail} />
          <QualitySection detail={detail} />
        </div>

        {/* 右栏 */}
        <div className="col-span-12 flex flex-col gap-6 lg:col-span-4">
          <Card title="骨架示意" subtitle="计数关键点（绿）与质量判定点（青）">
            <SkeletonFigure
              counterPoints={counterPoints}
              rulePoints={rulePoints}
              className="mx-auto w-full max-w-[260px]"
            />
          </Card>

          <Card title="配置摘要">
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-xs text-text3">文件路径</dt>
                <dd className="mt-0.5 font-mono text-text1">{detail.file_path}</dd>
              </div>
              <div>
                <dt className="text-xs text-text3">最后校验时间</dt>
                <dd className="mt-0.5 text-text1">
                  {detail.last_validated_at ?? "本次会话未校验"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-text3">警告</dt>
                <dd className="mt-0.5">
                  {detail.validation.warnings.length > 0 ? (
                    <ul className="space-y-1 text-amber">
                      {detail.validation.warnings.map((w, i) => (
                        <li key={i}>⚠ {w}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-text3">无</span>
                  )}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="原始 JSON">
            <details ref={jsonRef} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between [&::-webkit-details-marker]:hidden">
                <span className="text-sm text-text2">展开 / 折叠</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    void copyJson();
                  }}
                  className="flex items-center gap-1 rounded-[6px] px-2 py-1 text-xs text-text2 transition-colors hover:bg-surface2 hover:text-text1"
                >
                  <Copy size={13} />
                  复制
                </button>
              </summary>
              <pre
                className={cn(
                  "mt-3 max-h-80 overflow-auto rounded-[10px] border border-line1 bg-bg0 p-3 font-mono text-xs leading-relaxed text-text2",
                )}
              >
                {json}
              </pre>
            </details>
          </Card>
        </div>
      </div>
    </div>
  );
}