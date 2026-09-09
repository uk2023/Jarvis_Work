import React, { useEffect, useState } from 'react';
import { FileSearch, ChevronDown } from 'lucide-react';
import { TurnTrace, ActivityHistoryItem, AppTheme } from '../types';
import { api } from '../api/client';
import { TraceTreeViewer } from './TraceTreeViewer';
import { TabHeader } from './TabHeader';

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

  useEffect(() => { if (selectedTurnId && selectedTurnId !== activeTurnId) setActiveTurnId(selectedTurnId); }, [selectedTurnId]);
  useEffect(() => { loadTurns(); }, [activeTurnId]);
  const loadTurns = async () => { setIsLoading(true); try { const hist = await api.getActivityHistory(); setHistory(hist); const target = activeTurnId || hist[0]?.turnId; if (target) { if (!activeTurnId) setActiveTurnId(target); setCurrentTrace(await api.getTurnTrace(target)); } else setCurrentTrace(null); } catch (err) { console.error('Error fetching turn trace:', err); setCurrentTrace(null); } finally { setIsLoading(false); } };
  const visibleHistory = [...history].sort((a, b) => b.startTime - a.startTime).slice(0, historyLimit);
  useEffect(() => { if (activeTurnId && !visibleHistory.some(item => item.turnId === activeTurnId)) { const fallback = visibleHistory[0]?.turnId; if (fallback) selectTurn(fallback); } }, [historyLimit, history, activeTurnId, onSelectTurnId]);
  const selectTurn = (id: string) => { setActiveTurnId(id); onSelectTurnId?.(id); };

  const selectClass = 'shrink-0 py-1 px-2 text-[10px] font-mono bg-slate-50 border border-slate-200/60 rounded-lg text-slate-700 focus:outline-none dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200';
  const controls = <>
    <label className="shrink-0 flex items-center gap-1 text-[10px] font-mono text-slate-500 dark:text-slate-400"><span>TURN</span><select className={`${selectClass} max-w-[180px]`} value={activeTurnId} onChange={e => selectTurn(e.target.value)} disabled={!history.length}>{visibleHistory.length ? visibleHistory.map(item => <option key={item.turnId} value={item.turnId}>{item.turnId} — {item.query.slice(0, 38)}</option>) : <option value="">No recorded turns</option>}</select><ChevronDown size={11} /></label>
    <label className="shrink-0 flex items-center gap-1 text-[10px] font-mono text-slate-500 dark:text-slate-400"><span>SHOW</span><select className={selectClass} value={historyLimit} onChange={e => setHistoryLimit(Number(e.target.value))}>{[5, 10, 30, 50].map(limit => <option key={limit} value={limit}>LAST {limit} TURNS</option>)}</select><ChevronDown size={11} /></label>
    {isLoading && <span className="shrink-0 text-[10px] font-mono text-slate-400">LOADING</span>}
  </>;

  return (<div className="trace-inspector-page"><TabHeader icon={FileSearch} category="JARVIS / OBSERVABILITY" title="COGNITIVE TRACE" controls={controls} /><main className="trace-inspector-main">{currentTrace ? <TraceTreeViewer trace={currentTrace} theme={theme} initiallyExpanded={true} /> : <div className="trace-empty"><FileSearch size={26} /><strong>{isLoading ? 'LOADING COGNITIVE TRACE' : 'NO TRACE RECORDED'}</strong><span>{isLoading ? 'Fetching the latest workflow from JARVIS…' : 'Start a conversation to capture a per-turn trace.'}</span></div>}</main></div>);
}
