import React, { useState } from "react";
import { Sparkles, CheckCircle, Printer, Save } from "lucide-react";
import type { Patient, ClinicalReport } from "../types";

interface ReportStudioProps {
  patients: Patient[];
}

export const ReportStudio: React.FC<ReportStudioProps> = ({ patients }) => {
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [clinicalHistory, setClinicalHistory] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentReport, setCurrentReport] = useState<ClinicalReport | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !chiefComplaint.trim()) {
      alert("Please select a patient and enter chief complaint.");
      return;
    }

    setLoading(true);
    setSuccessMsg(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/reports/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({
          patient_id: selectedPatientId,
          chief_complaint: chiefComplaint,
          clinical_history: clinicalHistory,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setCurrentReport(data);
        setSuccessMsg("AI draft report generated successfully. You can edit all fields below before approval.");
      } else {
        alert(data.detail || "Report generation failed.");
      }
    } catch (err) {
      alert("Error generating report.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!currentReport) return;
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/reports/${currentReport.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify(currentReport),
      });
      if (res.ok) {
        setSuccessMsg("Draft report changes saved.");
      }
    } catch (e) {
      alert("Failed to save report.");
    }
  };

  const handleApprove = async () => {
    if (!currentReport) return;
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/reports/${currentReport.id}/approve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        setCurrentReport({ ...currentReport, status: "APPROVED" });
        setSuccessMsg("Report officially APPROVED by Attending Physician and committed to patient records & RAG.");
      }
    } catch (e) {
      alert("Failed to approve report.");
    }
  };

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Doctor AI Clinical Report Studio</h1>
          <p className="text-xs text-slate-500">Synthesize patient longitudinal vitals, labs, radiology findings, and institutional guidelines into an editable official report.</p>
        </div>

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {successMsg}
          </div>
        )}

        {/* Generator Form */}
        <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Patient *</label>
                <select
                  required
                  value={selectedPatientId}
                  onChange={(e) => setSelectedPatientId(e.target.value)}
                  className="w-full py-2.5 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                >
                  <option value="">-- Choose Patient --</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Chief Complaint *</label>
                <input
                  type="text"
                  required
                  value={chiefComplaint}
                  onChange={(e) => setChiefComplaint(e.target.value)}
                  placeholder="e.g. Acute onset of high fever, productive cough with purulent sputum, right-sided chest pain"
                  className="w-full py-2.5 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Clinical History & Presentation</label>
              <textarea
                rows={2}
                value={clinicalHistory}
                onChange={(e) => setClinicalHistory(e.target.value)}
                placeholder="e.g. Symptoms began 3 days ago. No previous respiratory admissions. Nonsmoker. Completed outpatient azithromycin with no resolution."
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="py-3 px-6 bg-rose-900 hover:bg-rose-800 text-white rounded-xl text-xs font-semibold shadow-md flex items-center justify-center gap-2 transition disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              <span>{loading ? "Synthesizing Evidence & Generating Draft..." : "Generate AI Patient Report Draft"}</span>
            </button>
          </form>
        </div>

        {/* Editable Report Workspace */}
        {currentReport && (
          <div className="p-8 bg-white rounded-2xl border border-slate-200 shadow-lg space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div>
                <input
                  type="text"
                  value={currentReport.title}
                  onChange={(e) => setCurrentReport({ ...currentReport, title: e.target.value })}
                  className="text-lg font-bold text-slate-900 w-full focus:outline-none focus:border-b-2 focus:border-rose-800"
                />
                <p className="text-xs text-slate-500 mt-1">Status: <strong className={currentReport.status === "APPROVED" ? "text-emerald-700" : "text-amber-700"}>{currentReport.status}</strong></p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleSaveDraft}
                  className="py-2 px-4 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <Save className="w-3.5 h-3.5" />
                  Save Draft
                </button>
                <button
                  onClick={() => window.print()}
                  className="py-2 px-4 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <Printer className="w-3.5 h-3.5" />
                  Print
                </button>
                {currentReport.status !== "APPROVED" && (
                  <button
                    onClick={handleApprove}
                    className="py-2 px-4 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md transition"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Approve Official Report
                  </button>
                )}
              </div>
            </div>

            {/* Editable Sections */}
            <div className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">1. Chief Complaint</label>
                <textarea
                  rows={2}
                  value={currentReport.chief_complaint || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, chief_complaint: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">2. Clinical History</label>
                <textarea
                  rows={2}
                  value={currentReport.clinical_history || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, clinical_history: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">3. Physical Observations & Vitals</label>
                <textarea
                  rows={2}
                  value={currentReport.observations || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, observations: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">4. Diagnostic Investigations (Labs & Radiology)</label>
                <textarea
                  rows={2}
                  value={currentReport.investigations || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, investigations: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">5. Clinical Assessment & Risk Stratification</label>
                <textarea
                  rows={3}
                  value={currentReport.clinical_assessment || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, clinical_assessment: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">6. Evidence-Based Recommendations & Management Plan</label>
                <textarea
                  rows={4}
                  value={currentReport.recommendations || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, recommendations: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider mb-1">7. Hospital Guidelines & Citations Grounding</label>
                <input
                  type="text"
                  value={currentReport.sources || ""}
                  onChange={(e) => setCurrentReport({ ...currentReport, sources: e.target.value })}
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
