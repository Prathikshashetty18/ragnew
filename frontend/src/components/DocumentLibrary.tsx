import React, { useState, useRef } from "react";
import { 
  FileText, Upload, CheckCircle2, Loader2, Sparkles, 
  Search, Filter, Database
} from "lucide-react";
import type { Document, Patient } from "../types";

interface DocumentLibraryProps {
  documents: Document[];
  patients: Patient[];
  onUploadFile: (file: File, scope: string, patientId?: string) => Promise<any>;
  onAskAboutDoc: (doc: Document) => void;
  isLoading?: boolean;
}

export const DocumentLibrary: React.FC<DocumentLibraryProps> = ({
  documents,
  patients,
  onUploadFile,
  onAskAboutDoc
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedScopeFilter, setSelectedScopeFilter] = useState<string>("all");
  const [uploadScope, setUploadScope] = useState<string>("knowledge_base");
  const [uploadPatientId, setUploadPatientId] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSubmit = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!file.name.endsWith(".pdf")) {
        alert("Only PDF documents are supported for clinical RAG indexing.");
        return;
      }

      setIsUploading(true);
      setUploadSuccessMsg(null);
      try {
        await onUploadFile(file, uploadScope, uploadPatientId || undefined);
        setUploadSuccessMsg(`Successfully uploaded and indexed "${file.name}"!`);
        setTimeout(() => setUploadSuccessMsg(null), 4000);
      } catch (err: any) {
        alert(err.message || "Upload failed.");
      } finally {
        setIsUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    }
  };

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesScope = selectedScopeFilter === "all" || doc.scope === selectedScopeFilter;
    return matchesSearch && matchesScope;
  });

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-1">
            <Database className="w-4 h-4" />
            <span>Document Repository</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Medical Document Library & Vector Index
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage hospital guidelines, patient imaging reports, lab panels, and clinical literature.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSubmit}
            accept=".pdf"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Chunking & Indexing...</span>
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                <span>Upload New Medical PDF</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
        <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
          Upload Destination & Scope
        </span>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
              Select Retrieval Scope
            </label>
            <select
              value={uploadScope}
              onChange={(e) => setUploadScope(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-medium text-slate-800 outline-none focus:border-blue-500"
            >
              <option value="knowledge_base">Hospital Knowledge Base (General Guidelines)</option>
              <option value="patient">Patient-Specific Document (Attached to Chart)</option>
              <option value="temporary">Temporary Session PDF (Personal Literature)</option>
            </select>
          </div>

          {uploadScope === "patient" && (
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Attach to Patient
              </label>
              <select
                value={uploadPatientId}
                onChange={(e) => setUploadPatientId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-medium text-slate-800 outline-none focus:border-blue-500"
              >
                <option value="">Select a Patient...</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>{p.id} - {p.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-end">
            <p className="text-[11px] text-slate-500 leading-relaxed">
              Uploaded PDFs undergo automatic text extraction, semantic chunking (500 tokens), and dense vector indexing via <strong>FAISS</strong> + <strong>BM25</strong>.
            </p>
          </div>
        </div>

        {uploadSuccessMsg && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 font-semibold flex items-center space-x-2 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{uploadSuccessMsg}</span>
          </div>
        )}
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search documents by filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-900 outline-none focus:border-blue-500 focus:bg-white"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <div className="flex bg-slate-100 p-1 rounded-xl text-xs font-semibold">
            {[
              { id: "all", label: "All Documents" },
              { id: "knowledge_base", label: "Guidelines" },
              { id: "patient", label: "Patient Charts" },
              { id: "temporary", label: "Session PDFs" }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedScopeFilter(tab.id)}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  selectedScopeFilter === tab.id
                    ? "bg-white text-blue-700 shadow-xs"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3.5 px-5">Document Name</th>
                <th className="py-3.5 px-4">Retrieval Scope</th>
                <th className="py-3.5 px-4">Patient Link</th>
                <th className="py-3.5 px-4">Chunks</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Date Uploaded</th>
                <th className="py-3.5 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    No documents match your query.
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-5 font-semibold text-slate-900 flex items-center space-x-2.5">
                      <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                        <FileText className="w-4 h-4" />
                      </div>
                      <span className="truncate max-w-xs">{doc.name}</span>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className={`px-2.5 py-0.5 rounded-full font-bold text-[10px] ${
                        doc.scope === "knowledge_base" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                        doc.scope === "patient" ? "bg-blue-50 text-blue-700 border border-blue-200" :
                        "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}>
                        {doc.scope === "knowledge_base" ? "Hospital Guideline" :
                         doc.scope === "patient" ? "Patient Chart" : "Session PDF"}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-mono font-bold text-slate-700">
                      {doc.patient_id ? doc.patient_id : "—"}
                    </td>

                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-600">
                      {doc.chunk_count} chunks
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center space-x-1 text-emerald-600 font-semibold text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Indexed</span>
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-500">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>

                    <td className="py-3.5 px-5 text-right">
                      <button
                        onClick={() => onAskAboutDoc(doc)}
                        className="inline-flex items-center space-x-1 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold rounded-lg transition-colors cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                        <span>Ask AI</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
