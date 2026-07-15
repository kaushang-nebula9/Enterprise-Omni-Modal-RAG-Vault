import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import {
  Database,
  ArrowLeft,
  ChevronDown,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { databaseHealthService } from "../../services/databaseHealthService";

export const DatabaseDrillDownPage: React.FC = () => {
  const navigate = useNavigate();
  const { connectionId } = useParams<{ connectionId: string }>();

  // Health & Analytics State
  const [queriesPage, setQueriesPage] = useState(1);
  const [queryHistory, setQueryHistory] = useState<any[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [isQueriesLoading, setIsQueriesLoading] = useState(false);
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>(
    {},
  );
  const [expandedSqls, setExpandedSqls] = useState<Record<number, boolean>>({});

  const lastFetchedRef = React.useRef<string>("");

  // Health Queries
  const { data: dbStatuses = [] } = useQuery({
    queryKey: ["database-health-status"],
    queryFn: databaseHealthService.getStatus,
  });

  const { data: connSchema = [], isLoading: isSchemaLoading } = useQuery({
    queryKey: ["database-health-schema", connectionId],
    queryFn: () => databaseHealthService.getConnectionSchema(connectionId!),
    enabled: !!connectionId,
  });

  // Query History Pagination Loader
  const loadQueries = async (connId: string, pageNum: number) => {
    setIsQueriesLoading(true);
    try {
      const res = await databaseHealthService.getConnectionQueries(
        connId,
        pageNum,
        10,
      );
      setQueryHistory(res.items);
      setTotalPages(res.pages || Math.ceil(res.total / 10) || 1);
    } catch (err) {
      console.error("Failed to load queries", err);
    } finally {
      setIsQueriesLoading(false);
    }
  };

  useEffect(() => {
    if (connectionId) {
      const key = `${connectionId}-${queriesPage}`;
      if (lastFetchedRef.current !== key) {
        lastFetchedRef.current = key;
        setQueryHistory([]);
        setExpandedSqls({});
        loadQueries(connectionId, queriesPage);
      }
    }
  }, [connectionId, queriesPage]);

  useEffect(() => {
    setQueriesPage(1);
  }, [connectionId]);

  const toggleTable = (tableName: string) => {
    setExpandedTables((prev) => ({ ...prev, [tableName]: !prev[tableName] }));
  };

  const toggleSql = (idx: number) => {
    setExpandedSqls((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

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
        {/* SECTION D: Per-Database Drill Down */}
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-slate-200/60 dark:border-slate-800/60 pb-4">
            <button
              onClick={() => navigate("/dashboard/databases/analytics")}
              className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Overview
            </button>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-855 dark:text-slate-150">
                Database Drill-down:{" "}
                {dbStatuses.find((s: any) => s.connection_id === connectionId)
                  ?.name || "Details"}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-6">
            {/* Paginated Query History Table */}
            <div className="flex flex-col gap-3 w-full">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500 font-sora">
                Query History
              </h3>
              <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                        <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                          Timestamp
                        </th>
                        <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                          User
                        </th>
                        <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                          Question
                        </th>
                        <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                          SQL
                        </th>
                        <th className="px-4 py-3.5 text-left font-semibold text-slate-600 dark:text-slate-400">
                          Latency
                        </th>
                        <th className="px-4 py-3.5 text-right font-semibold text-slate-600 dark:text-slate-400">
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {queryHistory.length === 0 ? (
                        <tr>
                          <td
                            colSpan={6}
                            className="px-4 py-16 text-center text-slate-400 dark:text-slate-500"
                          >
                            {isQueriesLoading
                              ? "Loading queries..."
                              : "No queries run on this database yet."}
                          </td>
                        </tr>
                      ) : (
                        queryHistory.map((q: any, idx: number) => {
                          const isSqlExpanded = expandedSqls[idx];
                          const sqlVal = q.generated_sql || "N/A";
                          const truncatedSql =
                            sqlVal.length > 120
                              ? sqlVal.substring(0, 120) + "..."
                              : sqlVal;
                          return (
                            <tr
                              key={idx}
                              className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors"
                            >
                              <td className="px-4 py-3.5 text-slate-500 whitespace-nowrap">
                                {new Date(q.timestamp).toLocaleString()}
                              </td>
                              <td
                                className="px-4 py-3.5 text-slate-700 dark:text-slate-350 truncate max-w-[200px]"
                                title={q.user_email || "Unknown User"}
                              >
                                {q.user_name ||
                                  (q.user_email &&
                                  q.user_email !== "unknown@example.com"
                                    ? q.user_email.split("@")[0]
                                    : "Unknown User")}
                              </td>
                              <td
                                className="px-4 py-3.5 text-slate-700 dark:text-slate-300 max-w-[300px] truncate"
                                title={q.natural_language_query}
                              >
                                {q.natural_language_query || "Unknown"}
                              </td>
                              <td className="px-4 py-3.5 font-mono text-xs text-slate-650 dark:text-slate-400 max-w-[400px]">
                                <div className="flex flex-col">
                                  <span className="break-all text-[11px]">
                                    {isSqlExpanded ? sqlVal : truncatedSql}
                                  </span>
                                  {sqlVal.length > 120 && (
                                    <button
                                      onClick={() => toggleSql(idx)}
                                      className="text-[9px] text-indigo-650 dark:text-indigo-400 hover:underline font-sans text-left mt-0.5 cursor-pointer"
                                    >
                                      {isSqlExpanded
                                        ? "Show less"
                                        : "Show full SQL"}
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td className="px-4 py-3.5 text-slate-500 whitespace-nowrap">
                                {q.execution_time_ms}ms
                              </td>
                              <td className="px-4 py-3.5 text-right">
                                {q.status === "success" ? (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400 border border-emerald-250 dark:border-emerald-900/50">
                                    Success
                                  </span>
                                ) : (
                                  <span
                                    className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-medium bg-rose-550 text-rose-700 dark:bg-rose-950/30 dark:text-rose-400 border border-rose-250 dark:border-rose-900/50"
                                    title={q.error_message || "Error"}
                                  >
                                    Failed
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination Footer */}
                {queryHistory.length > 0 && (
                  <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/20 dark:bg-slate-900/10 flex items-center justify-between select-none">
                    <span className="text-sm text-slate-500 dark:text-slate-400">
                      Showing page{" "}
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {queriesPage}
                      </span>{" "}
                      of{" "}
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {totalPages}
                      </span>
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          setQueriesPage((p) => Math.max(1, p - 1))
                        }
                        disabled={queriesPage === 1 || isQueriesLoading}
                        className="p-2 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none transition-colors cursor-pointer"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() =>
                          setQueriesPage((p) => Math.min(totalPages, p + 1))
                        }
                        disabled={
                          queriesPage === totalPages || isQueriesLoading
                        }
                        className="p-2 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 disabled:pointer-events-none transition-colors cursor-pointer"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Accordion Schema Viewer */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-3 w-full">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500 font-sora">
                Database Schema
              </h3>
              {isSchemaLoading ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-5 h-5 animate-spin text-indigo-600 dark:text-indigo-400" />
                </div>
              ) : connSchema.length === 0 ? (
                <div className="text-xs text-slate-400 py-6 text-center">
                  No schema cached. Try refreshing schema.
                </div>
              ) : (
                <div className="flex flex-col gap-2 max-h-fit overflow-y-auto pr-1">
                  {connSchema.map((tbl: any) => {
                    const isExpanded = expandedTables[tbl.table_name];
                    return (
                      <div
                        key={tbl.table_name}
                        className="border border-slate-100 dark:border-slate-800/50 rounded-lg overflow-hidden"
                      >
                        <button
                          onClick={() => toggleTable(tbl.table_name)}
                          className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/40 hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors text-left"
                        >
                          <span className="truncate">{tbl.table_name}</span>
                          <ChevronDown
                            className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          />
                        </button>
                        {isExpanded && (
                          <div className="px-3 py-2 bg-white dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800/50 flex flex-col gap-1.5 max-h-[220px] overflow-y-auto">
                            {tbl.columns.map((col: any) => {
                              const isPk = tbl.primary_key?.includes(col.name);
                              const fkRef = tbl.foreign_keys?.find((fk: any) =>
                                fk.constrained_columns.includes(col.name),
                              );
                              return (
                                <div
                                  key={col.name}
                                  className="flex justify-between items-center text-sm py-1"
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono text-slate-700 dark:text-slate-350 font-medium">
                                      {col.name}
                                    </span>
                                    {isPk && (
                                      <span className="bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900/30 px-1 py-0.5 rounded text-[9px] font-bold scale-90">
                                        PK
                                      </span>
                                    )}
                                    {fkRef && (
                                      <span
                                        className="bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-900/30 px-1 py-0.5 rounded text-[9px] font-bold cursor-help scale-90"
                                        title={`References ${fkRef.referred_table}(${fkRef.referred_columns})`}
                                      >
                                        FK → {fkRef.referred_table}
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-slate-400 dark:text-slate-500 uppercase font-mono text-xs">
                                    {col.type}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DatabaseDrillDownPage;
