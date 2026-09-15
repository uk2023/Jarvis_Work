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
<<<<<<< HEAD
  Clock,
  Shield,
=======
  FileCode,
  Phone,
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
} from 'lucide-react';
import { NeuralChat } from './components/NeuralChat';
import { OrganMatrix } from './components/OrganMatrix';
import { MemoryGraphViewer } from './components/MemoryGraphViewer';
import { AutonomyCuriosity } from './components/AutonomyCuriosity';
import { PythonCodeHub } from './components/PythonCodeHub';
import { DiagnosticsModal } from './components/DiagnosticsModal';
import { SessionActionSheet } from './components/SessionActionSheet';
import {
<<<<<<< HEAD
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
=======
  INITIAL_SESSIONS,
  INITIAL_MESSAGES_BY_SESSION,
  OLDER_ARCHIVED_MESSAGES,
} from './data/chatSessions';
import { HomeScreen } from './components/HomeScreen';
import { DashboardScreen } from './components/DashboardScreen';
import { VirtualCLIScreen } from './components/VirtualCLIScreen';
import { TraceInspectorScreen } from './components/TraceInspectorScreen';
import CodeBoxScreen from './components/CodeBoxScreen';
import VoiceCallScreen from './components/VoiceCallScreen';
import { prewarmVoice, unlockVoice } from './voice/jarvisVoice';
import OwnerLoginScreen from './components/OwnerLoginScreen';
import { loginRouteFromPath, applyRoutePath, clearRouteIds } from './routes/roleRoutes';
import { isReady, isReadyForRole } from './config/features';
import { UserChatView } from './components/UserChatView';
import { ChatThreadsSidebar } from './components/ChatThreadsSidebar';
import { StatusNotificationPopover } from './components/StatusNotificationPopover';
import { AuthModal } from './components/AuthModal';
import { SettingsModal } from './components/SettingsModal';
import { ProfileModal } from './components/ProfileModal';
>>>>>>> 90fbd2a (Save local project changes before branch checkout)

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

<<<<<<< HEAD
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
=======
  // AUTH STATE -- SINGLE SOURCE OF TRUTH (2026-09-13, UK: "koi bhi
  // password daalo to admin login ho jata hai", plus logout showing
  // wrong state). There were TWO competing auth stores: client.ts
  // holds the real backend-verified token in sessionStorage, while
  // this component independently trusted a localStorage marker called
  // 'jarvis_operator_token' -- and handleLoginSuccess wrote the
  // literal string 'operator-active' into it whenever no real token
  // existed. So the UI unlocked on a value it invented itself, with no
  // role attached and no server ever consulted; and because
  // localStorage outlives the sessionStorage token, the two disagreed
  // after a reload, which is the inconsistent logged-in/logged-out
  // display. Both now read from api.currentUser(), which only returns
  // a role when a real signed token from /api/auth/login is present.
  const [session, setSession] = useState(() => api.currentUser());
  const isAuthenticated = session.isLoggedIn;
  const role = session.role;                       // 'owner' | 'co_owner' | 'admin' | 'user' | 'guest'
  const isOwner = role === 'owner' || role === 'co_owner';
  const isAdmin = isOwner || role === 'admin';

  // SESSION-PERSISTENT UI STATE (2026-09-12, UK's explicit fix
  // request: minimizing Chrome on Android can cause the tab to be
  // discarded by the OS under memory pressure -- when reopened, the
  // page does a full reload and every useState here would normally
  // reset to its default, landing back on 'home' with the monitor/CLI
  // scroll and active section all lost. Read once from sessionStorage
  // on first render (survives a tab reload, cleared when the tab/
  // window actually closes -- the same scope as the auth session in
  // api/client.ts), then a single effect below keeps it in sync on
  // every change.
  // Voice needs warming before first use and unlocking on a real user
  // gesture -- see unlockVoice() in voice/jarvisVoice.ts for why the
  // browser silently drops utterances otherwise.
  // /owner is the owner and co-owner entrance. It is a separate SCREEN,
  // not a separate security boundary -- role is always checked
  // server-side against the session token. The route exists so the
  // owner is not forced through a signup form whose 3-character
  // username rule rejects "uk".
  const [ownerRoute] = useState(() => loginRouteFromPath() === 'owner');

  // Reflect the session in the address bar with an opaque id, so a
  // screenshot or a glance never exposes a username.
  useEffect(() => {
    const role = (session?.role as any) ?? 'guest';
    applyRoutePath(role);
  }, [session?.role]);

  useEffect(() => {
    prewarmVoice();
    const unlock = () => unlockVoice();
    window.addEventListener('pointerdown', unlock, { once: true });
    window.addEventListener('keydown', unlock, { once: true });
    return () => {
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
  }, []);

  const [currentView, setCurrentView] = useState<ConsoleView>(() => {
    try {
      return (sessionStorage.getItem('jarvis_ui_currentView') as ConsoleView) || 'home';
    } catch {
      return 'home';
    }
  });

  // Active dashboard section for sub-header navigation: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'
  const [dashboardSection, setDashboardSection] = useState<'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'>(() => {
    try {
      return (sessionStorage.getItem('jarvis_ui_dashboardSection') as any) || 'monitor';
    } catch {
      return 'monitor';
    }
  });

  useEffect(() => {
    try {
      sessionStorage.setItem('jarvis_ui_currentView', currentView);
      sessionStorage.setItem('jarvis_ui_dashboardSection', dashboardSection);
    } catch {
      // sessionStorage unavailable -- state simply won't survive a reload, no functional harm otherwise
    }
  }, [currentView, dashboardSection]);
>>>>>>> 90fbd2a (Save local project changes before branch checkout)

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
<<<<<<< HEAD
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
=======
    let timer: ReturnType<typeof setInterval> | null = null;
    if (isThinking) {
      setThinkingSeconds(0);
      timer = setInterval(() => {
        setThinkingSeconds(s => s + 0.1);
      }, 100);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isThinking]);

  const toggleTheme = () => {
    const nextTheme: AppTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    try {
      localStorage.setItem('jarvis_theme', nextTheme);
    } catch {}
  };

  const handleLoginSuccess = () => {
    // Re-read the REAL session that client.ts just persisted from the
    // backend's response. Nothing is invented here any more -- if the
    // backend did not return a valid token and role, the UI stays
    // logged out, which is the correct outcome for a failed login.
    const fresh = api.currentUser();
    setSession(fresh);
    try {
      localStorage.removeItem('jarvis_operator_token');  // clear the old fake marker if a previous build left one behind
    } catch {}
    // Only elevated roles have a dashboard to land on; a plain user
    // goes to chat, and a guest never reaches this handler at all.
    setCurrentView(fresh.role === 'owner' || fresh.role === 'co_owner' || fresh.role === 'admin' ? 'dashboard' : 'user_chat');
  };

  const handleLogout = () => {
    api.logout();
    setSession(api.currentUser());
    try {
      localStorage.removeItem('jarvis_operator_token');
    } catch {}
    setCurrentView('user_chat');
  };

  const navigateToTrace = (turnId: string) => {
    setSelectedTurnId(turnId);
    setCurrentView('inspector');
    setIsMobileNavOpen(false);
  };

  const navigateToCLI = () => {
    setCurrentView('cli');
    setIsMobileNavOpen(false);
  };

  // Chat Session Management Handlers (Claude-style)
  const handleNewChat = () => {
    const newId = `session-${Date.now()}`;
    const newSession: SessionItem = {
      sessionId: newId,
      title: 'New Conversation',
      createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      updatedAt: 'Just now',
      pinned: false,
      msgCount: 0,
      category: 'Today',
    };

    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
    setMessagesBySession(prev => ({
      ...prev,
      [newId]: [],
    }));
    setCurrentView('user_chat');
  };

  const handleDeleteSession = (sessionIdToDelete: string) => {
    const updated = sessions.filter(s => s.sessionId !== sessionIdToDelete);
    setSessions(updated);

    // Clean up messages
    setMessagesBySession(prev => {
      const next = { ...prev };
      delete next[sessionIdToDelete];
      return next;
    });

    if (activeSessionId === sessionIdToDelete) {
      if (updated.length > 0) {
        setActiveSessionId(updated[0].sessionId);
      } else {
        handleNewChat();
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
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

<<<<<<< HEAD
  // Send Message Handler
  const handleSendMessage = async (text: string) => {
=======
  const handleRenameSession = (sessionIdToRename: string, newTitle: string) => {
    setSessions(prev =>
      prev.map(s => (s.sessionId === sessionIdToRename ? { ...s, title: newTitle } : s))
    );
  };

  const handleTogglePinSession = (sessionIdToPin: string) => {
    setSessions(prev =>
      prev.map(s => (s.sessionId === sessionIdToPin ? { ...s, pinned: !s.pinned } : s))
    );
  };

  // Send message in current active session
  const handleSendMessage = async (text: string, realThinkingSteps?: { stage: string; content: string }[]) => {
    if (!text.trim() || isThinking) return;

>>>>>>> 90fbd2a (Save local project changes before branch checkout)
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

<<<<<<< HEAD
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
=======
      // NO FABRICATED STEPS (fixed 2026-09-15). This used to hardcode
      // the SAME four lines -- "Interpreted query semantics...",
      // "Surveyed FAISS vector episodic memory...", "Traversed
      // relationship graph...", "Formulated natural response" -- on
      // EVERY single reply, regardless of what actually happened. That
      // is fabricated telemetry, the same class of bug removed
      // elsewhere in this project (fake resource numbers, fake chat
      // fallbacks). It also explains why the message bubble's "Thought
      // for Xs" expander never matched the REAL streamed thinking
      // panel elsewhere on screen -- they were two disconnected
      // systems, one real, one invented.
      //
      // realThinkingSteps, when present, are the ACTUAL stages
      // UserChatView's extended-thinking stream captured for this
      // exact turn. Only real content goes on the message; if nothing
      // was captured (thinking was off, or produced nothing), the
      // expander simply does not appear -- no placeholder invented to
      // fill the gap.
      const jarvisMsg: ChatMessage = {
        id: res.messageId || `jarvis-${Date.now()}`,
        sessionId: activeSessionId,
        sender: 'jarvis',
        text: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        dateLabel: 'Today',
        source: 'web',
        thinkingDurationSeconds: Math.max(0.1, duration),
        thinkingProcess: realThinkingSteps && realThinkingSteps.length
          ? realThinkingSteps.map(s => s.content).filter(Boolean)
          : undefined,
      };

      setMessagesBySession(prev => ({
        ...prev,
        [activeSessionId]: [...(prev[activeSessionId] || []), jarvisMsg],
      }));
    } catch (err: any) {
      // NO FABRICATED REPLY (fixed 2026-09-15). This used to invent
      // "Understood, sir. I have processed '...' and verified
      // cognitive state consistency." on ANY failure -- network error,
      // backend down, timeout, anything. UK would read that as JARVIS
      // confidently confirming it did something, when the request had
      // actually failed outright. That is hallucination manufactured
      // by the frontend itself, not the model -- a failed request is a
      // failed request, shown as one.
      const duration = Number(((Date.now() - startTime) / 1000).toFixed(1));
      const errorMsg: ChatMessage = {
        id: `jarvis-error-${Date.now()}`,
        sessionId: activeSessionId,
        sender: 'jarvis',
        text: `Jawab nahi aaya -- ${err?.message || 'backend se connection nahi bana.'} `
             + `CLI mein JARVIS chal raha hai check karo.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        dateLabel: 'Today',
        source: 'web',
        thinkingDurationSeconds: Math.max(0.1, duration),
      };

      setMessagesBySession(prev => ({
        ...prev,
        [activeSessionId]: [...(prev[activeSessionId] || []), errorMsg],
      }));
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
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

  // On /owner: show the owner entrance until an owner/co-owner session
  // exists. Everything else in the app stays untouched.
  if (ownerRoute && session?.role !== 'owner' && session?.role !== 'co_owner') {
    return (
      <OwnerLoginScreen
        onAuthenticated={() => {
          clearRouteIds();
          setSession(api.currentUser());
        }}
        onBack={() => { window.location.href = '/'; }}
      />
    );
  }

  return (
    <div
      className={`flex h-[100dvh] w-full font-sans overflow-hidden antialiased select-none relative transition-colors duration-300 ${
        isDark ? 'bg-[#05060a] text-[#e0e0e0]' : 'bg-[#f8fafc] text-slate-900'
      }`}
    >
<<<<<<< HEAD
      {/* Background Subtle Grid Texture */}
      <div
        className={`absolute inset-0 pointer-events-none z-0 ${
          isDark ? 'bg-grid-dots opacity-15' : 'bg-grid-dots opacity-5'
        }`}
=======
      {/* ------------------------------------------------------------- */}
      {/* CLAUDE-STYLE CHAT THREADS SIDEBAR                             */}
      {/* ------------------------------------------------------------- */}
      <ChatThreadsSidebar
        theme={theme}
        isOpen={isMobileNavOpen}
        onClose={() => setIsMobileNavOpen(false)}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={id => {
          setActiveSessionId(id);
          setCurrentView('user_chat');
        }}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onTogglePinSession={handleTogglePinSession}
        onToggleTheme={toggleTheme}
        beatCount={beatCount}
        isAdmin={isAdmin}
        role={session?.role}
        displayName={session?.display_name || session?.username}
        onOpenProfileSettings={() => setIsProfileOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        onGoHome={() => setCurrentView('home')}
        currentView={currentView}
        onNavigateToView={view => setCurrentView(view)}
        onNavigateToCodebox={() => setCurrentView('codebox')}
        onLogout={handleLogout}
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
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
<<<<<<< HEAD
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
=======

            {/* CodeBox moved to the icon subheader (next to Virtual
                CLI) -- see the "5. CodeBox" block below, which replaced
                the old Organs button. Kept only here: nothing; this
                was the duplicate top-bar entry. */}

            {isReady('call') && (
            <button
              onClick={() => setCurrentView('call')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors"
              style={currentView === 'call' ? { backgroundColor: 'var(--jarvis-accent)', color: 'white' } : { color: 'var(--jarvis-text-muted)' }}
              title="Voice call"
            >
              <Phone className="w-3.5 h-3.5" />
              <span>Call</span>
            </button>
            )}
          </nav>

          {/* Right: ONLY the connection indicator -- no login button */}
          <div className="flex items-center gap-2">
            <StatusNotificationPopover
              theme={theme}
              isAdmin={isAdmin}
              onNavigateToTrace={navigateToTrace}
            />
          </div>
        </header>

        {/* ============================================================= */}
        {/* SUB-HEADER: 6 Admin Elements (Chat removed, Centered & Wide)   */}
        {/* a. Monitor • b. Trace Inspector • c. Memory & DB • d. Reasoning • e. Organs • f. Virtual CLI */}
        {/* ============================================================= */}
        {isAuthenticated && (
          <div
            className={`h-11 px-3 sm:px-6 border-b flex items-center justify-center shrink-0 z-20 transition-colors ${
              isDark
                ? 'bg-[#060911]/90 backdrop-blur-md border-white/10'
                : 'bg-slate-100/95 backdrop-blur-md border-slate-200 shadow-2xs'
            }`}
          >
            <div className="w-full max-w-xl flex items-center justify-center gap-1 sm:gap-2">
              {/* 1. Monitor */}
              <button
                onClick={() => {
                  setCurrentView('dashboard');
                  setDashboardSection('monitor');
                }}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'dashboard' && dashboardSection === 'monitor'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="Monitor (System Telemetry & Vitals)"
              >
                <Activity className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  Monitor
                </span>
              </button>

              {/* 2. Trace Inspector */}
              <button
                onClick={() => setCurrentView('inspector')}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'inspector'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="Trace Inspector (Turn Execution & Latency Waterfall)"
              >
                <FileSearch className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  Trace Inspector
                </span>
              </button>

              {/* 3. Memory and Database */}
              <button
                onClick={() => {
                  setCurrentView('dashboard');
                  setDashboardSection('memory');
                }}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'dashboard' && dashboardSection === 'memory'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="Memory & Database (Schema Contracts & Evolution DB)"
              >
                <Database className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  Memory & Database
                </span>
              </button>

              {/* 4. System Reasoning */}
              <button
                onClick={() => {
                  setCurrentView('dashboard');
                  setDashboardSection('reasoning');
                }}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'dashboard' && dashboardSection === 'reasoning'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="System Reasoning (Overnight Learning & Self-Improvement)"
              >
                <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  System Reasoning
                </span>
              </button>

              {/* 5. CodeBox -- REPLACES the old "Organs" button
                  (2026-09-14, UK: "organ inspection ko remove karke
                  wahan codebox daal do, virtual CLI ke bagal mein
                  icon ke saath"). Organ introspection data still
                  exists (see core/orchestration/organ_introspection.py)
                  and is reachable from the CLI's own diagnostics; it
                  was not deleted, just moved out of the icon row that
                  UK actually uses day to day.
                  Role-gated the same way the sidebar's CodeBox entry
                  is (features.ts) -- admin/owner/co_owner only, so a
                  plain user or guest does not even see the icon. */}
              {isReadyForRole('codebox', session?.role) && (
              <button
                onClick={() => setCurrentView('codebox')}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'codebox'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="CodeBox (Sandboxed Coding, 5-Layer QA)"
              >
                <FileCode className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  CodeBox
                </span>
              </button>
              )}

              {/* 6. Virtual CLI */}
              <button
                onClick={() => setCurrentView('cli')}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'cli'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="Virtual CLI (Diagnostic Shell & Terminal)"
              >
                <Terminal className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  Virtual CLI
                </span>
              </button>
            </div>
          </div>
        )}

        {/* View Switcher Routing */}
        <main className="flex-1 min-h-0 relative">
          {/* Home Landing Page (Default View) */}
          {currentView === 'home' && (
            <HomeScreen
              theme={theme}
              onNavigateToView={view => {
                if ((view === 'dashboard' || view === 'cli' || view === 'inspector') && !isAuthenticated) {
                  setIsAuthOpen(true);
                } else {
                  setCurrentView(view);
                }
              }}
              onStartChatWithPrompt={prompt => {
                setCurrentView('user_chat');
                handleSendMessage(prompt);
              }}
              isAdmin={isAdmin}
              onOpenAuth={() => setIsAuthOpen(true)}
            />
          )}

          {/* User Chat (Always accessible to all users) */}
          {currentView === 'user_chat' && (
            <UserChatView
              theme={theme}
              activeSessionId={activeSessionId}
              activeSessionTitle={activeSession?.title || 'New Conversation'}
              messages={currentMessages}
              onSendMessage={handleSendMessage}
              onLoadEarlierMessages={handleLoadEarlierMessages}
              hasOlderMessages={hasOlderMessages}
              isThinking={isThinking}
              thinkingSeconds={thinkingSeconds}
              isAdmin={isAdmin}
              onUnlockOperator={() => setIsProfileOpen(true)}
            />
          )}

          {/* Admin Protected Views: DashboardScreen */}
          {currentView === 'dashboard' &&
            (isAuthenticated ? (
              <DashboardScreen
                onSelectTurn={navigateToTrace}
                onNavigateToCLI={navigateToCLI}
                theme={theme}
                activeSection={dashboardSection}
                onSelectSection={sec => setDashboardSection(sec)}
              />
            ) : (
              <UserChatView
                theme={theme}
                activeSessionId={activeSessionId}
                activeSessionTitle={activeSession?.title || 'New Conversation'}
                messages={currentMessages}
                onSendMessage={handleSendMessage}
                onLoadEarlierMessages={handleLoadEarlierMessages}
                hasOlderMessages={hasOlderMessages}
                isThinking={isThinking}
                thinkingSeconds={thinkingSeconds}
                isAdmin={isAdmin}
                onUnlockOperator={() => setIsProfileOpen(true)}
              />
            ))}

          {currentView === 'codebox' && isReadyForRole('codebox', session?.role) && <CodeBoxScreen />}

          {currentView === 'call' && isReady('call') && <VoiceCallScreen />}

          {/* Admin Protected Views: VirtualCLIScreen */}
          {currentView === 'cli' &&
            (isAuthenticated ? (
              <VirtualCLIScreen theme={theme} />
            ) : (
              <UserChatView
                theme={theme}
                activeSessionId={activeSessionId}
                activeSessionTitle={activeSession?.title || 'New Conversation'}
                messages={currentMessages}
                onSendMessage={handleSendMessage}
                onLoadEarlierMessages={handleLoadEarlierMessages}
                hasOlderMessages={hasOlderMessages}
                isThinking={isThinking}
                thinkingSeconds={thinkingSeconds}
                isAdmin={isAdmin}
                onUnlockOperator={() => setIsProfileOpen(true)}
              />
            ))}

          {/* Admin Protected Views: TraceInspectorScreen */}
          {currentView === 'inspector' &&
            (isAuthenticated ? (
              /* THE ORIGINAL TRACE TREE, RESTORED (2026-09-14).
                 I replaced this whole screen with a new list view last
                 round. That was the wrong call: UK asked for a FILTER on
                 the existing trace, and the existing trace -- the
                 per-stage tree with PERCEPTION / INDEXING / ROUTING /
                 EXECUTION / LEARNING and the detail he actually reads --
                 is what he uses. Replacing a working view to add one
                 feature to it costs him the view.
                 The filter bar now sits ON TOP of it instead. */
              <TraceInspectorScreen
                selectedTurnId={selectedTurnId}
                onSelectTurnId={setSelectedTurnId}
                theme={theme}
                viewerRole={(session?.role as string) || 'guest'}
              />
            ) : (
              <UserChatView
                theme={theme}
                activeSessionId={activeSessionId}
                activeSessionTitle={activeSession?.title || 'New Conversation'}
                messages={currentMessages}
                onSendMessage={handleSendMessage}
                onLoadEarlierMessages={handleLoadEarlierMessages}
                hasOlderMessages={hasOlderMessages}
                isThinking={isThinking}
                thinkingSeconds={thinkingSeconds}
                isAdmin={isAdmin}
                onUnlockOperator={() => setIsProfileOpen(true)}
              />
            ))}
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
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
<<<<<<< HEAD
=======
        onToggleTheme={toggleTheme}
        onSetTheme={t => setTheme(t)}
      />

      {/* User Profile & Accounts Modal */}
      <ProfileModal
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        isAdmin={isAdmin}
        onLoginSuccess={handleLoginSuccess}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={toggleTheme}
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
      />
    </div>
  );
}

export default App;
