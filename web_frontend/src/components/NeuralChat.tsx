import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Send,
  Paperclip,
  Mic,
  MicOff,
  Volume2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Database,
  GitFork,
  CheckCircle2,
  Clock,
  SpellCheck,
  Bot,
  User,
  Zap,
  RotateCcw,
} from 'lucide-react';
import { ChatMessage, OrganismTelemetry, AppTheme } from '../types';
import { OrganismCore } from './OrganismCore';

interface NeuralChatProps {
  messages: ChatMessage[];
  isThinking: boolean;
  onSendMessage: (text: string) => void;
  onOpenCLI: () => void;
  telemetry: OrganismTelemetry;
  onQuickPrompt: (prompt: string) => void;
  onClearChat?: () => void;
  theme?: AppTheme;
}

export const NeuralChat: React.FC<NeuralChatProps> = ({
  messages,
  isThinking,
  onSendMessage,
  onOpenCLI,
  telemetry,
  onQuickPrompt,
  onClearChat,
  theme = 'dark',
}) => {
  const [inputText, setInputText] = useState('');
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Track previous message count and active session to prevent unwanted auto-scroll
  const prevMsgCountRef = useRef(0);
  const initialLoadDoneRef = useRef(false);

  const isDark = theme === 'dark';

  // Precision scroll helper
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior, block: 'end' });
    }
  }, []);

  // On first load of the thread, immediately jump to the bottom
  useEffect(() => {
    if (!initialLoadDoneRef.current && messages.length > 0) {
      initialLoadDoneRef.current = true;
      // Instant shift on initial mount/open
      scrollToBottom('auto');
    }
  }, [messages.length, scrollToBottom]);

  // Only auto-scroll when a new message is appended or when thinking starts
  useEffect(() => {
    if (messages.length > prevMsgCountRef.current) {
      scrollToBottom('smooth');
    }
    prevMsgCountRef.current = messages.length;
  }, [messages.length, scrollToBottom]);

  // Auto-scroll when assistant is thinking
  useEffect(() => {
    if (isThinking) {
      scrollToBottom('smooth');
    }
  }, [isThinking, scrollToBottom]);

  // WhatsApp-like Keyboard viewport adjustment:
  // When mobile keyboard opens or when input gets focus, ensure the last chat bubble shifts up
  useEffect(() => {
    const handleViewportChange = () => {
      // Small timeout to allow keyboard transition to settle
      setTimeout(() => {
        scrollToBottom('smooth');
      }, 150);
    };

    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', handleViewportChange);
    }

    return () => {
      if (window.visualViewport) {
        window.visualViewport.removeEventListener('resize', handleViewportChange);
      }
    };
  }, [scrollToBottom]);

  const handleInputFocus = () => {
    setTimeout(() => {
      scrollToBottom('smooth');
    }, 200);
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed || isThinking) return;

    onSendMessage(trimmed);
    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const autoResizeTextarea = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
  };

  const speakText = (text: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 0.95;
    window.speechSynthesis.speak(utterance);
  };

  const toggleSpeechRecognition = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Speech Recognition is not supported by your current browser.');
      return;
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRec();
    recognition.lang = 'hi-IN';
    recognition.interimResults = false;

    if (!isListening) {
      setIsListening(true);
      recognition.start();

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInputText(prev => (prev ? `${prev} ${transcript}` : transcript));
        setIsListening(false);
      };

      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
    } else {
      setIsListening(false);
      recognition.stop();
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div
      id="neural-chat-container"
      className="flex flex-col h-full w-full min-h-0 overflow-hidden relative"
    >
      {/* Messages Scroll Area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-4 space-y-4 overscroll-contain"
      >
        {!hasMessages ? (
          /* Empty / Animated JARVIS Logo Homepage State */
          <div className="h-full flex items-center justify-center">
            <OrganismCore
              telemetry={telemetry}
              onOpenCLI={onOpenCLI}
              onQuickPrompt={onQuickPrompt}
              theme={theme}
            />
          </div>
        ) : (
          /* Active Chat Thread */
          <div className="max-w-3xl mx-auto space-y-4 w-full pb-2">
            {/* Conversation Header Action */}
            <div
              className={`flex items-center justify-between pb-2 border-b text-[11px] font-mono ${
                isDark ? 'border-white/5 text-white/40' : 'border-slate-200 text-slate-400'
              }`}
            >
              <span className="flex items-center gap-1.5 font-medium">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                <span>NEURAL THREAD ACTIVE</span>
              </span>
              {onClearChat && (
                <button
                  onClick={onClearChat}
                  className={`flex items-center gap-1 transition px-2.5 py-1 rounded-lg cursor-pointer ${
                    isDark
                      ? 'hover:text-cyan-300 hover:bg-white/5'
                      : 'hover:text-cyan-600 hover:bg-slate-100 text-slate-500'
                  }`}
                  title="Clear conversation"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset Thread</span>
                </button>
              )}
            </div>

            {messages.map(msg => {
              const isJarvis = msg.sender === 'jarvis';
              const trace = msg.traceLog;
              const isTraceOpen = expandedTraceId === msg.id;

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-2.5 sm:gap-3 max-w-full ${
                    isJarvis ? 'mr-auto justify-start' : 'ml-auto justify-end'
                  }`}
                >
                  {/* Jarvis Avatar */}
                  {isJarvis && (
                    <div
                      className={`w-7 h-7 sm:w-8 sm:h-8 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 shadow-sm ${
                        isDark
                          ? 'bg-cyan-950/70 border border-cyan-400/40 text-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                          : 'bg-slate-900 border border-slate-700 text-cyan-300'
                      }`}
                    >
                      <Bot className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                    </div>
                  )}

                  {/* Message Bubble Column */}
                  <div
                    className={`flex flex-col gap-1.5 max-w-[88%] sm:max-w-[80%] ${
                      !isJarvis ? 'items-end' : 'items-start'
                    }`}
                  >
                    {/* Message Card */}
                    <div
                      className={`p-3.5 sm:p-4 rounded-2xl text-xs sm:text-[13px] leading-relaxed shadow-sm font-sans break-words ${
                        isJarvis
                          ? isDark
                            ? 'bg-[#0f121d] border border-white/10 text-white/90 rounded-tl-sm'
                            : 'bg-white border border-slate-200 text-slate-800 rounded-tl-sm shadow-sm'
                          : isDark
                          ? 'bg-[#152336] border border-cyan-500/40 text-cyan-50 rounded-tr-sm shadow-[0_0_15px_rgba(34,211,238,0.1)]'
                          : 'bg-slate-900 text-white rounded-tr-sm shadow-sm'
                      }`}
                    >
                      <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.text}</p>

                      {/* Extracted Fact Badge */}
                      {msg.extractedFact && (
                        <div
                          className={`mt-2.5 pt-2 border-t flex items-start gap-1.5 text-[10px] font-mono p-2 rounded-xl border ${
                            isDark
                              ? 'border-white/10 bg-cyan-400/10 text-cyan-200 border-cyan-400/30'
                              : 'border-slate-200 bg-sky-50 text-sky-800 border-sky-200'
                          }`}
                        >
                          <Zap className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                          <span className="break-all">
                            Engram: <strong>{msg.extractedFact.subject}</strong> ➔{' '}
                            <em>{msg.extractedFact.predicate}</em> ➔ <u>{msg.extractedFact.value}</u>
                          </span>
                        </div>
                      )}

                      {/* Footer Info & TTS Button */}
                      {isJarvis && (
                        <div
                          className={`mt-2.5 flex items-center justify-between text-[10px] pt-1.5 border-t font-mono ${
                            isDark ? 'border-white/5 text-white/40' : 'border-slate-100 text-slate-400'
                          }`}
                        >
                          <span>{msg.timestamp}</span>
                          <button
                            onClick={() => speakText(msg.text)}
                            className={`p-1 rounded-lg transition cursor-pointer ${
                              isDark
                                ? 'hover:text-cyan-300 hover:bg-white/10'
                                : 'hover:text-cyan-600 hover:bg-slate-100'
                            }`}
                            title="Play voice"
                          >
                            <Volume2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Cognitive Diagnostics Trace Accordion */}
                    {isJarvis && trace && (
                      <div
                        className={`w-full border rounded-xl overflow-hidden font-mono text-[10px] shadow-sm ${
                          isDark ? 'bg-black/40 border-white/10' : 'bg-slate-50 border-slate-200'
                        }`}
                      >
                        <button
                          onClick={() => setExpandedTraceId(isTraceOpen ? null : msg.id)}
                          className={`w-full flex items-center justify-between px-3 py-1.5 transition cursor-pointer ${
                            isDark
                              ? 'bg-white/[0.02] hover:bg-white/[0.06] text-cyan-300'
                              : 'bg-white hover:bg-slate-100 text-cyan-700'
                          }`}
                        >
                          <div className="flex items-center gap-1.5 truncate">
                            <Cpu className="w-3 h-3 text-cyan-400 shrink-0" />
                            <span className="font-semibold uppercase tracking-wider text-[9px] sm:text-[10px]">
                              Cognitive Trace
                            </span>
                            <span className={isDark ? 'text-white/40 text-[9px]' : 'text-slate-400 text-[9px]'}>
                              ({trace.latencySeconds.toFixed(2)}s)
                            </span>
                          </div>
                          <div className={isDark ? 'text-white/50 shrink-0' : 'text-slate-400 shrink-0'}>
                            {isTraceOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </div>
                        </button>

                        <AnimatePresence>
                          {isTraceOpen && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className={`p-3 space-y-2 border-t text-[9px] sm:text-[10px] ${
                                isDark
                                  ? 'border-white/10 text-white/80 bg-black/30'
                                  : 'border-slate-200 text-slate-700 bg-white'
                              }`}
                            >
                              {/* Timing metrics */}
                              <div
                                className={`grid grid-cols-2 gap-2 pb-1.5 border-b ${
                                  isDark ? 'border-white/10 text-white/60' : 'border-slate-200 text-slate-500'
                                }`}
                              >
                                <div className="flex items-center gap-1 truncate">
                                  <Database className="w-2.5 h-2.5 text-cyan-400 shrink-0" />
                                  <span>FAISS: {trace.memoryLookupSeconds.toFixed(3)}s</span>
                                </div>
                                <div className="flex items-center gap-1 truncate">
                                  <Clock className="w-2.5 h-2.5 text-green-400 shrink-0" />
                                  <span>Qwen 3B: {trace.llmInferenceSeconds.toFixed(2)}s</span>
                                </div>
                              </div>

                              {/* Typo corrections */}
                              {trace.typosCorrected && trace.typosCorrected.length > 0 && (
                                <div
                                  className={`flex items-start gap-1 p-1.5 rounded-lg border ${
                                    isDark
                                      ? 'text-yellow-300/90 bg-yellow-500/10 border-yellow-500/20'
                                      : 'text-amber-800 bg-amber-50 border-amber-200'
                                  }`}
                                >
                                  <SpellCheck className="w-3 h-3 text-yellow-500 shrink-0 mt-0.5" />
                                  <span className="break-all">
                                    Normalized:{' '}
                                    {trace.typosCorrected.map((t, idx) => (
                                      <span key={idx} className="underline decoration-dotted mr-1 font-semibold">
                                        "{t.raw}" ➔ "{t.corrected}"
                                      </span>
                                    ))}
                                  </span>
                                </div>
                              )}

                              {/* Vector Matches */}
                              <div>
                                <div className="text-cyan-500 dark:text-cyan-300 font-bold mb-0.5 flex items-center gap-1">
                                  <Database className="w-2.5 h-2.5" /> Vector Matches ({trace.vectorMatches.length}):
                                </div>
                                {trace.vectorMatches.length > 0 ? (
                                  <ul className="space-y-0.5 pl-2.5 border-l border-cyan-400/40">
                                    {trace.vectorMatches.map((m, i) => (
                                      <li key={i} className="break-words">
                                        <span className="font-semibold">{m.subject}</span> ➔ {m.predicate} ➔{' '}
                                        <span>{String(m.value)}</span>{' '}
                                        <span className="text-green-500 dark:text-green-400">
                                          ({(m.similarity * 100).toFixed(0)}%)
                                        </span>
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <div className={isDark ? 'text-white/40 italic pl-2.5' : 'text-slate-400 italic pl-2.5'}>
                                    0 vector recall
                                  </div>
                                )}
                              </div>

                              {/* Graph Relations */}
                              <div>
                                <div className="text-cyan-500 dark:text-cyan-300 font-bold mb-0.5 flex items-center gap-1">
                                  <GitFork className="w-2.5 h-2.5" /> Graph Relations ({trace.graphRelations.length}):
                                </div>
                                {trace.graphRelations.length > 0 ? (
                                  <ul className="space-y-0.5 pl-2.5 border-l border-cyan-400/40">
                                    {trace.graphRelations.map((g, i) => (
                                      <li key={i} className="break-words">
                                        ({g.subject}) ──[{g.predicate}]──&gt; ({g.target})
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <div className={isDark ? 'text-white/40 italic pl-2.5' : 'text-slate-400 italic pl-2.5'}>
                                    No graph edges
                                  </div>
                                )}
                              </div>

                              {/* Footer trace state */}
                              <div
                                className={`pt-1 flex items-center justify-between text-[8px] sm:text-[9px] ${
                                  isDark ? 'text-white/40' : 'text-slate-400'
                                }`}
                              >
                                <span className="flex items-center gap-1 text-green-500 dark:text-green-400 font-bold">
                                  <CheckCircle2 className="w-2.5 h-2.5" /> Pipeline Validated
                                </span>
                                <span>{trace.traceId}</span>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    )}
                  </div>

                  {/* User Avatar */}
                  {!isJarvis && (
                    <div
                      className={`w-7 h-7 sm:w-8 sm:h-8 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 ${
                        isDark
                          ? 'bg-white/10 border border-white/20 text-white/80'
                          : 'bg-slate-200 border border-slate-300 text-slate-700'
                      }`}
                    >
                      <User className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                    </div>
                  )}
                </motion.div>
              );
            })}

            {/* Thinking Status Indicator */}
            {isThinking && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-2.5 max-w-md mr-auto"
              >
                <div
                  className={`w-7 h-7 sm:w-8 sm:h-8 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                    isDark
                      ? 'bg-cyan-950/70 border border-cyan-400/40 text-cyan-300'
                      : 'bg-slate-900 text-cyan-300'
                  }`}
                >
                  <Bot className="w-3.5 h-3.5 animate-spin" style={{ animationDuration: '3s' }} />
                </div>
                <div
                  className={`px-3.5 py-2.5 rounded-2xl shadow-sm flex items-center gap-2.5 ${
                    isDark
                      ? 'bg-[#0f121d] border border-white/10 text-cyan-200'
                      : 'bg-white border border-slate-200 text-slate-700'
                  }`}
                >
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-300 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-200 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-[11px] sm:text-xs font-mono">
                    JARVIS synthesizing response...
                  </span>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* WHATSAPP-STYLE BOTTOM DOCK (Pinned to Bottom, Action Icons Fixed at Bottom-line, Textarea Expands Upwards) */}
      <div
        className={`shrink-0 border-t p-2 sm:p-3 z-20 transition-colors ${
          isDark
            ? 'bg-[#06080e]/95 backdrop-blur-2xl border-white/10'
            : 'bg-white/95 backdrop-blur-2xl border-slate-200 shadow-sm'
        }`}
      >
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex flex-col gap-1.5">
          {/* Main Input Bar Row: Container with Bottom Aligned Items */}
          <div className="flex items-end gap-2 w-full">
            {/* Input Capsule Box */}
            <div
              className={`flex-1 flex items-end rounded-2xl sm:rounded-3xl px-2.5 py-1.5 transition-all shadow-sm ${
                isDark
                  ? 'bg-white/[0.06] border border-white/15 focus-within:border-cyan-400/70 focus-within:shadow-[0_0_15px_rgba(34,211,238,0.15)]'
                  : 'bg-slate-100 border border-slate-300 focus-within:border-cyan-500 focus-within:bg-white focus-within:shadow-md'
              }`}
            >
              {/* Left Action Icons: Fixed at the bottom baseline (self-end) */}
              <div className="flex items-center gap-0.5 shrink-0 self-end mb-0.5">
                {/* Attachment Paperclip */}
                <button
                  type="button"
                  className={`w-8 h-8 rounded-xl flex items-center justify-center transition cursor-pointer ${
                    isDark
                      ? 'text-white/50 hover:text-cyan-300 hover:bg-white/10'
                      : 'text-slate-500 hover:text-cyan-600 hover:bg-slate-200'
                  }`}
                  title="Attach memory file or context"
                >
                  <Paperclip className="w-4 h-4" />
                </button>

                {/* Speech Recognition Mic */}
                <button
                  type="button"
                  onClick={toggleSpeechRecognition}
                  className={`w-8 h-8 rounded-xl flex items-center justify-center transition cursor-pointer ${
                    isListening
                      ? 'text-red-400 bg-red-500/20 animate-pulse'
                      : isDark
                      ? 'text-white/50 hover:text-cyan-300 hover:bg-white/10'
                      : 'text-slate-500 hover:text-cyan-600 hover:bg-slate-200'
                  }`}
                  title="Voice Speech Input (Hinglish Supported)"
                >
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              </div>

              {/* Textarea Input (Grows smoothly upward while icons stay pinned at bottom) */}
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputText}
                onChange={autoResizeTextarea}
                onKeyDown={handleKeyDown}
                onFocus={handleInputFocus}
                placeholder="Ask JARVIS (Hinglish & typos supported)..."
                className={`flex-1 bg-transparent border-none outline-none px-2.5 py-1 text-xs sm:text-[13px] font-sans resize-none max-h-36 min-h-[32px] overflow-y-auto leading-relaxed ${
                  isDark ? 'text-white placeholder-white/40' : 'text-slate-900 placeholder-slate-400'
                }`}
              />
            </div>

            {/* WhatsApp-Style Dedicated Circular Send Button (Fixed at Bottom-Right) */}
            <button
              type="submit"
              disabled={!inputText.trim() || isThinking}
              className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 self-end mb-0.5 transition-all transform active:scale-95 disabled:opacity-30 disabled:scale-100 disabled:shadow-none cursor-pointer shadow-md ${
                isDark
                  ? 'bg-cyan-400 hover:bg-cyan-300 text-black shadow-[0_0_12px_rgba(34,211,238,0.35)]'
                  : 'bg-slate-900 hover:bg-slate-800 text-white'
              }`}
              title="Send to JARVIS"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

          {/* Subtext info */}
          <div
            className={`flex items-center justify-between text-[9px] sm:text-[10px] px-2 font-mono ${
              isDark ? 'text-white/40' : 'text-slate-400'
            }`}
          >
            <span className="truncate">JARVIS 3B &bull; Android 8GB RAM</span>
            <button
              type="button"
              onClick={onOpenCLI}
              className={`flex items-center gap-1 cursor-pointer shrink-0 font-medium ${
                isDark ? 'text-cyan-400 hover:underline' : 'text-cyan-600 hover:underline'
              }`}
            >
              <Cpu className="w-2.5 h-2.5" /> CLI Trace
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
