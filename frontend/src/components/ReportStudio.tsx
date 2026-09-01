import React, { useState, useEffect } from "react";
import { Sparkles, CheckCircle2, Printer, AlertTriangle, ShieldCheck, Stethoscope, RefreshCw } from "lucide-react";
import type { Patient, ClinicalReport, UserProfile } from "../types";

interface ReportStudioProps {
  patients: Patient[];
  apiBase: string;
  token: string;
  currentUser: UserProfile;
  initialPatientId?: string;
}

export const ReportStudio: React.FC<ReportStudioProps> = ({
  patients,
  apiBase,
  token,
  currentUser,
  initialPatientId
}) => {
  const [selectedPatientId, setSelectedPatientId] = useState<string>(initialPatientId || (patients[0]?.id || ""));
  const [chiefComplaint, setChiefComplaint] = useState("Productive cough, fever (38.2 C), and right pleuritic chest pain for 4 days.");
  const [clinicalHistory, setClinicalHistory] = useState("No significant previous cardiopulmonary history. Presenting with acute respiratory distress.");
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeReport, setActiveReport] = useState<ClinicalReport | null>(null);
  
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (patients.length > 0 && !selectedPatientId) {
      setSelectedPatientId(patients[0].id);
    }
  }, [patients]);

  const showNotification = (type: "success" | "error", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const handleGenerateReport = async () => {
    if (!selectedPatientId) return;
    setIsGenerating(true);
    try {
      const res = await fetch(`${apiBase}/api/reports/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          patient_id: selectedPatientId,
          chief_complaint: chiefComplaint,
          clinical_history: clinicalHistory
        })
      });

      if (res.ok) {
        const data = await res.json();
        setActiveReport(data);
        showNotification("success", "AI Patient Report generated! Review and verify below.");
      } else {
        const err = await res.json();
        showNotification("error", err.detail || "Error generating report.");
      }
    } catch (e) {
      console.error(e);
      showNotification("error", "Network error during report synthesis.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApproveReport = async () => {
    if (!activeReport) return;
    try {
      const res = await fetch(`${apiBase}/api/reports/${activeReport.id}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setActiveReport(prev => prev ? { ...prev, status: "APPROVED", approved_at: new Date().toISOString() } : null);
        showNotification("success", "Report officially approved and committed to clinical record!");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const selectedPatient = patients.find(p => p.id === selectedPatientId);

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-1">
            <Stethoscope className="w-4 h-4" />
            <span>Physician Decision Support</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            AI Patient Clinical Report Studio
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Synthesize patient vitals, CBC labs, imaging findings, and clinical guidelines into structured draft reports.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-bold flex items-center space-x-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>NLI Grounded & Doctor Approved</span>
          </span>
        </div>
      </div>

      {msg && (
        <div className={`p-4 rounded-xl text-xs font-semibold flex items-center space-x-2 animate-fadeIn ${
          msg.type === "success" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" : "bg-red-50 border border-red-200 text-red-700"
        }`}>
          {msg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
          <span>{msg.text}</span>
        </div>
      )}

      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5">
        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
          1. Select Patient & Enter Clinical Presentation
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 mb-1.5">Select Patient</label>
            <select
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2.5 text-xs font-bold text-slate-900 outline-none focus:border-blue-500"
            >
              {patients.map(p => (
                <option key={p.id} value={p.id}>{p.id} - {p.name} ({p.department})</option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="block font-bold text-slate-700 mb-1.5">Chief Complaint</label>
            <input
              type="text"
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2.5 text-xs outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="text-xs">
          <label className="block font-bold text-slate-700 mb-1.5">Clinical History & Onset</label>
          <textarea
            rows={2}
            value={clinicalHistory}
            onChange={(e) => setClinicalHistory(e.target.value)}
            className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center justify-between pt-2">
          <span className="text-[11px] text-slate-500">
            Pipeline: Patient Vitals + CBC Panel + Radiology + FAISS Guidelines &rarr; Llama 3.3 70B &rarr; Structured Draft
          </span>

          <button
            type="button"
            onClick={handleGenerateReport}
            disabled={isGenerating}
            className="flex items-center space-x-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Synthesizing Report...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Generate AI Clinical Report</span>
              </>
            )}
          </button>
        </div>
      </div>

      {activeReport && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-lg p-6 md:p-8 space-y-6 animate-fadeIn">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-200">
            <div className="flex items-center space-x-3">
              <span
                className={`px-3 py-1 rounded-full text-xs font-extrabold tracking-wider uppercase flex items-center space-x-1.5 ${
                  activeReport.status === "APPROVED"
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                    : "bg-amber-100 text-amber-900 border border-amber-300 animate-pulse"
                }`}
              >
                <span>{activeReport.status}</span>
              </span>

              <span className="text-xs text-slate-400 font-medium">
                Created {new Date(activeReport.created_at).toLocaleString()}
              </span>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => window.print()}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors cursor-pointer"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>Print</span>
              </button>

              {activeReport.status !== "APPROVED" && currentUser.role === "DOCTOR" && (
                <button
                  onClick={handleApproveReport}
                  className="flex items-center space-x-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-emerald-500/20 cursor-pointer"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Approve & Sign Official Report</span>
                </button>
              )}
            </div>
          </div>

          {activeReport.status === "AI-GENERATED DRAFT" && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start space-x-3">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
              <div className="leading-relaxed">
                <strong>Physician Notice:</strong> This clinical report was synthesized by AI decision support. It must be carefully reviewed, edited if necessary, and approved by the attending physician before becoming part of the official legal medical record.
              </div>
            </div>
          )}

          <div className="space-y-6 text-slate-900">
            <div className="text-center space-y-1 pb-4 border-b border-slate-100">
              <h2 className="text-xl font-black tracking-tight text-slate-900">
                {activeReport.title}
              </h2>
              <p className="text-xs text-slate-500">
                Department of {selectedPatient?.department || "Medicine"} • Hospital Clinical Decision System
              </p>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="font-bold text-slate-400 block text-[10px] uppercase">Patient ID</span>
                <span className="font-mono font-bold text-blue-700">{selectedPatient?.id}</span>
              </div>
              <div>
                <span className="font-bold text-slate-400 block text-[10px] uppercase">Full Name</span>
                <span className="font-bold text-slate-800">{selectedPatient?.name}</span>
              </div>
              <div>
                <span className="font-bold text-slate-400 block text-[10px] uppercase">Age / Gender</span>
                <span className="font-semibold text-slate-800">{selectedPatient?.age} yrs • {selectedPatient?.gender}</span>
              </div>
              <div>
                <span className="font-bold text-slate-400 block text-[10px] uppercase">Attending Physician</span>
                <span className="font-bold text-slate-800">{currentUser.name}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2 bg-slate-50/50 p-4 rounded-xl border border-slate-200/80">
                <span className="text-xs font-black uppercase text-blue-800 tracking-wider">CHIEF COMPLAINT</span>
                <p className="text-xs text-slate-700 leading-relaxed">{activeReport.chief_complaint}</p>
              </div>

              <div className="space-y-2 bg-slate-50/50 p-4 rounded-xl border border-slate-200/80">
                <span className="text-xs font-black uppercase text-blue-800 tracking-wider">CLINICAL HISTORY</span>
                <p className="text-xs text-slate-700 leading-relaxed">{activeReport.clinical_history}</p>
              </div>

              <div className="space-y-2 bg-slate-50/50 p-4 rounded-xl border border-slate-200/80">
                <span className="text-xs font-black uppercase text-blue-800 tracking-wider">OBSERVATIONS & VITALS</span>
                <p className="text-xs text-slate-700 leading-relaxed">{activeReport.observations}</p>
              </div>

              <div className="space-y-2 bg-slate-50/50 p-4 rounded-xl border border-slate-200/80">
                <span className="text-xs font-black uppercase text-blue-800 tracking-wider">INVESTIGATIONS & LABS</span>
                <p className="text-xs text-slate-700 leading-relaxed">{activeReport.investigations}</p>
              </div>
            </div>

            <div className="space-y-2 bg-blue-50/30 p-5 rounded-xl border border-blue-200">
              <span className="text-xs font-black uppercase text-blue-900 tracking-wider">CLINICAL ASSESSMENT & DIAGNOSIS</span>
              <p className="text-xs text-slate-800 leading-relaxed font-medium">{activeReport.clinical_assessment}</p>
            </div>

            <div className="space-y-2 bg-emerald-50/30 p-5 rounded-xl border border-emerald-200">
              <span className="text-xs font-black uppercase text-emerald-900 tracking-wider">RECOMMENDATIONS & MANAGEMENT PLAN</span>
              <p className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">{activeReport.recommendations}</p>
            </div>

            <div className="space-y-2 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
              <span className="font-bold text-slate-500 uppercase tracking-wider block text-[10px]">CITED SOURCES & GUIDELINES</span>
              <p className="text-slate-600 font-mono text-[11px]">{activeReport.sources}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
