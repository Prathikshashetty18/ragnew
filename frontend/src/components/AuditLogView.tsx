import React, { useState, useEffect } from "react";
import { getApiUrl } from "../api/client";
import type { AuditLogItem } from "../types";

export const AuditLogView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);

  const fetchLogs = async () => {
    try {
      const res = await fetch(getApiUrl("/api/audit-logs?limit=100"), {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Hospital HIPAA & CDSS Compliance Audit Logs</h1>
          <p className="text-xs text-slate-500">Immutable chronological trail of clinical access, document approval lifecycles, and RAG queries.</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="p-4">Timestamp</th>
                <th className="p-4">Action</th>
                <th className="p-4">Staff Member</th>
                <th className="p-4">Resource</th>
                <th className="p-4">Status</th>
                <th className="p-4">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700 font-mono text-[11px]">
              {logs.map((l) => (
                <tr key={l.id} className="hover:bg-slate-50 transition">
                  <td className="p-4 text-slate-500">{new Date(l.timestamp).toLocaleString()}</td>
                  <td className="p-4 font-bold text-slate-900">{l.action}</td>
                  <td className="p-4 font-sans font-medium">{l.user_name} ({l.user_role})</td>
                  <td className="p-4">{l.resource_type} {l.resource_id ? `#${l.resource_id}` : ""}</td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                      l.status === "SUCCESS"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : "bg-rose-50 text-rose-800 border-rose-200"
                    }`}>
                      {l.status}
                    </span>
                  </td>
                  <td className="p-4 font-sans text-slate-600 max-w-xs truncate">{l.details || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
