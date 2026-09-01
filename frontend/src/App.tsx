import React, { useState, useEffect } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatArea } from "./components/ChatArea";
import { Login } from "./components/Login";
import { PatientDashboard } from "./components/PatientDashboard";
import { DashboardHome } from "./components/DashboardHome";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { KnowledgeBaseView } from "./components/KnowledgeBaseView";
import { Settings } from "lucide-react";

interface User {
  id: number;
  username: string;
  role: string;
  name: string;
}

interface Patient {
  id: string;
  name: string;
  age: number;
  gender: string;
  health_status: string;
  assigned_doctor: string;
}

interface Document {
  id: number;
  name: string;
  status: string;
  chunk_count: number;
  scope: string;
  created_at: string;
}

interface Session {
  id: string;
  title: string;
  created_at: string;
}

interface Message {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  confidence_level?: string;
  confidence_score?: number;
  evidence?: any[];
  verification_results?: any[];
  created_at: string;
}

const API_BASE = "http://127.0.0.1:8000";
const API_KEY = "dev_secret_key_to_protect_endpoints";

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("cdss_user");
    return saved ? JSON.parse(saved) : null;
  });

  const [activeScreen, setActiveScreen] = useState<"dashboard" | "clinical_ai" | "patients" | "documents" | "knowledge_base" | "settings">("dashboard");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [inspectedSentence, setInspectedSentence] = useState<any | null>(null);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [quickQuestion, setQuickQuestion] = useState<string>("");

  // Save/Restore user
  const handleLoginSuccess = (user: User) => {
    setCurrentUser(user);
    localStorage.setItem("cdss_user", JSON.stringify(user));
    setActiveScreen("dashboard");
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem("cdss_user");
    setMessages([]);
    setSessions([]);
    setActiveSessionId(null);
  };

  // Fetch initial hospital data
  const fetchData = async () => {
    if (!currentUser) return;

    try {
      // 1. Fetch Patients
      const pRes = await fetch(`${API_BASE}/api/patients`, {
        headers: {
          "X-API-Key": API_KEY,
          "X-User-Id": currentUser.username
        }
      });
      if (pRes.ok) {
        const pData = await pRes.json();
        setPatients(pData);
        if (pData.length > 0 && !selectedPatientId) {
          setSelectedPatientId(pData[0].id);
        }
      }

      // 2. Fetch Documents
      const dRes = await fetch(`${API_BASE}/api/documents`, {
        headers: {
          "X-API-Key": API_KEY,
          "X-User-Id": currentUser.username
        }
      });
      if (dRes.ok) {
        const dData = await dRes.json();
        setDocuments(dData);
      }

      // 3. Fetch Sessions
      const sRes = await fetch(`${API_BASE}/api/sessions`, {
        headers: {
          "X-API-Key": API_KEY,
          "X-User-Id": currentUser.username
        }
      });
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
    if (currentUser) {
      fetchData();
    }
  }, [currentUser]);

  // Fetch messages when activeSessionId changes
  useEffect(() => {
    if (!activeSessionId || !currentUser) return;

    const fetchSessionMessages = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/sessions/${activeSessionId}/messages`, {
          headers: {
            "X-API-Key": API_KEY,
            "X-User-Id": currentUser.username
          }
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
  }, [activeSessionId, currentUser]);

  // Create new consultation session
  const handleCreateSession = async () => {
    if (!currentUser) return;

    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
          "X-User-Id": currentUser.username
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

  // Delete consultation session
  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!currentUser) return;

    try {
      const res = await fetch(`${API_BASE}/api/sessions/${id}`, {
        method: "DELETE",
        headers: {
          "X-API-Key": API_KEY,
          "X-User-Id": currentUser.username
        }
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

  // Upload file
  const handleUploadFile = async (file: File, scope: string, patientId?: string) => {
    if (!currentUser) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("scope", scope);
    if (patientId) {
      formData.append("patient_id", patientId);
    }

    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      headers: {
        "X-API-Key": API_KEY,
        "X-User-Id": currentUser.username
      },
      body: formData
    });

    if (res.ok) {
      fetchData();
    } else {
      const err = await res.json();
      alert(err.detail || "Error uploading document.");
    }
  };

  // Send RAG Query
  const handleSendMessage = async (text: string, filters: any, directLlm: boolean) => {
    if (!currentUser) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      try {
        const sRes = await fetch(`${API_BASE}/api/sessions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            "X-User-Id": currentUser.username
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
          "X-API-Key": API_KEY,
          "X-User-Id": currentUser.username
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

  // Quick Action Shortcuts from Dashboard
  const handleQuickAsk = (question: string) => {
    setQuickQuestion(question);
    setActiveScreen("clinical_ai");
  };

  const handleSelectPatientForDashboard = (patientId: string) => {
    setSelectedPatientId(patientId);
    setActiveScreen("patients");
  };

  const handleAskAboutDoc = (doc: Document) => {
    setQuickQuestion(`Summarize the key clinical findings in ${doc.name}`);
    setActiveScreen("clinical_ai");
    handleCreateSession();
  };

  if (!currentUser) {
    return <Login onLoginSuccess={handleLoginSuccess} apiBase={API_BASE} />;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans antialiased">
      {/* Left Sidebar */}
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

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {activeScreen === "dashboard" && (
          <DashboardHome
            currentUser={currentUser}
            patients={patients}
            documents={documents}
            sessions={sessions}
            onNavigate={setActiveScreen}
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
            currentUser={currentUser}
            apiBase={API_BASE}
            apiKey={API_KEY}
            selectedPatientId={selectedPatientId}
            onSelectPatient={setSelectedPatientId}
            onSelectDocumentForChat={handleAskAboutDoc}
            onSelectPatientForChat={(pId) => {
              setSelectedPatientId(pId);
              setActiveScreen("clinical_ai");
            }}
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

        {activeScreen === "knowledge_base" && (
          <KnowledgeBaseView
            documents={documents}
            onConsultGuideline={(docName) => {
              setQuickQuestion(`What are the key clinical recommendations in ${docName}?`);
              setActiveScreen("clinical_ai");
            }}
          />
        )}

        {activeScreen === "settings" && (
          <div className="flex-1 h-full overflow-y-auto bg-slate-50 p-8 space-y-6">
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs max-w-2xl space-y-6">
              <div className="flex items-center space-x-2 text-slate-800">
                <Settings className="w-5 h-5 text-blue-600" />
                <h1 className="text-xl font-bold">System & RAG Configuration</h1>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">RAG Endpoint</label>
                  <input
                    type="text"
                    disabled
                    value={API_BASE}
                    className="w-full bg-slate-100 border border-slate-300 rounded-xl p-2.5 font-mono text-slate-600"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">API Key Authentication</label>
                  <input
                    type="password"
                    disabled
                    value={API_KEY}
                    className="w-full bg-slate-100 border border-slate-300 rounded-xl p-2.5 font-mono text-slate-600"
                  />
                </div>

                <div className="pt-4 border-t border-slate-200 space-y-2">
                  <div className="font-bold text-slate-800">Grounding & Reranker Settings</div>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-blue-800 space-y-1">
                    <div>• Retrieval: <strong>BM25 + FAISS Hybrid</strong> (Reciprocal Rank Fusion k=60)</div>
                    <div>• Reranker: <strong>Cross-Encoder</strong> (ms-marco-MiniLM-L-6-v2)</div>
                    <div>• Cosine Fact-Verification Threshold: <strong>0.70</strong></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
