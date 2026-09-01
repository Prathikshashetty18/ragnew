import React, { useState, useEffect } from "react";
import { 
  Users, UserPlus, Search, Sparkles,
  FileCheck2, CheckCircle2, AlertTriangle,
  PlusCircle
} from "lucide-react";
import type { Patient, UserProfile } from "../types";

interface PatientDashboardProps {
  patients: Patient[];
  onSelectPatient: (patientId: string) => void;
  onLaunchConsultation: (patientId: string, initialQuery?: string) => void;
  onLaunchReport: (patientId: string) => void;
  apiBase: string;
  token: string;
  currentUser: UserProfile;
  onRefreshPatients: () => void;
}

export const PatientDashboard: React.FC<PatientDashboardProps> = ({
  patients,
  onSelectPatient,
  onLaunchConsultation,
  onLaunchReport,
  apiBase,
  token,
  currentUser,
  onRefreshPatients
}) => {
  const [selectedPatientId, setSelectedPatientId] = useState<string>(patients[0]?.id || "");
  const [patientDetails, setPatientDetails] = useState<any>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "vitals" | "labs" | "radiology" | "notes" | "reports">("overview");

  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [regName, setRegName] = useState("");
  const [regAge, setRegAge] = useState<number>(45);
  const [regGender, setRegGender] = useState("Male");
  const [regDob] = useState("1981-05-12");
  const [regBlood, setRegBlood] = useState("O+");
  const [regContact, setRegContact] = useState("+91 98765 43210");
  const [regDept, setRegDept] = useState("Pulmonology");

  const [isAddVitalsOpen, setIsAddVitalsOpen] = useState(false);
  const [bp, setBp] = useState("120/80");
  const [pulse, setPulse] = useState(76);
  const [temp, setTemp] = useState(37.0);
  const [spo2, setSpo2] = useState(98);
  const [vitalsNotes] = useState("");

  const [isAddLabsOpen, setIsAddLabsOpen] = useState(false);
  const [hb, setHb] = useState(13.5);
  const [wbc, setWbc] = useState(7800);
  const [crp, setCrp] = useState("Normal (<5)");
  const [platelets, setPlatelets] = useState(250000);

  const [isAddNoteOpen, setIsAddNoteOpen] = useState(false);
  const [clinicalNoteText, setClinicalNoteText] = useState("");

  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const showNotification = (type: "success" | "error", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const isFrontDesk = currentUser.role === "FRONT_DESK" || currentUser.role === "ADMIN";
  const isDoctor = currentUser.role === "DOCTOR" || currentUser.role === "ADMIN";
  const isNurse = currentUser.role === "NURSE" || isDoctor;

  const fetchPatientProfile = async (id: string) => {
    if (!id) return;
    try {
      const res = await fetch(`${apiBase}/api/patients/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPatientDetails(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (selectedPatientId) {
      fetchPatientProfile(selectedPatientId);
    }
  }, [selectedPatientId, token]);

  const handleRegisterPatient = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${apiBase}/api/patients`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: regName,
          age: Number(regAge),
          gender: regGender,
          dob: regDob,
          blood_group: regBlood,
          contact_details: regContact,
          department: regDept
        })
      });
      if (res.ok) {
        const data = await res.json();
        showNotification("success", `Patient registered! Generated ID: ${data.id}`);
        setIsRegisterModalOpen(false);
        setRegName("");
        onRefreshPatients();
        setSelectedPatientId(data.id);
      } else {
        const err = await res.json();
        showNotification("error", err.detail || "Registration failed.");
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDischarge = async () => {
    if (!selectedPatientId) return;
    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/discharge`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        showNotification("success", "Patient marked as DISCHARGED.");
        onRefreshPatients();
        fetchPatientProfile(selectedPatientId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleArchive = async () => {
    if (!selectedPatientId) return;
    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/archive`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        showNotification("success", "Patient record ARCHIVED.");
        onRefreshPatients();
        fetchPatientProfile(selectedPatientId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddVitals = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/vitals`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ blood_pressure: bp, pulse: Number(pulse), temperature: Number(temp), spo2: Number(spo2), notes: vitalsNotes })
      });
      if (res.ok) {
        showNotification("success", "Vitals recorded successfully.");
        setIsAddVitalsOpen(false);
        fetchPatientProfile(selectedPatientId);
      }
    } catch (e) { console.error(e); }
  };

  const handleAddLabs = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/labs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ hemoglobin: Number(hb), wbc: Number(wbc), crp, platelets: Number(platelets) })
      });
      if (res.ok) {
        showNotification("success", "Lab results recorded.");
        setIsAddLabsOpen(false);
        fetchPatientProfile(selectedPatientId);
      }
    } catch (e) { console.error(e); }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${apiBase}/api/patients/${selectedPatientId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ notes: clinicalNoteText })
      });
      if (res.ok) {
        showNotification("success", "Clinical note saved.");
        setIsAddNoteOpen(false);
        setClinicalNoteText("");
        fetchPatientProfile(selectedPatientId);
      }
    } catch (e) { console.error(e); }
  };

  const filteredPatients = patients.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.department.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 text-slate-800 p-6 md:p-8 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-blue-600 text-xs font-bold uppercase tracking-wider mb-1">
            <Users className="w-4 h-4" />
            <span>Patient Lifecycle & Chart Management</span>
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Hospital Patients Directory
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Front Desk intake, clinical charts, longitudinal vitals & lab timelines.
          </p>
        </div>

        {isFrontDesk && (
          <button
            onClick={() => setIsRegisterModalOpen(true)}
            className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            <span>Register New Patient (Front Desk)</span>
          </button>
        )}
      </div>

      {msg && (
        <div className={`p-4 rounded-xl text-xs font-semibold flex items-center space-x-2 animate-fadeIn ${
          msg.type === "success" ? "bg-emerald-50 border border-emerald-200 text-emerald-700" : "bg-red-50 border border-red-200 text-red-700"
        }`}>
          {msg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
          <span>{msg.text}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs space-y-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search patient, ID, department..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex gap-1.5 overflow-x-auto text-[11px] font-bold">
              {["ALL", "ACTIVE", "DISCHARGED", "ARCHIVED"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1 rounded-lg transition-colors cursor-pointer ${
                    statusFilter === st
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {filteredPatients.map((p) => (
              <div
                key={p.id}
                onClick={() => {
                  setSelectedPatientId(p.id);
                  onSelectPatient(p.id);
                }}
                className={`p-4 rounded-2xl border transition-all cursor-pointer shadow-xs ${
                  selectedPatientId === p.id
                    ? "bg-white border-blue-500 ring-2 ring-blue-100"
                    : "bg-white border-slate-200 hover:border-blue-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-blue-700">{p.id}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    p.status === "ACTIVE" ? "bg-emerald-100 text-emerald-800" :
                    p.status === "DISCHARGED" ? "bg-slate-200 text-slate-700" :
                    "bg-amber-100 text-amber-800"
                  }`}>
                    {p.status}
                  </span>
                </div>
                <div className="font-bold text-sm text-slate-900 mt-1">{p.name}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {p.age} yrs • {p.gender} • {p.department}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-8 space-y-4">
          {patientDetails ? (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-200">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {patientDetails.id}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      patientDetails.status === "ACTIVE" ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"
                    }`}>
                      {patientDetails.status}
                    </span>
                  </div>
                  <h2 className="text-2xl font-black text-slate-900 mt-1">{patientDetails.name}</h2>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {patientDetails.age} yrs • {patientDetails.gender} • Blood Group: <strong>{patientDetails.blood_group || "Unknown"}</strong> • Dept: {patientDetails.department}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => onLaunchConsultation(patientDetails.id, `Clinical review and treatment guidelines for ${patientDetails.name}`)}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-md shadow-blue-500/20 cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Consult AI</span>
                  </button>

                  {isDoctor && (
                    <button
                      onClick={() => onLaunchReport(patientDetails.id)}
                      className="flex items-center space-x-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold shadow-md shadow-purple-500/20 cursor-pointer"
                    >
                      <FileCheck2 className="w-3.5 h-3.5" />
                      <span>Draft AI Report</span>
                    </button>
                  )}

                  {isFrontDesk && patientDetails.status === "ACTIVE" && (
                    <button
                      onClick={handleDischarge}
                      className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold cursor-pointer"
                    >
                      Discharge
                    </button>
                  )}

                  {isFrontDesk && patientDetails.status === "DISCHARGED" && (
                    <button
                      onClick={handleArchive}
                      className="px-3 py-2 bg-amber-50 hover:bg-amber-100 text-amber-800 rounded-xl text-xs font-bold cursor-pointer"
                    >
                      Archive Chart
                    </button>
                  )}
                </div>
              </div>

              <div className="flex gap-2 border-b border-slate-200 pb-2 text-xs font-bold overflow-x-auto">
                {[
                  { id: "overview", label: "Overview & Demographics" },
                  { id: "vitals", label: `Vitals (${patientDetails.vitals?.length || 0})` },
                  { id: "labs", label: `CBC Labs (${patientDetails.labs?.length || 0})` },
                  { id: "radiology", label: `Radiology (${patientDetails.radiology?.length || 0})` },
                  { id: "notes", label: `Doctor Notes (${patientDetails.notes?.length || 0})` },
                  { id: "reports", label: `Official Reports (${patientDetails.reports?.length || 0})` }
                ].map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setActiveTab(t.id as any)}
                    className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer shrink-0 ${
                      activeTab === t.id
                        ? "bg-blue-600 text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {activeTab === "overview" && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-400 font-bold uppercase text-[10px] block">Date of Birth</span>
                    <span className="font-bold text-slate-800">{patientDetails.dob || "—"}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-400 font-bold uppercase text-[10px] block">Contact Details</span>
                    <span className="font-bold text-slate-800">{patientDetails.contact_details || "—"}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-400 font-bold uppercase text-[10px] block">Assigned Doctor</span>
                    <span className="font-bold text-blue-700">{patientDetails.assigned_doctor || "Unassigned"}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-400 font-bold uppercase text-[10px] block">Admission Date</span>
                    <span className="font-medium text-slate-700">{new Date(patientDetails.admission_date).toLocaleDateString()}</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-400 font-bold uppercase text-[10px] block">Discharge Date</span>
                    <span className="font-medium text-slate-700">{patientDetails.discharge_date ? new Date(patientDetails.discharge_date).toLocaleDateString() : "Still Admitted"}</span>
                  </div>
                </div>
              )}

              {activeTab === "vitals" && (
                <div className="space-y-4">
                  {isNurse && (
                    <div className="flex justify-end">
                      <button
                        onClick={() => setIsAddVitalsOpen(true)}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold cursor-pointer"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        <span>Record Vitals</span>
                      </button>
                    </div>
                  )}

                  <div className="space-y-2">
                    {patientDetails.vitals?.length === 0 ? (
                      <div className="text-xs text-slate-400 text-center py-6">No vitals recorded.</div>
                    ) : (
                      patientDetails.vitals?.map((v: any) => (
                        <div key={v.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex justify-between items-center">
                          <div>
                            <span className="font-bold text-slate-800">BP: {v.blood_pressure} mmHg • Pulse: {v.pulse} bpm • Temp: {v.temperature} C • SpO2: {v.spo2}%</span>
                            <div className="text-[10px] text-slate-500 mt-0.5">Recorded by {v.recorded_by} • {new Date(v.timestamp).toLocaleString()}</div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {activeTab === "labs" && (
                <div className="space-y-4">
                  {isDoctor && (
                    <div className="flex justify-end">
                      <button
                        onClick={() => setIsAddLabsOpen(true)}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold cursor-pointer"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        <span>Record Lab Results</span>
                      </button>
                    </div>
                  )}

                  <div className="space-y-2">
                    {patientDetails.labs?.length === 0 ? (
                      <div className="text-xs text-slate-400 text-center py-6">No laboratory records found.</div>
                    ) : (
                      patientDetails.labs?.map((l: any) => (
                        <div key={l.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex justify-between items-center">
                          <div>
                            <span className="font-bold text-slate-800">Hb: {l.hemoglobin} g/dL • WBC: {l.wbc} /uL • CRP: {l.crp} • Platelets: {l.platelets}</span>
                            <div className="text-[10px] text-slate-500 mt-0.5">Recorded by {l.recorded_by} • {new Date(l.timestamp).toLocaleString()}</div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {activeTab === "notes" && (
                <div className="space-y-4">
                  {isDoctor && (
                    <div className="flex justify-end">
                      <button
                        onClick={() => setIsAddNoteOpen(true)}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold cursor-pointer"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        <span>Add Clinical Note</span>
                      </button>
                    </div>
                  )}

                  <div className="space-y-2">
                    {patientDetails.notes?.length === 0 ? (
                      <div className="text-xs text-slate-400 text-center py-6">No clinical notes recorded.</div>
                    ) : (
                      patientDetails.notes?.map((n: any) => (
                        <div key={n.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1">
                          <div className="font-bold text-blue-700">{n.author} ({new Date(n.timestamp).toLocaleString()})</div>
                          <p className="text-slate-800">{n.notes}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {activeTab === "reports" && (
                <div className="space-y-2">
                  {patientDetails.reports?.length === 0 ? (
                    <div className="text-xs text-slate-400 text-center py-6">No clinical reports filed.</div>
                  ) : (
                    patientDetails.reports?.map((r: any) => (
                      <div key={r.id} className="p-3 bg-purple-50/40 rounded-xl border border-purple-200 text-xs flex justify-between items-center">
                        <div>
                          <div className="font-bold text-slate-900">{r.title}</div>
                          <div className="text-[10px] text-slate-500">{r.doctor_name} • {new Date(r.created_at).toLocaleString()}</div>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          r.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                        }`}>
                          {r.status}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-xs text-slate-400">
              Select a patient from the left to view clinical chart.
            </div>
          )}
        </div>
      </div>

      {isRegisterModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white max-w-lg w-full rounded-2xl p-6 md:p-8 space-y-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h2 className="text-lg font-black text-slate-900">Front Desk: Register Patient</h2>
              <button onClick={() => setIsRegisterModalOpen(false)} className="text-slate-400 hover:text-slate-600">&times;</button>
            </div>

            <form onSubmit={handleRegisterPatient} className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Patient Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Robert Johnson"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Age</label>
                  <input
                    type="number"
                    required
                    value={regAge}
                    onChange={(e) => setRegAge(Number(e.target.value))}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Gender</label>
                  <select
                    value={regGender}
                    onChange={(e) => setRegGender(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Blood Group</label>
                  <select
                    value={regBlood}
                    onChange={(e) => setRegBlood(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                  >
                    <option value="O+">O+</option>
                    <option value="O-">O-</option>
                    <option value="A+">A+</option>
                    <option value="A-">A-</option>
                    <option value="B+">B+</option>
                    <option value="B-">B-</option>
                    <option value="AB+">AB+</option>
                    <option value="AB-">AB-</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Contact Phone</label>
                  <input
                    type="text"
                    value={regContact}
                    onChange={(e) => setRegContact(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Department</label>
                  <select
                    value={regDept}
                    onChange={(e) => setRegDept(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs"
                  >
                    <option value="Pulmonology">Pulmonology</option>
                    <option value="Cardiology">Cardiology</option>
                    <option value="Infectious Disease">Infectious Disease</option>
                    <option value="General Medicine">General Medicine</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setIsRegisterModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl font-bold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-blue-600 text-white rounded-xl font-bold shadow-md shadow-blue-500/20"
                >
                  Register & Assign ID
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isAddVitalsOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white max-w-md w-full rounded-2xl p-6 space-y-4 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Record Patient Vitals</h2>
            <form onSubmit={handleAddVitals} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">BP (mmHg)</label>
                  <input type="text" value={bp} onChange={(e) => setBp(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Pulse (bpm)</label>
                  <input type="number" value={pulse} onChange={(e) => setPulse(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Temp (C)</label>
                  <input type="number" step="0.1" value={temp} onChange={(e) => setTemp(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">SpO2 (%)</label>
                  <input type="number" value={spo2} onChange={(e) => setSpo2(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsAddVitalsOpen(false)} className="px-3 py-1.5 bg-slate-100 rounded-xl font-bold">Cancel</button>
                <button type="submit" className="px-4 py-1.5 bg-blue-600 text-white rounded-xl font-bold">Save Vitals</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isAddLabsOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white max-w-md w-full rounded-2xl p-6 space-y-4 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Record CBC & Lab Results</h2>
            <form onSubmit={handleAddLabs} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Hemoglobin (g/dL)</label>
                  <input type="number" step="0.1" value={hb} onChange={(e) => setHb(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">WBC Count (/uL)</label>
                  <input type="number" value={wbc} onChange={(e) => setWbc(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">CRP (mg/L)</label>
                  <input type="text" value={crp} onChange={(e) => setCrp(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Platelets (/uL)</label>
                  <input type="number" value={platelets} onChange={(e) => setPlatelets(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2" />
                </div>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsAddLabsOpen(false)} className="px-3 py-1.5 bg-slate-100 rounded-xl font-bold">Cancel</button>
                <button type="submit" className="px-4 py-1.5 bg-blue-600 text-white rounded-xl font-bold">Save Labs</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isAddNoteOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white max-w-md w-full rounded-2xl p-6 space-y-4 shadow-2xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Add Clinical Assessment Note</h2>
            <form onSubmit={handleAddNote} className="space-y-3 text-xs">
              <textarea
                rows={4}
                required
                placeholder="Enter clinical observations, differential diagnosis, or therapy changes..."
                value={clinicalNoteText}
                onChange={(e) => setClinicalNoteText(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs outline-none"
              />
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsAddNoteOpen(false)} className="px-3 py-1.5 bg-slate-100 rounded-xl font-bold">Cancel</button>
                <button type="submit" className="px-4 py-1.5 bg-blue-600 text-white rounded-xl font-bold">Save Note</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
