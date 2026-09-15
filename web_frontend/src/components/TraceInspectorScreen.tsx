import React, { useEffect, useState } from 'react';
import { FileSearch, RefreshCw, ChevronDown, Radio, Users } from 'lucide-react';
import { TurnTrace, ActivityHistoryItem, AppTheme } from '../types';
import { api } from '../api/client';
import { TraceTreeViewer } from './TraceTreeViewer';

interface TraceInspectorScreenProps {
  selectedTurnId?: string | null;
  onSelectTurnId?: (id: string) => void;
  theme: AppTheme;
  /** Role of whoever is signed in. Decides which scopes are offered
   *  here; the SERVER decides what is actually returned. */
  viewerRole?: string;
}

export function TraceInspectorScreen({ selectedTurnId, onSelectTurnId, theme, viewerRole = 'guest' }: TraceInspectorScreenProps) {
  // WHO-FILTER (added 2026-09-14). The trace tree below is unchanged --
  // this is the one thing UK asked for: a filter on top of the view he
  // already uses, not a replacement for it.
  //
  // Scope only changes WHICH turns are listed. It cannot widen access:
  // /api/trace applies the role rules server-side, so asking for 'all'
  // as a normal user still returns that user's turns.
  const [traceScope, setTraceScope] = useState<'mine' | 'all' | 'user' | 'role'>('mine');
  const [scopeValue, setScopeValue] = useState('');
  const [scopedTurns, setScopedTurns] = useState<any[] | null>(null);
  const [scopeNote, setScopeNote] = useState<string | null>(null);

  const canSeeOthers = viewerRole === 'owner' || viewerRole === 'co_owner' || viewerRole === 'admin';
  const [whoOpen, setWhoOpen] = useState(false);
  // SELECT, NOT TYPE (2026-09-15, UK: "mujhe select and choose chahiye
  // bas"). The scope=user/role filters used to be a free-text input --
  // pick from a real, fetched list of who has actually been active
  // instead of typing a username or role by hand and hoping it matches.
  const [activeUsers, setActiveUsers] = useState<{ username: string; role: string }[]>([]);
  const ROLE_OPTIONS = ['owner', 'co_owner', 'admin', 'user', 'guest'];

  useEffect(() => {
    if (!canSeeOthers) return;
    api.getActiveTraceUsers()
      .then(res => setActiveUsers((res?.users ?? []).map((u: any) => ({ username: u.username, role: u.role }))))
      .catch(() => setActiveUsers([]));
  }, [canSeeOthers, whoOpen]);
  const [history, setHistory] = useState<ActivityHistoryItem[]>([]);
  const [activeTurnId, setActiveTurnId] = useState(selectedTurnId || '');
  const [currentTrace, setCurrentTrace] = useState<TurnTrace | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLimit, setHistoryLimit] = useState(5);

  useEffect(() => {
    if (selectedTurnId && selectedTurnId !== activeTurnId) setActiveTurnId(selectedTurnId);
  }, [selectedTurnId]);

  useEffect(() => { loadTurns(); }, [activeTurnId]);

  // Pull the identity-tagged list when a scope other than the default
  // is chosen. 'mine' keeps the original behaviour untouched.
  useEffect(() => {
    if (traceScope === 'mine') { setScopedTurns(null); setScopeNote(null); return; }
    let cancelled = false;
    api.getTraces({
      scope: traceScope,
      username: traceScope === 'user' ? scopeValue : undefined,
      role: traceScope === 'role' ? scopeValue : undefined,
      limit: 40,
    })
      .then(res => {
        if (cancelled) return;
        if (!res?.allowed) { setScopedTurns([]); setScopeNote(res?.reason ?? null); return; }
        setScopedTurns(res.entries ?? []);
        setScopeNote(res.note ?? null);
      })
      .catch(err => { if (!cancelled) { setScopedTurns([]); setScopeNote(err?.message ?? null); } });
    return () => { cancelled = true; };
  }, [traceScope, scopeValue]);

  const loadTurns = async () => {
    setIsLoading(true);
    try {
      const hist = await api.getActivityHistory();
      setHistory(hist);
      const target = activeTurnId || hist[0]?.turnId;
      if (target) {
        if (!activeTurnId) setActiveTurnId(target);
        setCurrentTrace(await api.getTurnTrace(target));
      } else setCurrentTrace(null);
    } catch (err) {
      console.error('Error fetching turn trace:', err);
      setCurrentTrace(null);
    } finally {
      setIsLoading(false);
    }
  };

  const visibleHistory = [...history].sort((a, b) => b.startTime - a.startTime).slice(0, historyLimit);

  useEffect(() => {
    if (activeTurnId && !visibleHistory.some(item => item.turnId === activeTurnId)) {
      const fallback = visibleHistory[0]?.turnId;
      if (fallback) selectTurn(fallback);
    }
  }, [historyLimit, history, activeTurnId, onSelectTurnId]);

  const selectTurn = (id: string) => {
    setActiveTurnId(id);
    onSelectTurnId?.(id);
  };

  return (
    <div className="trace-inspector-page h-full overflow-y-auto overflow-x-hidden font-mono text-xs max-w-full p-3 sm:p-5">
      <header
        className="trace-inspector-bar"
        style={{ position: 'static', top: 'auto', bottom: 'auto', inset: 'auto', zIndex: 'auto' }}
      >
        <div className="trace-inspector-brand">
          <div className="trace-inspector-icon trace-inspector-icon-live"><FileSearch size={19} /><span className="trace-inspector-pulse" /></div>
          <div className="trace-inspector-heading">
            <div className="trace-inspector-eyebrow"><Radio size={10} /> JARVIS / OBSERVABILITY</div>
            <h1>Cognitive Trace</h1>
            <p>Per-turn execution monitor</p>
          </div>
        </div>

        <div className="trace-inspector-controls">
          <label className="trace-select-wrap trace-turn-select">
            <span>TURN</span>
            <select value={activeTurnId} onChange={e => selectTurn(e.target.value)} disabled={!history.length}>
              {visibleHistory.length ? visibleHistory.map(item => (
                <option key={item.turnId} value={item.turnId}>{item.turnId} — {item.query.slice(0, 38)}</option>
              )) : <option value="">No recorded turns</option>}
            </select>
            <ChevronDown size={14} />
          </label>
          <label className="trace-turn-window">
            <span>SHOW</span>
            <select value={historyLimit} onChange={e => setHistoryLimit(Number(e.target.value))}>
              {[5, 10, 30, 50].map(limit => <option key={limit} value={limit}>LAST {limit} TURNS</option>)}
            </select>
            <ChevronDown size={12} />
          </label>
          <button className="trace-action-btn trace-refresh" onClick={loadTurns} disabled={isLoading} title="Reload trace" aria-label="Reload trace">
            <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </header>

      {/* WHO filter -- SAME header-box style as the trace tree above
          (.trace-inspector-bar / -icon / -heading), collapsible, so it
          reads as part of the same instrument rather than a separate
          bolted-on control strip. */}
      <header
        className="trace-inspector-bar trace-who-bar"
        style={{ position: 'static', top: 'auto', bottom: 'auto', inset: 'auto', zIndex: 'auto' }}
      >
        <button
          type="button"
          className="trace-inspector-brand trace-who-brand-btn"
          onClick={() => setWhoOpen(o => !o)}
          aria-expanded={whoOpen}
        >
          <div className="trace-inspector-icon">
            <Users size={17} />
          </div>
          <div className="trace-inspector-heading">
            <div className="trace-inspector-eyebrow"><Radio size={10} /> JARVIS / IDENTITY</div>
            <h1>Session Filter</h1>
            <p>
              {scopedTurns === null
                ? `${viewerRole} view`
                : `${scopedTurns.length} turns -- ${traceScope}`}
            </p>
          </div>
          <ChevronDown
            size={16}
            style={{
              marginLeft: 4,
              transition: 'transform .18s',
              transform: whoOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              color: 'var(--jarvis-text-muted)',
            }}
          />
        </button>

        {whoOpen && (
          <div className="trace-inspector-controls trace-who-controls">
            <label className="trace-select-wrap trace-turn-select">
              <span>SCOPE</span>
              <select
                value={traceScope}
                onChange={e => { setTraceScope(e.target.value as any); setScopeValue(''); }}
              >
                <option value="mine">Mine</option>
                {canSeeOthers && <option value="all">All</option>}
                {canSeeOthers && <option value="user">User</option>}
                {canSeeOthers && <option value="role">Role</option>}
              </select>
              <ChevronDown size={14} />
            </label>

            {/* SELECT, NOT TYPE. Was a free-text input where UK had to
                type a username/role by hand with no guidance -- now a
                real dropdown of who has actually been active
                (scope=user) or the five real roles (scope=role). */}
            {traceScope === 'user' && (
              <label className="trace-select-wrap trace-turn-select">
                <span>USER</span>
                <select value={scopeValue} onChange={e => setScopeValue(e.target.value)}>
                  <option value="">Select a user...</option>
                  {activeUsers.map(u => (
                    <option key={u.username} value={u.username}>{u.username} ({u.role})</option>
                  ))}
                </select>
                <ChevronDown size={14} />
              </label>
            )}

            {traceScope === 'role' && (
              <label className="trace-select-wrap trace-turn-select">
                <span>ROLE</span>
                <select value={scopeValue} onChange={e => setScopeValue(e.target.value)}>
                  <option value="">Select a role...</option>
                  {ROLE_OPTIONS.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <ChevronDown size={14} />
              </label>
            )}

            <button
              className="trace-action-btn trace-refresh"
              onClick={() => setTraceScope(s => s)}
              title="Refresh"
              aria-label="Refresh"
            >
              <RefreshCw size={15} />
            </button>
          </div>
        )}
      </header>

      {scopeNote && <div className="trace-who-note">{scopeNote}</div>}

      {scopedTurns !== null && scopedTurns.length > 0 && whoOpen && (
        <div className="trace-who-list">
          {scopedTurns.slice(0, 12).map((entry: any) => (
            <button
              key={entry.request_id}
              className="trace-who-row"
              onClick={() => entry.request_id && selectTurn(entry.request_id)}
            >
              <span className="trace-who-user">{entry.username}</span>
              <span className="trace-who-role">{entry.role}</span>
              <span className="trace-who-text">{(entry.user_input || '').slice(0, 46)}</span>
              <span className="trace-who-time">{entry.timestamp}</span>
            </button>
          ))}
        </div>
      )}


      <main className="trace-inspector-main" style={{ width: '100%', minWidth: 0, margin: 0, padding: 0 }}>
        <style>{`
          .trace-inspector-page .trace-root { width:100%; max-width:100%; margin:0 auto; }
          .trace-inspector-page .trace-hero { padding:16px 16px 14px; }
          .trace-inspector-page .trace-hero-title { margin-top:12px; }
          .trace-inspector-page .trace-overview { margin-top:12px; gap:6px; }
          .trace-inspector-page .trace-metric { padding:8px 9px; }
          .trace-inspector-page .trace-flow { padding:14px 14px 16px; }
          .trace-inspector-page .trace-stage { margin-bottom:9px; border-radius:13px; }
          .trace-inspector-page .trace-stage-head { gap:7px; padding:9px 10px; }
          .trace-inspector-page .trace-stage-content { padding:10px; }
          .trace-inspector-page .trace-field { padding:8px 9px; }
          .trace-inspector-page .trace-flow-label { margin-bottom:9px; }
          .trace-inspector-page .trace-inspector-bar { position:static!important; top:auto!important; bottom:auto!important; inset:auto!important; z-index:auto!important; }
        `}</style>
        {currentTrace ? (
          <TraceTreeViewer trace={currentTrace} theme={theme} initiallyExpanded={true} />
        ) : (
          <div className="trace-empty">
            <FileSearch size={26} />
            <strong>{isLoading ? 'LOADING COGNITIVE TRACE' : 'NO TRACE RECORDED'}</strong>
            <span>{isLoading ? 'Fetching the latest workflow from JARVIS…' : 'Start a conversation to capture a per-turn trace.'}</span>
          </div>
        )}
      </main>
    </div>
  );
}
