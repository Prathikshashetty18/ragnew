import React from "react";
import { BookOpen, Database, FileText, CheckCircle2, Sparkles, Cpu, Layers } from "lucide-react";

interface Document {
  id: number;
  name: string;
  chunk_count: number;
  scope: string;
  created_at: string;
}

interface KnowledgeBaseViewProps {
  documents: Document[];
  onConsultGuideline: (docName: string) => void;
}

export const KnowledgeBaseView: React.FC<KnowledgeBaseViewProps> = ({
  documents,
  onConsultGuideline
}) => {
  const kbDocs = documents.filter((d) => d.scope === "knowledge_base");
  const totalChunks = kbDocs.reduce((acc, curr) => acc + (curr.chunk_count || 0), 0);

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-emerald-600 text-xs font-bold uppercase tracking-wider mb-1">
            <BookOpen className="w-4 h-4" />
            <span>Clinical Reference</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Hospital Clinical Knowledge Base
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Peer-reviewed hospital clinical practice guidelines, consensus protocols, and treatment standards.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="flex items-center space-x-1.5 px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>FAISS Index Active</span>
          </span>
        </div>
      </div>

      {/* Vector Store Architecture Card */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Embeddings Model</span>
          <div className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
            <Cpu className="w-4 h-4 text-blue-600" />
            <span>all-MiniLM-L6-v2</span>
          </div>
          <p className="text-[10px] text-slate-400">384-dimensional dense vectors</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Vector Store</span>
          <div className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
            <Database className="w-4 h-4 text-purple-600" />
            <span>FAISS IndexFlatIP</span>
          </div>
          <p className="text-[10px] text-slate-400">Normalized inner product search</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Keyword Search</span>
          <div className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
            <Layers className="w-4 h-4 text-amber-600" />
            <span>Pure Python BM25</span>
          </div>
          <p className="text-[10px] text-slate-400">Reciprocal Rank Fusion (RRF)</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Indexed Chunks</span>
          <div className="text-lg font-black text-slate-900 flex items-center space-x-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{totalChunks} Chunks</span>
          </div>
          <p className="text-[10px] text-slate-400">500 tokens / 50 token overlap</p>
        </div>
      </div>

      {/* Guidelines Cards */}
      <div className="space-y-4">
        <h3 className="text-base font-bold text-slate-900">Approved Medical Guidelines</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {kbDocs.map((doc) => (
            <div
              key={doc.id}
              className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4 flex flex-col justify-between"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold">
                    <FileText className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-bold">
                    {doc.chunk_count} Chunks
                  </span>
                </div>

                <h4 className="text-sm font-bold text-slate-900 leading-snug">
                  {doc.name}
                </h4>

                <p className="text-xs text-slate-500 leading-relaxed">
                  Hospital clinical standards covering diagnostic criteria, CURB-65 risk stratification, empirical antimicrobial recommendations, and monitoring protocols.
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-400">
                  Indexed {new Date(doc.created_at).toLocaleDateString()}
                </span>
                <button
                  onClick={() => onConsultGuideline(doc.name)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold rounded-xl transition-all cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Consult in AI</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
