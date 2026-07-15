import React, { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useReportGeneration } from "../../hooks/useReportGeneration";
import { ReportStepIndicator } from "./ReportStepIndicator";
import { getSessionReports } from "../../services/reportService";

interface ReportGenerationPanelProps {
  sessionId: string;
}

export const ReportGenerationPanel: React.FC<ReportGenerationPanelProps> = ({
  sessionId,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const { reportStatus, isTriggering, error, triggerReport, handleDownload } =
    useReportGeneration(sessionId);

  // Fetch reports count for session
  const { data: sessionReports = [] } = useQuery({
    queryKey: ["session-reports", sessionId],
    queryFn: () => getSessionReports(sessionId),
    enabled: !!sessionId,
    refetchInterval: 3000,
  });

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div className="relative inline-block text-right" ref={panelRef}>
      <div className="flex flex-col items-end gap-1">
        {reportStatus === null ? (
          <button
            onClick={() => {
              setIsOpen(true);
              triggerReport();
            }}
            disabled={isTriggering}
            type="button"
            className="px-3 py-1.5 mt-2 rounded-lg border border-[#1e3a5f] text-[#1e3a5f] bg-slate-50 hover:bg-[#1e3a5f] hover:text-white dark:bg-slate-900 dark:border-indigo-400 dark:text-indigo-400 dark:hover:bg-indigo-400 dark:hover:text-slate-950 transition-all text-sm font-semibold select-none outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isTriggering ? "Creating..." : "Create Report"}
          </button>
        ) : (
          <button
            onClick={() => setIsOpen(!isOpen)}
            type="button"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 mt-2 rounded-lg border border-[#1e3a5f] text-white bg-[#1e3a5f] hover:bg-[#152a45] dark:bg-indigo-500 dark:border-indigo-500 dark:text-slate-900 dark:hover:bg-indigo-400 transition-all text-sm font-semibold select-none outline-none"
          >
            <span>Report Status</span>
            <ChevronDown
              className={`w-3.5 h-3.5 text-white dark:text-slate-955 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            />
          </button>
        )}

        {sessionReports.length > 0 && (
          <Link
            to={`/dashboard/reports?session_id=${sessionId}`}
            className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline mt-1 font-semibold select-none cursor-pointer"
          >
            View Reports ({sessionReports.length})
          </Link>
        )}

        {error && reportStatus === null && (
          <p className="text-[10px] text-rose-500 font-medium max-w-[200px] text-right break-words leading-tight">
            {error}
          </p>
        )}
      </div>

      {isOpen && reportStatus !== null && (
        <div className="absolute right-0 mt-2 w-72 min-w-[280px] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-xl p-4 z-50 transition-all text-left">
          <ReportStepIndicator
            reportStatus={reportStatus}
            onDownload={handleDownload}
            onCreateNew={triggerReport}
          />
        </div>
      )}
    </div>
  );
};
export default ReportGenerationPanel;
