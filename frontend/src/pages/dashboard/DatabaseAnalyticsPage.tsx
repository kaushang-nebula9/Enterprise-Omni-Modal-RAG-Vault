import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Database, ArrowLeft, Loader2 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  CartesianGrid,
} from "recharts";
import { databaseHealthService } from "../../services/databaseHealthService";

export const DatabaseAnalyticsPage: React.FC = () => {
  const navigate = useNavigate();

  // Health Queries
  const { data: dbStatuses = [], isLoading: isStatusesLoading } = useQuery({
    queryKey: ["database-health-status"],
    queryFn: databaseHealthService.getStatus,
  });

  const { data: dbAnalytics, isLoading: isAnalyticsLoading } = useQuery({
    queryKey: ["database-health-analytics"],
    queryFn: databaseHealthService.getAnalytics,
  });

  function formatRelativeTime(iso: string | null): string {
    if (!iso) return "Never";
    const date = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  }

  return (
    <div className="space-y-6 text-slate-800 dark:text-slate-100 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 shrink-0">
        <div className="flex flex-col gap-1.5">
          <button
            onClick={() => navigate("/dashboard/databases")}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors w-fit cursor-pointer mb-1"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Databases
          </button>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Database className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
            Database Health & Analytics
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Monitor query latencies, connection status, schema caches, and
            analytics for all registered tenant databases.
          </p>
        </div>
      </div>

      <div className=" flex flex-col gap-6 shadow-sm">
        {/* OVERVIEW MAIN VIEW: SECTIONS A, B, C */}
        <div className="flex flex-col gap-6">
          {/* SECTION A: Per-database Status Cards */}
          <div className="flex flex-col gap-3">
            {/* <h3 className="text-xs font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500 font-sora">
                Connected Databases status
              </h3> */}
            {isStatusesLoading ? (
              <div className="flex justify-center items-center py-10 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
              </div>
            ) : dbStatuses.length === 0 ? (
              <div className="py-10 text-center text-slate-450 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm">
                No databases connected to overview.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {dbStatuses.map((s: any) => {
                  return (
                    <div
                      key={s.connection_id}
                      onClick={() =>
                        navigate(
                          `/dashboard/databases/analytics/${s.connection_id}`,
                        )
                      }
                      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm hover:shadow hover:border-slate-300 dark:hover:border-slate-700 transition-all cursor-pointer flex flex-col justify-between gap-2 group relative overflow-hidden"
                    >
                      <div className="flex items-center">
                        <h4 className="text-lg font-bold text-slate-800 dark:text-slate-100 group-hover:text-indigo-650 dark:group-hover:text-indigo-400 transition-colors truncate">
                          {s.name}
                        </h4>

                        {/* Status Indicator */}
                        <div className="ml-auto flex items-center justify-between gap-1">
                          <div className="flex items-center gap-2">
                            {s.status === "active" ? (
                              <span className="flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-450 bg-emerald-400/70 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-550 bg-emerald-500"></span>
                              </span>
                            ) : s.status === "degraded" ? (
                              <span className="h-2 w-2 rounded-full bg-amber-500"></span>
                            ) : (
                              <span className="h-2 w-2 rounded-full bg-rose-550 bg-rose-500"></span>
                            )}
                          </div>
                          <span className="text-xs font-bold text-slate-800 dark:text-slate-200 capitalize font-sans">
                            {s.status}
                          </span>
                        </div>
                      </div>

                      <div className="border-t border-slate-100 dark:border-slate-800/80 pt-3 flex flex-col gap-1.5 text-sm">
                        <div className="flex justify-between items-center text-slate-550 dark:text-slate-400">
                          <span>Queries:</span>
                          <span className="font-semibold text-slate-700 dark:text-slate-300">
                            {s.total_queries ?? 0}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-slate-550 dark:text-slate-400">
                          <span>Last Successful Query:</span>
                          <span className="font-semibold text-slate-700 dark:text-slate-300">
                            {formatRelativeTime(s.last_successful_query_at)}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-slate-550 dark:text-slate-400">
                          <span>Schema Introspected:</span>
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-slate-700 dark:text-slate-300">
                              {formatRelativeTime(
                                s.schema_last_introspected_at,
                              )}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* SECOND ROW: STATS & FAILURE REASONS + VOLUME CHART */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* SECTION B: Query Analytics Stats */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-5 lg:col-span-1 justify-between">
              <div className="flex flex-col gap-4">
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-500 font-sora">
                  Query Stats
                </h3>

                {/* Stat Boxes */}
                <div className="grid grid-cols-3 gap-2 text-center font-sans">
                  <div className="bg-slate-55 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/50">
                    <span className="text-xs text-slate-400 font-medium">
                      7 Days
                    </span>
                    <div className="text-lg font-bold text-slate-800 dark:text-slate-200 mt-0.5 font-sora">
                      {isAnalyticsLoading
                        ? "-"
                        : dbAnalytics?.metrics.last_7_days}
                    </div>
                  </div>
                  <div className="bg-slate-55 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/50">
                    <span className="text-xs text-slate-400 font-medium">
                      30 Days
                    </span>
                    <div className="text-lg font-bold text-slate-800 dark:text-slate-200 mt-0.5 font-sora">
                      {isAnalyticsLoading
                        ? "-"
                        : dbAnalytics?.metrics.last_30_days}
                    </div>
                  </div>
                  <div className="bg-slate-55 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/50">
                    <span className="text-xs text-slate-400 font-medium">
                      All Time
                    </span>
                    <div className="text-lg font-bold text-slate-800 dark:text-slate-200 mt-0.5 font-sora">
                      {isAnalyticsLoading ? "-" : dbAnalytics?.metrics.total}
                    </div>
                  </div>
                </div>

                {/* Ratio Bar */}
                <div className="flex flex-col gap-1.5 mt-2">
                  <div className="flex justify-between items-baseline text-sm text-slate-500">
                    <span>Success vs Failed</span>
                    <span className="font-bold text-slate-850 dark:text-slate-150">
                      {isAnalyticsLoading
                        ? "0%"
                        : `${dbAnalytics?.success_rate.success_rate_percentage}%`}
                    </span>
                  </div>
                  <div className="w-full bg-rose-300 dark:bg-rose-900/60 h-2 rounded-full overflow-hidden flex">
                    {!isAnalyticsLoading &&
                    dbAnalytics &&
                    dbAnalytics.success_rate.success_count +
                      dbAnalytics.success_rate.failed_count >
                      0 ? (
                      <div
                        className="bg-emerald-500 h-full transition-all duration-500"
                        style={{
                          width: `${dbAnalytics.success_rate.success_rate_percentage}%`,
                        }}
                      />
                    ) : (
                      <div className="bg-slate-200 dark:bg-slate-800 h-full w-full" />
                    )}
                  </div>
                  <div className="flex justify-between text-xs text-slate-400 mt-0.5">
                    <span className="text-emerald-600 dark:text-emerald-450 font-medium">
                      {isAnalyticsLoading
                        ? 0
                        : dbAnalytics?.success_rate.success_count}{" "}
                      Successes
                    </span>
                    <span className="text-rose-600 dark:text-rose-450 font-medium">
                      {isAnalyticsLoading
                        ? 0
                        : dbAnalytics?.success_rate.failed_count}{" "}
                      Failures
                    </span>
                  </div>
                </div>
              </div>

              {/* Failure Reasons list */}
              <div className="border-t border-slate-100 dark:border-slate-800/80 pt-4 flex flex-col gap-2.5">
                <span className="text-sm font-bold text-slate-450 dark:text-slate-500">
                  Failure Reasons Breakdown
                </span>
                {isAnalyticsLoading ? (
                  <div className="text-xs text-slate-400 py-3 text-center">
                    Loading reasons...
                  </div>
                ) : !dbAnalytics ||
                  Object.values(dbAnalytics.failure_reasons).reduce(
                    (a, b) => a + b,
                    0,
                  ) === 0 ? (
                  <div className="text-[11px] text-slate-400 py-2 text-center bg-slate-55 bg-slate-50 dark:bg-slate-800/20 border border-slate-100 dark:border-slate-800/50 rounded-lg">
                    No failures recorded. Nice!
                  </div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {Object.entries(dbAnalytics.failure_reasons)
                      .sort((a, b) => b[1] - a[1])
                      .map(([reason, count]) => (
                        <div
                          key={reason}
                          className="flex justify-between items-center text-xs"
                        >
                          <span className="text-slate-650 dark:text-slate-400 font-medium">
                            {reason}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-rose-50 dark:bg-rose-900/20 text-rose-600 dark:text-rose-400 font-bold font-mono text-xs">
                            {count}
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>

            {/* SECTION C: Query Volume Chart */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4 lg:col-span-2 min-h-[300px]">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500 font-sora">
                  Query Volume (Last 30 Days)
                </h3>
              </div>

              {isAnalyticsLoading ? (
                <div className="flex-1 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-650" />
                </div>
              ) : !dbAnalytics || dbAnalytics.query_volume.length === 0 ? (
                <div className="flex-1 flex items-center justify-center text-xs text-slate-400">
                  No query logs available in range.
                </div>
              ) : (
                <div className="flex-1 w-full min-h-[220px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={dbAnalytics.query_volume}
                      margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        className="stroke-slate-500 dark:stroke-slate-800/80"
                        stroke="currentColor"
                        opacity={0.3}
                      />
                      <XAxis
                        dataKey="date"
                        tickFormatter={(str) => {
                          const parts = str.split("-");
                          return parts.length > 2
                            ? `${parts[1]}/${parts[2]}`
                            : str;
                        }}
                        interval={4}
                        stroke="currentColor"
                        className="text-slate-700 dark:text-slate-400 text-xs font-sans"
                        tickLine={false}
                      />
                      <YAxis
                        allowDecimals={false}
                        stroke="currentColor"
                        className="text-slate-700 dark:text-slate-400 text-xs font-mono"
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(99, 102, 241, 0.08)", radius: 4 }}
                        contentStyle={{
                          backgroundColor: "rgba(15, 23, 42, 0.95)",
                          borderColor: "rgba(51, 65, 85, 0.5)",
                          borderRadius: "8px",
                          color: "#f8fafc",
                          fontSize: "11px",
                          fontFamily: "Inter, sans-serif",
                        }}
                        labelFormatter={(label) => `Date: ${label}`}
                        formatter={(value) => [`${value} queries`, "Volume"]}
                      />
                      <Bar dataKey="count" fill="#4f46e5" radius={[4, 4, 0, 0]}>
                        {dbAnalytics.query_volume.map(
                          (_: any, index: number) => (
                            <Cell
                              key={`cell-${index}`}
                              fill="#6366f1"
                              className="hover:fill-indigo-700 dark:hover:fill-indigo-400 transition-colors"
                            />
                          ),
                        )}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
export default DatabaseAnalyticsPage;
