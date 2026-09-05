import React from "react";
import { Activity, Users, BookOpen, ArrowRight, ShieldCheck } from "lucide-react";
import type { User, Patient } from "../types";

interface DashboardHomeProps {
  currentUser: User;
  patients: Patient[];
  setActiveView: (view: string) => void;
  onSelectPatientForChat: (patientId: string) => void;
}

export const DashboardHome: React.FC<DashboardHomeProps> = ({
  currentUser,
  patients,
  setActiveView,
  onSelectPatientForChat,
}) => {
  return (
    <div className="flex-1 h-screen overflow-y-auto bg-slate-50 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Welcome Header */}
        <div className="p-8 rounded-2xl bg-gradient-to-r from-rose-950 via-rose-900 to-rose-800 text-white shadow-lg relative overflow-hidden">
          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-2 text-rose-200 text-xs font-semibold uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4" />
              <span>Hospital Clinical Decision Support System</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Welcome, {currentUser.name}</h1>
            <p className="text-xs text-rose-100/80 mt-1 max-w-xl">
              Role: <strong className="text-white uppercase">{currentUser.role}</strong> &bull; Department: <strong>{currentUser.department || "Clinical Services"}</strong>
            </p>
          </div>
        </div>

        {/* Quick Launch Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div
            onClick={() => setActiveView("chat")}
            className="p-5 bg-white rounded-2xl border border-slate-200 shadow-sm hover:border-rose-300 hover:shadow-md transition cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-900 mb-3">
                <Activity className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-1">Clinical AI Consultation</h3>
              <p className="text-xs text-slate-500">Query verified hospital guidelines, antimicrobial protocols, and patient timelines.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-rose-900 gap-1">
              <span>Start Consultation</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>

          <div
            onClick={() => setActiveView("patients")}
            className="p-5 bg-white rounded-2xl border border-slate-200 shadow-sm hover:border-rose-300 hover:shadow-md transition cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-900 mb-3">
                <Users className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-1">Patient Directory</h3>
              <p className="text-xs text-slate-500">View admissions, vitals monitoring, CBC panels, and doctor assessments.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-rose-900 gap-1">
              <span>View {patients.length} Patients</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>

          <div
            onClick={() => setActiveView("knowledge_base")}
            className="p-5 bg-white rounded-2xl border border-slate-200 shadow-sm hover:border-rose-300 hover:shadow-md transition cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-900 mb-3">
                <BookOpen className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 mb-1">Knowledge Base</h3>
              <p className="text-xs text-slate-500">Hospital standard operating procedures, medical textbooks, and clinical policies.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center text-xs font-semibold text-rose-900 gap-1">
              <span>Explore Guidelines</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* Recent Inpatients */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Active Inpatients ({patients.length})</h2>
            <button onClick={() => setActiveView("patients")} className="text-xs font-semibold text-rose-900 hover:underline">
              View All
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {patients.slice(0, 4).map((p) => (
              <div key={p.id} className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-900">{p.name}</h4>
                  <p className="text-[10px] text-slate-500 font-mono">{p.id} &bull; {p.department}</p>
                  <p className="text-xs text-slate-700 mt-2 font-medium">Status: {p.health_status}</p>
                </div>
                <button
                  onClick={() => onSelectPatientForChat(p.id)}
                  className="mt-3 w-full py-1.5 bg-rose-900 hover:bg-rose-800 text-white rounded-lg text-xs font-semibold transition"
                >
                  Consult AI
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
