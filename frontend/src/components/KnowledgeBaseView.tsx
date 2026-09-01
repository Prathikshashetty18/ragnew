import React, { useState, useEffect } from "react";
import { 
  BookOpen, Upload, CheckCircle2, 
  AlertTriangle, Globe, PlusCircle
} from "lucide-react";
import type { Document, UserProfile } from "../types";

interface TrustedSource {
  id: number;
  name: string;
  domain: string;
  source_type: string;
  approval_status: string;
  created_at: string;
}

interface KnowledgeBaseViewProps {
  documents: Document[];
  apiBase: string;
  token: string;
  currentUser: UserProfile;
  onRefreshDocuments: () => void;
  onUploadFile: (file: File, scope: string, patientId?: string, docType?: string) => Promise<any>;
}

export const KnowledgeBaseView: React.FC<KnowledgeBaseViewProps> = ({
  documents,
  apiBase,
  token,
  currentUser,
  onRefreshDocuments,
  onUploadFile
}) => {
  const [activeTab, setActiveTab] = useState<"guidelines" | "approval_queue" | "trusted_sources">("guidelines");
  const [trustedSources, setTrustedSources] = useState<TrustedSource[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [isAddSourceModalOpen, setIsAddSourceModalOpen] = useState(false);
  const [sourceName, setSourceName] = useState("");
  const [sourceDomain, setSourceDomain] = useState("");

  const isAdmin = currentUser.role === "ADMIN";
  const isDoctor = currentUser.role === "DOCTOR" || isAdmin;

  const fetchTrustedSources = async () => {
    try {
      const res = await fetch(`${apiBase}/api/trusted-sources`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setTrustedSources(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchTrustedSources();
  }, [token]);

  const handleApproveDoc = async (docId: number) => {
    try {
      const res = await fetch(`${apiBase}/api/documents/${docId}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        onRefreshDocuments();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectDoc = async (docId: number) => {
    try {
      const res = await fetch(`${apiBase}/api/documents/${docId}/reject`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        onRefreshDocuments();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleArchiveDoc = async (docId: number) => {
    try {
      const res = await fetch(`${apiBase}/api/documents/${docId}/archive`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        onRefreshDocuments();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddTrustedSource = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${apiBase}/api/trusted-sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: sourceName, domain: sourceDomain, source_type: "guideline" })
      });
      if (res.ok) {
        setIsAddSourceModalOpen(false);
        setSourceName("");
        setSourceDomain("");
        fetchTrustedSources();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setIsUploading(true);
      setUploadMsg(null);
      try {
        const res = await onUploadFile(file, "knowledge_base");
        setUploadMsg({ type: "success", text: res.message || "Document uploaded successfully." });
        onRefreshDocuments();
      } catch (err: any) {
        setUploadMsg({ type: "error", text: err.message || "Upload failed." });
      } finally {
        setIsUploading(false);
      }
    }
  };

  const activeGuidelines = documents.filter(d => d.scope === "knowledge_base" && d.approval_status === "ACTIVE");
  const pendingQueue = documents.filter(d => d.scope === "knowledge_base" && (d.approval_status === "PENDING" || d.approval_status === "FLAGGED"));

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-1">
            <BookOpen className="w-4 h-4" />
            <span>Institutional Knowledge Base</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Clinical Guidelines & Trusted Sources
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Peer-reviewed hospital protocols, antibiotic guidelines, and authorized institutional registries.
          </p>
        </div>

        {isDoctor && (
          <label className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer">
            <Upload className="w-4 h-4" />
            <span>Upload Guideline PDF</span>
            <input type="file" accept=".pdf" onChange={handleFileInput} className="hidden" disabled={isUploading} />
          </label>
        )}
      </div>

      {uploadMsg && (
        <div className={`p-4 rounded-xl text-xs font-semibold flex items-center space-x-2 animate-fadeIn ${
          uploadMsg.type === "success" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" : "bg-red-50 border border-red-200 text-red-700"
        }`}>
          {uploadMsg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
          <span>{uploadMsg.text}</span>
        </div>
      )}

      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 text-xs font-bold">
        <button
          onClick={() => setActiveTab("guidelines")}
          className={`px-4 py-2 rounded-xl transition-all cursor-pointer ${
            activeTab === "guidelines" ? "bg-blue-600 text-white shadow-xs" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Active Hospital Guidelines ({activeGuidelines.length})
        </button>

        {isAdmin && (
          <button
            onClick={() => setActiveTab("approval_queue")}
            className={`px-4 py-2 rounded-xl transition-all cursor-pointer relative ${
              activeTab === "approval_queue" ? "bg-blue-600 text-white shadow-xs" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <span>Review & Approval Queue</span>
            {pendingQueue.length > 0 && (
              <span className="ml-2 bg-amber-500 text-white text-[10px] px-1.5 py-0.2 rounded-full font-mono">
                {pendingQueue.length}
              </span>
            )}
          </button>
        )}

        <button
          onClick={() => setActiveTab("trusted_sources")}
          className={`px-4 py-2 rounded-xl transition-all cursor-pointer ${
            activeTab === "trusted_sources" ? "bg-blue-600 text-white shadow-xs" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Trusted Sources Registry ({trustedSources.length})
        </button>
      </div>

      {activeTab === "guidelines" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeGuidelines.length === 0 ? (
            <div className="col-span-full py-12 text-center text-xs text-slate-400">
              No active clinical guidelines indexed. Doctors & Admins can upload PDFs above.
            </div>
          ) : (
            activeGuidelines.map((doc) => (
              <div key={doc.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-all space-y-3">
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                    <BookOpen className="w-5 h-5" />
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    ACTIVE (v{doc.version || "1.0"})
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-sm text-slate-900 leading-snug line-clamp-2" title={doc.name}>
                    {doc.name}
                  </h3>
                  <div className="text-[11px] text-slate-400 mt-1">
                    {doc.chunk_count} FAISS Chunks Indexed • Uploaded by {doc.uploaded_by || "System"}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                  <span className="text-[10px] text-slate-400 font-mono">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </span>
                  {isAdmin && (
                    <button
                      onClick={() => handleArchiveDoc(doc.id)}
                      className="text-amber-700 hover:text-amber-900 text-[11px] font-bold cursor-pointer"
                    >
                      Archive Edition
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "approval_queue" && (
        <div className="space-y-4">
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 leading-relaxed">
            <strong>Administrator Clinical Review Queue:</strong> Uploads by attending physicians are pre-evaluated by the automated clinical lexicon validator. Review medical relevance scores below before approving them for FAISS vector indexing.
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-5">Document Name</th>
                  <th className="py-3 px-4">Uploaded By</th>
                  <th className="py-3 px-4">Medical Relevance Score</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pendingQueue.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      No documents pending review.
                    </td>
                  </tr>
                ) : (
                  pendingQueue.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/80">
                      <td className="py-3.5 px-5 font-bold text-slate-900">
                        {doc.name}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        {doc.uploaded_by} ({doc.uploader_role})
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                          (doc.medical_relevance_score || 0) >= 0.5 ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                        }`}>
                          Relevance: {Math.round((doc.medical_relevance_score || 0) * 100)}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-bold text-amber-700">
                        {doc.approval_status}
                      </td>
                      <td className="py-3.5 px-5 text-right space-x-2">
                        <button
                          onClick={() => handleApproveDoc(doc.id)}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs cursor-pointer shadow-xs"
                        >
                          Approve & Index
                        </button>
                        <button
                          onClick={() => handleRejectDoc(doc.id)}
                          className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 rounded-lg font-bold text-xs cursor-pointer"
                        >
                          Reject
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "trusted_sources" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              Authoritative medical organizations approved for clinical evidence ingestion.
            </p>
            {isAdmin && (
              <button
                onClick={() => setIsAddSourceModalOpen(true)}
                className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                <PlusCircle className="w-4 h-4" />
                <span>Register Trusted Source</span>
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {trustedSources.map((s) => (
              <div key={s.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                    <Globe className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-900">{s.name}</h3>
                    <div className="text-xs text-slate-400 font-mono">{s.domain}</div>
                  </div>
                </div>

                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  {s.approval_status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {isAddSourceModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white max-w-md w-full rounded-2xl p-6 space-y-4 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Add Trusted Medical Source</h2>
            <form onSubmit={handleAddTrustedSource} className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Organization Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. American Thoracic Society (ATS)"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5"
                />
              </div>
              <div>
                <label className="block font-bold text-slate-700 mb-1">Domain URL</label>
                <input
                  type="text"
                  required
                  placeholder="thoracic.org"
                  value={sourceDomain}
                  onChange={(e) => setSourceDomain(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 font-mono"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsAddSourceModalOpen(false)} className="px-3 py-1.5 bg-slate-100 rounded-xl font-bold">Cancel</button>
                <button type="submit" className="px-4 py-1.5 bg-blue-600 text-white rounded-xl font-bold">Register Source</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
