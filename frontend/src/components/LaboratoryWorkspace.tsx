import React, { useState, useEffect } from "react";
import { TestTube, Upload, CheckCircle, Trash2 } from "lucide-react";
import { getApiUrl } from "../api/client";
import type { Patient, LabResult } from "../types";

interface LaboratoryWorkspaceProps {
  patients: Patient[];
}

export const LaboratoryWorkspace: React.FC<LaboratoryWorkspaceProps> = ({ patients }) => {
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [hemoglobin, setHemoglobin] = useState<string>("");
  const [wbc, setWbc] = useState<string>("");
  const [crp, setCrp] = useState<string>("");
  const [platelets, setPlatelets] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [records, setRecords] = useState<LabResult[]>([]);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchRecords = async () => {
    try {
      const res = await fetch(getApiUrl("/api/laboratory"), {
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
    if (!window.confirm("Are you sure you want to delete this laboratory panel?")) return;
    try {
      const res = await fetch(getApiUrl(`/api/laboratory/${recordId}`), {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
      if (res.ok) {
        setRecords((prev) => prev.filter((item) => item.id !== recordId));
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete laboratory record.");
      }
    } catch (e) {
      console.error("Failed to delete laboratory record:", e);
      alert("Failed to delete laboratory record.");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) {
      alert("Please select a patient.");
      return;
    }

    setLoading(true);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("patient_id", selectedPatientId);
    if (hemoglobin) formData.append("hemoglobin", hemoglobin);
    if (wbc) formData.append("wbc", wbc);
    if (crp) formData.append("crp", crp);
    if (platelets) formData.append("platelets", platelets);
    if (notes) formData.append("notes", notes);
    if (file) formData.append("file", file);

    try {
      const res = await fetch(getApiUrl("/api/laboratory/upload"), {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Laboratory results recorded successfully.`);
        setHemoglobin("");
        setWbc("");
        setCrp("");
        setPlatelets("");
        setNotes("");
        setFile(null);
        fetchRecords();
      } else {
        alert(data.detail || "Upload failed.");
      }
    } catch (err) {
      alert("Failed to submit laboratory panel.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Laboratory & Pathology Workspace</h1>
            <p className="text-xs text-slate-500">Record CBC panels, inflammatory biomarkers (CRP/ESR), biochemistry, and diagnostic PDFs.</p>
          </div>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-900 border border-rose-200">
            Pathology Laboratory
          </span>
        </div>

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {successMsg}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Entry Form */}
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Upload className="w-4 h-4 text-rose-900" />
              Record Lab Panel
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Hemoglobin (g/dL)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={hemoglobin}
                    onChange={(e) => setHemoglobin(e.target.value)}
                    placeholder="e.g. 13.5"
                    className="w-full py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">WBC Count (/uL)</label>
                  <input
                    type="number"
                    value={wbc}
                    onChange={(e) => setWbc(e.target.value)}
                    placeholder="e.g. 12500"
                    className="w-full py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">CRP (mg/L)</label>
                  <input
                    type="text"
                    value={crp}
                    onChange={(e) => setCrp(e.target.value)}
                    placeholder="e.g. 48.5 mg/L"
                    className="w-full py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Platelets (/uL)</label>
                  <input
                    type="number"
                    value={platelets}
                    onChange={(e) => setPlatelets(e.target.value)}
                    placeholder="e.g. 250000"
                    className="w-full py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Attach Lab PDF Report (Optional)</label>
                <input
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  accept=".pdf"
                  className="w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-rose-50 file:text-rose-900 hover:file:bg-rose-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Pathologist Observations / Notes</label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Marked neutrophilic leukocytosis with significant CRP elevation. Bacterial etiology suspected."
                  className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-rose-900 hover:bg-rose-800 text-white rounded-xl text-xs font-semibold shadow-md transition disabled:opacity-50"
              >
                {loading ? "Recording..." : "Save Laboratory Findings"}
              </button>
            </form>
          </div>

          {/* History */}
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <TestTube className="w-4 h-4 text-rose-900" />
              Recent Lab Panels ({records.length})
            </h2>

            <div className="flex-1 overflow-y-auto space-y-3 max-h-[520px] pr-1">
              {records.length === 0 ? (
                <p className="text-xs text-slate-400 italic py-4">No laboratory records found.</p>
              ) : (
                records.map((l) => (
                  <div key={l.id} className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h4 className="text-xs font-bold text-slate-900">
                        Patient: {l.patient_name || l.patient_id}
                      </h4>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-slate-400">
                          {new Date(l.timestamp).toLocaleDateString()}
                        </span>
                        <button
                          onClick={() => handleDeleteRecord(l.id)}
                          title="Delete Laboratory Record"
                          className="text-slate-400 hover:text-red-600 hover:bg-red-50 p-1 rounded transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-700 bg-white p-2.5 rounded-lg border border-slate-100 mb-2">
                      <div>Hb: <strong>{l.hemoglobin ? `${l.hemoglobin} g/dL` : "N/A"}</strong></div>
                      <div>WBC: <strong>{l.wbc ? `${l.wbc} /uL` : "N/A"}</strong></div>
                      <div>CRP: <strong>{l.crp || "N/A"}</strong></div>
                      <div>Platelets: <strong>{l.platelets || "N/A"}</strong></div>
                    </div>

                    {l.notes && (
                      <p className="text-xs text-slate-600 leading-relaxed mb-2">
                        {l.notes}
                      </p>
                    )}

                    <p className="text-[10px] text-slate-400">Technician: {l.technician_name}</p>
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
