import React from "react";

export interface ConfidencePillProps {
  level?: "High" | "Medium" | "Low" | string;
  score?: number;
}

export const ConfidencePill: React.FC<ConfidencePillProps> = ({ level = "High", score }) => {
  const normLevel = (level || "High").trim();
  const lower = normLevel.toLowerCase();

  const isHigh = lower === "high" || lower.includes("strongly");
  const isMed = lower === "medium" || lower === "med" || lower.includes("partially");

  let badgeStyle = "bg-rose-50 border-rose-200 text-rose-800";
  let dotColor = "bg-rose-500";
  let displayLevel = "Low";

  if (isHigh) {
    badgeStyle = "bg-emerald-50 border-emerald-200 text-emerald-800";
    dotColor = "bg-emerald-500";
    displayLevel = "High";
  } else if (isMed) {
    badgeStyle = "bg-amber-50 border-amber-200 text-amber-800";
    dotColor = "bg-amber-500";
    displayLevel = "Medium";
  }

  // Convert 0-1 float to percentage by multiplying by 100
  const scorePercent =
    score !== undefined && score !== null
      ? Math.round((typeof score === "number" ? score : parseFloat(score as any)) * 100)
      : null;

  return (
    <div className="inline-flex flex-wrap items-center gap-2">
      {/* Confidence Level */}
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${badgeStyle} select-none`}
      >
        <span className={`w-2 h-2 rounded-full ${dotColor}`} />
        <span>Confidence Level: {displayLevel}</span>
      </div>

      {/* Confidence Score */}
      {scorePercent !== null && !isNaN(scorePercent) && (
        <div
          className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 border border-slate-200 text-slate-700 select-none"
        >
          <span>Confidence Score: {scorePercent}%</span>
        </div>
      )}
    </div>
  );
};

