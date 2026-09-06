import React from "react";
import {
  Activity, Plus, MessageSquare, Users, FileText, Image as ImageIcon,
  TestTube, BookOpen, Shield, Key, LogOut, Trash2
} from "lucide-react";
import type { User, ChatSession } from "../types";

interface SidebarProps {
  currentUser: User;
  activeView: string;
  setActiveView: (view: string) => void;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentUser,
  activeView,
  setActiveView,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onLogout,
}) => {
  const role = (currentUser.role || "").toUpperCase();

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: Activity, roles: ["ADMIN", "DOCTOR", "INTERN", "NURSE", "RADIOLOGIST", "LABORATORY_TECHNICIAN", "FRONT_DESK", "OTHER_STAFF"] },
    { id: "chat", label: "Clinical AI", icon: MessageSquare, roles: ["ADMIN", "DOCTOR", "INTERN", "NURSE", "RADIOLOGIST", "LABORATORY_TECHNICIAN", "OTHER_STAFF"] },
    { id: "patients", label: "Patients", icon: Users, roles: ["ADMIN", "DOCTOR", "INTERN", "NURSE", "FRONT_DESK"] },
    { id: "reports", label: "Report Studio", icon: FileText, roles: ["ADMIN", "DOCTOR"] },
    { id: "radiology", label: "Radiology", icon: ImageIcon, roles: ["ADMIN", "DOCTOR", "INTERN", "RADIOLOGIST"] },
    { id: "laboratory", label: "Laboratory", icon: TestTube, roles: ["ADMIN", "DOCTOR", "INTERN", "LABORATORY_TECHNICIAN"] },
    { id: "knowledge_base", label: "Knowledge Base", icon: BookOpen, roles: ["ADMIN", "DOCTOR", "INTERN", "NURSE", "RADIOLOGIST", "LABORATORY_TECHNICIAN", "FRONT_DESK", "OTHER_STAFF"] },
    { id: "users", label: "Staff Management", icon: Key, roles: ["ADMIN"] },
    { id: "audit_logs", label: "Compliance Audit", icon: Shield, roles: ["ADMIN"] },
  ];

  const filteredNav = navItems.filter((item) => item.roles.includes(role));

  return (
    <aside className="w-64 bg-slate-950 text-slate-300 flex flex-col h-screen border-r border-slate-800 select-none">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80 bg-slate-950">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-rose-900/40 border border-rose-700/50 flex items-center justify-center shrink-0">
            <Activity className="w-5 h-5 text-rose-400" />
          </div>
          <div className="overflow-hidden">
            <h1 className="text-sm font-bold text-white tracking-tight truncate">Clinical RAG Hospital CDSS</h1>
            <p className="text-[11px] text-rose-300 font-medium truncate">Decision Support System</p>
          </div>
        </div>

        {/* Primary "+ New Chat" button */}
        <button
          onClick={onNewChat}
          className="mt-4 w-full py-2.5 px-3 bg-rose-900 hover:bg-rose-800 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 shadow-sm transition active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          <span>+ New Chat</span>
        </button>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 mb-2">Workspaces</div>
        {filteredNav.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition ${
                isActive
                  ? "bg-rose-900/30 text-rose-200 border border-rose-800/40 font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-rose-400" : "text-slate-400"}`} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}

        {/* Chat History */}
        <div className="pt-6 pb-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 mb-2 flex items-center justify-between">
            <span>Chat History</span>
            <span className="text-[10px] text-slate-400 font-normal">({sessions.length})</span>
          </div>

          <div className="space-y-0.5 max-h-48 overflow-y-auto pr-1">
            {sessions.length === 0 ? (
              <p className="text-[11px] text-slate-400 px-3 py-2 italic">No past chats recorded.</p>
            ) : (
              sessions.map((s) => {
                const isSelected = activeView === "chat" && activeSessionId === s.id;
                return (
                  <div
                    key={s.id}
                    className={`group flex items-center justify-between px-3 py-1.5 rounded-lg text-xs transition cursor-pointer ${
                      isSelected
                        ? "bg-slate-800 text-white font-medium"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
                    }`}
                    onClick={() => {
                      setActiveView("chat");
                      onSelectSession(s.id);
                    }}
                  >
                    <div className="flex items-center gap-2 overflow-hidden">
                      <MessageSquare className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                      <span className="truncate text-[11px]">{s.title || "Clinical Chat"}</span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(s.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-400 transition p-1"
                      title="Delete chat session"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* User Footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950">
        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800/50">
          <div className="overflow-hidden pr-2">
            <p className="text-xs font-semibold text-white truncate">{currentUser.name}</p>
            <p className="text-[10px] text-rose-300 uppercase tracking-wider font-semibold truncate">{currentUser.role}</p>
          </div>
          <button
            onClick={onLogout}
            title="Sign out"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition shrink-0"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
