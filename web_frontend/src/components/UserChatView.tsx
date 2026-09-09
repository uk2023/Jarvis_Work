import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clock,
  Check,
  CheckCheck,
  Copy,
  Mic,
  MicOff,
  Volume2,
  RefreshCw,
  History,
  Shield,
  HelpCircle,
  Radio,
} from 'lucide-react';
import { ChatMessage, AppTheme } from '../types';
import { AudioStreamClient } from '../api/audioStream';

interface UserChatViewProps {
  theme: AppTheme;
  activeSessionId: string;
  activeSessionTitle: string;
  messages: ChatMessage[];
  onSendMessage: (text: string) => Promise<void>;
  onLoadEarlierMessages: () => void;
  hasOlderMessages: boolean;
  isThinking: boolean;
  thinkingSeconds: number;
  isAdmin?: boolean;
  onUnlockOperator?: () => void;
}

export function UserChatView({
  theme,
  activeSessionId,
  activeSessionTitle,
  messages,
  onSendMessage,
  onLoadEarlierMessages,
  hasOlderMessages,
  isThinking,
  thinkingSeconds,
  isAdmin = false,
  onUnlockOperator,
}: UserChatViewProps) {
  const [inputVal, setInputVal] = useState('');
  const [expandedThoughtIds, setExpandedThoughtIds] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [streamStatus, setStreamStatus] = useState<'idle' | 'connecting' | 'streaming' | 'processing' | 'error'>('idle');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isFirstLoadRef = useRef(true);
  const audioStreamerRef = useRef<AudioStreamClient | null>(null);

  const isDark = theme === 'dark';

  // Audio Streamer setup for /ws/audio FastAPI Server-side STT
  useEffect(() => {
    audioStreamerRef.current = new AudioStreamClient({
      onPartialText: (partial) => {
        setInputVal(partial);
      },
      onFinalText: (final) => {
        if (final.trim()) {
          setInputVal(final.trim());
          handleSend(final.trim());
        }
        setIsRecording(false);
      },
      onStatusChange: (status) => {
        setStreamStatus(status);
        setIsRecording(status === 'streaming' || status === 'connecting');
      },
      onError: (err) => {
        console.warn('[UserChat] Audio stream error:', err);
        setIsRecording(false);
      },
    });

    return () => {
      audioStreamerRef.current?.stopStreaming();
    };
  }, []);

  // Scroll to bottom on initial load, session switch, and when new messages arrive (WhatsApp-style systematic loading)
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: isFirstLoadRef.current ? 'auto' : 'smooth',
      });
      isFirstLoadRef.current = false;
    }
  }, [messages.length, activeSessionId, isThinking]);

  // Adjust textarea height dynamically without jumping or clipping
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 28), 160)}px`;
    }
  }, [inputVal]);

  const toggleThought = (id: string) => {
    setExpandedThoughtIds(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSend = async (customText?: string) => {
    const text = (customText !== undefined ? customText : inputVal).trim();
    if (!text || isThinking) return;

    setInputVal('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    await onSendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFocus = () => {
    // When mobile virtual keyboard pops up, keep input visible
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 250);
  };

  const toggleMic = async () => {
    if (isRecording) {
      audioStreamerRef.current?.stopStreaming();
      setIsRecording(false);
      setStreamStatus('idle');
    } else {
      setIsRecording(true);
      const ok = await audioStreamerRef.current?.startStreaming();
      if (!ok) {
        setIsRecording(false);
        setStreamStatus('error');
      }
    }
  };

  const speakText = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 0.95;
      window.speechSynthesis.speak(utterance);
    }
  };

  // WhatsApp-style Grouping by Date
  const groupedMessages: { dateLabel: string; msgs: ChatMessage[] }[] = [];
  messages.forEach(msg => {
    const label = msg.dateLabel || 'Today';
    const lastGroup = groupedMessages[groupedMessages.length - 1];
    if (lastGroup && lastGroup.dateLabel === label) {
      lastGroup.msgs.push(msg);
    } else {
      groupedMessages.push({ dateLabel: label, msgs: [msg] });
    }
  });

  return (
    <div className="h-full flex flex-col relative overflow-hidden">
      {/* ------------------------------------------------------------- */}
      {/* CHAT SESSION SUB-HEADER (Current thread topic indicator)       */}
      {/* ------------------------------------------------------------- */}
      <div
        className={`h-11 px-3 sm:px-6 border-b flex items-center justify-between shrink-0 z-10 transition-colors ${
          isDark
            ? 'bg-[#080b14]/95 backdrop-blur-md border-white/10 text-slate-200'
            : 'bg-white/95 backdrop-blur-md border-slate-200 text-slate-800'
        }`}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1 mr-2">
          <span className="w-2 h-2 rounded-full bg-brand-500 shrink-0" />
          <h2 className="font-semibold text-xs tracking-tight truncate">
            {activeSessionTitle}
          </h2>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 font-mono shrink-0">
          <span className="hidden md:inline">Groq openai/gpt-oss-120b & Native Pipeline</span>
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/30 text-xs whitespace-nowrap">
            SYNAPSE READY
          </span>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* SCROLLABLE CHAT CANVAS (WhatsApp-like Date Grouped Stream)     */}
      {/* ------------------------------------------------------------- */}
      <div
        ref={chatContainerRef}
        className={`flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-4 space-y-4 ${
          isDark ? 'bg-[#060810]' : 'bg-[#F8FAFC]'
        }`}
      >
        {/* Load Earlier Messages Button (WhatsApp History Style) */}
        {hasOlderMessages && (
          <div className="flex justify-center pt-2 pb-1">
            <button
              onClick={onLoadEarlierMessages}
              className={`px-3 py-1.5 rounded-full border text-xs font-medium flex items-center gap-1.5 transition cursor-pointer shadow-xs ${
                isDark
                  ? 'bg-white/[0.04] hover:bg-white/[0.08] border-white/10 text-brand-300'
                  : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <History className="w-3.5 h-3.5 text-brand-500" />
              <span>Load earlier conversation messages</span>
            </button>
          </div>
        )}

        {/* Empty state when no messages */}
        {messages.length === 0 && (
          <div className="max-w-md mx-auto my-auto py-10 text-center space-y-5">
            <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
              <div
                className="absolute inset-0 rounded-full border-2 border-brand-400/30 animate-spin"
                style={{ animationDuration: '8s' }}
              />
              <div
                className="absolute inset-2 rounded-full border border-dashed border-brand-300/40 animate-spin"
                style={{ animationDuration: '14s', animationDirection: 'reverse' }}
              />
              <div className="w-10 h-10 rounded-full bg-brand-500/20 border border-brand-400 flex items-center justify-center shadow-[0_0_20px_rgba(34,211,238,0.4)]">
                <div className="w-4 h-4 rounded-full bg-brand-400 shadow-[0_0_10px_#22d3ee] animate-pulse" />
              </div>
            </div>

            <div className="space-y-1.5">
              <h2 className="text-lg font-bold tracking-tight text-slate-800 dark:text-slate-100">
                Good day. How may I assist you?
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
                Autonomous cognitive organism with vector memory, Hinglish phonetic tolerance, and local neural intelligence.
              </p>
            </div>

            {/* Interactive Starter Prompts (Rich guest questions about JARVIS) */}
            <div className="grid grid-cols-1 gap-2 text-left max-w-sm mx-auto pt-2">
              {[
                'Tell me about JARVIS and what you can do',
                'Explain your 10 internal cognitive organs',
                'What is your current cognitive status and memory health?',
                'Tell me about personal developer preferences & setup',
              ].map((starter, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(starter)}
                  className={`p-2.5 rounded-xl border text-xs text-left transition cursor-pointer group ${
                    isDark
                      ? 'bg-white/[0.02] hover:bg-brand-500/10 border-white/10 hover:border-brand-400/40 text-slate-300 hover:text-brand-200'
                      : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700 shadow-xs'
                  }`}
                >
                  <span className="font-medium">{starter}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Date Grouped Stream */}
        {groupedMessages.map((group, groupIdx) => (
          <div key={`group-${groupIdx}`} className="space-y-3">
            {/* Clean Floating Date Divider Badge */}
            <div className="flex justify-center relative my-4 z-0">
              <span
                className={`px-3 py-0.5 rounded-full text-xs font-semibold tracking-wide uppercase shadow-xs ${
                  isDark
                    ? 'bg-[#121829] border border-white/10 text-slate-300'
                    : 'bg-slate-200 border border-slate-300 text-slate-700'
                }`}
              >
                {group.dateLabel}
              </span>
            </div>

            {/* Group's Messages */}
            {group.msgs.map(msg => {
              const isUser = msg.sender === 'user';
              const isExpanded = !!expandedThoughtIds[msg.id];
              const isCopied = copiedId === msg.id;

              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    isUser ? 'items-end' : 'items-start'
                  } max-w-2xl ${isUser ? 'ml-auto' : 'mr-auto'} space-y-1`}
                >
                  {/* Claude-like Thinking Process Accordion (Jarvis Only) */}
                  {!isUser && msg.thinkingProcess && (
                    <div className="w-full max-w-xl">
                      <button
                        onClick={() => toggleThought(msg.id)}
                        className={`px-2.5 py-1 rounded-xl border text-xs font-mono flex items-center gap-2 transition cursor-pointer ${
                          isDark
                            ? 'bg-white/[0.03] hover:bg-white/[0.06] border-white/10 text-brand-300'
                            : 'bg-slate-100 hover:bg-slate-200/80 border-slate-200 text-slate-700'
                        }`}
                      >
                        <Sparkles className="w-3.5 h-3.5 text-brand-500" />
                        <span>Thought for {msg.thinkingDurationSeconds || 1.1}s</span>
                        {isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5 ml-auto text-slate-400" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 ml-auto text-slate-400" />
                        )}
                      </button>

                      {isExpanded && (
                        <div
                          className={`mt-1 p-3 rounded-xl border text-xs font-mono space-y-1.5 leading-relaxed ${
                            isDark
                              ? 'bg-black/50 border-white/10 text-slate-300'
                              : 'bg-slate-100/90 border-slate-200 text-slate-700'
                          }`}
                        >
                          <div className="text-xs uppercase font-bold tracking-wider text-brand-500 mb-1">
                            Cognitive Deliberation Steps:
                          </div>
                          {msg.thinkingProcess.map((step, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                              <span className="text-brand-500 font-bold">&bull;</span>
                              <span>{step}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* WhatsApp-like Message Bubble with Tail & Safe text wrapping */}
                  <div
                    className={`relative px-4 py-2.5 text-sm leading-relaxed max-w-[92%] sm:max-w-xl break-words [overflow-wrap:anywhere] ${
                      isUser
                        ? isDark
                          ? 'bg-brand-600 text-white rounded-2xl rounded-br-xs shadow-md shadow-brand-950/40'
                          : 'bg-brand-700 text-white rounded-2xl rounded-br-xs shadow-xs font-normal'
                        : isDark
                        ? 'bg-[#101524] border border-white/10 text-slate-100 rounded-2xl rounded-bl-xs shadow-sm'
                        : 'bg-white border border-slate-300 text-slate-900 rounded-2xl rounded-bl-xs shadow-xs font-normal'
                    }`}
                  >
                    <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{msg.text}</p>

                    {/* Bubble Bottom Metas: Timestamp & WhatsApp Double Checkmarks */}
                    <div
                      className={`mt-1 flex items-center justify-end gap-1.5 text-xs select-none ${
                        isUser
                          ? 'text-brand-100'
                          : 'text-slate-500 dark:text-slate-400 font-mono'
                      }`}
                    >
                      <span>{msg.timestamp}</span>

                      {/* WhatsApp Double Checkmark (for user sent messages) */}
                      {isUser && (
                        <CheckCheck className="w-3.5 h-3.5 text-brand-200 stroke-[2.5]" />
                      )}

                      {/* Jarvis Action buttons */}
                      {!isUser && (
                        <div className="flex items-center gap-1.5 ml-2">
                          <button
                            onClick={() => speakText(msg.text)}
                            className="hover:text-brand-500 transition cursor-pointer p-0.5"
                            title="Read aloud"
                          >
                            <Volume2 className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => handleCopy(msg.id, msg.text)}
                            className="hover:text-brand-500 transition cursor-pointer p-0.5"
                            title="Copy text"
                          >
                            {isCopied ? (
                              <Check className="w-3 h-3 text-emerald-500" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ))}

        {/* Live Claude-like Thinking Bubble (During response generation) */}
        {isThinking && (
          <div className="max-w-md mr-auto space-y-1">
            <div
              className={`p-3 rounded-2xl border flex items-center gap-2.5 text-xs font-mono animate-pulse ${
                isDark
                  ? 'bg-brand-950/20 border-brand-500/30 text-brand-300'
                  : 'bg-brand-50 border-brand-200 text-brand-800'
              }`}
            >
              <div className="w-2 h-2 rounded-full bg-brand-400 animate-ping" />
              <span>JARVIS is formulating response ({thinkingSeconds.toFixed(1)}s)...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ------------------------------------------------------------- */}
      {/* LOCKED WHATSAPP & AI STUDIO-INSPIRED BOTTOM INPUT BAR         */}
      {/* ------------------------------------------------------------- */}
      <footer
        className={`p-2.5 sm:p-3.5 border-t shrink-0 z-20 transition-colors ${
          isDark
            ? 'bg-[#080b14]/95 backdrop-blur-md border-white/10'
            : 'bg-white/95 backdrop-blur-md border-slate-200 shadow-[0_-2px_10px_rgba(0,0,0,0.03)]'
        }`}
      >
        <div className="max-w-3xl mx-auto space-y-2">
          {/* Live Audio Streaming Feedback */}
          {isRecording && (
            <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-brand-500/15 border border-brand-400/40 text-brand-300 text-xs font-mono animate-pulse">
              <div className="flex items-center gap-2">
                <Radio className="w-3.5 h-3.5 text-brand-400 animate-spin" />
                <span>
                  {streamStatus === 'connecting'
                    ? 'Connecting to /ws/audio streaming channel...'
                    : 'Streaming raw audio to server Whisper STT (Termux/FastAPI)...'}
                </span>
              </div>
              <span className="text-xs text-brand-400 font-bold uppercase">LIVE MIC</span>
            </div>
          )}

          {/* AI Studio & WhatsApp Hybrid Production Input Card */}
          <div
            className={`w-full rounded-2xl border transition-all duration-200 shadow-sm ${
              isDark
                ? 'bg-[#0e1322]/95 border-white/15 focus-within:border-brand-400 focus-within:ring-1 focus-within:ring-brand-500/30'
                : 'bg-white border-slate-300 focus-within:border-brand-600 focus-within:ring-1 focus-within:ring-brand-500/20'
            }`}
          >
            {/* Top: Auto-expanding Textarea - cleanly resizes with multi-line without button displacement */}
            <div className="p-3 pb-1">
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                onKeyDown={handleKeyDown}
                onFocus={handleFocus}
                placeholder="Message JARVIS (supports Hinglish)..."
                disabled={isThinking}
                className={`w-full bg-transparent resize-none text-sm outline-none placeholder:text-slate-400 leading-relaxed break-words overflow-y-auto block ${
                  isDark ? 'text-slate-100' : 'text-slate-900'
                }`}
                style={{ minHeight: '28px', maxHeight: '160px' }}
              />
            </div>

            {/* Bottom Action Strip: Clean left metadata + Right anchored controls that never jump */}
            <div className="flex items-center justify-between px-3 py-2 pt-1 border-t border-slate-100 dark:border-white/5 text-xs">
              <div className="flex items-center gap-2 text-xs text-slate-400 font-mono select-none">
                <span className="hidden sm:inline">Hinglish ready</span>
                <span className="text-slate-500 dark:text-slate-600 hidden sm:inline">&bull;</span>
                <span className="text-xs text-slate-400">Shift+Enter for newline</span>
              </div>

              {/* Anchored Action Controls: Voice Mic + Send */}
              <div className="flex items-center gap-1.5 ml-auto">
                <button
                  type="button"
                  onClick={toggleMic}
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition cursor-pointer shrink-0 ${
                    isRecording
                      ? 'bg-rose-500 text-white animate-pulse'
                      : isDark
                      ? 'text-slate-400 hover:text-brand-400 hover:bg-white/10'
                      : 'text-slate-500 hover:text-brand-600 hover:bg-slate-100'
                  }`}
                  title={isRecording ? 'Listening...' : 'Voice input'}
                >
                  {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>

                <button
                  type="button"
                  onClick={() => handleSend()}
                  disabled={!inputVal.trim() || isThinking}
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-all shrink-0 cursor-pointer ${
                    inputVal.trim() && !isThinking
                      ? 'bg-brand-600 hover:bg-brand-500 text-white shadow-sm scale-100'
                      : isDark
                      ? 'bg-white/5 text-slate-600 border border-white/5 cursor-not-allowed'
                      : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  }`}
                  title="Send message"
                >
                  <Send className="w-3.5 h-3.5 ml-0.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
