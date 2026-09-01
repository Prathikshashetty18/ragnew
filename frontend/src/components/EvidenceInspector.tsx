import React from "react";
import { X, FileText, CheckCircle, AlertTriangle, Scale, ShieldAlert } from "lucide-react";

interface InspectedSentence {
  sentence: string;
  status: string;
  score: number;
  source_sentence: string;
  pdf_name: string;
  page_number: number;
}

interface EvidenceInspectorProps {
  evidence: InspectedSentence | null;
  onClose: () => void;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({ evidence, onClose }) => {
  if (!evidence) return null;

  const isSupported = evidence.status === "Supported";
  const isPartial = evidence.status === "Partially Supported";
  
  let statusColor = "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900";
  let statusIcon = <ShieldAlert className="w-4 h-4 mr-1.5" />;
  
  if (isSupported) {
    statusColor = "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900";
    statusIcon = <CheckCircle className="w-4 h-4 mr-1.5" />;
  } else if (isPartial) {
    statusColor = "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900";
    statusIcon = <AlertTriangle className="w-4 h-4 mr-1.5" />;
  }

  return (
    <div className="w-80 md:w-96 border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 flex flex-col h-full shadow-lg z-20 animate-slideIn">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-900/50">
        <div className="flex items-center space-x-2">
          <Scale className="w-4.5 h-4.5 text-clinical-600 dark:text-clinical-400" />
          <h3 className="font-bold text-slate-850 dark:text-slate-100 text-sm">Evidence Inspector</h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
          aria-label="Close inspector"
        >
          <X className="w-4.5 h-4.5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Inspected Sentence */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            Verified Sentence
          </span>
          <p className="text-sm text-slate-700 dark:text-slate-350 bg-slate-50 dark:bg-slate-900 p-3 rounded-xl border border-slate-100 dark:border-slate-850 italic font-medium leading-relaxed">
            "{evidence.sentence}"
          </p>
        </div>

        {/* Verification Status */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            Verification Status
          </span>
          <div className={`flex items-center px-3 py-2.5 rounded-xl border text-xs font-semibold ${statusColor}`}>
            {statusIcon}
            <span>
              {evidence.status} ({Math.round(evidence.score * 100)}% match score)
            </span>
          </div>
        </div>

        {/* Sources metadata */}
        <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-850">
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">
            Guideline Source
          </span>

          <div className="flex items-start space-x-3 p-3 bg-slate-50/50 dark:bg-slate-900/30 border border-slate-150 dark:border-slate-850 rounded-xl text-xs">
            <FileText className="w-4 h-4 text-clinical-600 dark:text-clinical-400 shrink-0 mt-0.5" />
            <div className="space-y-1 min-w-0">
              <p className="font-semibold text-slate-800 dark:text-slate-200 truncate" title={evidence.pdf_name}>
                {evidence.pdf_name}
              </p>
              <div className="flex items-center space-x-2 text-slate-500 dark:text-slate-400">
                <span className="bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 rounded text-[10px]">
                  Page {evidence.page_number}
                </span>
                <span>•</span>
                <span>Similarity: {Math.round(evidence.score * 100)}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Supporting passage */}
        {isSupported || isPartial ? (
          <div className="space-y-1.5 pt-2">
            <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              Supporting Passage
            </span>
            <div className="text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-905 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 font-mono leading-relaxed whitespace-pre-wrap">
              "{evidence.source_sentence}"
            </div>
          </div>
        ) : (
          <div className="p-3 bg-red-50/50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/50 rounded-xl text-xs text-red-650 dark:text-red-300 leading-relaxed italic">
            This statement does not directly align with any retrieved guideline passages. The response has been downgraded to Low confidence as a safeguard against potential LLM hallucinations.
          </div>
        )}
      </div>
    </div>
  );
};
