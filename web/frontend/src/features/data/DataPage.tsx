import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { client } from "@/lib/api";
import { cn } from "@/lib/cn";
import { downloadCsv, type CsvCell } from "@/lib/csv";
import type { HistoryRecord } from "@/lib/types";
import { useUser } from "@/providers/UserProvider";
import { useToast } from "@/providers/Toaster";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Select } from "@/components/ui/Select";
import { DataPageHeader } from "./DataPageHeader";
import { ErrorRanking } from "./ErrorRanking";
import { HistoryDrawer } from "./HistoryDrawer";
import { HistoryTable } from "./HistoryTable";
import { KpiBar } from "./KpiBar";
import { ScoreTrendChart } from "./ScoreTrendChart";
import { WeeklyBarChart } from "./WeeklyBarChart";

const DAY_OPTIONS = [7, 14, 30] as const;
const PAGE_SIZE = 10;

export function DataPage() {
  const { activeUserId, currentUser } = useUser();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const action = searchParams.get("action") ?? "";
  const error = searchParams.get("error") ?? "";
  const tab = searchParams.get("tab") ?? "";
  const rawDays = Number(searchParams.get("days") ?? "14");
  const days = (DAY_OPTIONS as readonly number[]).includes(rawDays)
    ? rawDays
    : 14;

  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<HistoryRecord | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setPage(0);
    setSelected(null);
  }, [action, days, error, activeUserId]);

  useEffect(() => {
    if (tab !== "errors") return;
    const t = window.setTimeout(() => {
      document
        .getElementById("error-ranking")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
    return () => window.clearTimeout(t);
  }, [tab]);

  // 仅在同一用户内切换筛选时保留旧数据；切用户时不复用上一个用户的数据。
  const placeholderFor = <T,>(prev: T | undefined, prevQuery?: { queryKey: readonly unknown[] }) =>
    prevQuery?.queryKey[1] === activeUserId ? prev : undefined;

  const overview = useQuery({
    queryKey: ["overview", activeUserId, days],
    queryFn: () => client.getOverview(activeUserId, days),
    placeholderData: placeholderFor,
  });

  const history = useQuery({
    queryKey: ["history", activeUserId, action, days, error, page],
    queryFn: () =>
      client.getHistory({
        userId: activeUserId,
        actionId: action || undefined,
        days,
        error: error || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    placeholderData: placeholderFor,
  });

  const actions = useQuery({
    queryKey: ["actions"],
    queryFn: client.getActions,
  });

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const all = await client.getHistory({
        userId: activeUserId,
        actionId: action || undefined,
        days,
        error: error || undefined,
        limit: 100000,
        offset: 0,
      });
      const rows: CsvCell[][] = [
        ["时间", "动作", "次数", "组数", "评分", "时长(秒)", "错误"],
      ];
      for (const r of all.items) {
        rows.push([
          r.time,
          r.action_name,
          r.reps,
          r.sets,
          r.score ?? "",
          r.duration,
          r.errors.join("；"),
        ]);
      }
      const name = currentUser?.name ?? "用户";
      downloadCsv(
        `训练数据_${name}_${days}天_${new Date().toISOString().slice(0, 10)}.csv`,
        rows,
      );
      toast.push(`已导出 ${all.items.length} 条记录`, "mint");
    } catch {
      toast.push("导出失败，请重试", "coral");
    } finally {
      setExporting(false);
    }
  };

  const refreshing =
    !overview.isLoading &&
    !history.isLoading &&
    (overview.isFetching || history.isFetching);

  return (
    <div className="flex flex-col gap-6">
      <DataPageHeader
        userName={currentUser?.name}
        exporting={exporting}
        onExport={handleExport}
      />

      {overview.isError && (
        <ErrorBanner onRetry={() => overview.refetch()} />
      )}
      {actions.isError && <ErrorBanner onRetry={() => actions.refetch()} />}

      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={action}
          onChange={(e) => updateParam("action", e.target.value)}
          className="w-40"
          aria-label="按动作筛选"
        >
          <option value="">全部动作</option>
          {actions.data?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </Select>

        <div className="flex rounded-[10px] border border-line1 bg-surface1 p-0.5">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => updateParam("days", String(d))}
              className={cn(
                "rounded-[8px] px-3 py-1.5 text-xs font-medium transition-colors",
                days === d
                  ? "bg-surface2 text-text1"
                  : "text-text2 hover:text-text1",
              )}
            >
              {d} 天
            </button>
          ))}
        </div>

        {error && (
          <button
            type="button"
            onClick={() => updateParam("error", "")}
            className="inline-flex items-center gap-1 rounded-full border border-coral/30 bg-coral/10 px-3 py-1 text-xs text-coral transition-colors hover:bg-coral/15"
          >
            错误：{error} <X size={12} />
          </button>
        )}

        {refreshing && (
          <span className="text-xs text-text3">刷新中…</span>
        )}
      </div>

      {refreshing && (
        <div className="h-0.5 overflow-hidden rounded-full bg-surface2">
          <div className="h-full w-1/3 animate-pulse rounded-full bg-accent/70" />
        </div>
      )}

      <KpiBar
        data={overview.data}
        loading={overview.isLoading}
        days={days}
      />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 min-[1360px]:col-span-8">
          <WeeklyBarChart
            data={overview.data?.weekly_trend}
            loading={overview.isLoading}
          />
        </div>
        <div className="col-span-12 min-[1360px]:col-span-4">
          <ScoreTrendChart
            data={overview.data?.score_trend}
            loading={overview.isLoading}
            days={days}
          />
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div id="error-ranking" className="col-span-12 min-[1360px]:col-span-5">
          <ErrorRanking
            errors={overview.data?.top_errors}
            loading={overview.isLoading}
            activeError={error}
            onSelect={(tip) =>
              updateParam("error", error === tip ? "" : tip)
            }
          />
        </div>
        <div className="col-span-12 min-[1360px]:col-span-7">
          <HistoryTable
            data={history.data}
            loading={history.isLoading}
            isError={history.isError}
            onRetry={() => history.refetch()}
            onSelect={setSelected}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </div>
      </div>

      <p className="text-xs text-text3">
        数据来自本地 data/users/{currentUser?.name ?? "<用户名>"}/，视频帧不落盘。
        Mock 模式下非默认用户没有历史数据，用于演示切换用户后的隔离效果。
      </p>

      <HistoryDrawer
        record={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
