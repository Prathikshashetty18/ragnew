import React, { useState, useEffect, useRef } from "react";
import { 
  Activity, FileText, Upload, FlaskConical,
  CheckCircle2, AlertTriangle, User,
  Sparkles, Stethoscope
} from "lucide-react";

interface Vitals {
  id: number;
  blood_pressure: string;
  pulse: number;
  temperature: number;
  spo2: number;
  notes: string | null;
  recorded_by: string;
  timestamp: string;
}

interface LabResult {
  id: number;
  hemoglobin: number | null;
  wbc: number | null;
  crp: string | null;
  platelets: number | null;
  notes: string | null;
  recorded_by: string;
  timestamp: string;
}

interface RadiologyReport {
  id: number;
  findings: string;
  document_name: string | null;
  document_id: number | null;
  recorded_by: string;
  timestamp: string;
}

interface ClinicalNote {
  id: number;
  notes: string;
  author: string;
  timestamp: string;
}

interface Document {
  id: number;
  name: string;
  status: string;
  chunk_count: number;
  scope: string;
  document_type?: string;
  uploaded_by?: string;
  created_at: string;
}

interface Patient {
  id: string;
  name: string;
  age: number;
  gender: string;
  health_status: string;
  assigned_doctor: string;
  documents?: Document[];
  vitals?: Vitals[];
  labs?: LabResult[];
  radiology?: RadiologyReport[];
  notes?: ClinicalNote[];
}

interface PatientDashboardProps {
  patients: Patient[];
  currentUser: { id: number; username: string; role: string; name: string };
  apiBase: string;
  apiKey: string;
  selectedPatientId: string;
  onSelectPatient: (id: string) => void;
  onSelectDocumentForChat: (doc: Document) => void;
  onSelectPatientForChat: (patientId: string) => void;
}

export const PatientDashboard: React.FC<PatientDashboardProps> = ({
  patients,
  currentUser,
  apiBase,
  apiKey,
  selectedPatientId,
  onSelectPatient,
  onSelectDocumentForChat,
  onSelectPatientForChat
}) => {
  const [activeTab, setActiveTab] = useState<"overview" | "vitals" | "labs" | "radiology" | "notes" | "documents">("overview");
  const [patientData, setPatientData] = useState<Patient | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form states
  const [bp, setBp] = useState("");
  const [pulse, setPulse] = useState("");
  const [temp, setTemp] = useState("");
  const [spo2, setSpo2] = useState("");
  const [vitalsNotes, setVitalsNotes] = useState("");

  const [hb, setHb] = useState("");
  const [wbc, setWbc] = useState("");
  const [crp, setCrp] = useState("");
  const [platelets, setPlatelets] = useState("");
  const [labNotes, setLabNotes] = useState("");

  const [radFindings, setRadFindings] = useState("");
  const [noteContent, setNoteContent] = useState("");

  const radFileRef = useRef<HTMLInputElement>(null);

  const fetchPatientDetails = async (id: string) => {
    setErrorMsg(null);
    try {
      const res = await fetch(`${apiBase}/api/patients/${id}`, {
        headers: {
          "X-API-Key": apiKey,
          "X-User-Id": currentUser.username
        }
      });
      if (res.ok) {
        const data = await res.json();
        setPatientData(data);
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || "Error loading patient profile.");
      }
    } catch (e) {
      console.error(e);
      setErrorMsg("Network error loading patient profile.");
    }
  };

  useEffect(() => {
    if (selectedPatientId) {
      fetchPatientDetails(selectedPatientId);
    }
  }, [selectedPatientId]);

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  // Submit Vitals
  const handleSaveVitals = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) return;

    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/vitals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
          "X-User-Id": currentUser.username
        },
        body: JSON.stringify({
          blood_pressure: bp || "120/80",
          pulse: pulse ? parseInt(pulse) : 75,
          temperature: temp ? parseFloat(temp) : 37.0,
          spo2: spo2 ? parseInt(spo2) : 98,
          notes: vitalsNotes
        })
      });

      if (res.ok) {
        showSuccess("Vitals recorded successfully!");
        setBp(""); setPulse(""); setTemp(""); setSpo2(""); setVitalsNotes("");
        fetchPatientDetails(selectedPatientId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Submit Labs
  const handleSaveLabs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) return;

    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/labs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
          "X-User-Id": currentUser.username
        },
        body: JSON.stringify({
          hemoglobin: hb ? parseFloat(hb) : null,
          wbc: wbc ? parseInt(wbc) : null,
          crp: crp || null,
          platelets: platelets ? parseInt(platelets) : null,
          notes: labNotes
        })
      });

      if (res.ok) {
        showSuccess("Lab results recorded successfully!");
        setHb(""); setWbc(""); setCrp(""); setPlatelets(""); setLabNotes("");
        fetchPatientDetails(selectedPatientId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Submit Radiology Findings
  const handleSaveRadiology = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !radFindings.trim()) return;

    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/radiology`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
          "X-User-Id": currentUser.username
        },
        body: JSON.stringify({
          findings: radFindings
        })
      });

      if (res.ok) {
        showSuccess("Radiology findings logged successfully!");
        setRadFindings("");
        fetchPatientDetails(selectedPatientId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Submit Doctor Clinical Note
  const handleSaveNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !noteContent.trim()) return;

    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/notes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
          "X-User-Id": currentUser.username
        },
        body: JSON.stringify({
          notes: noteContent
        })
      });

      if (res.ok) {
        showSuccess("Clinical note saved!");
        setNoteContent("");
        fetchPatientDetails(selectedPatientId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Upload Patient PDF
  const handlePatientFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const formData = new FormData();
      formData.append("file", file);
      formData.append("scope", "patient");
      formData.append("patient_id", selectedPatientId);
      formData.append("document_type", "Radiology Report");

      try {
        const res = await fetch(`${apiBase}/api/upload`, {
          method: "POST",
          headers: {
            "X-API-Key": apiKey,
            "X-User-Id": currentUser.username
          },
          body: formData
        });

        if (res.ok) {
          showSuccess(`Uploaded & indexed "${file.name}"!`);
          fetchPatientDetails(selectedPatientId);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const patient = patientData || patients.find(p => p.id === selectedPatientId);

  return (
    <div className="flex-1 flex h-full bg-slate-50 overflow-hidden">
      {/* Patient List Column */}
      <div className="w-72 bg-white border-r border-slate-200 flex flex-col h-full shrink-0">
        <div className="p-4 border-b border-slate-200">
          <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-1">
            <User className="w-4 h-4" />
            <span>Hospital Patients</span>
          </div>
          <h2 className="text-base font-black text-slate-900">
            Assigned Records
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {patients.map((p) => (
            <div
              key={p.id}
              onClick={() => onSelectPatient(p.id)}
              className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                selectedPatientId === p.id
                  ? "bg-blue-50 border-blue-300 shadow-xs"
                  : "bg-white border-slate-200 hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-blue-700 bg-blue-100/60 px-2 py-0.5 rounded">
                  {p.id}
                </span>
                <span className="text-[10px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full">
                  {p.health_status}
                </span>
              </div>
              <div className="text-sm font-bold text-slate-900 mt-2">
                {p.name}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {p.age} yrs • {p.gender === "M" ? "Male" : "Female"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Patient Chart Detail Area */}
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-6 md:p-8 space-y-6">
        {/* Error / Success Banners */}
        {errorMsg && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-semibold flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 font-semibold flex items-center space-x-2 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {patient ? (
          <>
            {/* Top Patient Header Card */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
                    {patient.id}
                  </span>
                  <span className="text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                    {patient.health_status}
                  </span>
                </div>
                <h1 className="text-2xl font-black text-slate-900">
                  {patient.name}
                </h1>
                <p className="text-xs text-slate-500">
                  Age: <strong>{patient.age}</strong> • Gender: <strong>{patient.gender === "M" ? "Male" : "Female"}</strong> • Attending Physician: <strong>{patient.assigned_doctor}</strong>
                </p>
              </div>

              {/* Quick Action: Launch AI Consultation for this Patient */}
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => onSelectPatientForChat(patient.id)}
                  className="flex items-center space-x-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Consult AI for {patient.name}</span>
                </button>
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex bg-slate-200/80 p-1 rounded-xl text-xs font-bold max-w-2xl">
              {[
                { id: "overview", label: "Overview & Timeline" },
                { id: "vitals", label: "Vitals Log" },
                { id: "labs", label: "Laboratory (CBC)" },
                { id: "radiology", label: "Radiology" },
                { id: "notes", label: "Doctor Notes" },
                { id: "documents", label: "Attached PDFs" }
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id as any)}
                  className={`flex-1 py-2 px-3 rounded-lg transition-all text-center cursor-pointer ${
                    activeTab === t.id
                      ? "bg-white text-blue-700 shadow-xs font-black"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab 1: Overview & Timeline */}
            {activeTab === "overview" && (
              <div className="space-y-6">
                {/* Latest Clinical Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Latest Vitals */}
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase">
                      <span className="flex items-center space-x-1.5 text-blue-600">
                        <Activity className="w-4 h-4" />
                        <span>Latest Vitals</span>
                      </span>
                    </div>
                    {patientData?.vitals && patientData.vitals.length > 0 ? (
                      <div className="space-y-1.5 text-xs text-slate-800">
                        <div>BP: <strong>{patientData.vitals[0].blood_pressure}</strong> mmHg</div>
                        <div>Heart Rate: <strong>{patientData.vitals[0].pulse}</strong> bpm</div>
                        <div>Temperature: <strong>{patientData.vitals[0].temperature}</strong> °C</div>
                        <div>SpO₂: <strong>{patientData.vitals[0].spo2}</strong>%</div>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-400">No vitals recorded yet.</div>
                    )}
                  </div>

                  {/* Latest Lab Results */}
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase">
                      <span className="flex items-center space-x-1.5 text-emerald-600">
                        <FlaskConical className="w-4 h-4" />
                        <span>Latest CBC Labs</span>
                      </span>
                    </div>
                    {patientData?.labs && patientData.labs.length > 0 ? (
                      <div className="space-y-1.5 text-xs text-slate-800">
                        <div>Hemoglobin: <strong>{patientData.labs[0].hemoglobin}</strong> g/dL</div>
                        <div>WBC Count: <strong>{patientData.labs[0].wbc}</strong> /uL</div>
                        <div>CRP: <strong>{patientData.labs[0].crp}</strong></div>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-400">No lab panels on record.</div>
                    )}
                  </div>

                  {/* Latest Radiology */}
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase">
                      <span className="flex items-center space-x-1.5 text-purple-600">
                        <FileText className="w-4 h-4" />
                        <span>Radiology Findings</span>
                      </span>
                    </div>
                    {patientData?.radiology && patientData.radiology.length > 0 ? (
                      <p className="text-xs text-slate-800 line-clamp-3 leading-relaxed">
                        {patientData.radiology[0].findings}
                      </p>
                    ) : (
                      <div className="text-xs text-slate-400">No imaging reports logged.</div>
                    )}
                  </div>
                </div>

                {/* Timeline Feed */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900">Clinical Event Timeline</h3>
                  <div className="space-y-3">
                    {patientData?.notes?.map((n) => (
                      <div key={n.id} className="flex items-start space-x-3 p-3 bg-slate-50 rounded-xl text-xs">
                        <Stethoscope className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
                        <div>
                          <div className="font-bold text-slate-800">{n.author} logged Clinical Note</div>
                          <p className="text-slate-600 mt-0.5">{n.notes}</p>
                          <span className="text-[10px] text-slate-400">{new Date(n.timestamp).toLocaleString()}</span>
                        </div>
                      </div>
                    ))}
                    {patientData?.radiology?.map((r) => (
                      <div key={r.id} className="flex items-start space-x-3 p-3 bg-slate-50 rounded-xl text-xs">
                        <FileText className="w-4 h-4 text-purple-600 mt-0.5 shrink-0" />
                        <div>
                          <div className="font-bold text-slate-800">{r.recorded_by} recorded Radiology Findings</div>
                          <p className="text-slate-600 mt-0.5">{r.findings}</p>
                          <span className="text-[10px] text-slate-400">{new Date(r.timestamp).toLocaleString()}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Vitals Form & Log */}
            {activeTab === "vitals" && (
              <div className="space-y-6">
                {(currentUser.role === "nurse" || currentUser.role === "doctor") && (
                  <form onSubmit={handleSaveVitals} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
                    <h3 className="text-sm font-bold text-slate-900">Record New Vitals (Nurse / Triage)</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Blood Pressure (mmHg)</label>
                        <input
                          type="text"
                          placeholder="120/80"
                          value={bp}
                          onChange={(e) => setBp(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Pulse (bpm)</label>
                        <input
                          type="number"
                          placeholder="72"
                          value={pulse}
                          onChange={(e) => setPulse(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Temperature (°C)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="37.0"
                          value={temp}
                          onChange={(e) => setTemp(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">SpO₂ (%)</label>
                        <input
                          type="number"
                          placeholder="98"
                          value={spo2}
                          onChange={(e) => setSpo2(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                    </div>
                    <button
                      type="submit"
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold cursor-pointer"
                    >
                      Save Vitals
                    </button>
                  </form>
                )}

                {/* Vitals History Table */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase text-[10px]">
                      <tr>
                        <th className="p-3.5">Timestamp</th>
                        <th className="p-3.5">BP</th>
                        <th className="p-3.5">Pulse</th>
                        <th className="p-3.5">Temp</th>
                        <th className="p-3.5">SpO₂</th>
                        <th className="p-3.5">Recorded By</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {patientData?.vitals?.map((v) => (
                        <tr key={v.id}>
                          <td className="p-3.5 text-slate-500">{new Date(v.timestamp).toLocaleString()}</td>
                          <td className="p-3.5 font-bold">{v.blood_pressure}</td>
                          <td className="p-3.5">{v.pulse} bpm</td>
                          <td className="p-3.5">{v.temperature} °C</td>
                          <td className="p-3.5">{v.spo2}%</td>
                          <td className="p-3.5 font-semibold text-blue-700">{v.recorded_by}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tab 3: Laboratory */}
            {activeTab === "labs" && (
              <div className="space-y-6">
                {(currentUser.role === "lab_tech" || currentUser.role === "doctor") && (
                  <form onSubmit={handleSaveLabs} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
                    <h3 className="text-sm font-bold text-slate-900">Record CBC Laboratory Results</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Hemoglobin (g/dL)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="13.5"
                          value={hb}
                          onChange={(e) => setHb(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">WBC Count (/uL)</label>
                        <input
                          type="number"
                          placeholder="7500"
                          value={wbc}
                          onChange={(e) => setWbc(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">CRP (mg/L or Level)</label>
                        <input
                          type="text"
                          placeholder="Normal / Elevated"
                          value={crp}
                          onChange={(e) => setCrp(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Platelets (/uL)</label>
                        <input
                          type="number"
                          placeholder="250000"
                          value={platelets}
                          onChange={(e) => setPlatelets(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                        />
                      </div>
                    </div>
                    <button
                      type="submit"
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold cursor-pointer"
                    >
                      Save Lab Report
                    </button>
                  </form>
                )}

                <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase text-[10px]">
                      <tr>
                        <th className="p-3.5">Date</th>
                        <th className="p-3.5">Hemoglobin</th>
                        <th className="p-3.5">WBC Count</th>
                        <th className="p-3.5">CRP Marker</th>
                        <th className="p-3.5">Recorded By</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {patientData?.labs?.map((l) => (
                        <tr key={l.id}>
                          <td className="p-3.5 text-slate-500">{new Date(l.timestamp).toLocaleString()}</td>
                          <td className="p-3.5 font-bold">{l.hemoglobin} g/dL</td>
                          <td className="p-3.5">{l.wbc} /uL</td>
                          <td className="p-3.5 font-bold text-amber-700">{l.crp}</td>
                          <td className="p-3.5 font-semibold text-emerald-700">{l.recorded_by}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tab 4: Radiology */}
            {activeTab === "radiology" && (
              <div className="space-y-6">
                {(currentUser.role === "radiologist" || currentUser.role === "doctor") && (
                  <form onSubmit={handleSaveRadiology} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-slate-900">Log Radiology / Imaging Findings</h3>
                      <div>
                        <input
                          type="file"
                          ref={radFileRef}
                          onChange={handlePatientFileUpload}
                          accept=".pdf"
                          className="hidden"
                        />
                        <button
                          type="button"
                          onClick={() => radFileRef.current?.click()}
                          className="px-3 py-1.5 bg-purple-50 text-purple-700 border border-purple-200 rounded-xl text-xs font-bold hover:bg-purple-100 flex items-center space-x-1.5 cursor-pointer"
                        >
                          <Upload className="w-3.5 h-3.5" />
                          <span>Attach Imaging PDF</span>
                        </button>
                      </div>
                    </div>
                    <textarea
                      rows={3}
                      placeholder="e.g. Chest X-Ray demonstrates patchy opacity in right lower lobe consistent with focal pneumonia..."
                      value={radFindings}
                      onChange={(e) => setRadFindings(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs outline-none"
                    />
                    <button
                      type="submit"
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold cursor-pointer"
                    >
                      Save Findings
                    </button>
                  </form>
                )}

                <div className="space-y-3">
                  {patientData?.radiology?.map((r) => (
                    <div key={r.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
                      <div className="flex items-center justify-between text-xs font-bold text-purple-700">
                        <span>Report by {r.recorded_by}</span>
                        <span className="text-slate-400 font-normal">{new Date(r.timestamp).toLocaleString()}</span>
                      </div>
                      <p className="text-xs text-slate-800 leading-relaxed">{r.findings}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 5: Doctor Notes */}
            {activeTab === "notes" && (
              <div className="space-y-6">
                {currentUser.role === "doctor" && (
                  <form onSubmit={handleSaveNote} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
                    <h3 className="text-sm font-bold text-slate-900">Add Clinical Assessment & Plan</h3>
                    <textarea
                      rows={3}
                      placeholder="Assessment: Community acquired pneumonia. Plan: Initiate empirical amoxicillin therapy as per guidelines..."
                      value={noteContent}
                      onChange={(e) => setNoteContent(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs outline-none"
                    />
                    <button
                      type="submit"
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold cursor-pointer"
                    >
                      Save Clinical Note
                    </button>
                  </form>
                )}

                <div className="space-y-3">
                  {patientData?.notes?.map((n) => (
                    <div key={n.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-2">
                      <div className="flex items-center justify-between text-xs font-bold text-blue-700">
                        <span>{n.author}</span>
                        <span className="text-slate-400 font-normal">{new Date(n.timestamp).toLocaleString()}</span>
                      </div>
                      <p className="text-xs text-slate-800 leading-relaxed">{n.notes}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 6: Attached PDFs */}
            {activeTab === "documents" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900">Indexed Patient Documents</h3>
                  <div>
                    <input
                      type="file"
                      ref={radFileRef}
                      onChange={handlePatientFileUpload}
                      accept=".pdf"
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={() => radFileRef.current?.click()}
                      className="px-3 py-1.5 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 flex items-center space-x-1.5 cursor-pointer"
                    >
                      <Upload className="w-3.5 h-3.5" />
                      <span>Attach Document</span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {patientData?.documents?.map((doc) => (
                    <div key={doc.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <FileText className="w-6 h-6 text-blue-600 shrink-0" />
                        <div>
                          <div className="text-xs font-bold text-slate-900">{doc.name}</div>
                          <div className="text-[10px] text-slate-500">{doc.chunk_count} Chunks Indexed</div>
                        </div>
                      </div>
                      <button
                        onClick={() => onSelectDocumentForChat(doc)}
                        className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold text-xs rounded-xl flex items-center space-x-1 cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Query in AI</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-12 text-slate-400 text-xs">
            Select a patient from the left column to view chart.
          </div>
        )}
      </div>
    </div>
  );
};
