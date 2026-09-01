import React, { useState, useEffect } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { Login } from "./components/Login";
import { PatientDashboard } from "./components/PatientDashboard";
import { DashboardHome } from "./components/DashboardHome";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { KnowledgeBaseView } from "./components/KnowledgeBaseView";
import { ReportStudio } from "./components/ReportStudio";
import { UserManagement } from "./components/UserManagement";
import { AuditLogView } from "./components/AuditLogView";
import type { UserProfile, Patient, Document, Session, Message } from "./types";

const API_BASE = "http://127.0.0.1:8000";

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem("cdss_user");
    return saved ? JSON.parse(saved) : null;
  });

  const [token, setToken] = useState<string>(() => {
    return localStorage.getItem("cdss_token") || "";
  });

  const [activeScreen, setActiveScreen] = useState<string>("dashboard");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [inspectedSentence, setInspectedSentence] = useState<any | null>(null);
  const [reportPatientId, setReportPatientId] = useState<string>("");
  const [quickQuestion, setQuickQuestion] = useState<string>("");

  const handleLoginSuccess = (user: UserProfile, accessToken: string) => {
    setCurrentUser(user);
    setToken(accessToken);
    localStorage.setItem("cdss_user", JSON.stringify(user));
    localStorage.setItem("cdss_token", accessToken);
    setActiveScreen("dashboard");
  };

  const handleLogout = () => {
    setCurrentUser(null);
    setToken("");
    localStorage.removeItem("cdss_user");
    localStorage.removeItem("cdss_token");
    setMessages([]);
    setSessions([]);
    setActiveSessionId(null);
  };

  const authHeaders = {
    Authorization: `Bearer ${token}`
  };

  const fetchData = async () => {
    if (!currentUser || !token) return;

    try {
      const pRes = await fetch(`${API_BASE}/api/patients`, { headers: authHeaders });
      if (pRes.ok) {
        const pData = await pRes.json();
        setPatients(pData);
      }

      const dRes = await fetch(`${API_BASE}/api/documents`, { headers: authHeaders });
      if (dRes.ok) {
        const dData = await dRes.json();
        setDocuments(dData);
      }

      const sRes = await fetch(`${API_BASE}/api/sessions`, { headers: authHeaders });
      if (sRes.ok) {
        const sData = await sRes.json();
        setSessions(sData);
        if (sData.length > 0 && !activeSessionId) {
          setActiveSessionId(sData[0].id);
        }
      }
    } catch (e) {
      console.error("Error fetching hospital data:", e);
    }
  };

  useEffect(() => {
    if (currentUser && token) {
      fetchData();
    }
  }, [currentUser, token]);

  useEffect(() => {
    if (!activeSessionId || !currentUser || !token) return;

    const fetchSessionMessages = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/sessions/${activeSessionId}/messages`, {
          headers: authHeaders
        });
        if (res.ok) {
          const data = await res.json();
          setMessages(data);
        }
      } catch (e) {
        console.error("Error fetching messages:", e);
      }
    };

    fetchSessionMessages();
  }, [activeSessionId, currentUser, token]);

  const handleCreateSession = async () => {
    if (!currentUser || !token) return;

    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders
        },
        body: JSON.stringify({ title: "New Consultation" })
      });
      if (res.ok) {
        const newSession = await res.json();
        setSessions(prev => [newSession, ...prev]);
        setActiveSessionId(newSession.id);
        setMessages([]);
      }
    } catch (e) {
      console.error("Error creating session:", e);
    }
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!currentUser || !token) return;

    try {
      const res = await fetch(`${API_BASE}/api/sessions/${id}`, {
        method: "DELETE",
        headers: authHeaders
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (activeSessionId === id) {
          const remaining = sessions.filter(s => s.id !== id);
          if (remaining.length > 0) {
            setActiveSessionId(remaining[0].id);
          } else {
            setActiveSessionId(null);
            setMessages([]);
          }
        }
      }
    } catch (e) {
      console.error("Error deleting session:", e);
    }
  };

  const handleUploadFile = async (file: File, scope: string, patientId?: string, docType?: string) => {
    if (!currentUser || !token) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("scope", scope);
    if (patientId) formData.append("patient_id", patientId);
    if (docType) formData.append("document_type", docType);

    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      headers: authHeaders,
      body: formData
    });

    if (res.ok) {
      const data = await res.json();
      fetchData();
      return data;
    } else {
      const err = await res.json();
      throw new Error(err.detail || "Error uploading document.");
    }
  };

  const handleSendMessage = async (text: string, filters: any, directLlm: boolean) => {
    if (!currentUser || !token) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      try {
        const sRes = await fetch(`${API_BASE}/api/sessions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders
          },
          body: JSON.stringify({ title: text.slice(0, 30) })
        });
        if (sRes.ok) {
          const sData = await sRes.json();
          setSessions(prev => [sData, ...prev]);
          setActiveSessionId(sData.id);
          targetSessionId = sData.id;
        }
      } catch (e) {
        console.error(e);
      }
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders
        },
        body: JSON.stringify({
          session_id: targetSessionId,
          query: text,
          filters: filters,
          direct_llm: directLlm
        })
      });

      if (res.ok) {
        const assistantMsg: Message = await res.json();
        setMessages(prev => [...prev, assistantMsg]);
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Error generating response.");
      }
    } catch (e) {
      console.error(e);
      alert("Network error: Failed to reach RAG server.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAsk = (question: string) => {
    setQuickQuestion(question);
    setActiveScreen("clinical_ai");
  };

  const handleSelectPatientForDashboard = (patientId: string) => {
    setReportPatientId(patientId);
    setActiveScreen("patients");
  };

  const handleAskAboutDoc = (doc: Document) => {
    setQuickQuestion(`Summarize the clinical guidelines and recommendations in ${doc.name}`);
    setActiveScreen("clinical_ai");
    handleCreateSession();
  };

  const handleLaunchReport = (patientId: string) => {
    setReportPatientId(patientId);
    setActiveScreen("reports");
  };

  if (!currentUser || !token) {
    return <Login onLoginSuccess={handleLoginSuccess} apiBase={API_BASE} />;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans antialiased">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onCreateSession={handleCreateSession}
        onDeleteSession={handleDeleteSession}
        isOpen={isSidebarOpen}
        onToggleOpen={() => setIsSidebarOpen(!isSidebarOpen)}
        activeScreen={activeScreen}
        onNavigate={setActiveScreen}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {activeScreen === "dashboard" && (
          <DashboardHome
            currentUser={currentUser}
            patients={patients}
            documents={documents}
            sessions={sessions}
            onNavigate={(screen) => setActiveScreen(screen)}
            onSelectPatient={handleSelectPatientForDashboard}
            onSelectSession={setActiveSessionId}
            onQuickAsk={handleQuickAsk}
          />
        )}

        {activeScreen === "clinical_ai" && (
          <ChatArea
            messages={messages}
            activeSessionId={activeSessionId}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            isSidebarOpen={isSidebarOpen}
            onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
            onInspectSentence={setInspectedSentence}
            activeInspectedSentence={inspectedSentence}
            onUploadFile={handleUploadFile}
            patients={patients}
            documents={documents}
            initialQuery={quickQuestion}
          />
        )}

        {activeScreen === "patients" && (
          <PatientDashboard
            patients={patients}
            onSelectPatient={(id) => setReportPatientId(id)}
            onLaunchConsultation={(_id, q) => {
              if (q) setQuickQuestion(q);
              setActiveScreen("clinical_ai");
            }}
            onLaunchReport={handleLaunchReport}
            apiBase={API_BASE}
            token={token}
            currentUser={currentUser}
            onRefreshPatients={fetchData}
          />
        )}

        {activeScreen === "reports" && (
          <ReportStudio
            patients={patients}
            apiBase={API_BASE}
            token={token}
            currentUser={currentUser}
            initialPatientId={reportPatientId}
          />
        )}

        {activeScreen === "knowledge_base" && (
          <KnowledgeBaseView
            documents={documents}
            apiBase={API_BASE}
            token={token}
            currentUser={currentUser}
            onRefreshDocuments={fetchData}
            onUploadFile={handleUploadFile}
          />
        )}

        {activeScreen === "documents" && (
          <DocumentLibrary
            documents={documents}
            patients={patients}
            onUploadFile={handleUploadFile}
            onAskAboutDoc={handleAskAboutDoc}
            isLoading={isLoading}
          />
        )}

        {activeScreen === "users" && currentUser.role === "ADMIN" && (
          <UserManagement
            apiBase={API_BASE}
            token={token}
          />
        )}

        {activeScreen === "audit_logs" && currentUser.role === "ADMIN" && (
          <AuditLogView
            apiBase={API_BASE}
            token={token}
          />
        )}
      </main>
    </div>
  );
};

export default App;
