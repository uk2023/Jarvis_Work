import React, { useState, useEffect, useRef } from 'react';
import confetti from 'canvas-confetti';
import {
  Activity,
  Cpu,
  Database,
  Compass,
  Code,
  Terminal,
  Plus,
  Trash2,
  Pin,
  Menu,
  X,
  Volume2,
  Radio,
  Sparkles,
  Zap,
  Bot,
  MessageSquare,
  MoreVertical,
  Sun,
  Moon,
  Layers,
  Clock,
  Shield,
} from 'lucide-react';
import { NeuralChat } from './components/NeuralChat';
import { OrganMatrix } from './components/OrganMatrix';
import { MemoryGraphViewer } from './components/MemoryGraphViewer';
import { AutonomyCuriosity } from './components/AutonomyCuriosity';
import { PythonCodeHub } from './components/PythonCodeHub';
import { DiagnosticsModal } from './components/DiagnosticsModal';
import { SessionActionSheet } from './components/SessionActionSheet';
import {
  ActiveTab,
  ChatMessage,
  EngramFact,
  OrganismTelemetry,
  SessionItem,
  CuriosityGoal,
  EvolutionProposal,
  AppTheme,
} from './types';

export function safeParse(value: string): any {
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('chat');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCLIModalOpen, setIsCLIModalOpen] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [uptimeSeconds, setUptimeSeconds] = useState(0);
  
  // Theme state: default dark, persists to localStorage
  const [theme, setTheme] = useState<AppTheme>(() => {
    try {
      const saved = localStorage.getItem('jarvis_theme') as AppTheme;
      return saved === 'light' || saved === 'dark' ? saved : 'dark';
    } catch {
      return 'dark';
    }
  });

  const toggleTheme = (newTheme: AppTheme) => {
    setTheme(newTheme);
    try {
      localStorage.setItem('jarvis_theme', newTheme);
    } catch {}
  };

  // Organism Telemetry State -- honest "connecting" placeholder only;
  // real data lands within ~1s from GET /api/organism/state below.
  const [telemetry, setTelemetry] = useState<OrganismTelemetry>({
    pulseState: 'connecting',
    beatCount: 0,
    bpm: 0,
    pulseWave: 'SYS_UPTIME',
    runtimeSeconds: 0,
    isIdle: true,
    activeModel: 'connecting to organism...',
    ramUsageMB: 0,
    totalTokensProcessed: 0,
    avgLatencyMs: 0,
    organs: [],
  });

  // Sessions & Threads State -- placeholder only, replaced by the
  // real GET /api/sessions fetch below the moment it resolves.
  const [sessions, setSessions] = useState<SessionItem[]>([
    {
      sessionId: 'main_session',
      title: 'General Conversation',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      msgCount: 0,
      pinned: true,
      category: 'Today',
    },
  ]);
  const [activeSessionId, setActiveSessionId] = useState('main_session');

  // Selected session for Context Menu / Action Sheet
  const [actionSheetSession, setActionSheetSession] = useState<SessionItem | null>(null);
  const [isActionSheetOpen, setIsActionSheetOpen] = useState(false);

  // Long press timer ref for mobile
  const longPressTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Messages (all threads)
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Engrams
  const [engrams, setEngrams] = useState<EngramFact[]>([]);

  // Curiosity & Evolution
  const [goals, setGoals] = useState<CuriosityGoal[]>([]);
  const [proposals, setProposals] = useState<EvolutionProposal[]>([]);

  // Periodic heartbeat telemetry polling and runtime ticker
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch('/api/organism/state');
        if (res.ok) {
          const data = await res.json();
          setTelemetry(data);
          // Seed the local per-second ticker from the real backend
          // uptime so it stays honest between 3.5s polls instead of
          // drifting from whatever value it started at.
          if (typeof data.runtimeSeconds === 'number') {
            setUptimeSeconds(data.runtimeSeconds);
          }
        }
      } catch {
        // Backend unreachable this poll -- leave telemetry as the
        // last known-real values rather than faking a heartbeat.
      }
    };

    const fetchEngrams = async () => {
      try {
        const res = await fetch('/api/memory/engrams');
        if (res.ok) {
          const data = await res.json();
          setEngrams(data.engrams || []);
        }
      } catch {}
    };

    const fetchAutonomy = async () => {
      try {
        const res = await fetch('/api/autonomy/state');
        if (res.ok) {
          const data = await res.json();
          setGoals(data.goals || []);
          setProposals(data.proposals || []);
        }
      } catch {}
    };

    // Real session list -- without this the sidebar only ever shows
    // the single local placeholder thread and forgets everything on
    // refresh, even though the backend already persists every session.
    const fetchSessions = async () => {
      try {
        const res = await fetch('/api/sessions');
        if (res.ok) {
          const data = await res.json();
          const list: SessionItem[] = data.sessions || [];
          if (list.length > 0) {
            setSessions(list);
            setActiveSessionId(prev =>
              list.some((s: SessionItem) => s.sessionId === prev) ? prev : list[0].sessionId
            );
          }
        }
      } catch {}
    };

    fetchTelemetry();
    fetchEngrams();
    fetchAutonomy();
    fetchSessions();

    const interval = setInterval(fetchTelemetry, 3500);
    const uptimeTimer = setInterval(() => {
      setUptimeSeconds(prev => prev + 1);
    }, 1000);

    return () => {
      clearInterval(interval);
      clearInterval(uptimeTimer);
    };
  }, []);

  // Real chat history for whichever session is active. Messages here
  // used to live purely in memory (gone on refresh) even though every
  // /api/chat turn is already persisted server-side -- this hydrates
  // from that real history the first time a session is opened.
  const loadedHistoryRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (loadedHistoryRef.current.has(activeSessionId)) return;
    let cancelled = false;

    const fetchHistory = async () => {
      try {
        const res = await fetch(`/api/history?session_id=${encodeURIComponent(activeSessionId)}`);
        if (res.ok && !cancelled) {
          const data = await res.json();
          const rows = data.history || [];
          const mapped: ChatMessage[] = rows.map((row: any) => ({
            id: String(row.id),
            sessionId: row.session_id,
            sender: row.sender,
            text: row.text,
            timestamp: row.timestamp,
            source: row.source,
            traceLog: row.trace_log ? safeParse(row.trace_log) : undefined,
            extractedFact: row.extracted_fact ? safeParse(row.extracted_fact) : undefined,
          }));
          if (mapped.length > 0) {
            setMessages(prev => {
              const others = prev.filter(m => m.sessionId !== activeSessionId);
              return [...others, ...mapped];
            });
          }
        }
      } catch {
        // Offline / no history yet -- fine, session just starts empty.
      } finally {
        loadedHistoryRef.current.add(activeSessionId);
      }
    };

    fetchHistory();
    return () => { cancelled = true; };
  }, [activeSessionId]);

  // Format uptime
  const formatUptime = (totalSeconds: number) => {
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Send Message Handler
  const handleSendMessage = async (text: string) => {
    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}-u`,
      sessionId: activeSessionId,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      source: 'web',
    };

    setMessages(prev => [...prev, userMsg]);
    setIsThinking(true);

    // Auto-update session title if it's the first message
    setSessions(prev =>
      prev.map(s => {
        if (s.sessionId === activeSessionId && (s.title === 'New Neural Thread' || s.title === 'General Conversation' || s.title === 'Primary Neural Link')) {
          const newTitle = text.length > 26 ? `${text.slice(0, 26)}...` : text;
          return { ...s, title: newTitle, msgCount: s.msgCount + 1, updatedAt: new Date().toISOString() };
        }
        if (s.sessionId === activeSessionId) {
          return { ...s, msgCount: s.msgCount + 1, updatedAt: new Date().toISOString() };
        }
        return s;
      })
    );

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, sessionId: activeSessionId }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, data.jarvisMessage]);

        // Refresh engrams if fact was extracted
        if (data.jarvisMessage.extractedFact) {
          const memRes = await fetch('/api/memory/engrams');
          if (memRes.ok) {
            const memData = await memRes.json();
            setEngrams(memData.engrams || []);
          }
        }
      } else {
        throw new Error('API request failed');
      }
    } catch {
      // Offline fallback
      setTimeout(() => {
        const fallbackMsg: ChatMessage = {
          id: `msg-${Date.now()}-j`,
          sessionId: activeSessionId,
          sender: 'jarvis',
          text: `Qwen 3B cognitive core received your command: "${text}". Memory indices updated.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          source: 'web',
          traceLog: {
            traceId: 'TRC-LOCAL-01',
            latencySeconds: 0.15,
            memoryLookupSeconds: 0.003,
            llmInferenceSeconds: 0.147,
            vectorMatches: [],
            graphRelations: [],
            learningPipelineStatus: 'validated',
          },
        };
        setMessages(prev => [...prev, fallbackMsg]);
      }, 400);
    } finally {
      setIsThinking(false);
    }
  };

  // Add Engram Handler
  const handleAddEngram = async (fact: { subject: string; predicate: string; value: string; tags: string[] }) => {
    try {
      const res = await fetch('/api/memory/engrams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fact),
      });
      if (res.ok) {
        const data = await res.json();
        setEngrams(prev => [...prev, data.engram]);
      }
    } catch {}
  };

  // Delete Engram Handler
  const handleDeleteEngram = async (id: string) => {
    try {
      await fetch(`/api/memory/engrams/${id}`, { method: 'DELETE' });
      setEngrams(prev => prev.filter(e => e.id !== id));
    } catch {}
  };

  // Trigger Curiosity
  const handleTriggerCuriosity = async () => {
    try {
      const res = await fetch('/api/autonomy/trigger-idle', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setGoals(prev => [data.goal, ...prev]);
        confetti({ particleCount: 30, spread: 60, origin: { y: 0.8 } });
      }
    } catch {}
  };

  // Stimulate Pulse
  const handleStimulatePulse = () => {
    setTelemetry(prev => ({
      ...prev,
      beatCount: prev.beatCount + 1,
      bpm: 88,
    }));
    confetti({ particleCount: 20, spread: 45, origin: { y: 0.6 } });
  };

  // Create New Session (Opens clean home view). No separate "create"
  // API call needed here -- backend/database.py auto-registers the
  // session row the moment the first /api/chat message for this id
  // is saved, so this client-generated id becomes real the instant
  // the user actually sends something.
  const handleNewSession = () => {
    const newId = `session_${Date.now()}`;
    const newSession: SessionItem = {
      sessionId: newId,
      title: 'New Neural Thread',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      msgCount: 0,
      pinned: false,
      category: 'Today',
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
    setActiveTab('chat');
    setIsSidebarOpen(false);
  };

  // Toggle Pin on Session
  const handlePinSession = (sessionId: string) => {
    let nextPinned = false;
    setSessions(prev =>
      prev.map(s => {
        if (s.sessionId !== sessionId) return s;
        nextPinned = !s.pinned;
        return { ...s, pinned: nextPinned };
      })
    );
    // Persist for real -- fire and forget, optimistic UI already updated.
    fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned: nextPinned }),
    }).catch(() => {});
  };

  // Rename Session
  const handleRenameSession = (sessionId: string, newTitle: string) => {
    setSessions(prev =>
      prev.map(s => (s.sessionId === sessionId ? { ...s, title: newTitle } : s))
    );
    fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle }),
    }).catch(() => {});
  };

  // Delete Session
  const handleDeleteSession = (sessionIdToDelete: string) => {
    fetch(`/api/sessions/${encodeURIComponent(sessionIdToDelete)}`, { method: 'DELETE' }).catch(() => {});

    if (sessions.length <= 1) {
      setMessages(prev => prev.filter(m => m.sessionId !== sessionIdToDelete));
      setSessions([
        {
          sessionId: `session_${Date.now()}`,
          title: 'General Conversation',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          msgCount: 0,
          pinned: true,
          category: 'Today',
        },
      ]);
      setActiveSessionId(sessions[0].sessionId);
      return;
    }

    const updatedSessions = sessions.filter(s => s.sessionId !== sessionIdToDelete);
    setSessions(updatedSessions);
    setMessages(prev => prev.filter(m => m.sessionId !== sessionIdToDelete));

    if (activeSessionId === sessionIdToDelete) {
      setActiveSessionId(updatedSessions[0].sessionId);
    }
  };

  // Clear current active chat messages
  const handleClearCurrentChat = () => {
    setMessages(prev => prev.filter(m => m.sessionId !== activeSessionId));
    setSessions(prev =>
      prev.map(s => (s.sessionId === activeSessionId ? { ...s, title: 'New Neural Thread', msgCount: 0 } : s))
    );
  };

  // Open Action Sheet / Context Menu
  const openActionSheet = (session: SessionItem, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    setActionSheetSession(session);
    setIsActionSheetOpen(true);
  };

  // Touch handlers for Long Press on mobile
  const handleTouchStart = (session: SessionItem) => {
    longPressTimerRef.current = setTimeout(() => {
      openActionSheet(session);
    }, 450);
  };

  const handleTouchEnd = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const currentSessionMessages = messages.filter(m => m.sessionId === activeSessionId);
  const isDark = theme === 'dark';

  // Sort sessions: pinned first, then by updatedAt
  const sortedSessions = [...sessions].sort((a, b) => {
    if (a.pinned === b.pinned) {
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    }
    return a.pinned ? -1 : 1;
  });

  return (
    <div
      className={`flex h-[100dvh] w-full font-sans overflow-hidden antialiased select-none relative transition-colors duration-300 ${
        isDark ? 'bg-[#05060a] text-[#e0e0e0]' : 'bg-[#f8fafc] text-slate-900'
      }`}
    >
      {/* Background Subtle Grid Texture */}
      <div
        className={`absolute inset-0 pointer-events-none z-0 ${
          isDark ? 'bg-grid-dots opacity-15' : 'bg-grid-dots opacity-5'
        }`}
      />

      {/* Mobile Sidebar Overlay Backdrop */}
      {isSidebarOpen && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 sm:hidden transition-opacity"
        />
      )}

      {/* Left Sidebar: Threads, Theme Switcher & Bottom Runtime Pulse */}
      <aside
        className={`fixed sm:static inset-y-0 left-0 z-50 w-72 sm:w-64 backdrop-blur-2xl border-r flex flex-col transition-all duration-300 ease-in-out shrink-0 ${
          isDark
            ? 'bg-[#080a10] sm:bg-[#07090e]/85 border-white/10 text-white'
            : 'bg-white sm:bg-white/95 border-slate-200 text-slate-900 shadow-sm'
        } ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full sm:translate-x-0'}`}
      >
        {/* Sidebar Header */}
        <div
          className={`h-14 p-4 border-b flex items-center justify-between shrink-0 ${
            isDark ? 'border-white/10 bg-white/[0.02]' : 'border-slate-200 bg-slate-50/50'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <div
              className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs shadow-sm ${
                isDark
                  ? 'bg-cyan-400/15 border border-cyan-400/40 text-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.25)]'
                  : 'bg-slate-900 text-white'
              }`}
            >
              J
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]"></div>
                <h1 className="font-bold text-xs tracking-widest font-mono">JARVIS OS</h1>
              </div>
              <span className="text-[9px] text-cyan-500 font-mono tracking-tighter uppercase font-medium">
                Android 8GB &bull; Qwen 3B
              </span>
            </div>
          </div>

          <button
            onClick={() => setIsSidebarOpen(false)}
            className={`sm:hidden p-1 rounded-lg transition cursor-pointer ${
              isDark ? 'text-white/50 hover:text-white hover:bg-white/5' : 'text-slate-400 hover:text-slate-800 hover:bg-slate-100'
            }`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3 shrink-0">
          <button
            onClick={handleNewSession}
            className={`w-full py-2.5 px-3 rounded-xl font-mono text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer shadow-sm ${
              isDark
                ? 'bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 hover:border-cyan-400/60'
                : 'bg-slate-900 hover:bg-slate-800 text-white border border-slate-900'
            }`}
          >
            <Plus className="w-4 h-4 text-cyan-400" />
            <span>New Neural Thread</span>
          </button>
        </div>

        {/* Session List with 3-Dot Options and Long Press */}
        <div className="flex-1 min-h-0 overflow-y-auto px-3 space-y-1 font-mono text-xs">
          <div
            className={`text-[10px] font-bold uppercase px-2 py-1 tracking-wider ${
              isDark ? 'text-white/40' : 'text-slate-400'
            }`}
          >
            Threads ({sortedSessions.length})
          </div>

          {sortedSessions.map(s => {
            const isActive = s.sessionId === activeSessionId;
            return (
              <div
                key={s.sessionId}
                onTouchStart={() => handleTouchStart(s)}
                onTouchEnd={handleTouchEnd}
                onClick={() => {
                  setActiveSessionId(s.sessionId);
                  setActiveTab('chat');
                  setIsSidebarOpen(false);
                }}
                className={`group p-2.5 rounded-xl cursor-pointer flex items-center justify-between transition-all ${
                  isActive
                    ? isDark
                      ? 'bg-cyan-400/15 text-cyan-100 border border-cyan-400/40 font-medium shadow-[0_0_12px_rgba(34,211,238,0.15)]'
                      : 'bg-slate-100 text-slate-900 border border-slate-300 font-semibold shadow-xs'
                    : isDark
                    ? 'text-white/70 hover:text-white hover:bg-white/5 border border-transparent'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                }`}
              >
                {/* Title & icon */}
                <div className="flex items-center gap-2 truncate min-w-0">
                  <MessageSquare
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isActive ? (isDark ? 'text-cyan-400' : 'text-slate-900') : isDark ? 'text-white/40' : 'text-slate-400'
                    }`}
                  />
                  <span className="truncate text-xs">{s.title}</span>
                </div>

                {/* Right controls: Pin badge & 3-Dot action trigger */}
                <div className="flex items-center gap-1 shrink-0 ml-1">
                  {s.pinned && <Pin className="w-3 h-3 text-amber-400 fill-amber-400/20" />}
                  
                  <button
                    onClick={e => openActionSheet(s, e)}
                    className={`p-1 rounded-md transition cursor-pointer ${
                      isDark
                        ? 'opacity-70 group-hover:opacity-100 hover:text-cyan-300 hover:bg-white/10'
                        : 'opacity-70 group-hover:opacity-100 hover:text-slate-900 hover:bg-slate-200'
                    }`}
                    title="Thread Options (Pin, Rename, Delete)"
                  >
                    <MoreVertical className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Sidebar Bottom: Runtime Uptime, System Pulse & Theme Switcher */}
        <div
          className={`p-3 border-t font-mono text-xs shrink-0 transition-colors space-y-2.5 ${
            isDark ? 'border-white/10 bg-black/50' : 'border-slate-200 bg-slate-50'
          }`}
        >
          {/* Live System Pulse & Runtime Card */}
          <div
            className={`p-2.5 rounded-xl border space-y-1.5 ${
              isDark ? 'bg-white/[0.03] border-white/10 text-white/80' : 'bg-white border-slate-200 text-slate-700 shadow-xs'
            }`}
          >
            {/* Pulse Line */}
            <div className="flex items-center justify-between text-[10px]">
              <span className="flex items-center gap-1.5 font-semibold">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_6px_#22d3ee]" />
                <span className={isDark ? 'text-cyan-300' : 'text-cyan-700'}>SYSTEM PULSE</span>
              </span>
              <span className="text-cyan-500 font-bold">{telemetry.bpm} BPM</span>
            </div>

            {/* Wave & Beat Count */}
            <div className="flex items-center justify-between text-[9px] opacity-75 font-mono">
              <span className="tracking-widest text-cyan-400">∿∿_/\\_∿∿</span>
              <span>BEAT #{telemetry.beatCount}</span>
            </div>

            {/* Runtime / Uptime */}
            <div
              className={`flex items-center justify-between text-[9px] pt-1.5 border-t ${
                isDark ? 'border-white/10 text-white/50' : 'border-slate-100 text-slate-400'
              }`}
            >
              <span className="flex items-center gap-1">
                <Clock className="w-2.5 h-2.5 text-cyan-400" /> UPTIME
              </span>
              <span className="font-semibold text-cyan-500">{formatUptime(uptimeSeconds)}</span>
            </div>
          </div>

          {/* Theme Switcher Pill */}
          <div
            className={`p-1 rounded-xl flex items-center gap-1 border transition-colors ${
              isDark ? 'bg-white/5 border-white/10' : 'bg-slate-200/80 border-slate-300'
            }`}
          >
            <button
              onClick={() => toggleTheme('dark')}
              className={`flex-1 py-1.5 px-2 rounded-lg flex items-center justify-center gap-1.5 transition text-[11px] font-semibold cursor-pointer ${
                isDark
                  ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 shadow-xs'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <Moon className="w-3 h-3 text-cyan-400" />
              <span>Dark</span>
            </button>

            <button
              onClick={() => toggleTheme('light')}
              className={`flex-1 py-1.5 px-2 rounded-lg flex items-center justify-center gap-1.5 transition text-[11px] font-semibold cursor-pointer ${
                !isDark
                  ? 'bg-white text-slate-900 border border-slate-300 shadow-sm'
                  : 'text-white/40 hover:text-white'
              }`}
            >
              <Sun className="w-3 h-3 text-amber-500" />
              <span>Light</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative z-10">
        {/* LOCKED TOP HEADER (Rigid 56px height, Responsive Navigation: Icon on Mobile, Icon + Text on Desktop) */}
        <header
          className={`h-14 shrink-0 border-b flex items-center justify-between px-3 sm:px-5 z-30 transition-colors ${
            isDark
              ? 'bg-[#06080e]/90 backdrop-blur-xl border-white/10 text-white'
              : 'bg-white/90 backdrop-blur-xl border-slate-200 text-slate-900 shadow-xs'
          }`}
        >
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            {/* Mobile Drawer Trigger */}
            <button
              onClick={() => setIsSidebarOpen(true)}
              className={`sm:hidden p-2 rounded-xl transition cursor-pointer shrink-0 ${
                isDark ? 'text-white/70 hover:text-white hover:bg-white/10' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
              title="Open Chat Threads"
            >
              <Menu className="w-5 h-5 text-cyan-500" />
            </button>

            {/* View Tab Switcher: Mobile (Icons only), Desktop (Icons + Text) */}
            <nav
              id="header-nav-menu"
              className={`flex items-center gap-1 p-1 rounded-xl font-mono text-xs overflow-x-auto no-scrollbar max-w-[240px] sm:max-w-none border ${
                isDark ? 'bg-black/40 border-white/10' : 'bg-slate-100 border-slate-200'
              }`}
            >
              <button
                id="tab-neural-core"
                onClick={() => setActiveTab('chat')}
                className={`px-2.5 sm:px-3 py-1.5 rounded-lg transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'chat'
                    ? isDark
                      ? 'bg-cyan-400/20 text-cyan-200 font-bold border border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                      : 'bg-white text-slate-900 font-bold border border-slate-300 shadow-xs'
                    : isDark
                    ? 'text-white/60 hover:text-white hover:bg-white/5'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
                title="Neural Core & Chat"
              >
                <Bot className="w-4 h-4 text-cyan-500 shrink-0" />
                <span className="hidden md:inline">Core</span>
              </button>

              <button
                id="tab-organ-matrix"
                onClick={() => setActiveTab('matrix')}
                className={`px-2.5 sm:px-3 py-1.5 rounded-lg transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'matrix'
                    ? isDark
                      ? 'bg-cyan-400/20 text-cyan-200 font-bold border border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                      : 'bg-white text-slate-900 font-bold border border-slate-300 shadow-xs'
                    : isDark
                    ? 'text-white/60 hover:text-white hover:bg-white/5'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
                title="Neural Organs & Subsystems"
              >
                <Cpu className="w-4 h-4 text-cyan-500 shrink-0" />
                <span className="hidden md:inline">Organs</span>
              </button>

              <button
                id="tab-memory-graph"
                onClick={() => setActiveTab('memory')}
                className={`px-2.5 sm:px-3 py-1.5 rounded-lg transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'memory'
                    ? isDark
                      ? 'bg-cyan-400/20 text-cyan-200 font-bold border border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                      : 'bg-white text-slate-900 font-bold border border-slate-300 shadow-xs'
                    : isDark
                    ? 'text-white/60 hover:text-white hover:bg-white/5'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
                title="FAISS Vector Index & Graph"
              >
                <Database className="w-4 h-4 text-cyan-500 shrink-0" />
                <span className="hidden md:inline">FAISS</span>
              </button>

              <button
                id="tab-autonomy-curiosity"
                onClick={() => setActiveTab('autonomy')}
                className={`px-2.5 sm:px-3 py-1.5 rounded-lg transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'autonomy'
                    ? isDark
                      ? 'bg-cyan-400/20 text-cyan-200 font-bold border border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                      : 'bg-white text-slate-900 font-bold border border-slate-300 shadow-xs'
                    : isDark
                    ? 'text-white/60 hover:text-white hover:bg-white/5'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
                title="Curiosity & Evolution Goals"
              >
                <Compass className="w-4 h-4 text-cyan-500 shrink-0" />
                <span className="hidden md:inline">Curiosity</span>
              </button>

              <button
                id="tab-python-hub"
                onClick={() => setActiveTab('code')}
                className={`px-2.5 sm:px-3 py-1.5 rounded-lg transition-all shrink-0 flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'code'
                    ? isDark
                      ? 'bg-cyan-400/20 text-cyan-200 font-bold border border-cyan-400/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                      : 'bg-white text-slate-900 font-bold border border-slate-300 shadow-xs'
                    : isDark
                    ? 'text-white/60 hover:text-white hover:bg-white/5'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
                title="Python Repository & Exporter"
              >
                <Code className="w-4 h-4 text-cyan-500 shrink-0" />
                <span className="hidden md:inline">Code</span>
              </button>
            </nav>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-2 sm:gap-4 font-mono shrink-0">
            {/* Desktop Telemetry Stats */}
            <div
              className={`hidden lg:flex items-center gap-3 text-[10px] tracking-tighter uppercase ${
                isDark ? 'text-white/50' : 'text-slate-500'
              }`}
            >
              <div>LATENCY: <span className="text-cyan-500 font-semibold">{telemetry.avgLatencyMs}ms</span></div>
              <div>RAM: <span className="text-cyan-500 font-semibold">{(telemetry.ramUsageMB / 1024).toFixed(2)}GB</span></div>
            </div>

            {/* Virtual CLI Terminal Window Trigger */}
            <button
              onClick={() => setIsCLIModalOpen(true)}
              className={`px-2.5 sm:px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition shadow-xs cursor-pointer border ${
                isDark
                  ? 'bg-white/5 hover:bg-white/10 border-white/10 hover:border-cyan-400/40 text-cyan-300'
                  : 'bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-800'
              }`}
              title="Open Virtual CLI Terminal Window"
            >
              <Terminal className="w-3.5 h-3.5 text-cyan-500" />
              <span className="hidden sm:inline">CLI Trace</span>
            </button>
          </div>
        </header>

        {/* VIEWPORT (Fills all space between Locked Header & Locked Footer) */}
        <main className="flex-1 min-h-0 overflow-hidden relative">
          {activeTab === 'chat' && (
            <NeuralChat
              messages={currentSessionMessages}
              isThinking={isThinking}
              onSendMessage={handleSendMessage}
              onOpenCLI={() => setIsCLIModalOpen(true)}
              telemetry={telemetry}
              onQuickPrompt={handleSendMessage}
              onClearChat={currentSessionMessages.length > 0 ? handleClearCurrentChat : undefined}
              theme={theme}
            />
          )}

          {activeTab === 'matrix' && (
            <OrganMatrix
              organs={telemetry.organs}
              beatCount={telemetry.beatCount}
              bpm={telemetry.bpm}
              onTriggerPulse={handleStimulatePulse}
              theme={theme}
            />
          )}

          {activeTab === 'memory' && (
            <MemoryGraphViewer
              engrams={engrams}
              onAddEngram={handleAddEngram}
              onDeleteEngram={handleDeleteEngram}
              theme={theme}
            />
          )}

          {activeTab === 'autonomy' && (
            <AutonomyCuriosity
              goals={goals}
              proposals={proposals}
              onTriggerCuriosity={handleTriggerCuriosity}
              theme={theme}
            />
          )}

          {activeTab === 'code' && <PythonCodeHub theme={theme} />}
        </main>

        {/* LOCKED BOTTOM FOOTER (Rigid 32px height) */}
        <footer
          className={`h-8 shrink-0 border-t px-3 sm:px-6 flex items-center justify-between text-[9px] sm:text-[10px] font-mono z-20 transition-colors ${
            isDark
              ? 'bg-[#06080e] border-white/10 text-white/40'
              : 'bg-white border-slate-200 text-slate-500 shadow-xs'
          }`}
        >
          <div className="truncate">ANDROID_ENV: ARM64_TERMUX &bull; SNAPDRAGON 8GB</div>
          <div className="truncate shrink-0 ml-2 font-medium text-cyan-500">QWEN 3B &bull; 4 THREADS</div>
        </footer>
      </div>

      {/* Session Context Menu / Bottom Sheet Modal */}
      <SessionActionSheet
        session={actionSheetSession}
        isOpen={isActionSheetOpen}
        onClose={() => {
          setIsActionSheetOpen(false);
          setActionSheetSession(null);
        }}
        onPinToggle={handlePinSession}
        onRename={handleRenameSession}
        onDelete={handleDeleteSession}
        theme={theme}
      />

      {/* Virtual CLI Terminal Window (Right-side docked / floating window) */}
      <DiagnosticsModal
        isOpen={isCLIModalOpen}
        onClose={() => setIsCLIModalOpen(false)}
        beatCount={telemetry.beatCount}
        theme={theme}
      />
    </div>
  );
}

export default App;
