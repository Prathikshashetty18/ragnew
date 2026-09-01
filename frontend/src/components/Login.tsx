import React, { useState } from "react";
import { Shield, User, Lock, Eye, EyeOff, CheckCircle2, Stethoscope, Sparkles, ArrowRight } from "lucide-react";

interface LoginProps {
  onLoginSuccess: (user: { id: number; username: string; role: string; name: string }) => void;
  apiBase: string;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess, apiBase }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("••••••••");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (selectedUsername: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: selectedUsername || username })
      });
      if (res.ok) {
        const user = await res.json();
        onLoginSuccess(user);
      } else {
        const err = await res.json();
        setError(err.detail || "Authentication failed. Please verify username.");
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
      username: "arun",
      name: "Dr. Arun",
      role: "Attending Physician",
      badge: "Doctor",
      badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
      description: "Assigned to Patients P001 & P002. Full clinical & AI access."
    },
    {
      username: "meera",
      name: "Dr. Meera",
      role: "Consultant Physician",
      badge: "Doctor",
      badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
      description: "Assigned to Patients P003 & P004. Prescribing & diagnosis."
    },
    {
      username: "priya",
      name: "Priya",
      role: "Staff Nurse",
      badge: "Nurse",
      badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
      description: "Hospital-wide vitals recording, patient triage & care notes."
    },
    {
      username: "rahul_rad",
      name: "Rahul",
      role: "Diagnostic Radiologist",
      badge: "Radiology",
      badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
      description: "Uploads X-Ray/CT imaging reports & logs formal findings."
    },
    {
      username: "ananya_lab",
      name: "Ananya",
      role: "Laboratory Technologist",
      badge: "Lab Tech",
      badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
      description: "Records CBC metrics, inflammatory markers & biochem panels."
    },
    {
      username: "arjun_intern",
      name: "Arjun",
      role: "Clinical Resident / Intern",
      badge: "Intern",
      badgeColor: "bg-slate-100 text-slate-700 border-slate-200",
      description: "Read-only observation across hospital patients & Clinical AI."
    }
  ];

  return (
    <div className="flex min-h-screen w-screen bg-slate-900 font-sans antialiased overflow-x-hidden">
      {/* Left side: Brand identity & Healthcare Overview */}
      <div className="hidden lg:flex w-5/12 bg-gradient-to-br from-slate-900 via-slate-850 to-blue-950 text-white flex-col justify-between p-12 relative border-r border-slate-800">
        {/* Background decorative glow */}
        <div className="absolute top-1/4 left-10 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-10 right-10 w-80 h-80 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Brand Header */}
        <div className="flex items-center space-x-3 z-10">
          <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight tracking-tight text-white">
              RAG Based Clinical Decision System
            </h1>
            <p className="text-xs text-blue-300 font-medium">
              Hospital Clinical Decision Support System
            </p>
          </div>
        </div>

        {/* Center Hero Information */}
        <div className="space-y-6 max-w-lg z-10 my-auto">
          <div className="inline-flex items-center space-x-2 bg-blue-500/15 border border-blue-400/30 px-3 py-1 rounded-full text-xs font-semibold text-blue-200">
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            <span>Multi-Role Clinical Intelligence</span>
          </div>

          <h2 className="text-3xl font-extrabold text-white leading-tight tracking-tight">
            AI-powered clinical decision support grounded in trusted medical documents.
          </h2>

          <p className="text-sm text-slate-300 leading-relaxed">
            Empowering doctors, nurses, radiologists, and laboratory teams with verified clinical retrieval, structured patient timelines, and sentence-level evidence verification.
          </p>

          <div className="space-y-3.5 pt-3">
            <div className="flex items-start space-x-3 text-xs text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
              <span><strong>Hybrid Retrieval (BM25 + FAISS)</strong>: Precise medical term matching combined with dense vector semantic search.</span>
            </div>
            <div className="flex items-start space-x-3 text-xs text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
              <span><strong>Scoped Patient Records</strong>: Strict role-based access filtering patient-specific PDFs and hospital clinical guidelines.</span>
            </div>
            <div className="flex items-start space-x-3 text-xs text-slate-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
              <span><strong>Sentence Verification & Citations</strong>: Every recommendation is audited with page citations and confidence scoring.</span>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="pt-6 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 z-10">
          <span>Enterprise Healthcare CDSS</span>
          <span className="flex items-center space-x-1.5 font-medium text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>RAG Engine Online</span>
          </span>
        </div>
      </div>

      {/* Right side: Login & Demo Roles Access */}
      <div className="w-full lg:w-7/12 flex items-center justify-center p-6 md:p-12 bg-slate-50 overflow-y-auto">
        <div className="max-w-xl w-full space-y-8 bg-white p-8 md:p-10 rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-200">
          {/* Top heading */}
          <div>
            <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-2">
              <Stethoscope className="w-4 h-4" />
              <span>Clinician Portal</span>
            </div>
            <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
              Welcome back
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              Sign in to continue to your clinical workspace
            </p>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium flex items-center space-x-2 animate-fadeIn">
              <span className="w-1.5 h-1.5 bg-red-500 rounded-full shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Login Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (username.trim()) handleLogin(username.trim());
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Username or Staff Email
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400">
                  <User className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  required
                  placeholder="Enter username (e.g. arun, priya, rahul_rad)"
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
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100 rounded-xl pl-10 pr-10 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
              <label className="flex items-center space-x-2 cursor-pointer select-none">
                <input type="checkbox" defaultChecked className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
                <span>Remember this workstation</span>
              </label>
              <span className="text-blue-600 hover:underline cursor-pointer">Demo credentials active</span>
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
                  <span>Sign In to Clinical Workspace</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Access Roles */}
          <div className="space-y-3 pt-6 border-t border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Quick Demo Role Switcher
              </span>
              <span className="text-[11px] text-slate-400">Click to log in as:</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {demoAccounts.map((account) => (
                <button
                  key={account.username}
                  type="button"
                  onClick={() => {
                    setUsername(account.username);
                    handleLogin(account.username);
                  }}
                  className="group flex flex-col p-3 text-left bg-slate-50 hover:bg-blue-50/60 border border-slate-200 hover:border-blue-300 rounded-xl transition-all cursor-pointer shadow-xs hover:shadow-md"
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-xs font-bold text-slate-800 group-hover:text-blue-700">
                      {account.name}
                    </span>
                    <span className={`text-[10px] border font-bold px-2 py-0.5 rounded-full ${account.badgeColor}`}>
                      {account.badge}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-500 group-hover:text-slate-600 mt-1 leading-snug">
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
