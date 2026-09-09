import React, { useEffect, useState } from 'react';
import { FileSearch, RefreshCw, ChevronDown, Radio } from 'lucide-react';
import { TurnTrace, ActivityHistoryItem, AppTheme } from '../types';
import { api } from '../api/client';
import { TraceTreeViewer } from './TraceTreeViewer';

interface TraceInspectorScreenProps {
  selectedTurnId?: string | null;
  onSelectTurnId?: (id: string) => void;
  theme: AppTheme;
}

export function TraceInspectorScreen({ selectedTurnId, onSelectTurnId, theme }: TraceInspectorScreenProps) {
  const [history, setHistory] = useState<ActivityHistoryItem[]>([]);
  const [activeTurnId, setActiveTurnId] = useState(selectedTurnId || '');
  const [currentTrace, setCurrentTrace] = useState<TurnTrace | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLimit, setHistoryLimit] = useState(5);

  useEffect(() => {
    if (selectedTurnId && selectedTurnId !== activeTurnId) setActiveTurnId(selectedTurnId);
  }, [selectedTurnId]);

  useEffect(() => { loadTurns(); }, [activeTurnId]);

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
    <div className="trace-inspector-page h-full overflow-y-auto overflow-x-hidden font-mono text-xs max-w-full">
      <header className="trace-inspector-bar">
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
                <option key={item.turnId} value={item.turnId}>
                  {item.turnId} — {item.query.slice(0, 38)}
                </option>
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

      <main className="trace-inspector-main">
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
