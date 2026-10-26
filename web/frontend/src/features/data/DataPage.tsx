import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { useToast } from "@/providers/Toaster";
import { useUser } from "@/providers/UserProvider";
import { Select } from "@/components/ui/Select";
import type { HistoryRecord } from "@/lib/types";
import { KpiBar } from "./KpiBar";
import { WeeklyBarChart } from "./WeeklyBarChart";
import { ScoreTrendChart } from "./ScoreTrendChart";
import { ErrorRanking } from "./ErrorRanking";
import { HistoryTable, HISTORY_PAGE_SIZE } from "./HistoryTable";
import { HistoryDrawer } from "./HistoryDrawer";

const DAY_OPTIONS = [7, 14, 30, 90] as const;

export function DataPage() {
  const { activeUserId, currentUser } = useUser();
  const userId = activeUserId ?? "default";
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();

  const actionId = searchParams.get("action") ?? "";
  const days = Number(searchParams.get("days") ?? "30");
  const error = searchParams.get("error") ?? "";
  const tab = searchParams.get("tab");

  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<HistoryRecord | null>(null);
  const [exporting, setExporting] = useState(false);

  // 仅在同用户内切换筛选/翻页时保留旧数据；切用户不复用上一个用户的数据
  const keepForSameUser = <T,>(
    prev: T | undefined,
    prevQuery?: { queryKey: readonly unknown[] },
  ) => (prevQuery?.queryKey[1] === userId ? prev : undefined);

  const overview = useQuery({
    queryKey: ["overview", userId],
    queryFn: () => client.getOverview(userId),
  });

  const actions = useQuery({
    queryKey: ["actions"],
    queryFn: client.getActions,
  });

  const history = useQuery({
    queryKey: ["history", userId, actionId, days, error, page],
    queryFn: () =>
      client.getHistory({
        userId,
        actionId: actionId || undefined,
        days,
        error: error || undefined,
        limit: HISTORY_PAGE_SIZE,
        offset: (page - 1) * HISTORY_PAGE_SIZE,
      }),
    placeholderData: keepForSameUser,
  });

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value == null || value === "") next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  // 从总览「最常犯的错」跳转（/data?tab=errors）：滚动定位到错误排行
  useEffect(() => {
    if (tab === "errors") {
      requestAnimationFrame(() => {
        document
          .getElementById("data-errors")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, [tab]);

  const handleExport = async () => {
    const total = history.data?.total ?? 0;
    if (total === 0) {
      toast.push("当前筛选下没有可导出的记录", "neutral");
      return;
    }
    setExporting(true);
    try {
      const result = await client.getHistory({
        userId,
        actionId: actionId || undefined,
        days,
        error: error || undefined,
        limit: total,
        offset: 0,
      });
      const headers = ["时间", "日期", "动作", "次数", "组数", "评分", "时长(秒)", "错误"];
      const rows = result.items.map((r) => [
        r.time,
        r.date,
        r.action_name,
        r.reps,
        r.sets,
        r.score ?? "",
        r.duration,
        r.errors.join("；"),
      ]);
      const dateStr = new Date().toISOString().slice(0, 10);
      downloadCsv(
        `训练数据_${currentUser?.name ?? "用户"}_${dateStr}.csv`,
        headers,
        rows,
      );
      toast.push(`已导出 ${result.items.length} 条记录`, "mint");
    } catch {
      toast.push("导出失败", "coral");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-medium text-text1">训练数据</h1>
        <p className="mt-1 text-sm text-text3">查看训练趋势、评分与历史明细。</p>
      </div>

      {/* 筛选栏 */}
      <div className="flex flex-wrap items-end gap-3 rounded-card border border-line1 bg-surface1 px-4 py-3">
        <label className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-[0.12em] text-text2">
            动作
          </span>
          <Select
            value={actionId}
            onChange={(e) => {
              setPage(1);
              setParam("action", e.target.value || null);
            }}
            className="w-40"
          >
            <option value="">全部动作</option>
            {actions.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-[0.12em] text-text2">
            时间范围
          </span>
          <Select
            value={String(days)}
            onChange={(e) => {
              setPage(1);
              setParam("days", e.target.value);
            }}
            className="w-32"
          >
            {DAY_OPTIONS.map((d) => (
              <option key={d} value={String(d)}>
                近 {d} 天
              </option>
            ))}
          </Select>
        </label>

        {error && (
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-[0.12em] text-text2">
              错误筛选
            </span>
            <div className="flex h-10 items-center gap-2 rounded-[10px] border border-coral/30 bg-coral/[0.06] px-3">
              <span className="max-w-[240px] truncate text-sm text-coral">
                {error}
              </span>
              <button
                type="button"
                onClick={() => {
                  setPage(1);
                  setParam("error", null);
                }}
                className="text-xs text-text3 hover:text-text1"
              >
                清除
              </button>
            </div>
          </label>
        )}
      </div>

      <KpiBar
        data={overview.data}
        isLoading={overview.isLoading}
        isError={overview.isError}
        onRetry={() => overview.refetch()}
      />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 min-[1360px]:col-span-7">
          <WeeklyBarChart
            data={overview.data?.weekly_trend}
            isLoading={overview.isLoading}
            isError={overview.isError}
            onRetry={() => overview.refetch()}
          />
        </div>
        <div className="col-span-12 min-[1360px]:col-span-5">
          <ScoreTrendChart
            data={overview.data?.score_trend}
            isLoading={overview.isLoading}
            isError={overview.isError}
            onRetry={() => overview.refetch()}
          />
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 min-[1360px]:col-span-5" id="data-errors">
          <ErrorRanking
            data={overview.data?.top_errors}
            isLoading={overview.isLoading}
            isError={overview.isError}
            onRetry={() => overview.refetch()}
            activeError={error}
            onSelect={(tip) => {
              setPage(1);
              setParam("error", tip === error ? null : tip);
            }}
          />
        </div>
        <div className="col-span-12 min-[1360px]:col-span-7">
          <HistoryTable
            items={history.data?.items}
            total={history.data?.total ?? 0}
            page={page}
            onPageChange={setPage}
            isLoading={history.isLoading}
            isError={history.isError}
            onRetry={() => history.refetch()}
            onSelect={setSelected}
            onExport={handleExport}
            isExporting={exporting}
            filtered={Boolean(actionId || error)}
          />
        </div>
      </div>

      <HistoryDrawer record={selected} onClose={() => setSelected(null)} />
    </div>
  );
}