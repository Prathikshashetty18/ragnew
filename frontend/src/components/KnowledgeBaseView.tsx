import React, { useState, useEffect } from "react";
import { Upload, CheckCircle, Check, Archive } from "lucide-react";
import type { DocumentItem, User } from "../types";

interface KnowledgeBaseViewProps {
  currentUser: User;
}

export const KnowledgeBaseView: React.FC<KnowledgeBaseViewProps> = ({ currentUser }) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("Hospital Guideline");
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const isAdmin = currentUser.role === "ADMIN";
  const canUpload = ["ADMIN", "DOCTOR"].includes(currentUser.role);

  const fetchDocs = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/documents?scope=knowledge_base", {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setUploadMsg(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("scope", "knowledge_base");
    formData.append("document_type", docType);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setUploadMsg(data.message || "Document uploaded successfully.");
        setFile(null);
        fetchDocs();
      } else {
        alert(data.detail || "Upload rejected.");
      }
    } catch (err) {
      alert("Error uploading document.");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: number) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/documents/${id}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        fetchDocs();
      }
    } catch (e) {
      alert("Approval failed.");
    }
  };

  const handleArchive = async (id: number) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/documents/${id}/archive`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        fetchDocs();
      }
    } catch (e) {
      alert("Archive failed.");
    }
  };

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Hospital Clinical Knowledge Base & Guidelines</h1>
          <p className="text-xs text-slate-500">Curated clinical practice guidelines, standard operating procedures, and antimicrobial stewardship protocols.</p>
        </div>

        {uploadMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {uploadMsg}
          </div>
        )}

        {/* Upload Box for Clinicians & Admins */}
        {canUpload && (
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Upload className="w-4 h-4 text-rose-900" />
              Upload Medical Guideline / Textbook (PDF)
            </h2>

            <form onSubmit={handleUpload} className="flex flex-col md:flex-row gap-3 items-end">
              <div className="flex-1">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select PDF File</label>
                <input
                  type="file"
                  required
                  accept=".pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-rose-50 file:text-rose-900 hover:file:bg-rose-100"
                />
              </div>

              <div className="w-full md:w-56">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Document Type</label>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                >
                  <option value="Hospital Guideline">Hospital Guideline</option>
                  <option value="Hospital SOP">Hospital SOP</option>
                  <option value="Hospital Policy">Hospital Policy</option>
                  <option value="Medical Textbook">Medical Textbook</option>
                  <option value="Research Paper">Research Paper</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={loading || !file}
                className="py-2.5 px-5 bg-rose-900 hover:bg-rose-800 text-white text-xs font-semibold rounded-xl shadow-sm transition disabled:opacity-50"
              >
                {loading ? "Validating..." : "Submit Guideline"}
              </button>
            </form>
          </div>
        )}

        {/* Documents Table */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Indexed Guidelines & Policies ({documents.length})</h3>
          </div>

          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="p-4">Document Name</th>
                <th className="p-4">Type</th>
                <th className="p-4">Version</th>
                <th className="p-4">Status</th>
                <th className="p-4">Chunks</th>
                <th className="p-4">Uploaded By</th>
                {isAdmin && <th className="p-4 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {documents.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50/80 transition">
                  <td className="p-4 font-semibold text-slate-900">
                    <a
                      href={`http://127.0.0.1:8000/api/documents/${d.id}/file`}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-rose-900 underline"
                    >
                      {d.name}
                    </a>
                  </td>
                  <td className="p-4">{d.document_type || "Guideline"}</td>
                  <td className="p-4 font-mono">{d.version}</td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      d.approval_status === "ACTIVE"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : d.approval_status === "PENDING"
                        ? "bg-amber-50 text-amber-800 border-amber-200"
                        : "bg-rose-50 text-rose-800 border-rose-200"
                    }`}>
                      {d.approval_status}
                    </span>
                  </td>
                  <td className="p-4 font-mono">{d.chunk_count}</td>
                  <td className="p-4">{d.uploaded_by} ({d.uploader_role || "System"})</td>
                  {isAdmin && (
                    <td className="p-4 text-right space-x-2">
                      {d.approval_status === "PENDING" && (
                        <button
                          onClick={() => handleApprove(d.id)}
                          className="p-1 text-emerald-700 hover:bg-emerald-50 rounded"
                          title="Approve and Index"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                      )}
                      {d.approval_status === "ACTIVE" && (
                        <button
                          onClick={() => handleArchive(d.id)}
                          className="p-1 text-slate-500 hover:text-rose-700 rounded"
                          title="Archive from Vector Store"
                        >
                          <Archive className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
