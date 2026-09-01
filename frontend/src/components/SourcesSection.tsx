import React, { useState } from "react";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";

interface EvidenceItem {
  pdf_name: string;
  page_number: number;
  supporting_text: string;
  response_sentence: string;
}

interface SourcesSectionProps {
  sources: EvidenceItem[];
}

export const SourcesSection: React.FC<SourcesSectionProps> = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-4 border border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50/50 dark:bg-slate-900/20 overflow-hidden select-none transition-colors duration-200">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white font-semibold text-xs transition-colors duration-150"
      >
        <div className="flex items-center space-x-2">
          <FileText className="w-3.5 h-3.5" />
          <span>Sources & Evidence ({sources.length})</span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-3.5 h-3.5" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5" />
        )}
      </button>

      {isOpen && (
        <div className="px-3 pb-3 divide-y divide-slate-100 dark:divide-slate-850 max-h-60 overflow-y-auto bg-white dark:bg-slate-950 transition-colors duration-200">
          {sources.map((src, idx) => (
            <div key={idx} className="py-2.5 first:pt-1 last:pb-0 text-[11px] space-y-1">
              <div className="flex items-center space-x-2 text-clinical-600 dark:text-clinical-400 font-bold">
                <FileText className="w-3 h-3 text-slate-400 shrink-0" />
                <span className="truncate max-w-[280px]">{src.pdf_name}</span>
                <span className="bg-slate-100 dark:bg-slate-850 text-slate-600 dark:text-slate-400 border border-slate-200/50 dark:border-slate-800 px-1 py-0.5 rounded text-[9px] font-mono leading-none">
                  Page {src.page_number}
                </span>
              </div>
              <div className="pl-5 text-slate-600 dark:text-slate-350 italic leading-relaxed font-sans border-l border-slate-200 dark:border-slate-850">
                "{src.supporting_text}"
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
