import React, { useState, useEffect } from "react";
import { UserPlus, CheckCircle, Edit3, X } from "lucide-react";
import { getApiUrl } from "../api/client";
import type { User } from "../types";
import { DOCTOR_SPECIALTIES } from "../types";

export const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("DOCTOR");
  const [department, setDepartment] = useState("Internal Medicine");
  const [specialty, setSpecialty] = useState<string>("General Medicine");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit Specialty Modal state
  const [editingDoctor, setEditingDoctor] = useState<User | null>(null);
  const [editSpecialtyVal, setEditSpecialtyVal] = useState<string>("General Medicine");

  const fetchUsers = async () => {
    try {
      const res = await fetch(getApiUrl("/api/users"), {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccessMsg(null);

    try {
      const res = await fetch(getApiUrl("/api/users"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({
          username,
          password,
          name,
          role,
          department,
          specialty: role === "DOCTOR" ? specialty : undefined,
          email: email || undefined,
          must_change_password: false,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Created account for ${name} (${role})`);
        setUsername("");
        setPassword("");
        setName("");
        setEmail("");
        setSpecialty("General Medicine");
        fetchUsers();
      } else {
        alert(data.detail || "User creation failed.");
      }
    } catch (e) {
      alert("Error creating user.");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateDoctorSpecialty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingDoctor) return;
    setLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/users/${editingDoctor.id}`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({
          specialty: editSpecialtyVal,
        }),
      });
      if (res.ok) {
        setSuccessMsg(`Updated specialty for Dr. ${editingDoctor.name} to ${editSpecialtyVal}`);
        setEditingDoctor(null);
        fetchUsers();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to update specialty.");
      }
    } catch (e) {
      alert("Error updating specialty.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    const nextStatus = user.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    try {
      const res = await fetch(getApiUrl(`/api/users/${user.id}/status?status=${nextStatus}`), {
        method: "PATCH",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        fetchUsers();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to update user status.");
      }
    } catch (e) {
      alert("Error updating status.");
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (!window.confirm(`Are you sure you want to delete staff account for ${user.name} (@${user.username})? Any active patients assigned to this doctor will be unassigned for reassignment.`)) {
      return;
    }
    try {
      const res = await fetch(getApiUrl(`/api/users/${user.id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        setSuccessMsg(`User ${user.name} deleted successfully.`);
        fetchUsers();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete user.");
      }
    } catch (e) {
      alert("Error deleting user.");
    }
  };

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Hospital Staff RBAC & Identity Management</h1>
          <p className="text-xs text-slate-500">Provision authorized hospital user accounts with explicit clinical role permissions.</p>
        </div>

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-700" />
            {successMsg}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Create User Form */}
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-rose-900" />
              Add Hospital Staff Member
            </h2>

            <form onSubmit={handleCreateUser} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Full Legal Name *</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Dr. Ramesh Gupta"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Username *</label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. ramesh_gupta"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Password *</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Hospital Role *</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                >
                  <option value="DOCTOR">Attending Physician (DOCTOR)</option>
                  <option value="RADIOLOGIST">Radiologist (RADIOLOGIST)</option>
                  <option value="LABORATORY_TECHNICIAN">Laboratory Technician (LABORATORY_TECHNICIAN)</option>
                  <option value="NURSE">Staff Nurse (NURSE)</option>
                  <option value="INTERN">Resident Intern (INTERN)</option>
                  <option value="FRONT_DESK">Front Desk & Registration (FRONT_DESK)</option>
                  <option value="ADMIN">Hospital Administrator (ADMIN)</option>
                  <option value="OTHER_STAFF">Hospital General Staff (OTHER_STAFF)</option>
                </select>
              </div>

              {role === "DOCTOR" && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Doctor Specialty <span className="text-rose-600">*</span>
                  </label>
                  <select
                    value={specialty}
                    onChange={(e) => setSpecialty(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800 font-medium"
                  >
                    {DOCTOR_SPECIALTIES.map((spec) => (
                      <option key={spec} value={spec}>
                        {spec}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Clinical specialization for patient care assignment.
                  </p>
                </div>
              )}

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Department</label>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="e.g. Cardiology"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Institutional Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. ramesh@hospital.org"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3 bg-rose-900 hover:bg-rose-800 text-white font-semibold rounded-xl shadow-md transition disabled:opacity-50"
              >
                {loading ? "Creating Account..." : "Provision Staff Account"}
              </button>
            </form>
          </div>

          {/* User List */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="p-4">Name / Username</th>
                  <th className="p-4">Role</th>
                  <th className="p-4">Department</th>
                  <th className="p-4">Specialty</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-left min-w-[130px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50 transition">
                    <td className="p-4 font-semibold text-slate-900">
                      <div>{u.name}</div>
                      <div className="text-[11px] text-slate-400 font-mono font-normal">@{u.username}</div>
                    </td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-800 border border-slate-200">
                        {u.role}
                      </span>
                    </td>
                    <td className="p-4">{u.department || "General"}</td>
                    <td className="p-4">
                      {u.role === "DOCTOR" ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
                          {u.specialty || "General Medicine"}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic text-[11px]">—</span>
                      )}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                        u.status === "ACTIVE"
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : "bg-rose-50 text-rose-800 border-rose-200"
                      }`}>
                        {u.status}
                      </span>
                    </td>
                    <td className="p-4 text-left">
                      <div className="flex flex-col items-start gap-1.5 whitespace-nowrap">
                        {u.role === "DOCTOR" && (
                          <button
                            type="button"
                            onClick={() => {
                              setEditingDoctor(u);
                              setEditSpecialtyVal(u.specialty || "General Medicine");
                            }}
                            className="text-xs font-semibold text-blue-700 hover:text-blue-900 underline text-left cursor-pointer"
                          >
                            Edit Specialty
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(u)}
                          className={`text-xs font-semibold underline text-left cursor-pointer ${
                            u.status === "ACTIVE" ? "text-amber-700 hover:text-amber-900" : "text-emerald-800 hover:text-emerald-700"
                          }`}
                        >
                          {u.status === "ACTIVE" ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteUser(u)}
                          className="text-xs font-semibold text-rose-700 hover:text-rose-900 underline text-left cursor-pointer"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Edit Specialty Modal */}
        {editingDoctor && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-blue-700" />
                  Edit Doctor Specialty
                </h2>
                <button
                  onClick={() => setEditingDoctor(null)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <p className="text-xs text-slate-600 mb-3">
                Update clinical specialty for <strong>{editingDoctor.name}</strong> (@{editingDoctor.username}):
              </p>

              <form onSubmit={handleUpdateDoctorSpecialty} className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Clinical Specialty</label>
                  <select
                    value={editSpecialtyVal}
                    onChange={(e) => setEditSpecialtyVal(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800 font-medium"
                  >
                    {DOCTOR_SPECIALTIES.map((spec) => (
                      <option key={spec} value={spec}>
                        {spec}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setEditingDoctor(null)}
                    className="py-2 px-3 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="py-2 px-4 bg-blue-700 hover:bg-blue-800 text-white rounded-xl font-semibold shadow transition disabled:opacity-50"
                  >
                    {loading ? "Saving..." : "Save Specialty"}
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
