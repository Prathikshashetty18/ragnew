import React, { useState, useEffect } from "react";
import { ShieldAlert, Search, RefreshCw, Filter } from "lucide-react";

interface AuditLogItem {
  id: number;
  user_id?: number;
  user_name?: string;
  user_role?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  status: string;
  details?: string;
  timestamp: string;
}

interface AuditLogViewProps {
  apiBase: string;
  token: string;
}

export const AuditLogView: React.FC<AuditLogViewProps> = ({ apiBase, token }) => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [isLoading, setIsLoading] = useState(false);

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/audit-logs?limit=200`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [token]);

  const filteredLogs = logs.filter((l) => {
    const matchesSearch =
      l.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (l.user_name && l.user_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (l.details && l.details.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (l.resource_id && l.resource_id.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === "ALL" || l.status.toUpperCase() === statusFilter.toUpperCase();
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-purple-600 text-xs font-bold uppercase tracking-wider mb-1">
            <ShieldAlert className="w-4 h-4" />
            <span>Compliance & Audit Records</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Hospital System Audit Logs
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Immutable log of clinical actions, user creation/deactivation, patient lifecycle transitions, and document approvals.
          </p>
        </div>

        <button
          onClick={fetchLogs}
          disabled={isLoading}
          className="flex items-center space-x-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all cursor-pointer"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          <span>Refresh Logs</span>
        </button>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by action, actor, resource ID, details..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-900 outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-100 border border-slate-300 rounded-xl px-3 py-1.5 text-xs font-semibold text-slate-800 outline-none"
          >
            <option value="ALL">All Outcomes</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILURE">Failure</option>
            <option value="DENIED">Denied</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
            <tr>
              <th className="py-3.5 px-5">Timestamp</th>
              <th className="py-3.5 px-4">Actor</th>
              <th className="py-3.5 px-4">Action</th>
              <th className="py-3.5 px-4">Resource</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-5">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
            {filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400 font-sans text-xs">
                  No audit records found.
                </td>
              </tr>
            ) : (
              filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-5 text-slate-500 whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>

                  <td className="py-3 px-4 font-sans font-bold text-slate-800">
                    <div>{log.user_name || "System"}</div>
                    {log.user_role && (
                      <span className="text-[9px] text-slate-400 font-mono">{log.user_role}</span>
                    )}
                  </td>

                  <td className="py-3 px-4 font-bold text-blue-700">
                    {log.action}
                  </td>

                  <td className="py-3 px-4 text-slate-600">
                    <span className="bg-slate-100 px-1.5 py-0.5 rounded text-[10px]">
                      {log.resource_type}:{log.resource_id || "*"}
                    </span>
                  </td>

                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-0.5 rounded-full font-bold text-[9px] ${
                        log.status === "SUCCESS" ? "bg-emerald-100 text-emerald-800" :
                        log.status === "DENIED" ? "bg-amber-100 text-amber-800" :
                        "bg-red-100 text-red-800"
                      }`}
                    >
                      {log.status}
                    </span>
                  </td>

                  <td className="py-3 px-5 text-slate-600 font-sans text-xs max-w-xs truncate" title={log.details || ""}>
                    {log.details || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
