import React, { useState, useEffect } from "react";
import { FileText, ExternalLink } from "lucide-react";
import { getApiUrl } from "../api/client";
import type { DocumentItem, User } from "../types";

interface DocumentLibraryProps {
  currentUser: User;
}

export const DocumentLibrary: React.FC<DocumentLibraryProps> = ({ currentUser }) => {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const isAdmin = currentUser.role === "ADMIN";

  const fetchDocs = async () => {
    try {
      const res = await fetch(getApiUrl("/api/documents"), {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setDocs(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleArchive = async (id: number) => {
    try {
      const res = await fetch(getApiUrl(`/api/documents/${id}/archive`), {
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
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Hospital Clinical Document Archive</h1>
          <p className="text-xs text-slate-500">Comprehensive repository of all indexed clinical documents, patient attachments, and radiology files.</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="p-4">Document Title</th>
                <th className="p-4">Scope</th>
                <th className="p-4">Patient Link</th>
                <th className="p-4">Status</th>
                <th className="p-4">Indexed Chunks</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {docs.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50 transition">
                  <td className="p-4 font-semibold text-slate-900 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-400" />
                    <span>{d.name}</span>
                  </td>
                  <td className="p-4 uppercase text-[10px] font-bold text-slate-500">{d.scope}</td>
                  <td className="p-4 font-mono">{d.patient_id || "Hospital-wide"}</td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      d.approval_status === "ACTIVE"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : "bg-slate-100 text-slate-700 border-slate-200"
                    }`}>
                      {d.approval_status}
                    </span>
                  </td>
                  <td className="p-4 font-mono">{d.chunk_count}</td>
                  <td className="p-4 text-right space-x-3">
                    <a
                      href={getApiUrl(`/api/documents/${d.id}/file`)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-rose-900 hover:text-rose-700 font-semibold inline-flex items-center gap-1"
                    >
                      <span>Open File</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                    {isAdmin && d.approval_status === "ACTIVE" && (
                      <button
                        onClick={() => handleArchive(d.id)}
                        className="text-slate-400 hover:text-rose-700 font-semibold"
                        title="Archive and Remove from Vector Store"
                      >
                        Archive
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
