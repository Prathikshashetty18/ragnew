import React, { useState } from "react";
import { Lock, User as UserIcon, ShieldAlert, Activity, ArrowRight } from "lucide-react";
import type { User } from "../types";

interface LoginProps {
  onLoginSuccess: (user: User, token: string) => void;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed.");
      }

      onLoginSuccess(data.user, data.access_token);
    } catch (err: any) {
      setError(err.message || "Unable to reach authentication server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 selection:bg-rose-900 selection:text-white">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden">
        {/* Burgundy Hospital Header */}
        <div className="bg-gradient-to-r from-rose-950 via-rose-900 to-rose-800 p-8 text-white relative">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20">
              <Activity className="w-6 h-6 text-rose-200" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white leading-tight">Clinical RAG Hospital CDSS</h1>
              <p className="text-xs text-rose-200/90 font-medium">Clinical Decision Support System</p>
            </div>
          </div>
          <p className="text-xs text-rose-100/75 mt-3">
            Secure clinical portal for hospital staff, physicians, radiologists, and diagnostic specialists.
          </p>
        </div>

        {/* Login Form */}
        <div className="p-8">
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-rose-700 shrink-0 mt-0.5" />
              <p className="text-xs text-rose-900 font-medium leading-relaxed">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Username or Employee ID
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. arun, rahul_rad, ananya_lab, admin"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-800 focus:bg-white transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-800 focus:bg-white transition"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 px-4 bg-rose-900 hover:bg-rose-800 text-white text-sm font-semibold rounded-xl shadow-lg shadow-rose-950/20 transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <span>Verifying credentials...</span>
              ) : (
                <>
                  <span>Sign In to Clinical Portal</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Safe demo accounts hint */}
          <div className="mt-8 pt-6 border-t border-slate-100">
            <p className="text-[11px] font-semibold uppercase text-slate-400 tracking-wider mb-2">Hospital Staff Accounts [DEMO / SYNTHETIC DATA]</p>
            <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-100">
              <div><span className="font-semibold text-slate-800">Admin:</span> admin / Admin@123</div>
              <div><span className="font-semibold text-slate-800">Doctor:</span> arun / Doctor@123</div>
              <div><span className="font-semibold text-slate-800">Radiologist:</span> rahul_rad / Radio@123</div>
              <div><span className="font-semibold text-slate-800">Lab Tech:</span> ananya_lab / Lab@123</div>
              <div><span className="font-semibold text-slate-800">Nurse:</span> priya / Nurse@123</div>
              <div><span className="font-semibold text-slate-800">Front Desk:</span> frontdesk / Front@123</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
