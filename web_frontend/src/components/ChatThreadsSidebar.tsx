import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  MessageSquare,
  Pin,
  PinOff,
  MoreVertical,
  Trash2,
  Edit2,
  Check,
  X,
  Radio,
  Search,
  Shield,
  User,
  LogIn,
  Settings,
  PanelLeftClose,
  PanelLeft,
  ChevronDown,
  ChevronRight,
  Clock,
  Activity,
  FileSearch,
  Database,
  Sparkles,
  Layers,
  Terminal,
} from 'lucide-react';
import { AppTheme, SessionItem } from '../types';

interface ChatThreadsSidebarProps {
  theme: AppTheme;
  isOpen: boolean;
  onClose: () => void;
  sessions: SessionItem[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, newTitle: string) => void;
  onTogglePinSession: (id: string) => void;
  onToggleTheme?: () => void;
  beatCount: number;
  isAdmin: boolean;
  onOpenProfileSettings: () => void;
  onOpenSettings?: () => void;
  onGoHome?: () => void;
  currentView?: string;
  onNavigateToView?: (view: 'user_chat' | 'dashboard' | 'cli' | 'inspector') => void;
  onOpenAuth?: () => void;
  onLogout?: () => void;
}

export function ChatThreadsSidebar({
  theme,
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onTogglePinSession,
  onToggleTheme,
  beatCount,
  isAdmin,
  onOpenProfileSettings,
  onOpenSettings,
  onGoHome,
  currentView = 'user_chat',
  onNavigateToView,
  onOpenAuth,
}: ChatThreadsSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [menuOpenSessionId, setMenuOpenSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [inspectionOpen, setInspectionOpen] = useState(true);

  // Collapsible section states
  const [pinnedOpen, setPinnedOpen] = useState(true);
  const [recentOpen, setRecentOpen] = useState(true);
  const [olderOpen, setOlderOpen] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  const isDark = theme === 'dark';

  // Keep the global view marker in sync so the existing contextual sub-header
  // is hidden on Home/Chat and only shown while one of the six inspection views is active.
  useEffect(() => {
    document.documentElement.dataset.jarvisView = currentView;
    return () => {
      delete document.documentElement.dataset.jarvisView;
    };
  }, [currentView]);

  // Focus input when editing begins
  useEffect(() => {
    if (editingSessionId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingSessionId]);

  // Click outside to close three-dots menu
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenSessionId(null);
      }
    }
    if (menuOpenSessionId) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpenSessionId]);

  const handleStartRename = (session: SessionItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuOpenSessionId(null);
    setEditingSessionId(session.sessionId);
    setEditTitle(session.title);
  };

  const handleSaveRename = (sessionId: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim());
    }
    setEditingSessionId(null);
  };

  const filteredSessions = sessions.filter(s =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Grouping: Pinned, Recent (last 7 days), and Older
  const pinnedSessions = filteredSessions.filter(s => s.pinned);
  const unpinnedSessions = filteredSessions.filter(s => !s.pinned);

  const recentSessions = unpinnedSessions.filter(
    s => s.category === 'Today' || s.category === 'Yesterday' || s.category === 'Previous 7 Days'
  );
  const olderSessions = unpinnedSessions.filter(
    s => s.category !== 'Today' && s.category !== 'Yesterday' && s.category !== 'Previous 7 Days'
  );

  const inspectionItems = [
    { label: 'Monitor', icon: Activity, active: currentView === 'dashboard', section: 'monitor' as const, title: 'Cognitive Monitor' },
    { label: 'Trace', icon: FileSearch, active: currentView === 'inspector', section: null, title: 'Trace Inspector' },
    { label: 'Memory', icon: Database, active: currentView === 'dashboard' && currentView === 'dashboard', section: 'memory' as const, title: 'Memory & Database' },
    { label: 'Reasoning', icon: Sparkles, active: currentView === 'dashboard', section: 'reasoning' as const, title: 'System Reasoning' },
    { label: 'Organs', icon: Layers, active: currentView === 'dashboard', section: 'organs' as const, title: 'Organ Introspection' },
    { label: 'CLI', icon: Terminal, active: currentView === 'cli', section: null, title: 'Virtual CLI' },
  ];

  const navigateInspection = (section: 'monitor' | 'memory' | 'reasoning' | 'organs' | null, view: 'dashboard' | 'inspector' | 'cli') => {
    if (!onNavigateToView) return;
    if (view === 'dashboard') {
      onNavigateToView('dashboard');
      window.dispatchEvent(new CustomEvent('jarvis:inspection-section', { detail: section || 'monitor' }));
    } else {
      onNavigateToView(view);
    }
    onClose();
  };

  const renderSessionItem = (session: SessionItem) => {
    const isActive = session.sessionId === activeSessionId;
    const isEditing = editingSessionId === session.sessionId;
    const isMenuOpen = menuOpenSessionId === session.sessionId;

    return (
      <div
        key={session.sessionId}
        className={`group relative rounded-xl px-2.5 py-1.5 flex items-center gap-2 transition cursor-pointer text-xs select-none ${
          isActive
            ? isDark
              ? 'bg-brand-500/15 border border-brand-400/40 text-brand-200 font-semibold'
              : 'bg-brand-50 border border-brand-400 text-brand-900 font-semibold shadow-2xs'
            : isDark
            ? 'hover:bg-white/5 text-slate-300 hover:text-white border border-transparent'
            : 'hover:bg-slate-100 text-slate-700 hover:text-slate-950 border border-transparent'
        }`}
        onClick={() => {
          if (!isEditing) {
            onSelectSession(session.sessionId);
            onClose();
          }
        }}
      >
        <MessageSquare
          className={`w-3.5 h-3.5 shrink-0 transition-colors ${
            isActive
              ? 'text-brand-500'
              : isDark
              ? 'text-slate-500 group-hover:text-slate-300'
              : 'text-slate-400 group-hover:text-slate-600'
          }`}
        />

        {isEditing ? (
          <form
            onSubmit={e => handleSaveRename(session.sessionId, e)}
            className="flex-1 flex items-center gap-1 min-w-0"
            onClick={e => e.stopPropagation()}
          >
            <input
              ref={editInputRef}
              type="text"
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              className={`w-full text-xs px-1.5 py-0.5 rounded border outline-none ${
                isDark
                  ? 'bg-black/60 border-brand-400 text-white'
                  : 'bg-white border-brand-600 text-slate-900'
              }`}
            />
            <button type="submit" className="p-1 text-emerald-500 hover:text-emerald-400 cursor-pointer" title="Save"><Check className="w-3.5 h-3.5" /></button>
            <button type="button" onClick={() => setEditingSessionId(null)} className="p-1 text-slate-400 hover:text-slate-200 cursor-pointer" title="Cancel"><X className="w-3.5 h-3.5" /></button>
          </form>
        ) : (
          <div className="flex-1 min-w-0 flex items-center justify-between gap-1">
            <span className="truncate leading-tight">{session.title}</span>
            {session.pinned && <Pin className="w-2.5 h-2.5 text-brand-500 dark:text-brand-400 shrink-0 opacity-80" />}
          </div>
        )}

        {!isEditing && (
          <div className="relative">
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                setMenuOpenSessionId(isMenuOpen ? null : session.sessionId);
              }}
              className={`p-1 rounded-md transition cursor-pointer ${
                isMenuOpen
                  ? 'opacity-100 bg-white/10 text-brand-400'
                  : 'opacity-0 group-hover:opacity-100 text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-white/10'
              }`}
              title="Chat options"
            >
              <MoreVertical className="w-3 h-3" />
            </button>
            {isMenuOpen && (
              <div
                ref={menuRef}
                className={`absolute right-0 top-6 w-36 rounded-xl border shadow-xl z-50 py-1 space-y-0.5 text-xs animate-in fade-in duration-100 ${
                  isDark ? 'bg-[#0f1422] border-white/15 text-slate-200 shadow-black/80' : 'bg-white border-slate-200 text-slate-800 shadow-slate-300/50'
                }`}
                onClick={e => e.stopPropagation()}
              >
                <button onClick={e => { e.stopPropagation(); onTogglePinSession(session.sessionId); setMenuOpenSessionId(null); }} className={`w-full px-2.5 py-1.5 flex items-center gap-2 text-left transition cursor-pointer ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'}`}>
                  {session.pinned ? <><PinOff className="w-3.5 h-3.5 text-slate-400" /><span>Unpin</span></> : <><Pin className="w-3.5 h-3.5 text-brand-400" /><span>Pin chat</span></>}
                </button>
                <button onClick={e => handleStartRename(session, e)} className={`w-full px-2.5 py-1.5 flex items-center gap-2 text-left transition cursor-pointer ${isDark ? 'hover:bg-white/10' : 'hover:bg-slate-100'}`}>
                  <Edit2 className="w-3.5 h-3.5 text-slate-400" /><span>Rename</span>
                </button>
                <button onClick={e => { e.stopPropagation(); onDeleteSession(session.sessionId); setMenuOpenSessionId(null); }} className={`w-full px-2.5 py-1.5 flex items-center gap-2 text-left text-rose-500 transition cursor-pointer ${isDark ? 'hover:bg-rose-500/15' : 'hover:bg-rose-50'}`}>
                  <Trash2 className="w-3.5 h-3.5" /><span>Delete</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <style>{`
        html[data-jarvis-view="home"] #app-root > div.flex-1.flex.flex-col > div:nth-child(2),
        html[data-jarvis-view="user_chat"] #app-root > div.flex-1.flex.flex-col > div:nth-child(2) {
          display: none !important;
        }
      `}</style>

      {isOpen && <div onClick={onClose} className="fixed inset-0 bg-black/60 backdrop-blur-xs z-30 md:hidden" />}

      <aside
        className={`fixed inset-y-0 left-0 z-40 border-r transition-all duration-200 flex flex-col justify-between md:static md:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'} ${isCollapsed ? 'md:w-16' : 'w-64'} ${isDark ? 'bg-[#080b14] border-white/10 text-slate-200' : 'bg-white border-slate-200 text-slate-800 shadow-[2px_0_12px_rgba(0,0,0,0.03)]'}`}
      >
        <div className="p-3 border-b border-slate-200 dark:border-white/10 space-y-2.5">
          <div className="flex items-center justify-between">
            <button onClick={() => { if (onGoHome) onGoHome(); onClose(); }} className="flex items-center gap-2 text-left cursor-pointer group select-none min-w-0" title="Return to Home">
              <div className="w-7 h-7 rounded-xl bg-brand-500/15 border border-brand-400/40 flex items-center justify-center group-hover:scale-105 transition-transform shrink-0"><span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" /></div>
              {!isCollapsed && <span className="font-extrabold text-xs tracking-wider uppercase text-slate-900 dark:text-brand-400 group-hover:text-brand-600 dark:group-hover:text-brand-300 transition-colors truncate">JARVIS</span>}
            </button>
            <button onClick={() => setIsCollapsed(!isCollapsed)} className="hidden md:flex p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition cursor-pointer" title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
              {isCollapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 md:hidden text-slate-400 cursor-pointer" title="Close sidebar"><X className="w-4 h-4" /></button>
          </div>

          {isCollapsed ? (
            <button onClick={() => { onNewChat(); onClose(); }} className="w-10 h-10 mx-auto rounded-xl bg-brand-600 hover:bg-brand-500 text-white flex items-center justify-center transition cursor-pointer shadow-xs" title="New Chat"><Plus className="w-4 h-4" /></button>
          ) : (
            <button onClick={() => { onNewChat(); onClose(); }} className="w-full py-2 px-3 rounded-xl bg-brand-600 hover:bg-brand-500 border border-brand-500 text-white flex items-center justify-center gap-2 text-xs font-semibold transition cursor-pointer shadow-xs"><Plus className="w-3.5 h-3.5" /><span>New Chat</span></button>
          )}

          {/* Inspection navigation lives permanently below New Chat. */}
          {isAdmin && (
            <div className="pt-1">
              <button
                onClick={() => setInspectionOpen(!inspectionOpen)}
                className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-[0.12em] transition ${isDark ? 'text-slate-400 hover:text-slate-200 hover:bg-white/5' : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'}`}
                title="Inspection navigation"
              >
                <span className="flex items-center gap-1.5"><Shield className="w-3 h-3 text-brand-500" /> Inspection</span>
                {inspectionOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>

              {inspectionOpen && !isCollapsed && (
                <div className="grid grid-cols-3 gap-1.5 mt-1.5">
                  {inspectionItems.map(({ label, icon: Icon, section, title }) => {
                    const active = section === 'memory'
                      ? currentView === 'dashboard'
                      : label === 'Monitor'
                      ? currentView === 'dashboard'
                      : label === 'Reasoning'
                      ? currentView === 'dashboard'
                      : label === 'Organs'
                      ? currentView === 'dashboard'
                      : label === 'Trace'
                      ? currentView === 'inspector'
                      : currentView === 'cli';
                    return (
                      <button
                        key={label}
                        onClick={() => navigateInspection(section, label === 'Trace' ? 'inspector' : label === 'CLI' ? 'cli' : 'dashboard')}
                        className={`min-w-0 h-12 rounded-lg border flex flex-col items-center justify-center gap-1 transition-all cursor-pointer ${active ? 'bg-brand-600 text-white border-brand-500 shadow-xs' : isDark ? 'bg-white/[0.025] border-white/10 text-slate-400 hover:text-white hover:bg-white/10' : 'bg-slate-50 border-slate-200 text-slate-500 hover:text-slate-900 hover:bg-slate-100'}`}
                        title={title}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        <span className="text-[8px] font-semibold truncate max-w-full px-1">{label}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {inspectionOpen && isCollapsed && (
                <div className="grid grid-cols-1 gap-1 mt-1.5">
                  {inspectionItems.map(({ label, icon: Icon, section, title }) => (
                    <button
                      key={label}
                      onClick={() => navigateInspection(section, label === 'Trace' ? 'inspector' : label === 'CLI' ? 'cli' : 'dashboard')}
                      className={`w-10 h-9 mx-auto rounded-lg border flex items-center justify-center transition-all cursor-pointer ${isDark ? 'bg-white/[0.025] border-white/10 text-slate-400 hover:text-white hover:bg-white/10' : 'bg-slate-50 border-slate-200 text-slate-500 hover:text-slate-900 hover:bg-slate-100'}`}
                      title={title}
                    ><Icon className="w-3.5 h-3.5" /></button>
                  ))}
                </div>
              )}
            </div>
          )}

          {!isCollapsed && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-sm" style={{ backgroundColor: 'var(--jarvis-surface)', borderColor: 'var(--jarvis-border)', color: 'var(--jarvis-text)' }}>
              <Search size={13} style={{ color: 'var(--jarvis-text-muted)' }} className="shrink-0" />
              <input type="text" placeholder="Search chats..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="w-full bg-transparent outline-none text-sm" style={{ color: 'var(--jarvis-text)' }} />
              {searchQuery && <button onClick={() => setSearchQuery('')} className="text-slate-400 hover:text-slate-200 cursor-pointer"><X className="w-3 h-3" /></button>}
            </div>
          )}
        </div>

        {isCollapsed ? (
          <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-2">
            {sessions.slice(0, 8).map(session => {
              const isActive = session.sessionId === activeSessionId;
              return (
                <button key={session.sessionId} onClick={() => onSelectSession(session.sessionId)} className={`w-10 h-10 mx-auto rounded-xl flex items-center justify-center transition cursor-pointer relative group ${isActive ? 'bg-brand-600 text-white shadow-xs' : isDark ? 'hover:bg-white/10 text-slate-400 hover:text-white' : 'hover:bg-slate-100 text-slate-600 hover:text-slate-900'}`} title={session.title}>
                  <MessageSquare className="w-4 h-4" />
                  {session.pinned && <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-brand-400" />}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-3 font-sans">
            {pinnedSessions.length > 0 && (
              <div className="space-y-1">
                <button onClick={() => setPinnedOpen(!pinnedOpen)} className="w-full px-2 py-1 flex items-center justify-between text-xs font-medium transition-colors cursor-pointer select-none" style={{ color: 'var(--jarvis-text-muted)' }}>
                  <span className="flex items-center gap-1.5"><Pin className="w-2.5 h-2.5 text-brand-500" /><span>Pinned</span></span>
                  {pinnedOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                </button>
                {pinnedOpen && pinnedSessions.map(renderSessionItem)}
              </div>
            )}
            <div className="space-y-1">
              <button onClick={() => setRecentOpen(!recentOpen)} className="w-full px-2 py-1 flex items-center justify-between text-xs font-medium transition-colors cursor-pointer select-none" style={{ color: 'var(--jarvis-text-muted)' }}>
                <span className="flex items-center gap-1.5"><Clock className="w-2.5 h-2.5 text-brand-500" /><span>Recent (Last 7 Days)</span></span>
                {recentOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </button>
              {recentOpen && (recentSessions.length > 0 ? recentSessions.map(renderSessionItem) : <div className="px-3 py-2 text-xs text-slate-400 italic">No recent chats</div>)}
            </div>
            {olderSessions.length > 0 && (
              <div className="space-y-1">
                <button onClick={() => setOlderOpen(!olderOpen)} className="w-full px-2 py-1 flex items-center justify-between text-xs font-medium transition-colors cursor-pointer select-none" style={{ color: 'var(--jarvis-text-muted)' }}>
                  <span>Older Conversations</span>
                  {olderOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                </button>
                {olderOpen && olderSessions.map(renderSessionItem)}
              </div>
            )}
            {filteredSessions.length === 0 && <div className="text-center py-8 text-xs text-slate-400">No conversations found</div>}
          </div>
        )}

        <div className="p-2.5 border-t border-slate-200 dark:border-white/10 space-y-2 select-none">
          {isCollapsed ? (
            <div className="flex flex-col items-center gap-2">
              <button onClick={onOpenProfileSettings} className="w-9 h-9 rounded-xl bg-brand-500/20 text-brand-400 border border-brand-400/30 flex items-center justify-center font-bold text-xs hover:scale-105 transition-transform cursor-pointer" title="Profile & Settings">{isAdmin ? 'AD' : <User className="w-4 h-4" />}</button>
              {onOpenSettings && <button onClick={onOpenSettings} className="w-9 h-9 rounded-xl hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 hover:text-brand-500 transition flex items-center justify-center cursor-pointer" title="Settings"><Settings className="w-4 h-4" /></button>}
            </div>
          ) : (
            <div className={`p-2 rounded-xl border flex items-center justify-between gap-1.5 transition ${isDark ? 'bg-white/[0.02] border-white/10 text-white' : 'bg-slate-50 border-slate-200 text-slate-900 shadow-2xs'}`}>
              <div onClick={onOpenProfileSettings} className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer group p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition" title="Touch profile to open profile & account settings">
                <div className="relative shrink-0">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${isAdmin ? 'bg-brand-500/20 text-brand-600 dark:text-brand-300 border border-brand-400' : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-white/10'}`}>{isAdmin ? 'AD' : <User className="w-3.5 h-3.5" />}</div>
                  <span className={`absolute bottom-0 right-0 w-2 h-2 rounded-full border border-white dark:border-[#080b14] ${isAdmin ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                </div>
                <div className="min-w-0 flex-1 text-left">
                  <div className="flex items-center gap-1.5 leading-tight"><span className="font-semibold text-xs truncate group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">{isAdmin ? 'Admin' : 'Guest User'}</span><span className={`text-xs px-1 py-0.2 rounded font-mono font-bold uppercase border ${isAdmin ? 'bg-brand-500/15 text-brand-700 dark:text-brand-400 border-brand-500/30' : 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30'}`}>{isAdmin ? 'OPERATOR' : 'GUEST'}</span></div>
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-mono block truncate">{isAdmin ? 'Profile & Account' : 'Tap for settings'}</span>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {!isAdmin && onOpenAuth && <button type="button" onClick={e => { e.stopPropagation(); onOpenAuth(); }} className="px-2 py-1 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs flex items-center gap-1 transition cursor-pointer shadow-xs" title="Sign in to JARVIS"><LogIn className="w-3 h-3" /><span>Login</span></button>}
                {onOpenSettings && <button type="button" onClick={e => { e.stopPropagation(); onOpenSettings(); }} className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 transition cursor-pointer" title="System Settings"><Settings className="w-3.5 h-3.5" /></button>}
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
