import React from "react";
import { 
  Plus, MessageSquare, Trash2, FileText, PanelLeftClose, 
  LayoutDashboard, Users, BrainCircuit, LogOut,
  Shield, BookOpen, Clock, Settings
} from "lucide-react";

interface Session {
  id: string;
  title: string;
  created_at: string;
}

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  isOpen: boolean;
  onToggleOpen: () => void;
  activeScreen: "dashboard" | "clinical_ai" | "patients" | "documents" | "knowledge_base" | "settings";
  onNavigate: (screen: "dashboard" | "clinical_ai" | "patients" | "documents" | "knowledge_base" | "settings") => void;
  currentUser: { id: number; username: string; role: string; name: string };
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
  isOpen,
  onToggleOpen,
  activeScreen,
  onNavigate,
  currentUser,
  onLogout
}) => {
  return (
    <aside
      className={`relative z-20 flex flex-col h-full bg-slate-900 border-r border-slate-800 text-slate-300 transition-all duration-300 ease-in-out shrink-0 select-none ${
        isOpen ? "w-64" : "w-0 overflow-hidden"
      }`}
    >
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div 
          onClick={() => onNavigate("dashboard")}
          className="flex items-center space-x-2.5 cursor-pointer group"
        >
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 group-hover:bg-blue-500 transition-colors">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-xs leading-tight text-white group-hover:text-blue-300 transition-colors">
              RAG Based CDSS
            </div>
            <div className="text-[10px] text-slate-400 font-medium">
              Clinical Decision System
            </div>
          </div>
        </div>

        <button
          onClick={onToggleOpen}
          className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* New Consultation Action Button */}
      <div className="p-3">
        <button
          onClick={() => {
            onCreateSession();
            onNavigate("clinical_ai");
          }}
          className="w-full flex items-center justify-center space-x-2 py-2.5 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Consultation</span>
        </button>
      </div>

      {/* Navigation Links */}
      <div className="px-3 py-2 space-y-1">
        <button
          onClick={() => onNavigate("dashboard")}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeScreen === "dashboard"
              ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
          }`}
        >
          <LayoutDashboard className="w-4 h-4 shrink-0" />
          <span>Dashboard</span>
        </button>

        <button
          onClick={() => onNavigate("clinical_ai")}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeScreen === "clinical_ai"
              ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
          }`}
        >
          <BrainCircuit className="w-4 h-4 shrink-0" />
          <span>Clinical AI</span>
        </button>

        <button
          onClick={() => onNavigate("patients")}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeScreen === "patients"
              ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
          }`}
        >
          <Users className="w-4 h-4 shrink-0" />
          <span>Patient Charts</span>
        </button>

        <button
          onClick={() => onNavigate("documents")}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeScreen === "documents"
              ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
          }`}
        >
          <FileText className="w-4 h-4 shrink-0" />
          <span>Document Library</span>
        </button>

        <button
          onClick={() => onNavigate("knowledge_base")}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeScreen === "knowledge_base"
              ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
          }`}
        >
          <BookOpen className="w-4 h-4 shrink-0" />
          <span>Knowledge Base</span>
        </button>

        <button
          onClick={() => onNavigate("settings")}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeScreen === "settings"
              ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
              : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
          }`}
        >
          <Settings className="w-4 h-4 shrink-0" />
          <span>System Settings</span>
        </button>
      </div>

      {/* Consultation History */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        <div className="flex items-center justify-between px-2 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          <span>Consultation History</span>
          <Clock className="w-3 h-3 text-slate-500" />
        </div>

        <div className="space-y-1">
          {sessions.length === 0 ? (
            <div className="text-center py-4 text-[11px] text-slate-600 italic">
              No previous chats
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => {
                  onSelectSession(session.id);
                  onNavigate("clinical_ai");
                }}
                className={`group flex items-center justify-between p-2 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                  activeSessionId === session.id && activeScreen === "clinical_ai"
                    ? "bg-slate-800 text-white font-semibold"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                }`}
              >
                <div className="flex items-center space-x-2 truncate">
                  <MessageSquare className="w-3.5 h-3.5 shrink-0 text-slate-400 group-hover:text-blue-400" />
                  <span className="truncate">{session.title || "Clinical Chat"}</span>
                </div>
                <button
                  onClick={(e) => onDeleteSession(session.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-opacity"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Bottom User Profile Card & Logout */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="w-8 h-8 rounded-full bg-blue-600/30 border border-blue-500/40 flex items-center justify-center text-blue-300 font-bold text-xs shrink-0">
              {currentUser.name ? currentUser.name.charAt(0) : "U"}
            </div>
            <div className="truncate">
              <div className="text-xs font-bold text-slate-200 truncate">
                {currentUser.name}
              </div>
              <div className="text-[10px] text-slate-400 capitalize">
                {currentUser.role}
              </div>
            </div>
          </div>

          <button
            onClick={onLogout}
            title="Sign Out"
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-red-400 transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
