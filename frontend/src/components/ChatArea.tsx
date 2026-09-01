import React, { useState, useRef, useEffect } from "react";
import { 
  Send, Sparkles, Paperclip, ShieldCheck, 
  Copy, Check, BookOpen, User, FileText, 
  Layers, Info, ArrowRight, Cpu, RefreshCw, PanelLeft
} from "lucide-react";

interface Evidence {
  pdf_name: string;
  page_number: number;
  supporting_text: string;
  response_sentence?: string;
}

interface VerificationResult {
  sentence: string;
  status: string;
  score: number;
  source_sentence?: string;
  pdf_name?: string;
  page_number?: number;
}

interface Message {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  confidence_level?: string;
  confidence_score?: number;
  evidence?: Evidence[];
  verification_results?: VerificationResult[];
  created_at: string;
}

interface Patient {
  id: string;
  name: string;
}

interface Document {
  id: number;
  name: string;
  status: string;
  chunk_count: number;
  scope: string;
}

interface ChatAreaProps {
  messages: Message[];
  activeSessionId?: string | null;
  onSendMessage: (text: string, filters: any, directLlm: boolean) => void;
  isLoading: boolean;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  onInspectSentence: (sentence: any | null) => void;
  activeInspectedSentence?: any | null;
  onUploadFile: (file: File, scope: string, patientId?: string) => Promise<void>;
  patients: Patient[];
  documents?: Document[];
  initialQuery?: string;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  onSendMessage,
  isLoading,
  isSidebarOpen,
  onToggleSidebar,
  onInspectSentence,
  onUploadFile,
  patients,
  initialQuery
}) => {
  const [inputText, setInputText] = useState(initialQuery || "");
  const [scope, setScope] = useState<"knowledge_base" | "patient" | "temporary" | "patient_and_kb">("knowledge_base");
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [directLlm, setDirectLlm] = useState<boolean>(false);
  const [verifyModeMap, setVerifyModeMap] = useState<Record<string, boolean>>({});
  const [copiedMap, setCopiedMap] = useState<Record<string, boolean>>({});
  const [isUploading, setIsUploading] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialQuery) {
      setInputText(initialQuery);
    }
  }, [initialQuery]);

  useEffect(() => {
    if (patients.length > 0 && !selectedPatientId) {
      setSelectedPatientId(patients[0].id);
    }
  }, [patients]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = () => {
    if (!inputText.trim() || isLoading) return;

    const filters: any = { scope };
    if (scope === "patient" || scope === "patient_and_kb") {
      filters.patient_id = selectedPatientId;
    }

    onSendMessage(inputText.trim(), filters, directLlm);
    setInputText("");
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith(".pdf")) {
        setIsUploading(true);
        try {
          await onUploadFile(file, "temporary");
          setScope("temporary");
        } catch (err) {
          console.error(err);
        } finally {
          setIsUploading(false);
        }
      } else {
        alert("Only PDF documents are supported.");
      }
    }
  };

  const copyToClipboard = (msgId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMap(prev => ({ ...prev, [msgId]: true }));
    setTimeout(() => {
      setCopiedMap(prev => ({ ...prev, [msgId]: false }));
    }, 2000);
  };

  const toggleVerifyMode = (msgId: string) => {
    setVerifyModeMap(prev => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
    if (verifyModeMap[msgId]) {
      onInspectSentence(null);
    }
  };

  const suggestedFollowUps = [
    "What are the alternate antibiotic choices for penicillin-allergic patients?",
    "What is the recommended follow-up timeline for this condition?",
    "What criteria determine safe hospital discharge for pneumonia?"
  ];

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 relative overflow-hidden">
      {/* Top Bar: Scoping & Engine Controls */}
      <header className="px-6 py-3.5 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0 shadow-2xs z-10">
        <div className="flex items-center space-x-3">
          {!isSidebarOpen && (
            <button
              onClick={onToggleSidebar}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-600 cursor-pointer"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          )}

          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-slate-900">Retrieval Scope:</span>
            <div className="flex bg-slate-100 p-1 rounded-xl text-xs font-semibold">
              <button
                type="button"
                onClick={() => setScope("knowledge_base")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center space-x-1.5 ${
                  scope === "knowledge_base"
                    ? "bg-white text-blue-700 shadow-xs font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Hospital Guidelines</span>
              </button>

              <button
                type="button"
                onClick={() => setScope("patient")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center space-x-1.5 ${
                  scope === "patient"
                    ? "bg-white text-blue-700 shadow-xs font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <User className="w-3.5 h-3.5" />
                <span>Patient Record</span>
              </button>

              <button
                type="button"
                onClick={() => setScope("patient_and_kb")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center space-x-1.5 ${
                  scope === "patient_and_kb"
                    ? "bg-white text-blue-700 shadow-xs font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Patient + Guidelines</span>
              </button>

              <button
                type="button"
                onClick={() => setScope("temporary")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center space-x-1.5 ${
                  scope === "temporary"
                    ? "bg-white text-blue-700 shadow-xs font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Session PDF</span>
              </button>
            </div>
          </div>

          {(scope === "patient" || scope === "patient_and_kb") && (
            <select
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              className="bg-slate-100 border border-slate-300 rounded-lg px-2.5 py-1 text-xs font-bold text-slate-800 outline-none focus:border-blue-500"
            >
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} - {p.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Strict RAG vs Direct LLM Mode Switch */}
        <div className="flex items-center space-x-2">
          <span className="text-xs font-medium text-slate-500">Mode:</span>
          <button
            type="button"
            onClick={() => setDirectLlm(!directLlm)}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center space-x-1.5 ${
              directLlm
                ? "bg-amber-100 text-amber-800 border border-amber-300"
                : "bg-emerald-50 text-emerald-700 border border-emerald-300"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>{directLlm ? "Direct LLM (Unverified)" : "Strict RAG (Verified)"}</span>
          </button>
        </div>
      </header>

      {/* Chat Messages Feed */}
      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto space-y-4 my-auto py-12">
            <div className="w-14 h-14 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center shadow-md shadow-blue-500/10">
              <Sparkles className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">
                Clinical AI Decision Support
              </h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Ask questions regarding patient diagnostics, antibiotic therapy guidelines, clinical management, and lab evaluations grounded directly in authorized hospital records.
              </p>
            </div>

            <div className="w-full space-y-2 pt-2 text-left">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Suggested Prompts
              </span>
              {suggestedFollowUps.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setInputText(q);
                    if (inputRef.current) inputRef.current.focus();
                  }}
                  className="w-full p-3 bg-white hover:bg-blue-50/60 border border-slate-200 hover:border-blue-300 rounded-xl text-xs text-slate-800 font-medium transition-all text-left flex items-center justify-between group cursor-pointer shadow-2xs"
                >
                  <span>{q}</span>
                  <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.role === "user" ? "items-end" : "items-start"
              } space-y-2`}
            >
              {/* Message Header */}
              <div className="flex items-center space-x-2 text-xs text-slate-500 px-1">
                <span className="font-bold text-slate-700">
                  {msg.role === "user" ? "You (Clinician)" : "Clinical Decision Assistant"}
                </span>
                <span>•</span>
                <span>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>

              {/* Message Box */}
              <div
                className={`max-w-3xl rounded-2xl p-5 shadow-xs leading-relaxed text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white font-medium"
                    : "bg-white text-slate-900 border border-slate-200 space-y-4"
                }`}
              >
                {/* Content */}
                <div className="whitespace-pre-wrap">
                  {msg.content}
                </div>

                {/* Assistant RAG Metadata Badges */}
                {msg.role === "assistant" && (
                  <div className="space-y-4 pt-3 border-t border-slate-100">
                    {/* Confidence & Verification Status Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        {msg.confidence_level && (
                          <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold flex items-center space-x-1 ${
                            msg.confidence_level === "High"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : msg.confidence_level === "Medium"
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-red-50 text-red-700 border border-red-200"
                          }`}>
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>{msg.confidence_level} Confidence ({Math.round((msg.confidence_score || 0) * 100)}%)</span>
                          </span>
                        )}

                        {msg.verification_results && msg.verification_results.length > 0 && (
                          <button
                            onClick={() => toggleVerifyMode(msg.id)}
                            className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition-colors flex items-center space-x-1 cursor-pointer"
                          >
                            <Info className="w-3.5 h-3.5 text-blue-600" />
                            <span>{verifyModeMap[msg.id] ? "Hide Verification" : "Inspect Sentence Verification"}</span>
                          </button>
                        )}
                      </div>

                      <button
                        onClick={() => copyToClipboard(msg.id, msg.content)}
                        className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
                        title="Copy to clipboard"
                      >
                        {copiedMap[msg.id] ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>

                    {/* Sentence Verification Inspection Drawer */}
                    {verifyModeMap[msg.id] && msg.verification_results && (
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2.5 animate-fadeIn">
                        <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                          <ShieldCheck className="w-4 h-4 text-emerald-600" />
                          <span>Sentence-Level Fact Verification</span>
                        </div>
                        <div className="space-y-2">
                          {msg.verification_results.map((vr, idx) => (
                            <div
                              key={idx}
                              onClick={() => onInspectSentence(vr)}
                              className="p-3 bg-white border border-slate-200 hover:border-blue-400 rounded-lg text-xs space-y-1.5 transition-all cursor-pointer shadow-2xs"
                            >
                              <div className="flex items-center justify-between">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  vr.status === "Supported" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
                                }`}>
                                  {vr.status} (Score: {Math.round(vr.score * 100)}%)
                                </span>
                                {vr.pdf_name && (
                                  <span className="text-[10px] text-slate-500 font-mono">
                                    {vr.pdf_name} (p. {vr.page_number})
                                  </span>
                                )}
                              </div>
                              <p className="text-slate-800 font-medium">{vr.sentence}</p>
                              {vr.source_sentence && (
                                <p className="text-[11px] text-slate-500 italic bg-slate-50 p-1.5 rounded">
                                  Source: "{vr.source_sentence}"
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Retrieved Evidence & Source Citations */}
                    {msg.evidence && msg.evidence.length > 0 && (
                      <div className="bg-blue-50/50 p-4 rounded-xl border border-blue-100 space-y-2">
                        <div className="text-xs font-bold text-blue-900 uppercase tracking-wider flex items-center space-x-1.5">
                          <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                          <span>Retrieved Evidence & Citations</span>
                        </div>
                        <div className="space-y-2">
                          {msg.evidence.map((ev, idx) => (
                            <div key={idx} className="p-2.5 bg-white border border-blue-200/80 rounded-lg text-xs space-y-1">
                              <div className="flex items-center justify-between text-blue-800 font-bold text-[11px]">
                                <span className="flex items-center space-x-1">
                                  <FileText className="w-3.5 h-3.5 text-blue-600" />
                                  <span>{ev.pdf_name}</span>
                                </span>
                                <span className="font-mono bg-blue-100 px-1.5 py-0.5 rounded text-[10px]">
                                  Page {ev.page_number}
                                </span>
                              </div>
                              <p className="text-slate-700 text-[11px] leading-relaxed">
                                "{ev.supporting_text}"
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex items-center space-x-3 p-4 bg-white rounded-2xl border border-slate-200 max-w-sm shadow-xs animate-pulse">
            <RefreshCw className="w-5 h-5 text-blue-600 animate-spin" />
            <div className="space-y-1">
              <span className="text-xs font-bold text-slate-800">RAG Pipeline Executing...</span>
              <p className="text-[11px] text-slate-500">FAISS + BM25 Hybrid Retrieval & Cross-Encoder Reranking</p>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <footer className="p-4 md:p-6 bg-white border-t border-slate-200 space-y-2 shrink-0">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf"
          className="hidden"
        />

        <div className="relative flex items-center bg-slate-50 border border-slate-300 focus-within:border-blue-600 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-100 rounded-2xl transition-all shadow-2xs">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            title="Upload personal PDF for this session"
            className="p-3 text-slate-400 hover:text-blue-600 transition-colors cursor-pointer disabled:opacity-50"
          >
            {isUploading ? <RefreshCw className="w-5 h-5 animate-spin text-blue-600" /> : <Paperclip className="w-5 h-5" />}
          </button>

          <textarea
            ref={inputRef}
            rows={1}
            value={inputText}
            onChange={(e) => {
              setInputText(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
            }}
            onKeyDown={handleKeyDown}
            placeholder="Ask Clinical AI a question or request treatment guidance..."
            className="flex-1 bg-transparent py-3 px-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none resize-none max-h-36"
          />

          <button
            type="button"
            onClick={handleSend}
            disabled={!inputText.trim() || isLoading}
            className="p-2.5 m-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-all disabled:opacity-40 cursor-pointer shadow-xs shadow-blue-500/20"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
          <span className="flex items-center space-x-1">
            <Info className="w-3 h-3 text-blue-500" />
            <span>Clinical decision-support tool. Always verify with primary hospital clinical protocols.</span>
          </span>
          <span className="hidden sm:inline">Press <kbd className="font-mono bg-slate-100 px-1 rounded">Enter</kbd> to send</span>
        </div>
      </footer>
    </div>
  );
};
