import React, { useState, useEffect } from "react";
import { Image as ImageIcon, Upload, CheckCircle, AlertCircle, Trash2 } from "lucide-react";
import { getApiUrl } from "../api/client";
import type { Patient, RadiologyRecord } from "../types";

interface RadiologyWorkspaceProps {
  patients: Patient[];
}

export const RadiologyWorkspace: React.FC<RadiologyWorkspaceProps> = ({ patients }) => {
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [modality, setModality] = useState("X-Ray");
  const [findings, setFindings] = useState("");
  const [impression, setImpression] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [records, setRecords] = useState<RadiologyRecord[]>([]);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchRecords = async () => {
    try {
      const res = await fetch(getApiUrl("/api/radiology"), {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRecords(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, []);

  const handleDeleteRecord = async (recordId: number) => {
    if (!window.confirm("Are you sure you want to delete this radiology report?")) return;
    try {
      const res = await fetch(getApiUrl(`/api/radiology/${recordId}`), {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
      if (res.ok) {
        setRecords((prev) => prev.filter((item) => item.id !== recordId));
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete radiology record.");
      }
    } catch (e) {
      console.error("Failed to delete radiology record:", e);
      alert("Failed to delete radiology record.");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !findings.trim()) {
      alert("Please select a patient and provide textual findings.");
      return;
    }

    setLoading(true);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("patient_id", selectedPatientId);
    formData.append("modality", modality);
    formData.append("findings", findings);
    if (impression) formData.append("impression", impression);
    if (file) formData.append("file", file);

    try {
      const res = await fetch(getApiUrl("/api/radiology/upload"), {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Radiology record logged successfully for patient.`);
        setFindings("");
        setImpression("");
        setFile(null);
        fetchRecords();
      } else {
        alert(data.detail || "Upload failed.");
      }
    } catch (err) {
      alert("Failed to submit radiology report.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Radiology Imaging & Reports Workspace</h1>
            <p className="text-xs text-slate-500">Record diagnostic impressions, upload medical imaging (DICOM/X-Ray/CT/MRI/PDF), and link to patient chart.</p>
          </div>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-900 border border-rose-200">
            Radiologist Certified Entry
          </span>
        </div>

        {/* Notice on AI diagnostic policy */}
        <div className="p-4 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-700 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-slate-500 shrink-0 mt-0.5" />
          <p>
            <strong>Hospital Governance Notice:</strong> Uploaded images are stored as clinical reference artifacts. Only licensed radiologist-entered findings, impressions, or validated text reports feed into authorized Clinical RAG evidence.
          </p>
        </div>

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {successMsg}
          </div>
        )}

        {/* Form and History Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Entry Form */}
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Upload className="w-4 h-4 text-rose-900" />
              New Diagnostic Entry
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
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
                      {p.name} ({p.id}) - {p.department}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Modality *</label>
                <select
                  value={modality}
                  onChange={(e) => setModality(e.target.value)}
                  className="w-full py-2.5 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                >
                  <option value="Chest X-Ray">Chest X-Ray</option>
                  <option value="CT Scan">CT Scan (Thorax / Abdomen / Head)</option>
                  <option value="MRI">MRI</option>
                  <option value="Ultrasound">Ultrasound</option>
                  <option value="X-Ray Skeletal">X-Ray Skeletal</option>
                  <option value="Other">Other Imaging</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Imaging File (PDF, PNG, JPG, DICOM .dcm)</label>
                <input
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  accept=".pdf,.png,.jpg,.jpeg,.dcm"
                  className="w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-rose-50 file:text-rose-900 hover:file:bg-rose-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Radiological Findings *</label>
                <textarea
                  required
                  rows={4}
                  value={findings}
                  onChange={(e) => setFindings(e.target.value)}
                  placeholder="e.g. Right lower lobe consolidation with prominent air bronchograms. No significant pleural effusion or pneumothorax..."
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Impression & Differential</label>
                <textarea
                  rows={2}
                  value={impression}
                  onChange={(e) => setImpression(e.target.value)}
                  placeholder="e.g. Findings highly consistent with acute bacterial lobar pneumonia. Clinical correlation advised."
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-rose-900 hover:bg-rose-800 text-white rounded-xl text-xs font-semibold shadow-md transition disabled:opacity-50"
              >
                {loading ? "Recording & Indexing..." : "Submit Approved Radiology Report"}
              </button>
            </form>
          </div>

          {/* Radiology History */}
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-rose-900" />
              Recent Radiology Exams ({records.length})
            </h2>

            <div className="flex-1 overflow-y-auto space-y-3 max-h-[520px] pr-1">
              {records.length === 0 ? (
                <p className="text-xs text-slate-400 italic py-4">No radiology exams logged yet.</p>
              ) : (
                records.map((r) => (
                  <div key={r.id} className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <h4 className="text-xs font-bold text-slate-900">{r.modality}</h4>
                        <p className="text-[11px] text-slate-500">Patient: <strong>{r.patient_name}</strong> ({r.patient_id})</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {r.status}
                        </span>
                        <button
                          onClick={() => handleDeleteRecord(r.id)}
                          title="Delete Radiology Record"
                          className="text-slate-400 hover:text-red-600 hover:bg-red-50 p-1 rounded transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <p className="text-xs text-slate-700 mb-2 leading-relaxed">
                      <strong>Findings:</strong> {r.findings}
                    </p>

                    {r.impression && (
                      <p className="text-xs text-rose-950 font-medium mb-2">
                        <strong>Impression:</strong> {r.impression}
                      </p>
                    )}

                    <div className="flex items-center justify-between text-[10px] text-slate-400 pt-2 border-t border-slate-200">
                      <span>Reported by: {r.radiologist_name}</span>
                      <span>{new Date(r.timestamp).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
