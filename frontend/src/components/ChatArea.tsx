import React, { useState, useRef, useEffect } from "react";
import {
  Send, Paperclip, Mic, MicOff, Square,
  FileText, ExternalLink, Sparkles, User as UserIcon, Bot,
  FileSearch
} from "lucide-react";
import { ConfidencePill } from "./ConfidencePill";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { getApiUrl } from "../api/client";
import type { ChatMessage, Patient, SourceCard } from "../types";

interface ChatAreaProps {
  messages: ChatMessage[];
  onSendMessage: (query: string, directLlm: boolean, attachedDocId?: number) => void;
  onStopGeneration?: () => void;
  isLoading: boolean;
  patients: Patient[];
  selectedPatientId: string | null;
  onSelectPatient: (id: string | null) => void;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  onSendMessage,
  onStopGeneration,
  isLoading,
  patients,
  selectedPatientId,
  onSelectPatient,
}) => {
  const [input, setInput] = useState("");
  const [directLlm, setDirectLlm] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [attachedPdf, setAttachedPdf] = useState<{ id: number; name: string } | null>(null);
  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [selectedSources, setSelectedSources] = useState<SourceCard[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    // Auto-update right panel sources from last message if present
    const lastMsg = messages[messages.length - 1];
    if (lastMsg && lastMsg.role === "assistant") {
      if (lastMsg.sources && lastMsg.sources.length > 0) {
        setSelectedSources(lastMsg.sources);
      } else {
        setSelectedSources([]);
      }
    }
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim(), directLlm, attachedPdf?.id);
    setInput("");
  };

  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingPdf(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("scope", "temporary");
    formData.append("document_type", "Patient Clinical Document");

    try {
      const res = await fetch(getApiUrl("/api/upload"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setAttachedPdf({ id: data.id, name: data.name });
      } else {
        alert(data.detail || "PDF upload failed.");
      }
    } catch (err) {
      alert("Error attaching PDF.");
    } finally {
      setUploadingPdf(false);
    }
  };

  const handleDetachPdf = async () => {
    if (!attachedPdf) return;
    const docId = attachedPdf.id;
    setAttachedPdf(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    try {
      await fetch(getApiUrl(`/api/chat/attachments/${docId}`), {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("cdss_token") || ""}`,
        },
      });
    } catch (e) {
      console.error("Error detaching temporary attachment:", e);
    }
  };

  const recognitionRef = useRef<any>(null);

  const toggleVoiceInput = () => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Speech recognition is not supported in this browser.");
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {}
        recognitionRef.current = null;
      }
      setIsRecording(false);
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;

    recognition.onstart = () => setIsRecording(true);
    recognition.onend = () => {
      setIsRecording(false);
      recognitionRef.current = null;
    };
    recognition.onerror = () => {
      setIsRecording(false);
      recognitionRef.current = null;
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };

    try {
      recognition.start();
    } catch (e) {
      setIsRecording(false);
      recognitionRef.current = null;
    }
  };

  const selectedPatient = patients.find((p) => p.id === selectedPatientId);

  return (
    <div className="flex-1 flex h-screen overflow-hidden bg-slate-50">
      {/* Central Chat Interface */}
      <div className="flex-1 flex flex-col h-full overflow-hidden border-r border-slate-200 bg-white">
        {/* Top Scope & Patient Bar */}
        <div className="px-6 py-3.5 border-b border-slate-200 bg-white flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Patient Scope:</div>
            <select
              value={selectedPatientId || ""}
              onChange={(e) => onSelectPatient(e.target.value || null)}
              className="py-1.5 px-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-800"
            >
              <option value="">Hospital Knowledge Base (All Guidelines)</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id}) - {p.department}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            {/* Mode Switcher */}
            <button
              type="button"
              onClick={() => setDirectLlm(false)}
              className={`py-1 px-3 rounded-lg text-xs font-semibold transition ${
                !directLlm
                  ? "bg-rose-900 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Strict RAG (Grounding)
            </button>
            <button
              type="button"
              onClick={() => setDirectLlm(true)}
              className={`py-1 px-3 rounded-lg text-xs font-semibold transition ${
                directLlm
                  ? "bg-amber-700 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Direct LLM (General)
            </button>
          </div>
        </div>

        {/* Attached PDF Banner */}
        {attachedPdf && (
          <div className="px-6 py-2 bg-rose-50 border-b border-rose-200 flex items-center justify-between text-xs text-rose-950 font-medium">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-rose-800" />
              <span>Session PDF Attached: <strong>{attachedPdf.name}</strong> (Queries strictly isolated to this file)</span>
            </div>
            <button
              onClick={handleDetachPdf}
              className="text-rose-800 hover:text-rose-950 text-xs font-semibold underline cursor-pointer"
            >
              Detach
            </button>
          </div>
        )}

        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center mb-4">
                <Sparkles className="w-6 h-6 text-rose-800" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">Clinical Decision Support AI</h3>
              <p className="text-xs text-slate-500 leading-relaxed mb-6">
                Query verified institutional guidelines, review longitudinal patient charts, or chat with attached clinical PDFs with NLI claim verification.
              </p>
              <div className="grid grid-cols-1 gap-2 w-full text-left">
                <button
                  onClick={() => setInput("What are the empirical antibiotic guidelines for severe community-acquired pneumonia?")}
                  className="p-3 rounded-xl bg-slate-50 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 text-xs text-slate-800 transition"
                >
                  "What are the empirical antibiotic guidelines for severe community-acquired pneumonia?"
                </button>
                <button
                  onClick={() => setInput("Summarize Rahul Sharma's latest vitals, inflammatory markers, and radiology findings.")}
                  className="p-3 rounded-xl bg-slate-50 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 text-xs text-slate-800 transition"
                >
                  "Summarize Rahul Sharma's latest vitals, inflammatory markers, and radiology findings."
                </button>
              </div>
            </div>
          ) : (
            messages.map((m) => {
              const isUser = m.role === "user";
              return (
                <div key={m.id} className={`flex gap-3 w-full ${isUser ? "justify-end" : "justify-start"}`}>
                  {!isUser && (
                    <div className="w-8 h-8 rounded-xl bg-rose-900 flex items-center justify-center text-white shrink-0 shadow-xs mt-1">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`${
                    isUser
                      ? "max-w-[75%] sm:max-w-md md:max-w-lg lg:max-w-xl bg-rose-900 text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-xs text-sm font-medium leading-relaxed"
                      : "w-full max-w-4xl lg:max-w-5xl bg-white border border-slate-200/90 rounded-2xl rounded-tl-sm p-6 md:p-7 shadow-xs text-slate-900 text-[14px] leading-relaxed space-y-4"
                  }`}>
                    {/* Metadata Header for Assistant (Strict RAG mode only) */}
                    {!isUser && (
                      (!selectedPatientId && m.confidence_score !== null && m.confidence_score !== undefined && Boolean(m.confidence_level)) ||
                      (m.sources && m.sources.length > 0)
                    ) && (
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-1 border-b border-slate-100 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-800 text-xs">Clinical Decision Assistant</span>
                          {!selectedPatientId && m.confidence_score !== null && m.confidence_score !== undefined && Boolean(m.confidence_level) && (
                            <ConfidencePill
                              level={m.confidence_level}
                              score={m.confidence_score}
                            />
                          )}
                        </div>

                        {m.sources && m.sources.length > 0 && (
                          <button
                            type="button"
                            onClick={() => setSelectedSources(m.sources || [])}
                            className="text-[11px] font-semibold text-rose-900 hover:text-rose-700 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100/80 border border-rose-200/70 transition-colors cursor-pointer"
                          >
                            <FileSearch className="w-3.5 h-3.5" />
                            <span>{m.sources.length} Sources Cited</span>
                          </button>
                        )}
                      </div>
                    )}

                    {/* Message Body with Markdown Rendering */}
                    {isUser ? (
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    ) : (
                      <div className="text-slate-850 text-[14px] leading-relaxed">
                        <MarkdownRenderer content={m.content} />
                      </div>
                    )}
                  </div>

                  {isUser && (
                    <div className="w-8 h-8 rounded-xl bg-slate-200 flex items-center justify-center text-slate-700 shrink-0 mt-1 shadow-2xs">
                      <UserIcon className="w-4 h-4" />
                    </div>
                  )}
                </div>
              );
            })
          )}
          {isLoading && (
            <div className="flex gap-3.5 items-center text-slate-500 text-xs">
              <div className="w-8 h-8 rounded-xl bg-rose-900/10 border border-rose-200 flex items-center justify-center text-rose-800">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <span>Searching clinical vector index & synthesizing evidence...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-slate-200 bg-white">
          <form onSubmit={handleSend} className="relative flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handlePdfUpload}
              accept=".pdf"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingPdf}
              title="Attach PDF for Session-Isolated RAG"
              className="p-2.5 rounded-xl border border-slate-200 text-slate-600 hover:text-rose-900 hover:bg-rose-50 transition"
            >
              <Paperclip className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={toggleVoiceInput}
              title={isRecording ? "Stop Recording" : "Voice Dictation"}
              className={`p-2.5 rounded-xl border transition ${
                isRecording
                  ? "bg-rose-900 text-white border-rose-900 animate-pulse"
                  : "border-slate-200 text-slate-600 hover:text-rose-900 hover:bg-rose-50"
              }`}
            >
              {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                selectedPatient
                  ? `Ask about ${selectedPatient.name}'s chart, vitals, labs, or guidelines...`
                  : "Ask a clinical question, guideline protocol, or patient name..."
              }
              className="flex-1 py-3 px-4 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-800 focus:bg-white transition"
            />

            {isLoading ? (
              <button
                type="button"
                onClick={onStopGeneration}
                title="Stop generation"
                className="p-3 bg-red-600 hover:bg-red-700 text-white rounded-xl shadow-md transition flex items-center justify-center cursor-pointer"
              >
                <Square className="w-4 h-4 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="p-3 bg-rose-900 hover:bg-rose-800 text-white rounded-xl shadow-md shadow-rose-950/20 transition disabled:opacity-40"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </form>
        </div>
      </div>

      {/* Right Supporting Sources Side Panel */}
      <div className="w-80 h-full overflow-y-auto bg-slate-50 p-5 border-l border-slate-200 flex flex-col">
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-rose-900" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Supporting Sources</h3>
          </div>
          <span className="text-[11px] font-semibold text-slate-500">{selectedSources.length} Cited</span>
        </div>

        {selectedSources.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-400">
            <FileSearch className="w-8 h-8 mb-2 opacity-50 text-slate-400" />
            <p className="text-xs">No citations for the current message.</p>
            <p className="text-[11px] text-slate-400 mt-1">Grounding evidence cards will appear here during Strict RAG.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {selectedSources.map((src, idx) => {
              const citationId = src.citation_id || idx + 1;
              return (
                <div
                  key={idx}
                  className="p-3.5 bg-white rounded-xl border border-slate-200 shadow-xs hover:border-rose-300 transition"
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="flex items-start gap-1.5 min-w-0">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-rose-50 text-rose-900 border border-rose-200 shrink-0">
                        [{citationId}]
                      </span>
                      <h4 className="text-xs font-bold text-slate-900 leading-snug break-words">{src.title}</h4>
                    </div>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200 shrink-0">
                      Pg {src.page || 1}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                    <span>Section:</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-100/70 border border-slate-200/80 font-semibold text-slate-800 text-[10px]">
                      {src.section || "Clinical Assessment"}
                    </span>
                  </div>

                  {src.supporting_text && (
                    <p className="text-[11px] text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-150 leading-relaxed mb-2.5 line-clamp-4">
                      "{src.supporting_text}"
                    </p>
                  )}

                  {src.view_url && (
                    <a
                      href={getApiUrl(src.view_url)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-rose-900 hover:text-rose-700"
                    >
                      <span>Open Verified Source</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
