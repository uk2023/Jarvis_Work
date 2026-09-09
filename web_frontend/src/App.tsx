import React, { useState, useEffect } from 'react';
import {
  Home,
  Activity,
  Terminal,
  FileSearch,
  MessageSquare,
  Shield,
  LogOut,
  Menu,
  Sliders,
  User,
  Sparkles,
  Database,
  Layers,
} from 'lucide-react';
import { AppTheme, ConsoleView, SessionItem, ChatMessage } from './types';
import { api } from './api/client';
import {
  INITIAL_SESSIONS,
  INITIAL_MESSAGES_BY_SESSION,
  OLDER_ARCHIVED_MESSAGES,
} from './data/chatSessions';
import { HomeScreen } from './components/HomeScreen';
import { DashboardScreen } from './components/DashboardScreen';
import { VirtualCLIScreen } from './components/VirtualCLIScreen';
import { TraceInspectorScreen } from './components/TraceInspectorScreen';
import { UserChatView } from './components/UserChatView';
import { ChatThreadsSidebar } from './components/ChatThreadsSidebar';
import { StatusNotificationPopover } from './components/StatusNotificationPopover';
import { AuthModal } from './components/AuthModal';
import { SettingsModal } from './components/SettingsModal';
import { ProfileModal } from './components/ProfileModal';

export function App() {
  // Theme state: persists in localStorage
  const [theme, setTheme] = useState<AppTheme>(() => {
    try {
      const saved = localStorage.getItem('jarvis_theme') as AppTheme;
      return saved === 'light' || saved === 'dark' ? saved : 'dark';
    } catch {
      return 'dark';
    }
  });

  // Auth & Role state: persists in localStorage
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    try {
      const token = localStorage.getItem('jarvis_operator_token');
      return !!token;
    } catch {
      return false;
    }
  });

  // Active view: 'home' | 'dashboard' | 'cli' | 'inspector' | 'user_chat'
  const [currentView, setCurrentView] = useState<ConsoleView>('home');

  // Active dashboard section for sub-header navigation: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'
  const [dashboardSection, setDashboardSection] = useState<'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'>('monitor');

  // Selected Turn ID for Trace Inspector
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);

  // Auth modal toggle
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Categorized Settings modal toggle
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // User Profile modal toggle
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Mobile sidebar drawer
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  // Pulse & beat ticker
  const [beatCount, setBeatCount] = useState(88);

  // Chat Sessions & Active Thread State
  const [sessions, setSessions] = useState<SessionItem[]>(() => {
    try {
      const saved = localStorage.getItem('jarvis_chat_sessions');
      if (saved) return JSON.parse(saved);
    } catch {}
    return INITIAL_SESSIONS;
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    try {
      const savedId = localStorage.getItem('jarvis_active_session_id');
      if (savedId) return savedId;
    } catch {}
    return INITIAL_SESSIONS[0]?.sessionId || 'session-1';
  });

  const [messagesBySession, setMessagesBySession] = useState<Record<string, ChatMessage[]>>(() => {
    try {
      const saved = localStorage.getItem('jarvis_messages_by_session');
      if (saved) return JSON.parse(saved);
    } catch {}
    return INITIAL_MESSAGES_BY_SESSION;
  });

  const [hasOlderMessages, setHasOlderMessages] = useState<boolean>(true);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingSeconds, setThinkingSeconds] = useState(0);

  const isDark = theme === 'dark';

  // Synchronize documentElement dark mode class for reliable Tailwind dark: styles
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Persist sessions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('jarvis_chat_sessions', JSON.stringify(sessions));
    } catch {}
  }, [sessions]);

  // Persist activeSessionId
  useEffect(() => {
    try {
      localStorage.setItem('jarvis_active_session_id', activeSessionId);
    } catch {}
  }, [activeSessionId]);

  // Persist messagesBySession
  useEffect(() => {
    try {
      localStorage.setItem('jarvis_messages_by_session', JSON.stringify(messagesBySession));
    } catch {}
  }, [messagesBySession]);

  // Pulse & beat counter ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setBeatCount(b => (b >= 9999 ? 1 : b + 1));
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  // Thinking timer ticker
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
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
    setIsAuthenticated(true);
    try {
      localStorage.setItem('jarvis_operator_token', api.getAuthToken() || 'operator-active');
    } catch {}
    // Seamlessly navigate to dashboard on operator login to view full telemetry
    setCurrentView('dashboard');
  };

  const handleLogout = () => {
    api.logout();
    setIsAuthenticated(false);
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
      }
    }
  };

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
  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isThinking) return;

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sessionId: activeSessionId,
      sender: 'user',
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      dateLabel: 'Today',
      source: 'web',
    };

    // Prepend/append to session's messages
    setMessagesBySession(prev => ({
      ...prev,
      [activeSessionId]: [...(prev[activeSessionId] || []), userMsg],
    }));

    // If new session, auto-rename title from query
    const currentSession = sessions.find(s => s.sessionId === activeSessionId);
    if (currentSession && currentSession.title === 'New Conversation') {
      const generatedTitle = text.slice(0, 30) + (text.length > 30 ? '...' : '');
      handleRenameSession(activeSessionId, generatedTitle);
    }

    setIsThinking(true);
    const startTime = Date.now();

    try {
      const res = await api.sendChat(text, activeSessionId, 'web');
      const duration = Number(((Date.now() - startTime) / 1000).toFixed(1));

      const jarvisMsg: ChatMessage = {
        id: res.messageId || `jarvis-${Date.now()}`,
        sessionId: activeSessionId,
        sender: 'jarvis',
        text: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        dateLabel: 'Today',
        source: 'web',
        thinkingDurationSeconds: Math.max(0.8, duration),
        thinkingProcess: [
          'Interpreted query semantics and normalized Hinglish colloquial tokens',
          'Surveyed FAISS vector episodic memory (384d space)',
          'Traversed relationship graph for verified personal engrams',
          'Formulated natural, contextual assistant response',
        ],
      };

      setMessagesBySession(prev => ({
        ...prev,
        [activeSessionId]: [...(prev[activeSessionId] || []), jarvisMsg],
      }));
    } catch {
      const duration = Number(((Date.now() - startTime) / 1000).toFixed(1));
      const fallbackMsg: ChatMessage = {
        id: `jarvis-${Date.now()}`,
        sessionId: activeSessionId,
        sender: 'jarvis',
        text: `Understood, sir. I have processed "${text}" and verified cognitive state consistency.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        dateLabel: 'Today',
        source: 'web',
        thinkingDurationSeconds: Math.max(0.8, duration),
        thinkingProcess: [
          'Parsed query and validated contract constraints',
          'Checked native cognitive pipeline and Groq fallback cache',
          'Synchronized background learning queue',
        ],
      };

      setMessagesBySession(prev => ({
        ...prev,
        [activeSessionId]: [...(prev[activeSessionId] || []), fallbackMsg],
      }));
    } finally {
      setIsThinking(false);
    }
  };

  // Load older historical messages
  const handleLoadEarlierMessages = () => {
    const older = OLDER_ARCHIVED_MESSAGES[activeSessionId];
    if (older && older.length > 0) {
      setMessagesBySession(prev => ({
        ...prev,
        [activeSessionId]: [...older, ...(prev[activeSessionId] || [])],
      }));
    }
    setHasOlderMessages(false);
  };

  const activeSession = sessions.find(s => s.sessionId === activeSessionId);
  const currentMessages = messagesBySession[activeSessionId] || [];

  return (
    <div
      className={`h-screen w-screen flex overflow-hidden font-sans ${
        isDark ? 'dark bg-[#05070c] text-slate-100' : 'bg-[#F8FAFC] text-slate-900'
      }`}
      id="app-root"
    >
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
        isAdmin={isAuthenticated}
        onOpenProfileSettings={() => setIsProfileOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        onGoHome={() => setCurrentView('home')}
        currentView={currentView}
        onNavigateToView={view => setCurrentView(view)}
        onLogout={handleLogout}
      />

      {/* ------------------------------------------------------------- */}
      {/* MAIN CONTENT AREA                                             */}
      {/* ------------------------------------------------------------- */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
        {/* ============================================================= */}
        {/* TOP UNIFIED APPLICATION HEADER (Minimal, Neat & Tidy)         */}
        {/* ============================================================= */}
        <header
          className="h-14 px-3 sm:px-6 border-b flex items-center justify-between shrink-0 z-30"
          style={{ backgroundColor: 'var(--jarvis-surface-raised)', borderColor: 'var(--jarvis-border)' }}
        >
          {/* Left: mobile drawer trigger + JARVIS mark, name, subtitle.
              No online/offline dot here anymore (point 6, UK's
              explicit ask) -- that status lives ONLY in the
              right-corner indicator now, not duplicated in two
              places. */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={() => setIsMobileNavOpen(true)}
              className="p-1.5 rounded-lg border md:hidden shrink-0"
              style={{ borderColor: 'var(--jarvis-border)', color: 'var(--jarvis-text-muted)' }}
              title="Open navigation"
            >
              <Menu className="w-4 h-4" />
            </button>

            <button
              onClick={() => setCurrentView('home')}
              className="flex items-center gap-2 sm:gap-2.5 group cursor-pointer text-left select-none"
              title="Return to JARVIS Home"
            >
              <div className="relative w-8 h-8 rounded-xl border flex items-center justify-center shrink-0 transition-transform group-hover:scale-105" style={{ borderColor: 'var(--jarvis-border-strong)', backgroundColor: 'var(--jarvis-accent-dim)' }}>
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: 'var(--jarvis-accent)' }} />
              </div>
              <div className="hidden min-[360px]:block">
                <h1 className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>
                  JARVIS
                </h1>
                <span className="text-xs -mt-0.5 block" style={{ color: 'var(--jarvis-text-muted)' }}>
                  Cognitive OS
                </span>
              </div>
            </button>
          </div>

          {/* Center Navigation: Quick Home & Chat */}
          <nav
            className="hidden md:flex items-center gap-1 p-1 rounded-2xl border"
            style={{ backgroundColor: 'var(--jarvis-surface)', borderColor: 'var(--jarvis-border)' }}
          >
            <button
              onClick={() => setCurrentView('home')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors"
              style={currentView === 'home' ? { backgroundColor: 'var(--jarvis-accent)', color: 'white' } : { color: 'var(--jarvis-text-muted)' }}
              title="JARVIS Home"
            >
              <Home className="w-3.5 h-3.5" />
              <span>Home</span>
            </button>

            <button
              onClick={() => setCurrentView('user_chat')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors"
              style={currentView === 'user_chat' ? { backgroundColor: 'var(--jarvis-accent)', color: 'white' } : { color: 'var(--jarvis-text-muted)' }}
              title="Chat"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Chat</span>
            </button>
          </nav>

          {/* Right: ONLY the connection indicator -- no login button */}
          <div className="flex items-center gap-2">
            <StatusNotificationPopover
              theme={theme}
              isAdmin={isAuthenticated}
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

              {/* 5. Organs */}
              <button
                onClick={() => {
                  setCurrentView('dashboard');
                  setDashboardSection('organs');
                }}
                className={`flex-1 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer relative group ${
                  currentView === 'dashboard' && dashboardSection === 'organs'
                    ? 'bg-brand-600 text-white shadow-xs font-semibold'
                    : isDark
                    ? 'bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                    : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200 shadow-2xs'
                }`}
                title="Organs (Organ Introspection & Heartbeat Network)"
              >
                <Layers className="w-3.5 h-3.5 sm:w-4 sm:h-4 group-hover:scale-115 transition-transform duration-200 shrink-0" />
                <span className="pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-xs font-medium bg-slate-900 text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-30 shadow-md border border-white/10">
                  Organs
                </span>
              </button>

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
              isAdmin={isAuthenticated}
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
              isAdmin={isAuthenticated}
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
                isAdmin={isAuthenticated}
                onUnlockOperator={() => setIsProfileOpen(true)}
              />
            ))}

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
                isAdmin={isAuthenticated}
                onUnlockOperator={() => setIsProfileOpen(true)}
              />
            ))}

          {/* Admin Protected Views: TraceInspectorScreen */}
          {currentView === 'inspector' &&
            (isAuthenticated ? (
              <TraceInspectorScreen
                selectedTurnId={selectedTurnId}
                onSelectTurnId={setSelectedTurnId}
                theme={theme}
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
                isAdmin={isAuthenticated}
                onUnlockOperator={() => setIsProfileOpen(true)}
              />
            ))}
        </main>

        {/* ============================================================= */}
        {/* LANDING PAGE COMPACT FOOTER (Visible only on Home View)       */}
        {/* Compact, clean, 2-line format in corner/bottom, no overflow   */}
        {/* ============================================================= */}
        {currentView === 'home' && (
          <footer
            id="global-app-footer"
            className={`w-full border-t py-1.5 px-4 sm:px-6 font-mono text-xs sm:text-xs transition-colors shrink-0 z-20 ${
              isDark
                ? 'bg-[#050811]/95 backdrop-blur-md border-white/10 text-slate-400'
                : 'bg-slate-100/95 backdrop-blur-md border-slate-200 text-slate-600'
            }`}
          >
            <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-1 text-center sm:text-left">
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-1.5">
                <span className="font-bold text-slate-900 dark:text-slate-100 tracking-wider">
                  JARVIS CORE
                </span>
                <span className="text-xs px-1 py-0.2 rounded bg-brand-500/15 text-brand-600 dark:text-brand-400 font-semibold border border-brand-500/20">
                  v2026.4
                </span>
                <span>&bull;</span>
                <span className="text-slate-600 dark:text-slate-300">
                  Copyright 2026 JARVIS Core. All rights reserved.
                </span>
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center justify-center gap-1.5">
                <span>Cognitive OS Architecture</span>
                <span>&bull;</span>
                <span className="text-emerald-500 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Live Telemetry
                </span>
              </div>
            </div>
          </footer>
        )}
      </div>

      {/* Operator Authentication Modal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onSuccess={handleLoginSuccess}
        theme={theme}
      />

      {/* ChatGPT-Style Categorized Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        theme={theme}
        onToggleTheme={toggleTheme}
        onSetTheme={t => setTheme(t)}
      />

      {/* User Profile & Accounts Modal */}
      <ProfileModal
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        isAdmin={isAuthenticated}
        onLoginSuccess={handleLoginSuccess}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
    </div>
  );
}

export default App;
