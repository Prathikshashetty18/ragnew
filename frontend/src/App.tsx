import React, { useState, useEffect, useRef } from "react";
import { Login } from "./components/Login";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { PatientDashboard } from "./components/PatientDashboard";
import { ReportStudio } from "./components/ReportStudio";
import { RadiologyWorkspace } from "./components/RadiologyWorkspace";
import { LaboratoryWorkspace } from "./components/LaboratoryWorkspace";
import { KnowledgeBaseView } from "./components/KnowledgeBaseView";
import { UserManagement } from "./components/UserManagement";
import { AuditLogView } from "./components/AuditLogView";
import { DashboardHome } from "./components/DashboardHome";
import { getApiUrl } from "./api/client";
import type { User, Patient, ChatSession, ChatMessage, SourceCard } from "./types";

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [activeView, setActiveView] = useState("dashboard");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("cdss_token");
    if (token) {
      fetch(getApiUrl("/api/auth/me"), {
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
      const res = await fetch(getApiUrl("/api/patients"), {
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
      const res = await fetch(getApiUrl("/api/sessions"), {
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
      const res = await fetch(getApiUrl(`/api/sessions/${sessionId}/messages`), {
        headers: { Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        const formatted = data.map((m: any) => {
          let sources = m.sources;
          if (!sources || sources.length === 0) {
            if (m.evidence && Array.isArray(m.evidence) && m.evidence.length > 0) {
              sources = m.evidence.map((ev: any, idx: number) => ({
                document_id: String(ev.chunk_id || idx + 1),
                citation_id: idx + 1,
                title: ev.source || ev.title || "Clinical Document",
                page: ev.page || 1,
                section: ev.section || "Clinical Finding",
                relevance: 0.85,
                supporting_text: ev.supporting_text || ""
              }));
            }
          }
          return {
            ...m,
            sources: sources || []
          };
        });
        setMessages(formatted);
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
      const res = await fetch(getApiUrl("/api/sessions"), {
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
      await fetch(getApiUrl(`/api/sessions/${id}`), {
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
      const res = await fetch(getApiUrl("/api/sessions"), {
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

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch(getApiUrl("/api/ask"), {
        method: "POST",
        signal: controller.signal,
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
        const mappedSources: SourceCard[] = [];
        if (data.citations && Array.isArray(data.citations) && data.citations.length > 0) {
          data.citations.forEach((c: any) => {
            const evMatch = data.evidence?.find((e: any) => e.source === c.pdf_name && (e.page === c.page_number || !e.page));
            mappedSources.push({
              document_id: String(c.chunk_id || c.citation_id),
              citation_id: c.citation_id,
              title: c.pdf_name || "Clinical Document",
              page: c.page_number || 1,
              section: c.section || "General",
              subsection: c.subsection,
              relevance: c.authority_score || 0.8,
              supporting_text: evMatch?.supporting_text || c.supporting_text || ""
            });
          });
        } else if (data.sources && Array.isArray(data.sources)) {
          mappedSources.push(...data.sources);
        } else if (data.evidence && Array.isArray(data.evidence)) {
          data.evidence.forEach((ev: any, idx: number) => {
            mappedSources.push({
              document_id: String(ev.chunk_id || idx + 1),
              citation_id: idx + 1,
              title: ev.source || ev.title || "Clinical Document",
              page: ev.page || 1,
              section: ev.section || "Clinical Assessment",
              relevance: 0.85,
              supporting_text: ev.supporting_text || ""
            });
          });
        }

        setMessages((prev) => [
          ...prev,
          {
            id: data.id,
            role: "assistant",
            content: data.content || data.answer || "",
            mode: data.mode,
            confidence_level: data.confidence_level,
            confidence_score: data.confidence_score,
            sources: mappedSources,
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
      if (err.name === "AbortError") {
        setMessages((prev) => [
          ...prev,
          {
            id: `stop-${Date.now()}`,
            role: "assistant",
            content: "*Clinical consultation response stopped by user.*",
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: "Unable to reach Clinical RAG service.",
            confidence_level: "Low",
          },
        ]);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
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
            onStopGeneration={handleStopGeneration}
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
        {activeView === "users" && <UserManagement />}
        {activeView === "audit_logs" && <AuditLogView />}
      </main>
    </div>
  );
};

export default App;
