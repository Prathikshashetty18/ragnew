import React, { useState, useEffect } from "react";
import { Activity, UserPlus, CheckCircle, UserCheck, Stethoscope, RefreshCw, HeartPulse, PlusCircle, Clock, X, Trash2 } from "lucide-react";
import { getApiUrl } from "../api/client";
import type { Patient, User, PatientVitals } from "../types";
import { DOCTOR_SPECIALTIES } from "../types";

interface DoctorOption {
  id: number;
  name: string;
  role?: string;
  department: string;
  specialty?: string;
  employee_id?: string;
}

interface PatientDashboardProps {
  patients: Patient[];
  currentUser: User;
  onSelectPatientForChat: (patientId: string) => void;
  onRefreshPatients: () => void;
}

export const formatPainSeverity = (severity?: string | null): string => {
  switch (severity) {
    case "NO_PAIN": return "No Pain";
    case "MILD": return "Mild";
    case "MODERATE": return "Moderate";
    case "SEVERE": return "Severe";
    default: return "—";
  }
};

export const PatientDashboard: React.FC<PatientDashboardProps> = ({
  patients,
  currentUser,
  onSelectPatientForChat,
  onRefreshPatients,
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [reassignPatient, setReassignPatient] = useState<Patient | null>(null);
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("");
  const [doctors, setDoctors] = useState<DoctorOption[]>([]);
  const [intakeSpecialtyFilter, setIntakeSpecialtyFilter] = useState<string>("");
  const [reassignSpecialtyFilter, setReassignSpecialtyFilter] = useState<string>("");
  
  // Filtered doctor lists for intake and reassignment
  const filteredIntakeDoctors = intakeSpecialtyFilter
    ? doctors.filter((d) => (d.specialty || "General Medicine") === intakeSpecialtyFilter)
    : doctors;

  const filteredReassignDoctors = reassignSpecialtyFilter
    ? doctors.filter((d) => (d.specialty || "General Medicine") === reassignSpecialtyFilter)
    : doctors;
  
  // Vitals Management States
  const [vitalsPatient, setVitalsPatient] = useState<Patient | null>(null);
  const [patientVitalsList, setPatientVitalsList] = useState<PatientVitals[]>([]);
  const [loadingVitals, setLoadingVitals] = useState(false);
  const [showRecordVitalsForm, setShowRecordVitalsForm] = useState(false);
  
  // Structured Vitals Form Fields
  const [vBp, setVBp] = useState("");
  const [vPulse, setVPulse] = useState("");
  const [vRr, setVRr] = useState("");
  const [vTemp, setVTemp] = useState("");
  const [vSpo2, setVSpo2] = useState("");
  const [vGlucose, setVGlucose] = useState("");
  const [vPainSeverity, setVPainSeverity] = useState("");
  const [vIntakeOutput, setVIntakeOutput] = useState("");
  const [vNotes, setVNotes] = useState("");
  
  // Intake Form States
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("Male");
  const [bloodGroup, setBloodGroup] = useState("O+");
  const [department, setDepartment] = useState("Internal Medicine");
  const [contact, setContact] = useState("");
  const [assignedDoctorId, setAssignedDoctorId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const isFrontDesk = currentUser.role === "FRONT_DESK";
  const isDoctor = currentUser.role === "DOCTOR" || currentUser.role === "INTERN";
  const canRecordVitals = currentUser.role === "NURSE" || currentUser.role === "DOCTOR" || currentUser.role === "ADMIN";

  // Fetch active doctors for assignment dropdowns
  const fetchDoctors = async () => {
    try {
      const res = await fetch(getApiUrl("/api/doctors"), {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setDoctors(data);
      }
    } catch (e) {
      console.error("Failed to fetch doctors list:", e);
    }
  };

  const fetchPatientVitals = async (patientId: string) => {
    setLoadingVitals(true);
    try {
      const res = await fetch(getApiUrl(`/api/patients/${patientId}/vitals`), {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setPatientVitalsList(data);
      }
    } catch (e) {
      console.error("Failed to fetch vitals:", e);
    } finally {
      setLoadingVitals(false);
    }
  };

  const handleOpenVitalsModal = (p: Patient) => {
    setVitalsPatient(p);
    setShowRecordVitalsForm(false);
    fetchPatientVitals(p.id);
  };

  const handleRecordVitals = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vitalsPatient) return;

    if (vPainSeverity.trim()) {
      const allowed = ["NO_PAIN", "MILD", "MODERATE", "SEVERE"];
      if (!allowed.includes(vPainSeverity.trim())) {
        alert("Invalid pain severity value.");
        return;
      }
    }

    setLoading(true);

    try {
      const payload: any = {};
      if (vBp.trim()) payload.blood_pressure = vBp.trim();
      if (vPulse.trim()) payload.pulse = parseInt(vPulse);
      if (vRr.trim()) payload.respiratory_rate = parseInt(vRr);
      if (vTemp.trim()) payload.temperature = parseFloat(vTemp);
      if (vSpo2.trim()) payload.spo2 = parseInt(vSpo2);
      if (vGlucose.trim()) payload.blood_glucose = parseFloat(vGlucose);
      if (vPainSeverity.trim()) payload.pain_severity = vPainSeverity.trim();
      if (vIntakeOutput.trim()) payload.intake_output = vIntakeOutput.trim();
      if (vNotes.trim()) payload.notes = vNotes.trim();

      const res = await fetch(getApiUrl(`/api/patients/${vitalsPatient.id}/vitals`), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Vitals recorded for patient ${vitalsPatient.name}`);
        setVBp("");
        setVPulse("");
        setVRr("");
        setVTemp("");
        setVSpo2("");
        setVGlucose("");
        setVPainSeverity("");
        setVIntakeOutput("");
        setVNotes("");
        setShowRecordVitalsForm(false);
        fetchPatientVitals(vitalsPatient.id);
      } else {
        alert(data.detail || "Failed to record vitals.");
      }
    } catch (e) {
      alert("Error submitting vitals.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVitals = async (vitalsId: number) => {
    if (!vitalsPatient) return;
    if (!window.confirm("Are you sure you want to delete this vitals record?")) return;
    try {
      const res = await fetch(getApiUrl(`/api/patients/${vitalsPatient.id}/vitals/${vitalsId}`), {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
      if (res.ok) {
        setPatientVitalsList((prev) => prev.filter((item) => item.id !== vitalsId));
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete vitals record.");
      }
    } catch (e) {
      console.error("Failed to delete vitals record:", e);
      alert("Failed to delete vitals record.");
    }
  };

  useEffect(() => {
    fetchDoctors();
  }, []);

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccessMsg(null);

    try {
      const payload: any = {
        name,
        age: parseInt(age),
        gender,
        blood_group: bloodGroup,
        department,
        contact_details: contact,
      };

      if (assignedDoctorId) {
        payload.assigned_doctor_id = parseInt(assignedDoctorId);
      }

      const res = await fetch(getApiUrl("/api/patients"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Patient registered with ID: ${data.id}`);
        setShowAddModal(false);
        setName("");
        setAge("");
        setContact("");
        setAssignedDoctorId("");
        setIntakeSpecialtyFilter("");
        onRefreshPatients();
      } else {
        alert(data.detail || "Patient registration failed.");
      }
    } catch (e) {
      alert("Error registering patient.");
    } finally {
      setLoading(false);
    }
  };

  const handleReassignDoctor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reassignPatient || !selectedDoctorId) return;

    setLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/patients/${reassignPatient.id}`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({
          assigned_doctor_id: parseInt(selectedDoctorId),
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Patient ${reassignPatient.name} re-assigned to new attending physician.`);
        setReassignPatient(null);
        setSelectedDoctorId("");
        setReassignSpecialtyFilter("");
        onRefreshPatients();
      } else {
        alert(data.detail || "Re-assignment failed.");
      }
    } catch (e) {
      alert("Error re-assigning doctor.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePatient = async (patient: Patient) => {
    if (!window.confirm(`Are you sure you want to delete patient record for ${patient.name} (${patient.id})? This will unindex their clinical documents and remove them from active directories.`)) {
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/patients/${patient.id}`), {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Patient ${patient.name} deleted successfully.`);
        onRefreshPatients();
      } else {
        alert(data.detail || "Failed to delete patient.");
      }
    } catch (err) {
      alert("Error deleting patient.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Patient Directory & Longitudinal Charts</h1>
            <p className="text-xs text-slate-500">
              {isDoctor
                ? "Attending Physician Portal: Displaying only your assigned patients under strict clinical isolation."
                : "Manage inpatient admissions, assign attending physicians, and access longitudinal clinical timelines."}
            </p>
          </div>

          {isFrontDesk && (
            <button
              onClick={() => setShowAddModal(true)}
              className="py-2.5 px-4 bg-rose-900 hover:bg-rose-800 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-sm transition"
            >
              <UserPlus className="w-4 h-4" />
              <span>Register New Patient</span>
            </button>
          )}
        </div>

        {isDoctor && (
          <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900 font-semibold flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Stethoscope className="w-4 h-4 text-blue-700" />
              <span>Assigned Clinician Filter Active: Showing {patients.length} patient(s) assigned to Dr. {currentUser.name}.</span>
            </div>
            <span className="text-[10px] bg-blue-100 px-2 py-0.5 rounded font-mono">ROLE: {currentUser.role}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {successMsg}
          </div>
        )}

        {/* Patient Cards Grid */}
        {patients.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400">
            <Stethoscope className="w-10 h-10 mx-auto mb-3 opacity-40 text-slate-400" />
            <h3 className="text-sm font-bold text-slate-700">No Patients Found</h3>
            <p className="text-xs text-slate-500 mt-1">
              {isDoctor
                ? "You currently have no assigned patients in your clinical care list."
                : "No patient records match the current filter."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {patients.map((p) => (
              <div
                key={p.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md hover:border-rose-300 transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{p.name}</h3>
                      <p className="text-[11px] text-slate-500 font-mono font-medium">{p.id}</p>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      p.status === "ACTIVE"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : p.status === "DISCHARGED"
                        ? "bg-slate-100 text-slate-700 border-slate-200"
                        : "bg-amber-50 text-amber-800 border-amber-200"
                    }`}>
                      {p.status}
                    </span>
                  </div>

                  {/* Assigned Doctor Badge */}
                  <div className="mb-3 flex items-center justify-between bg-rose-50/70 border border-rose-100 text-rose-950 px-2.5 py-1.5 rounded-lg text-xs">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <UserCheck className="w-3.5 h-3.5 text-rose-800 shrink-0" />
                      <span className="text-[11px] font-medium truncate">
                        Attending: <strong>{p.assigned_doctor ? `Dr. ${p.assigned_doctor}` : "Unassigned"}</strong>
                      </span>
                    </div>
                    {p.assigned_doctor_specialty && (
                      <span className="ml-2 shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-900 border border-blue-200">
                        {p.assigned_doctor_specialty}
                      </span>
                    )}
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4">
                    <div className="flex justify-between">
                      <span>Age / Gender:</span>
                      <strong className="text-slate-800">{p.age} yrs / {p.gender}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Blood Group:</span>
                      <strong className="text-slate-800">{p.blood_group || "Unknown"}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Department:</span>
                      <strong className="text-slate-800">{p.department}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Status:</span>
                      <strong className="text-slate-800">{p.health_status}</strong>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex flex-col gap-2">
                  <button
                    onClick={() => onSelectPatientForChat(p.id)}
                    className="w-full py-2 px-3 bg-rose-50 hover:bg-rose-900 hover:text-white text-rose-900 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                  >
                    <Activity className="w-3.5 h-3.5" />
                    <span>Consult Patient AI</span>
                  </button>

                  <button
                    onClick={() => handleOpenVitalsModal(p)}
                    className="w-full py-1.5 px-3 bg-emerald-50 hover:bg-emerald-800 hover:text-white text-emerald-900 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                  >
                    <HeartPulse className="w-3.5 h-3.5 text-emerald-700" />
                    <span>Vitals & Nursing Chart</span>
                  </button>

                  {isFrontDesk && (
                    <button
                      onClick={() => {
                        setReassignPatient(p);
                        setSelectedDoctorId(p.assigned_doctor_id ? String(p.assigned_doctor_id) : "");
                      }}
                      className="w-full py-1.5 px-2.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1 transition"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Re-assign Doctor</span>
                    </button>
                  )}

                  {(isFrontDesk || currentUser.role === "ADMIN") && (
                    <button
                      onClick={() => handleDeletePatient(p)}
                      className="w-full py-1.5 px-2.5 text-rose-700 hover:text-rose-900 hover:bg-rose-50 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1 transition"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Delete Patient</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Modal for Front Desk Registering New Patient */}
        {showAddModal && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
              <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-rose-900" />
                Hospital Patient Intake (Front Desk)
              </h2>

              <form onSubmit={handleCreatePatient} className="space-y-3.5 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Full Legal Name *</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Ramesh Kulkarni"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Age (Years) *</label>
                    <input
                      type="number"
                      required
                      value={age}
                      onChange={(e) => setAge(e.target.value)}
                      placeholder="e.g. 52"
                      className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Gender *</label>
                    <select
                      value={gender}
                      onChange={(e) => setGender(e.target.value)}
                      className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                    >
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Blood Group</label>
                    <select
                      value={bloodGroup}
                      onChange={(e) => setBloodGroup(e.target.value)}
                      className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
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
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Patient Department (Ward/Unit)</label>
                    <input
                      type="text"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                      placeholder="e.g. Pulmonology"
                      className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                    />
                  </div>
                </div>

                {/* Assigned Doctor Dropdown with Specialty Filtering */}
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Filter Doctors by Specialty</label>
                    <select
                      value={intakeSpecialtyFilter}
                      onChange={(e) => {
                        setIntakeSpecialtyFilter(e.target.value);
                        setAssignedDoctorId("");
                      }}
                      className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800 font-medium"
                    >
                      <option value="">All Specialties ({doctors.length} Doctors Available)</option>
                      {DOCTOR_SPECIALTIES.map((spec) => {
                        const count = doctors.filter((d) => (d.specialty || "General Medicine") === spec).length;
                        return (
                          <option key={spec} value={spec}>
                            {spec} ({count})
                          </option>
                        );
                      })}
                    </select>
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Assign Attending Physician</label>
                    <select
                      value={assignedDoctorId}
                      onChange={(e) => setAssignedDoctorId(e.target.value)}
                      className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800 font-medium"
                    >
                      <option value="">-- Select Doctor (or assign later) --</option>
                      {filteredIntakeDoctors.map((d) => (
                        <option key={d.id} value={d.id}>
                          Dr. {d.name} — {d.specialty || "General Medicine"} ({d.department})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Contact & Address</label>
                  <input
                    type="text"
                    value={contact}
                    onChange={(e) => setContact(e.target.value)}
                    placeholder="e.g. +91 98450 12345, Bangalore"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="py-2.5 px-4 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="py-2.5 px-5 bg-rose-900 hover:bg-rose-800 text-white rounded-xl font-semibold shadow-md disabled:opacity-50"
                  >
                    {loading ? "Registering..." : "Complete Intake"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal for Front Desk Re-assigning Doctor */}
        {reassignPatient && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
              <h2 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-rose-900" />
                Re-assign Attending Physician
              </h2>
              <p className="text-xs text-slate-500 mb-4">
                Update clinical assignment for <strong>{reassignPatient.name}</strong> ({reassignPatient.id}).
              </p>

              <form onSubmit={handleReassignDoctor} className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Filter Doctors by Specialty</label>
                  <select
                    value={reassignSpecialtyFilter}
                    onChange={(e) => {
                      setReassignSpecialtyFilter(e.target.value);
                      setSelectedDoctorId("");
                    }}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800 font-medium"
                  >
                    <option value="">All Specialties ({doctors.length} Doctors Available)</option>
                    {DOCTOR_SPECIALTIES.map((spec) => {
                      const count = doctors.filter((d) => (d.specialty || "General Medicine") === spec).length;
                      return (
                        <option key={spec} value={spec}>
                          {spec} ({count})
                        </option>
                      );
                    })}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Select New Attending Doctor *</label>
                  <select
                    required
                    value={selectedDoctorId}
                    onChange={(e) => setSelectedDoctorId(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800 font-medium"
                  >
                    <option value="">-- Select Doctor --</option>
                    {filteredReassignDoctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        Dr. {d.name} — {d.specialty || "General Medicine"} ({d.department})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setReassignPatient(null)}
                    className="py-2.5 px-4 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading || !selectedDoctorId}
                    className="py-2.5 px-5 bg-rose-900 hover:bg-rose-800 text-white rounded-xl font-semibold shadow-md disabled:opacity-50"
                  >
                    {loading ? "Re-assigning..." : "Update Assignment"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal for Patient Vitals Monitoring & Recording */}
        {vitalsPatient && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 max-h-[90vh] flex flex-col">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center">
                    <HeartPulse className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900">
                      Nursing Vitals & Physiological Chart
                    </h2>
                    <p className="text-xs text-slate-500 font-mono">
                      Patient: <strong>{vitalsPatient.name}</strong> ({vitalsPatient.id})
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setVitalsPatient(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex items-center justify-between pt-3 pb-2">
                <span className="text-xs font-semibold text-slate-700">
                  {showRecordVitalsForm ? "New Vitals Entry" : `Recorded Observations (${patientVitalsList.length})`}
                </span>
                {canRecordVitals && (
                  <button
                    onClick={() => setShowRecordVitalsForm(!showRecordVitalsForm)}
                    className="py-1 px-3 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
                  >
                    {showRecordVitalsForm ? <Clock className="w-3.5 h-3.5" /> : <PlusCircle className="w-3.5 h-3.5" />}
                    <span>{showRecordVitalsForm ? "View Timeline" : "Record New Vitals"}</span>
                  </button>
                )}
              </div>

              <div className="flex-1 overflow-y-auto space-y-4 py-2">
                {showRecordVitalsForm ? (
                  <form onSubmit={handleRecordVitals} className="space-y-3.5 text-xs bg-slate-50 p-4 rounded-xl border border-slate-200">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Blood Pressure</label>
                        <input
                          type="text"
                          placeholder="e.g. 120/80"
                          value={vBp}
                          onChange={(e) => setVBp(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Heart Rate (bpm)</label>
                        <input
                          type="number"
                          placeholder="e.g. 74"
                          value={vPulse}
                          onChange={(e) => setVPulse(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Resp. Rate (/min)</label>
                        <input
                          type="number"
                          placeholder="e.g. 16"
                          value={vRr}
                          onChange={(e) => setVRr(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">SpO2 (%)</label>
                        <input
                          type="number"
                          placeholder="e.g. 98"
                          value={vSpo2}
                          onChange={(e) => setVSpo2(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Temperature (°C)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="e.g. 36.8"
                          value={vTemp}
                          onChange={(e) => setVTemp(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Blood Glucose (mg/dL)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="e.g. 105.0"
                          value={vGlucose}
                          onChange={(e) => setVGlucose(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Pain Severity</label>
                        <select
                          value={vPainSeverity}
                          onChange={(e) => setVPainSeverity(e.target.value)}
                          className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700 text-sm"
                        >
                          <option value="">Select pain severity</option>
                          <option value="NO_PAIN">No Pain</option>
                          <option value="MILD">Mild</option>
                          <option value="MODERATE">Moderate</option>
                          <option value="SEVERE">Severe</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Intake / Output</label>
                      <input
                        type="text"
                        placeholder="e.g. Intake: 1500ml, Output: 1400ml"
                        value={vIntakeOutput}
                        onChange={(e) => setVIntakeOutput(e.target.value)}
                        className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                      />
                    </div>

                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Nursing Observations & Clinical Notes</label>
                      <textarea
                        rows={2}
                        placeholder="e.g. Patient resting comfortably, hemodynamically stable on room air."
                        value={vNotes}
                        onChange={(e) => setVNotes(e.target.value)}
                        className="w-full p-2 bg-white border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                      />
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setShowRecordVitalsForm(false)}
                        className="py-2 px-3 rounded-lg border border-slate-200 text-slate-700 hover:bg-white font-semibold"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={loading}
                        className="py-2 px-4 bg-emerald-800 hover:bg-emerald-900 text-white rounded-lg font-semibold shadow-sm disabled:opacity-50"
                      >
                        {loading ? "Saving..." : "Commit Vitals Record"}
                      </button>
                    </div>
                  </form>
                ) : loadingVitals ? (
                  <div className="text-center py-8 text-xs text-slate-400">Loading physiological history...</div>
                ) : patientVitalsList.length === 0 ? (
                  <div className="text-center py-8 bg-slate-50 rounded-xl border border-slate-100 text-xs text-slate-500">
                    No vitals recorded for this patient yet.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {patientVitalsList.map((v) => (
                      <div key={v.id} className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-2">
                        <div className="flex items-center justify-between text-slate-500 text-[11px] pb-1.5 border-b border-slate-200">
                          <span className="font-semibold text-slate-800">Recorded by: {v.recorded_by || "Nursing Staff"}</span>
                          <div className="flex items-center gap-2">
                            <span className="font-mono">{v.timestamp ? new Date(v.timestamp).toLocaleString() : "Recent"}</span>
                            {(currentUser.role === "NURSE" || currentUser.role === "ADMIN") && (
                              <button
                                onClick={() => handleDeleteVitals(v.id)}
                                title="Delete Vitals Record"
                                className="text-slate-400 hover:text-red-600 hover:bg-red-50 p-1 rounded transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Blood Pressure</span>
                            <strong className="text-slate-800">{v.blood_pressure || "—"} mmHg</strong>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Heart Rate</span>
                            <strong className="text-slate-800">{v.pulse ? `${v.pulse} bpm` : "—"}</strong>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Resp. Rate</span>
                            <strong className="text-slate-800">{v.respiratory_rate ? `${v.respiratory_rate} /min` : "—"}</strong>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">SpO2</span>
                            <strong className="text-slate-800">{v.spo2 ? `${v.spo2}%` : "—"}</strong>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Temperature</span>
                            <strong className="text-slate-800">{v.temperature ? `${v.temperature} °C` : "—"}</strong>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Blood Glucose</span>
                            <strong className="text-slate-800">{v.blood_glucose ? `${v.blood_glucose} mg/dL` : "—"}</strong>
                          </div>
                          <div className="bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Pain Severity</span>
                            <strong className="text-slate-800">{formatPainSeverity(v.pain_severity)}</strong>
                          </div>
                        </div>
                        {v.intake_output && (
                          <div className="bg-white p-2 rounded-lg border border-slate-100 text-[11px]">
                            <span className="text-slate-400 block text-[10px]">Intake / Output</span>
                            <span className="text-slate-800 font-medium">{v.intake_output}</span>
                          </div>
                        )}
                        {v.notes && (
                          <div className="text-[11px] text-slate-600 bg-white p-2 rounded-lg border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Notes</span>
                            <span>{v.notes}</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
