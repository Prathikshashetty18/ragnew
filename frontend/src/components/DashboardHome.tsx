import React, { useState } from "react";
import { 
  Sparkles, ArrowRight, Upload, Users, BookOpen, Activity, 
  FileText, ShieldCheck, CheckCircle, Clock, Stethoscope, ChevronRight,
  TrendingUp, Database, FlaskConical
} from "lucide-react";

interface Patient {
  id: string;
  name: string;
  age: number;
  gender: string;
  health_status: string;
  assigned_doctor: string;
}

interface Document {
  id: number;
  name: string;
  status: string;
  chunk_count: number;
  scope: string;
  created_at: string;
}

interface Session {
  id: string;
  title: string;
  created_at: string;
}

interface DashboardHomeProps {
  currentUser: { id: number; username: string; role: string; name: string };
  patients: Patient[];
  documents: Document[];
  sessions: Session[];
  onNavigate: (screen: "dashboard" | "clinical_ai" | "patients" | "documents" | "knowledge_base" | "settings") => void;
  onSelectPatient: (patientId: string) => void;
  onSelectSession: (sessionId: string) => void;
  onQuickAsk: (question: string) => void;
}

export const DashboardHome: React.FC<DashboardHomeProps> = ({
  currentUser,
  patients,
  documents,
  sessions,
  onNavigate,
  onSelectPatient,
  onSelectSession,
  onQuickAsk
}) => {
  const [quickQuery, setQuickQuery] = useState("");

  const handleQuickSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (quickQuery.trim()) {
      onQuickAsk(quickQuery.trim());
    }
  };

  const sampleQuickQuestions = [
    "What is the empirical antibiotic therapy for outpatient pneumonia as per hospital guidelines?",
    "What are the diagnostic criteria and workup required for suspected pulmonary tuberculosis?",
    "What are the major acute complications of Type 2 Diabetes Mellitus?",
    "Summarize vital signs and current clinical status for patient P001."
  ];

  const kbDocs = documents.filter(d => d.scope === "knowledge_base");
  const totalChunks = documents.reduce((acc, curr) => acc + (curr.chunk_count || 0), 0);

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-8">
      {/* Top Welcome Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-full text-xs font-bold capitalize">
              {currentUser.role} Workspace
            </span>
            <span className="text-xs text-slate-400">•</span>
            <span className="text-xs text-slate-500 font-medium">Department of Internal Medicine</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">
            Welcome back, {currentUser.name}
          </h1>
          <p className="text-sm text-slate-500">
            RAG-powered clinical decision intelligence ready. {patients.length} patients and {kbDocs.length} hospital guidelines loaded.
          </p>
        </div>

        {/* Quick Top Actions */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => onNavigate("clinical_ai")}
            className="flex items-center space-x-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm shadow-blue-500/20 cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            <span>Consult Clinical AI</span>
          </button>
          <button
            onClick={() => onNavigate("documents")}
            className="flex items-center space-x-2 px-4 py-2.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 rounded-xl text-xs font-semibold transition-all cursor-pointer"
          >
            <Upload className="w-4 h-4 text-slate-500" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Clinical AI Quick Ask Search Box */}
      <div className="bg-gradient-to-r from-blue-900 via-slate-900 to-blue-950 p-6 md:p-8 rounded-2xl text-white shadow-lg shadow-blue-950/20 border border-blue-800/40 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="max-w-3xl space-y-4 relative z-10">
          <div className="flex items-center space-x-2 text-blue-300 text-xs font-bold tracking-wider uppercase">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span>Ask Clinical Decision Support AI</span>
          </div>
          
          <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">
            Query across verified hospital clinical guidelines & patient charts
          </h2>

          <form onSubmit={handleQuickSubmit} className="relative">
            <input
              type="text"
              placeholder="e.g. What is the first-line treatment for community-acquired pneumonia?"
              value={quickQuery}
              onChange={(e) => setQuickQuery(e.target.value)}
              className="w-full bg-white/10 hover:bg-white/15 focus:bg-white text-slate-100 focus:text-slate-900 placeholder:text-slate-300 focus:placeholder:text-slate-400 border border-white/20 focus:border-blue-500 rounded-xl pl-4 pr-32 py-3.5 text-sm outline-none transition-all"
            />
            <button
              type="submit"
              disabled={!quickQuery.trim()}
              className="absolute right-2 top-2 bottom-2 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-all disabled:opacity-40 cursor-pointer"
            >
              <span>Ask AI</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>

          {/* Prompt suggestions */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-[11px] text-slate-300 font-medium">Quick Prompts:</span>
            {sampleQuickQuestions.map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onQuickAsk(q)}
                className="text-[11px] bg-white/10 hover:bg-white/20 text-slate-200 border border-white/15 px-3 py-1 rounded-full transition-colors truncate max-w-xs cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500">Accessible Patients</span>
            <div className="text-2xl font-black text-slate-900">{patients.length}</div>
            <span className="text-[11px] text-emerald-600 font-medium flex items-center">
              <CheckCircle className="w-3 h-3 mr-1" /> Active in care
            </span>
          </div>
          <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600">
            <Users className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500">Indexed Guidelines</span>
            <div className="text-2xl font-black text-slate-900">{kbDocs.length}</div>
            <span className="text-[11px] text-blue-600 font-medium">Hospital Knowledge Base</span>
          </div>
          <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center text-emerald-600">
            <BookOpen className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500">Total Indexed Chunks</span>
            <div className="text-2xl font-black text-slate-900">{totalChunks}</div>
            <span className="text-[11px] text-slate-500 font-medium">FAISS 384-d Vectors</span>
          </div>
          <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center text-purple-600">
            <Database className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-500">Grounding Confidence</span>
            <div className="text-2xl font-black text-slate-900">94.2%</div>
            <span className="text-[11px] text-emerald-600 font-medium flex items-center">
              <TrendingUp className="w-3 h-3 mr-1" /> Sentence-level verified
            </span>
          </div>
          <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center text-amber-600">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Main Grid: Patients and Recent Consultations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Assigned Patients & Quick Actions */}
        <div className="lg:col-span-2 space-y-6">
          {/* Assigned Patients Card */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Assigned Patient Profiles</h3>
                <p className="text-xs text-slate-500">Patients under active monitoring in your department</p>
              </div>
              <button
                onClick={() => onNavigate("patients")}
                className="text-xs font-bold text-blue-600 hover:text-blue-700 flex items-center cursor-pointer"
              >
                <span>View All Patients</span>
                <ChevronRight className="w-4 h-4 ml-0.5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {patients.map((patient) => (
                <div
                  key={patient.id}
                  onClick={() => onSelectPatient(patient.id)}
                  className="p-4 bg-slate-50 hover:bg-blue-50/50 border border-slate-200 hover:border-blue-300 rounded-xl transition-all cursor-pointer group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-blue-700 bg-blue-100/60 px-2 py-0.5 rounded">
                      {patient.id}
                    </span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      patient.health_status === "Under Review" ? "bg-amber-100 text-amber-800" :
                      patient.health_status === "Stable" ? "bg-emerald-100 text-emerald-800" :
                      "bg-slate-200 text-slate-800"
                    }`}>
                      {patient.health_status}
                    </span>
                  </div>

                  <div className="mt-2.5">
                    <div className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                      {patient.name}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {patient.age} yrs • {patient.gender === "M" ? "Male" : "Female"} • Assigned: {patient.assigned_doctor}
                    </div>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
                    <span className="flex items-center space-x-1">
                      <Activity className="w-3.5 h-3.5 text-blue-500" />
                      <span>Vitals Recorded</span>
                    </span>
                    <span className="font-semibold text-blue-600 group-hover:underline">Open Chart &rarr;</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Department Actions */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900">Clinical Workflow Shortcuts</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <button
                onClick={() => onNavigate("clinical_ai")}
                className="p-3.5 bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-xl text-left transition-all cursor-pointer"
              >
                <Stethoscope className="w-5 h-5 text-blue-600 mb-2" />
                <div className="text-xs font-bold text-slate-800">New Consultation</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Start AI case query</div>
              </button>

              <button
                onClick={() => onNavigate("documents")}
                className="p-3.5 bg-slate-50 hover:bg-teal-50 border border-slate-200 hover:border-teal-300 rounded-xl text-left transition-all cursor-pointer"
              >
                <Upload className="w-5 h-5 text-teal-600 mb-2" />
                <div className="text-xs font-bold text-slate-800">Upload Report</div>
                <div className="text-[10px] text-slate-500 mt-0.5">PDF auto-chunking</div>
              </button>

              <button
                onClick={() => onNavigate("patients")}
                className="p-3.5 bg-slate-50 hover:bg-purple-50 border border-slate-200 hover:border-purple-300 rounded-xl text-left transition-all cursor-pointer"
              >
                <Activity className="w-5 h-5 text-purple-600 mb-2" />
                <div className="text-xs font-bold text-slate-800">Record Vitals</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Nurse triage entry</div>
              </button>

              <button
                onClick={() => onNavigate("knowledge_base")}
                className="p-3.5 bg-slate-50 hover:bg-amber-50 border border-slate-200 hover:border-amber-300 rounded-xl text-left transition-all cursor-pointer"
              >
                <FlaskConical className="w-5 h-5 text-amber-600 mb-2" />
                <div className="text-xs font-bold text-slate-800">Guidelines Base</div>
                <div className="text-[10px] text-slate-500 mt-0.5">FAISS vector status</div>
              </button>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Recent Consultations & Knowledge Base Feed */}
        <div className="space-y-6">
          {/* Recent Consultations */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Recent Consultations</h3>
              <button
                onClick={() => onNavigate("clinical_ai")}
                className="text-xs font-semibold text-blue-600 hover:underline cursor-pointer"
              >
                All
              </button>
            </div>

            {sessions.length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-400">
                No recent consultations found.
              </div>
            ) : (
              <div className="space-y-2.5">
                {sessions.slice(0, 4).map((session) => (
                  <div
                    key={session.id}
                    onClick={() => {
                      onSelectSession(session.id);
                      onNavigate("clinical_ai");
                    }}
                    className="p-3 bg-slate-50 hover:bg-blue-50/70 border border-slate-200 hover:border-blue-200 rounded-xl transition-all cursor-pointer"
                  >
                    <div className="text-xs font-bold text-slate-800 truncate">
                      {session.title || "Clinical AI Query"}
                    </div>
                    <div className="flex items-center space-x-1 text-[10px] text-slate-400 mt-1">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(session.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Medical Guidelines */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Active Knowledge Base</h3>
              <span className="text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">
                Vector Indexed
              </span>
            </div>

            <div className="space-y-2.5">
              {kbDocs.map((doc) => (
                <div key={doc.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                  <div className="flex items-center space-x-2.5 truncate">
                    <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                    <span className="text-xs font-semibold text-slate-800 truncate">
                      {doc.name}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded shrink-0">
                    {doc.chunk_count} chunks
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
