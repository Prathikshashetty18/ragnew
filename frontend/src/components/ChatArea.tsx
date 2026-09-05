import React, { useState, useRef, useEffect } from "react";
import {
  Send, Paperclip, Mic, MicOff,
  FileText, ExternalLink, Sparkles, User as UserIcon, Bot,
  FileSearch
} from "lucide-react";
import { ConfidencePill } from "./ConfidencePill";
import type { ChatMessage, Patient, SourceCard } from "../types";

interface ChatAreaProps {
  messages: ChatMessage[];
  onSendMessage: (query: string, directLlm: boolean, attachedDocId?: number) => void;
  isLoading: boolean;
  patients: Patient[];
  selectedPatientId: string | null;
  onSelectPatient: (id: string | null) => void;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  onSendMessage,
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
    if (lastMsg && lastMsg.role === "assistant" && lastMsg.sources && lastMsg.sources.length > 0) {
      setSelectedSources(lastMsg.sources);
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
      const res = await fetch("http://127.0.0.1:8000/api/upload", {
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

  const toggleVoiceInput = () => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Speech recognition is not supported in this browser.");
      return;
    }

    if (isRecording) {
      setIsRecording(false);
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => setIsRecording(true);
    recognition.onend = () => setIsRecording(false);
    recognition.onerror = () => setIsRecording(false);

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };

    recognition.start();
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
              onClick={() => setAttachedPdf(null)}
              className="text-rose-800 hover:text-rose-950 text-xs font-semibold underline"
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
                <div key={m.id} className={`flex gap-3.5 ${isUser ? "justify-end" : "justify-start"}`}>
                  {!isUser && (
                    <div className="w-8 h-8 rounded-xl bg-rose-900 flex items-center justify-center text-white shrink-0 shadow-sm mt-0.5">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed ${
                    isUser
                      ? "bg-rose-900 text-white rounded-tr-none shadow-sm"
                      : "bg-white border border-slate-200 text-slate-900 rounded-tl-none shadow-sm"
                  }`}>
                    {/* Metadata Header for Assistant */}
                    {!isUser && (
                      <div className="flex items-center justify-between gap-4 pb-2.5 mb-2.5 border-b border-slate-100 text-xs">
                        <div className="flex items-center gap-2">
                          {(m.confidence_level || m.confidence_score !== undefined) && (
                            <ConfidencePill
                              level={m.confidence_level}
                              score={m.confidence_score}
                            />
                          )}
                        </div>

                        {m.sources && m.sources.length > 0 && (
                          <button
                            onClick={() => setSelectedSources(m.sources || [])}
                            className="text-[11px] font-semibold text-rose-900 hover:text-rose-700 flex items-center gap-1 underline"
                          >
                            <FileSearch className="w-3.5 h-3.5" />
                            {m.sources.length} Sources
                          </button>
                        )}
                      </div>
                    )}

                    {/* Markdown / Text Content with High-Contrast Text */}
                    <div className="prose prose-sm max-w-none text-slate-900 whitespace-pre-wrap font-normal">
                      {m.content}
                    </div>
                  </div>

                  {isUser && (
                    <div className="w-8 h-8 rounded-xl bg-slate-200 flex items-center justify-center text-slate-700 shrink-0 mt-0.5">
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

            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="p-3 bg-rose-900 hover:bg-rose-800 text-white rounded-xl shadow-md shadow-rose-950/20 transition disabled:opacity-40"
            >
              <Send className="w-4 h-4" />
            </button>
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
            {selectedSources.map((src, idx) => (
              <div
                key={idx}
                className="p-3.5 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-rose-300 transition"
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <h4 className="text-xs font-bold text-slate-900 leading-snug">{src.title}</h4>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-900 border border-rose-200 shrink-0">
                    Pg {src.page || 1}
                  </span>
                </div>

                <div className="text-[11px] text-slate-500 font-medium mb-2">
                  Section: <span className="text-slate-700">{src.section || "Clinical Assessment"}</span>
                </div>

                {src.supporting_text && (
                  <p className="text-[11px] text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 leading-relaxed mb-2.5 line-clamp-3">
                    "{src.supporting_text}"
                  </p>
                )}

                {src.view_url && (
                  <a
                    href={`http://127.0.0.1:8000${src.view_url}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-rose-900 hover:text-rose-700"
                  >
                    <span>Open Verified Source</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
