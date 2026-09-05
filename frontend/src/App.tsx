import React, { useState, useEffect } from "react";
import { Login } from "./components/Login";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { PatientDashboard } from "./components/PatientDashboard";
import { ReportStudio } from "./components/ReportStudio";
import { RadiologyWorkspace } from "./components/RadiologyWorkspace";
import { LaboratoryWorkspace } from "./components/LaboratoryWorkspace";
import { KnowledgeBaseView } from "./components/KnowledgeBaseView";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { UserManagement } from "./components/UserManagement";
import { AuditLogView } from "./components/AuditLogView";
import { DashboardHome } from "./components/DashboardHome";
import type { User, Patient, ChatSession, ChatMessage } from "./types";

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [activeView, setActiveView] = useState("dashboard");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("cdss_token");
    if (token) {
      fetch("http://127.0.0.1:8000/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((u) => {
          if (u) setCurrentUser(u);
        })
        .catch(() => {});
    }
  }, []);

  const fetchPatients = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/patients", {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setPatients(data);
      }
    } catch (e) {}
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/sessions", {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        if (!activeSessionId && data.length > 0) {
          setActiveSessionId(data[0].id);
          fetchMessages(data[0].id);
        }
      }
    } catch (e) {}
  };

  const fetchMessages = async (sessionId: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/sessions/${sessionId}/messages`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {}
  };

  useEffect(() => {
    if (currentUser) {
      fetchPatients();
      fetchSessions();
    }
  }, [currentUser]);

  const handleLoginSuccess = (user: User, token: string) => {
    localStorage.setItem("cdss_token", token);
    setCurrentUser(user);
    setActiveView("dashboard");
  };

  const handleLogout = () => {
    localStorage.removeItem("cdss_token");
    setCurrentUser(null);
    setMessages([]);
    setActiveSessionId(null);
  };

  const handleNewChat = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/sessions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({ title: "New Chat" }),
      });
      if (res.ok) {
        const newSession = await res.json();
        setSessions([newSession, ...sessions]);
        setActiveSessionId(newSession.id);
        setMessages([]);
        setActiveView("chat");
      }
    } catch (e) {}
  };

  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    fetchMessages(id);
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await fetch(`http://127.0.0.1:8000/api/sessions/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      const updated = sessions.filter((s) => s.id !== id);
      setSessions(updated);
      if (activeSessionId === id) {
        if (updated.length > 0) {
          setActiveSessionId(updated[0].id);
          fetchMessages(updated[0].id);
        } else {
          setActiveSessionId(null);
          setMessages([]);
        }
      }
    } catch (e) {}
  };

  const handleSendMessage = async (query: string, directLlm: boolean, attachedDocId?: number) => {
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      const res = await fetch("http://127.0.0.1:8000/api/sessions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({ title: query.slice(0, 30) }),
      });
      const newSession = await res.json();
      currentSessionId = newSession.id;
      setSessions([newSession, ...sessions]);
      setActiveSessionId(newSession.id);
    }

    const optimisticUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: query,
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);
    setIsLoading(true);

    const filters: any = {};
    if (attachedDocId) {
      filters.scope = "temporary";
      filters.document_id = attachedDocId;
    } else if (selectedPatientId) {
      filters.scope = "patient";
      filters.patient_id = selectedPatientId;
    } else {
      filters.scope = "knowledge_base";
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          query,
          filters,
          direct_llm: directLlm,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            id: data.id,
            role: "assistant",
            content: data.content,
            mode: data.mode,
            confidence_level: data.confidence_level,
            confidence_score: data.confidence_score,
            sources: data.sources,
            evidence: data.evidence,
          },
        ]);
        fetchSessions();
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `Error: ${data.detail || "Clinical CDSS Query Failed"}`,
            confidence_level: "Low",
          },
        ]);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: "Unable to reach Clinical RAG service.",
          confidence_level: "Low",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPatientForChat = (patientId: string) => {
    setSelectedPatientId(patientId);
    setActiveView("chat");
  };

  if (!currentUser) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden font-sans antialiased text-slate-900 bg-slate-50">
      <Sidebar
        currentUser={currentUser}
        activeView={activeView}
        setActiveView={setActiveView}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onLogout={handleLogout}
      />

      <main className="flex-1 flex overflow-hidden">
        {activeView === "dashboard" && (
          <DashboardHome
            currentUser={currentUser}
            patients={patients}
            setActiveView={setActiveView}
            onSelectPatientForChat={handleSelectPatientForChat}
          />
        )}
        {activeView === "chat" && (
          <ChatArea
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            patients={patients}
            selectedPatientId={selectedPatientId}
            onSelectPatient={setSelectedPatientId}
          />
        )}
        {activeView === "patients" && (
          <PatientDashboard
            patients={patients}
            currentUser={currentUser}
            onSelectPatientForChat={handleSelectPatientForChat}
            onRefreshPatients={fetchPatients}
          />
        )}
        {activeView === "reports" && <ReportStudio patients={patients} />}
        {activeView === "radiology" && <RadiologyWorkspace patients={patients} />}
        {activeView === "laboratory" && <LaboratoryWorkspace patients={patients} />}
        {activeView === "knowledge_base" && <KnowledgeBaseView currentUser={currentUser} />}
        {activeView === "documents" && <DocumentLibrary currentUser={currentUser} />}
        {activeView === "users" && <UserManagement />}
        {activeView === "audit_logs" && <AuditLogView />}
      </main>
    </div>
  );
};

export default App;
