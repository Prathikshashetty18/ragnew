import React, { useState } from "react";
import { Activity, UserPlus, CheckCircle } from "lucide-react";
import type { Patient, User } from "../types";

interface PatientDashboardProps {
  patients: Patient[];
  currentUser: User;
  onSelectPatientForChat: (patientId: string) => void;
  onRefreshPatients: () => void;
}

export const PatientDashboard: React.FC<PatientDashboardProps> = ({
  patients,
  currentUser,
  onSelectPatientForChat,
  onRefreshPatients,
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("Male");
  const [bloodGroup, setBloodGroup] = useState("O+");
  const [department, setDepartment] = useState("Internal Medicine");
  const [contact, setContact] = useState("");
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const canRegister = ["ADMIN", "FRONT_DESK"].includes(currentUser.role);

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccessMsg(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/patients", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({
          name,
          age: parseInt(age),
          gender,
          blood_group: bloodGroup,
          department,
          contact_details: contact,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Patient registered with ID: ${data.id}`);
        setShowAddModal(false);
        setName("");
        setAge("");
        setContact("");
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

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Patient Directory & Longitudinal Charts</h1>
            <p className="text-xs text-slate-500">Manage inpatient admissions, access timeline records, and trigger patient-specific AI consultations.</p>
          </div>

          {canRegister && (
            <button
              onClick={() => setShowAddModal(true)}
              className="py-2.5 px-4 bg-rose-900 hover:bg-rose-800 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-sm transition"
            >
              <UserPlus className="w-4 h-4" />
              <span>Register New Patient</span>
            </button>
          )}
        </div>

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {successMsg}
          </div>
        )}

        {/* Patient Cards Grid */}
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

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                <button
                  onClick={() => onSelectPatientForChat(p.id)}
                  className="w-full py-2 px-3 bg-rose-50 hover:bg-rose-900 hover:text-white text-rose-900 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                >
                  <Activity className="w-3.5 h-3.5" />
                  <span>Consult Patient AI</span>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Modal for Registering New Patient */}
        {showAddModal && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
              <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-rose-900" />
                Hospital Patient Intake
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
                    <label className="block font-semibold text-slate-700 mb-1">Department</label>
                    <input
                      type="text"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                      placeholder="e.g. Pulmonology"
                      className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                    />
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
      </div>
    </div>
  );
};
