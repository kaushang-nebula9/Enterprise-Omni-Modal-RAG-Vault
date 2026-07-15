import React from "react";
import { Check, X, Circle } from "lucide-react";
import type { ReportStatus } from "../../types/chat";

interface ReportStepIndicatorProps {
  reportStatus: ReportStatus;
  onDownload: () => void;
  onCreateNew: () => void;
}

const STEP_LABELS = {
  gather: "Gathering Session Data",
  cluster: "Clustering Topics",
  synthesize: "Synthesizing Content",
  assemble: "Assembling Report",
  render: "Rendering PDF",
  deliver: "Finalizing",
} as const;

const STEPS_ORDER = [
  "gather",
  "cluster",
  "synthesize",
  "assemble",
  "render",
  "deliver",
] as const;

export const ReportStepIndicator: React.FC<ReportStepIndicatorProps> = ({
  reportStatus,
  onDownload,
  onCreateNew,
}) => {
  const stepsMap = React.useMemo(() => {
    return new Map(reportStatus.steps.map((s) => [s.step_name, s]));
  }, [reportStatus.steps]);

  return (
    <div className="flex flex-col gap-4 w-full select-none">
      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-800 pb-2">
        Report Generation Status
      </h3>
      <div className="flex flex-col gap-3">
        {STEPS_ORDER.map((stepKey) => {
          const step = stepsMap.get(stepKey);
          const label = STEP_LABELS[stepKey];

          let icon = (
            <Circle className="w-4 h-4 text-slate-300 dark:text-slate-650" />
          );
          let duration = "";
          let errorMessage = "";

          if (step) {
            if (step.status === "success") {
              icon = <Check className="w-4 h-4 text-emerald-500 font-bold" />;
              if (step.duration_ms !== null) {
                duration = `${(step.duration_ms / 1000).toFixed(1)}s`;
              }
            } else if (step.status === "running") {
              icon = (
                <div className="animate-spin rounded-full border-2 border-blue-500 border-t-transparent w-4 h-4" />
              );
            } else if (step.status === "failed") {
              icon = <X className="w-4 h-4 text-rose-500 font-bold" />;
              errorMessage = step.error_message || "An error occurred";
            }
          }

          return (
            <div
              key={stepKey}
              className="flex items-start gap-3 text-xs leading-normal"
            >
              <div className="mt-0.5 shrink-0 flex items-center justify-center w-5 h-5">
                {icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-700 dark:text-slate-300">
                  {label}
                </p>
                {errorMessage && (
                  <p className="text-[10px] text-rose-500 mt-0.5 break-words font-medium">
                    {errorMessage}
                  </p>
                )}
                {duration && (
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                    {duration}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="border-t border-slate-100 dark:border-slate-800 pt-3 flex flex-col gap-2 w-full">
        {reportStatus.status === "complete" ? (
          <>
            <button
              onClick={onDownload}
              type="button"
              className="w-full py-2 px-4 rounded-lg bg-[#1e3a5f] hover:bg-[#152a45] text-white text-xs font-bold shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#1e3a5f] text-center"
            >
              Download Report
            </button>
            <button
              onClick={onCreateNew}
              type="button"
              className="w-full py-2 px-4 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-55 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold shadow-sm transition-all focus:outline-none text-center"
            >
              Create New Report
            </button>
          </>
        ) : reportStatus.status === "failed" ? (
          <>
            <p className="text-xs text-rose-500 font-semibold text-center leading-normal mb-1">
              Report generation failed.
            </p>
            <button
              onClick={onCreateNew}
              type="button"
              className="w-full py-2 px-4 rounded-lg bg-[#1e3a5f] hover:bg-[#152a45] text-white text-xs font-bold shadow-sm transition-all focus:outline-none text-center"
            >
              Try Again
            </button>
          </>
        ) : (
          <p className="text-xs text-slate-400 dark:text-slate-500 text-center font-medium animate-pulse">
            Generating report, you can continue chatting...
          </p>
        )}
      </div>
    </div>
  );
};
