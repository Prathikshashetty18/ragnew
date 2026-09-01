import React, { useState } from "react";
import { Shield, User, Lock, Eye, EyeOff, CheckCircle2, Stethoscope, Sparkles, ArrowRight } from "lucide-react";
import type { UserProfile } from "../types";

interface LoginProps {
  onLoginSuccess: (user: UserProfile, token: string) => void;
  apiBase: string;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess, apiBase }) => {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("Admin@123");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (selectedUsername?: string, selectedPassword?: string) => {
    setIsLoading(true);
    setError(null);
    const u = selectedUsername || username;
    const p = selectedPassword || password;

    try {
      const res = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p })
      });
      if (res.ok) {
        const data = await res.json();
        onLoginSuccess(data.user, data.access_token);
      } else {
        const err = await res.json();
        setError(err.detail || "Authentication failed. Please verify credentials.");
      }
    } catch (e) {
      console.error(e);
      setError("Cannot reach backend server. Please verify the FastAPI service is active.");
    } finally {
      setIsLoading(false);
    }
  };

  const demoAccounts = [
    {
      username: "admin",
      password: "Admin@123",
      name: "Hospital Admin",
      badge: "ADMIN",
      badgeColor: "bg-red-50 text-red-700 border-red-200",
      description: "User management, guideline approvals, policy control & audit logs."
    },
    {
      username: "arun",
      password: "Doctor@123",
      name: "Dr. Arun",
      badge: "DOCTOR",
      badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
      description: "Assigned to P001 & P002. Clinical diagnosis, AI report drafting & approvals."
    },
    {
      username: "meera",
      password: "Doctor@123",
      name: "Dr. Meera",
      badge: "DOCTOR",
      badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
      description: "Assigned to P003 & P004. Prescribing, clinical assessment & discharge."
    },
    {
      username: "frontdesk",
      password: "Front@123",
      name: "Sarah",
      badge: "FRONT_DESK",
      badgeColor: "bg-cyan-50 text-cyan-700 border-cyan-200",
      description: "Patient registration, Unique ID generation, doctor assignment & lifecycle."
    },
    {
      username: "priya",
      password: "Nurse@123",
      name: "Priya",
      badge: "NURSE",
      badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
      description: "Vitals monitoring, patient observation notes & clinical triage."
    },
    {
      username: "arjun_intern",
      password: "Intern@123",
      name: "Arjun",
      badge: "INTERN",
      badgeColor: "bg-slate-100 text-slate-700 border-slate-200",
      description: "Read-only patient charts, Clinical AI querying & evidence review."
    }
  ];

  return (
    <div className="flex min-h-screen w-screen bg-slate-900 font-sans antialiased overflow-x-hidden">
      <div className="hidden lg:flex w-5/12 bg-gradient-to-br from-slate-900 via-slate-850 to-blue-950 text-white flex-col justify-between p-12 relative border-r border-slate-800">
        <div className="flex items-center space-x-3 z-10">
          <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight tracking-tight text-white">
              Hospital Clinical RAG System
            </h1>
            <p className="text-xs text-blue-300 font-medium">
              Enterprise Clinical Decision Support & AI Assistant
            </p>
          </div>
        </div>

        <div className="space-y-6 max-w-lg z-10 my-auto">
          <div className="inline-flex items-center space-x-2 bg-blue-500/15 border border-blue-400/30 px-3 py-1 rounded-full text-xs font-semibold text-blue-200">
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            <span>Role-Based Healthcare Intelligence</span>
          </div>

          <h2 className="text-3xl font-extrabold text-white leading-tight tracking-tight">
            Evidence-grounded clinical decision support with NLI validation.
          </h2>

          <p className="text-sm text-slate-300 leading-relaxed">
            Empowering hospital professionals with verified clinical retrieval, structured patient timelines, AI report drafting, and sentence-level evidence verification.
          </p>

          <div className="space-y-3.5 pt-3">
            <div className="flex items-start space-x-3 text-xs text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
              <span><strong>Hospital User Management & RBAC</strong>: Granular permissions for 6 clinical roles.</span>
            </div>
            <div className="flex items-start space-x-3 text-xs text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
              <span><strong>Patient Lifecycle & AI Reports</strong>: Front-desk registration, doctor assignment, report drafting & approvals.</span>
            </div>
            <div className="flex items-start space-x-3 text-xs text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
              <span><strong>NLI Fact-Verification Engine</strong>: Premise-hypothesis entailment validation to suppress hallucinations.</span>
            </div>
          </div>
        </div>

        <div className="pt-6 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 z-10">
          <span>Hospital Compliance System</span>
          <span className="flex items-center space-x-1.5 font-medium text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>RAG Engine Online</span>
          </span>
        </div>
      </div>

      <div className="w-full lg:w-7/12 flex items-center justify-center p-6 md:p-12 bg-slate-50 overflow-y-auto">
        <div className="max-w-xl w-full space-y-7 bg-white p-8 md:p-10 rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-200">
          <div>
            <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-1.5">
              <Stethoscope className="w-4 h-4" />
              <span>Professional Portal</span>
            </div>
            <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
              Sign In to Clinical Workspace
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Enter individual credentials or select a verified hospital role below
            </p>
          </div>

          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium flex items-center space-x-2 animate-fadeIn">
              <span className="w-1.5 h-1.5 bg-red-500 rounded-full shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (username.trim()) handleLogin();
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Username or Staff ID
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400">
                  <User className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  required
                  placeholder="Enter username (e.g. admin, arun, frontdesk)"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400">
                  <Lock className="w-4 h-4" />
                </span>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100 rounded-xl pl-10 pr-10 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !username.trim()}
              className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all shadow-md shadow-blue-500/20 cursor-pointer disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="space-y-3 pt-5 border-t border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Quick Demo Role Switcher
              </span>
              <span className="text-[10px] text-slate-400">Click to authenticate instantly:</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {demoAccounts.map((account) => (
                <button
                  key={account.username}
                  type="button"
                  onClick={() => {
                    setUsername(account.username);
                    setPassword(account.password);
                    handleLogin(account.username, account.password);
                  }}
                  className="group flex flex-col p-3 text-left bg-slate-50 hover:bg-blue-50/60 border border-slate-200 hover:border-blue-300 rounded-xl transition-all cursor-pointer shadow-2xs hover:shadow-sm"
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-xs font-bold text-slate-800 group-hover:text-blue-700">
                      {account.name}
                    </span>
                    <span className={`text-[9px] border font-bold px-2 py-0.5 rounded-full ${account.badgeColor}`}>
                      {account.badge}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 group-hover:text-slate-600 mt-1 leading-snug">
                    {account.description}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
