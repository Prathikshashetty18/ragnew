import React from "react";
import { ShieldCheck, AlertCircle, ShieldAlert } from "lucide-react";

interface ConfidencePillProps {
  level: "High" | "Medium" | "Low" | string;
  score: number;
}

export const ConfidencePill: React.FC<ConfidencePillProps> = ({ level, score }) => {
  const isHigh = level.toLowerCase() === "high";
  const isMedium = level.toLowerCase() === "medium";

  let bgClass = "bg-red-50 border-red-200 text-red-700 dark:bg-red-950/30 dark:border-red-900/50 dark:text-red-300";
  let icon = <ShieldAlert className="w-3.5 h-3.5 mr-1 text-red-650 dark:text-red-405" />;
  let tooltipText = "Warning: Contains unsupported statements or low context match.";

  if (isHigh) {
    bgClass = "bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-950/30 dark:border-emerald-900/50 dark:text-emerald-300";
    icon = <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-600 dark:text-emerald-400" />;
    tooltipText = "Verified: All sentences match source clinical documents with high similarity.";
  } else if (isMedium) {
    bgClass = "bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-950/30 dark:border-amber-900/50 dark:text-amber-300";
    icon = <AlertCircle className="w-3.5 h-3.5 mr-1 text-amber-600 dark:text-amber-400" />;
    tooltipText = "Caution: Clinical context matched, but verification scores are moderate.";
  }

  return (
    <div
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold border ${bgClass} select-none cursor-help transition-all duration-200`}
      title={`${tooltipText} (Score: ${score})`}
    >
      {icon}
      <span>{level} Confidence ({Math.round(score * 100)}%)</span>
    </div>
  );
};
