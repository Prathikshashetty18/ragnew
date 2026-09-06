import React, { useState } from "react";
import {
  Lock,
  User as UserIcon,
  ShieldAlert,
  Activity,
  ArrowRight,
  ShieldCheck,
  Stethoscope,
  Sparkles,
  Eye,
  EyeOff,
  UserCheck
} from "lucide-react";
import type { User } from "../types";

interface LoginProps {
  onLoginSuccess: (user: User, token: string) => void;
}

interface DemoAccount {
  role: string;
  badge: string;
  badgeColor: string;
  username: string;
  password: string;
  name: string;
  description: string;
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    role: "Admin",
    badge: "ADMIN",
    badgeColor: "bg-slate-100 text-slate-700 border-slate-200",
    username: "admin",
    password: "Admin@123",
    name: "Hospital Admin",
    description: "System governance & audits",
  },
  {
    role: "Doctor",
    badge: "PHYSICIAN",
    badgeColor: "bg-sky-50 text-sky-700 border-sky-200",
    username: "reshma",
    password: "reshma@123",
    name: "Dr. Reshma",
    description: "Attending Physician & CDSS",
  },
  {
    role: "Radiologist",
    badge: "IMAGING",
    badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
    username: "prakash_rad",
    password: "Radio@123",
    name: "Dr. Prakash",
    description: "Radiology scans & reports",
  },
  {
    role: "Lab Tech",
    badge: "PATHOLOGY",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
    username: "rakshith",
    password: "rakshith@123",
    name: "Rakshith",
    description: "Blood panels & lab diagnostics",
  },
  {
    role: "Nurse",
    badge: "NURSING",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    username: "riya",
    password: "riya@123",
    name: "Riya",
    description: "Vitals tracking & triage",
  },
  {
    role: "Front Desk",
    badge: "ADMISSION",
    badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
    username: "shreya",
    password: "shreya@123",
    name: "Shreya",
    description: "Patient intake & assignment",
  },
];

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

  const handleFillDemo = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-slate-950 selection:bg-rose-900 selection:text-white font-sans antialiased">
      {/* Left Clinical Branding Panel */}
      <div className="lg:w-1/2 bg-gradient-to-br from-rose-950 via-rose-900 to-rose-950 text-white p-8 sm:p-12 lg:p-16 flex flex-col justify-between relative overflow-hidden border-b lg:border-b-0 lg:border-r border-rose-900/40">
        {/* Subtle Decorative Background Aura */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-rose-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Top Branding Header */}
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 shadow-inner">
              <Activity className="w-6 h-6 text-rose-200" />
            </div>
            <div>
              <span className="text-xs uppercase tracking-widest font-bold text-rose-200 block">
                Clinical RAG CDSS
              </span>
              <span className="text-[11px] text-rose-300/80 font-medium">
                Enterprise Clinical Decision Support
              </span>
            </div>
          </div>
        </div>

        {/* Center Main Typography */}
        <div className="my-10 lg:my-0 relative z-10 max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-800/40 border border-rose-700/40 text-rose-200 text-xs font-semibold mb-6">
            <Sparkles className="w-3.5 h-3.5 text-rose-300" />
            <span>Next-Generation Hospital AI Platform</span>
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-[1.15]">
            Your Clinical Support System.
          </h1>

          <p className="text-base sm:text-lg text-rose-100/90 font-normal mt-4 leading-relaxed">
            Connecting clinical knowledge with better patient care.
          </p>

          {/* Clinical Feature List */}
          <div className="mt-8 space-y-3.5 pt-6 border-t border-rose-800/40 text-xs sm:text-sm text-rose-100/80">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-4 h-4 text-rose-300 shrink-0 mt-0.5" />
              <span>
                <strong>Evidence-Grounded Intelligence</strong> — Multi-source retrieval across guidelines, PubMed literature, and patient EHR.
              </span>
            </div>
            <div className="flex items-start gap-3">
              <Stethoscope className="w-4 h-4 text-rose-300 shrink-0 mt-0.5" />
              <span>
                <strong>Role-Specific Workspaces</strong> — Tailored interfaces for Physicians, Radiologists, Pathologists, and Nurses.
              </span>
            </div>
          </div>
        </div>

        {/* Bottom Hospital Trust Footer */}
        <div className="relative z-10 pt-4 border-t border-rose-900/60 flex items-center justify-between text-[11px] text-rose-300/70">
          <span>Enterprise CDSS Platform</span>
          <span>NABH & HIPAA Compliant</span>
        </div>
      </div>

      {/* Right Authentication Panel */}
      <div className="lg:w-1/2 bg-slate-50 flex flex-col justify-center items-center p-6 sm:p-10 lg:p-14 overflow-y-auto">
        <div className="w-full max-w-md bg-white p-7 sm:p-9 rounded-3xl shadow-xl shadow-slate-200/60 border border-slate-200/80">
          {/* Form Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
              Sign In to Clinical Portal
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Enter your hospital credentials to access your clinical workspace.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3">
              <ShieldAlert className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
              <p className="text-xs text-rose-900 font-medium leading-relaxed">{error}</p>
            </div>
          )}

          {/* Sign In Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Username or Employee ID
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. reshma, admin, rakshith"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-800 focus:bg-white focus:border-rose-800 transition shadow-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-800 focus:bg-white focus:border-rose-800 transition shadow-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none"
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 px-4 bg-rose-900 hover:bg-rose-800 active:bg-rose-950 text-white text-xs sm:text-sm font-semibold rounded-xl shadow-lg shadow-rose-950/20 hover:shadow-rose-950/30 transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <span>Authenticating with server...</span>
              ) : (
                <>
                  <span>Sign In to Clinical Portal</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Demo Accounts Quick-Fill Section */}
          <div className="mt-7 pt-5 border-t border-slate-100">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5 text-rose-800" />
                Hospital Demo Accounts
              </span>
              <span className="text-[10px] text-slate-400 font-medium">Click to fill</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.username}
                  type="button"
                  onClick={() => handleFillDemo(account.username, account.password)}
                  className="text-left p-2.5 rounded-xl border border-slate-200/90 bg-slate-50/70 hover:bg-rose-50/60 hover:border-rose-300 transition group focus:outline-none focus:ring-1 focus:ring-rose-700"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-bold text-slate-800 group-hover:text-rose-900">
                      {account.role}
                    </span>
                    <span className={`text-[8px] font-semibold px-1.5 py-0.2 rounded border ${account.badgeColor}`}>
                      {account.badge}
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-600 truncate">
                    {account.username}
                  </div>
                  <div className="text-[9px] font-mono text-slate-400 truncate">
                    {account.password}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
