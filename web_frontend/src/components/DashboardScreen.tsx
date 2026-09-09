import React, { useEffect, useState } from 'react';
import { Activity, ArrowRight, BarChart3, ExternalLink, RefreshCw, Terminal } from 'lucide-react';
import { LiveStateResponse, SystemResourcesData, ActivityHistoryItem, AppTheme } from '../types';
import { api } from '../api/client';
import { OrganIntrospectionViewer } from './OrganIntrospectionViewer';
import { OvernightLearningCard } from './OvernightLearningCard';
import { SelfImprovementList } from './SelfImprovementList';
import { MemoryDBPipeline } from './MemoryDBPipeline';
import { TabHeader } from './TabHeader';
import { CognitivePipelineCard } from './CognitivePipelineCard';
import { CognitiveMonitoringCards } from './CognitiveMonitoringCards';

interface DashboardScreenProps {
  onSelectTurn: (turnId: string) => void;
  onNavigateToCLI: () => void;
  theme: AppTheme;
  activeSection?: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all';
  onSelectSection?: (section: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all') => void;
}

export function DashboardScreen({ onSelectTurn, onNavigateToCLI, theme, activeSection = 'monitor' }: DashboardScreenProps) {
  const [liveState, setLiveState] = useState<LiveStateResponse | null>(null);
  const [resources, setResources] = useState<SystemResourcesData | null>(null);
  const [history, setHistory] = useState<ActivityHistoryItem[]>([]);
  const [pollIntervalMs, setPollIntervalMs] = useState(2000);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentSection, setCurrentSection] = useState<'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'>(activeSection);
  const isDark = theme === 'dark';

  useEffect(() => setCurrentSection(activeSection), [activeSection]);

  const fetchDashboardData = async () => {
    try {
      setIsRefreshing(true);
      const [stateRes, resRes, histRes] = await Promise.all([
        api.getLiveState(),
        api.getResources(),
        api.getActivityHistory(),
      ]);
      setLiveState(stateRes);
      setResources(resRes);
      setHistory(histRes);
    } catch (err) {
      console.error('Failed to load dashboard metrics:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = pollIntervalMs > 0 ? setInterval(fetchDashboardData, pollIntervalMs) : null;
    return () => { if (interval) clearInterval(interval); };
  }, [pollIntervalMs]);

  const showMonitor = currentSection === 'monitor' || currentSection === 'all';
  const showMemory = currentSection === 'memory' || currentSection === 'all';
  const showReasoning = currentSection === 'reasoning' || currentSection === 'all';
  const showOrgans = currentSection === 'organs' || currentSection === 'all';

  const surface = isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900';
  const logSurface = isDark ? 'bg-black/30 border-white/5' : 'bg-slate-950 border-slate-200';
  const headerControls = (
    <>
      <span className="trace-tab-control">PID: {liveState?.pid || '—'}</span>
      <select value={pollIntervalMs} onChange={e => setPollIntervalMs(Number(e.target.value))} className="trace-tab-control cursor-pointer outline-none">
        <option value={1000}>POLL: 1s</option>
        <option value={2000}>POLL: 2s</option>
        <option value={5000}>POLL: 5s</option>
        <option value={0}>POLL: PAUSED</option>
      </select>
      <button onClick={fetchDashboardData} disabled={isRefreshing} className="trace-action-btn flex items-center gap-1.5" title="Sync now" aria-label="Sync now">
        <RefreshCw className={`h-3 w-3 ${isRefreshing ? 'animate-spin' : ''}`} />SYNC
      </button>
    </>
  );

  return (
    <div className={`h-full overflow-y-auto overflow-x-hidden p-3 sm:p-5 space-y-3 font-mono text-xs max-w-full ${isDark ? 'trace-dark' : 'trace-light'}`}>
      {showMonitor && <>
        <TabHeader icon={Activity} category="JARVIS / OBSERVABILITY" title="COGNITIVE MONITOR" subtitle="Live organism runtime monitor" controls={headerControls} />

        <CognitivePipelineCard liveState={liveState} theme={theme} />
        <CognitiveMonitoringCards liveState={liveState} resources={resources} theme={theme} />

        <section id="card-activity-history" className={`trace-root overflow-hidden ${surface}`}>
          <div className="px-3 py-2.5 sm:px-4">
            <div className="flex items-center justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 min-w-0"><BarChart3 className="w-3.5 h-3.5 text-[#5b8def] shrink-0" /><h2 className="font-bold text-[10px] uppercase tracking-wider truncate">Recent Activity History</h2></div>
              <span className="text-[8px] text-slate-500 uppercase shrink-0">Completed Turns</span>
            </div>
            <div className={`border overflow-hidden ${logSurface}`}>
              <div className="max-h-60 overflow-y-auto p-1.5">
                {history.length === 0 ? <div className="p-2 text-slate-500 text-[10px]">No activity history available.</div> : history.map(item => {
                  const running = item.endTime === null;
                  return <div key={item.turnId} onClick={() => onSelectTurn(item.turnId)} className={`group flex flex-wrap items-center gap-x-2.5 gap-y-1 px-2 py-1.5 cursor-pointer border border-transparent text-[9px] transition ${isDark ? 'hover:bg-white/[.035] hover:border-white/5' : 'hover:bg-white/10 hover:border-white/5'}`}>
                    <span className="text-[#5b8def] font-bold shrink-0">{item.turnId}</span>
                    <span className="truncate max-w-[220px] text-slate-300" title={item.query}>{item.query}</span>
                    <span className={running ? 'text-amber-400' : 'text-slate-400'}>{running ? 'RUNNING' : `${item.durationSeconds.toFixed(2)}s`}</span>
                    <span className="flex items-center gap-1 text-slate-500 min-w-0 truncate">{item.stagePath.map((stage, index) => <React.Fragment key={`${item.turnId}-${stage}-${index}`}><span>{stage}</span>{index < item.stagePath.length - 1 && <ArrowRight className="w-2.5 h-2.5 shrink-0" />}</React.Fragment>)}</span>
                    <button onClick={e => { e.stopPropagation(); onSelectTurn(item.turnId); }} className="ml-auto text-[#5b8def] opacity-70 group-hover:opacity-100 shrink-0" title="Inspect turn"><ExternalLink className="w-3 h-3" /></button>
                  </div>;
                })}
              </div>
            </div>
          </div>
        </section>

        <section id="card-internal-logs" className={`trace-root overflow-hidden ${surface}`}>
          <div className="px-3 py-2.5 sm:px-4">
            <div className="flex items-center justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 min-w-0"><Terminal className="w-3.5 h-3.5 text-[#5b8def] shrink-0" /><h2 className="font-bold text-[10px] uppercase tracking-wider truncate">Internal Diagnostic Logs</h2></div>
              <button onClick={onNavigateToCLI} className={`px-2 py-1 border flex items-center gap-1 text-[9px] font-bold shrink-0 ${isDark ? 'bg-white/5 hover:bg-white/10 border-white/10 text-[#5b8def]' : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-[#4f7ed8]'}`}><Terminal className="w-3 h-3" />Open Virtual CLI</button>
            </div>
            <div className={`border overflow-hidden ${logSurface}`}>
              <div className="max-h-60 overflow-y-auto p-2 space-y-1">
                {(liveState?.logs ?? []).length === 0 ? <div className="text-slate-500 text-[10px]">No diagnostic logs available.</div> : (liveState?.logs ?? []).map((log, index) => {
                  const level = typeof log === 'object' && log !== null && 'level' in log ? String((log as { level?: string }).level || 'info').toLowerCase() : 'info';
                  const message = typeof log === 'string' ? log : typeof log === 'object' && log !== null && 'message' in log ? String((log as { message?: unknown }).message ?? '') : String(log);
                  const warning = level === 'warning' || level === 'warn';
                  const error = level === 'error';
                  return <div key={index} className={`flex gap-2 text-[9px] leading-relaxed min-w-0 ${error ? 'text-rose-400' : warning ? 'text-amber-300' : isDark ? 'text-slate-400' : 'text-slate-300'}`}>
                    <span className="opacity-40 shrink-0">[{String(index + 1).padStart(3, '0')}]</span><span className={`font-bold uppercase shrink-0 ${error ? 'text-rose-400' : warning ? 'text-amber-400' : 'text-[#5b8def]'}`}>{level}</span><span className="min-w-0 break-words">{message}</span>
                  </div>;
                })}
              </div>
            </div>
          </div>
        </section>
      </>}

      {showMemory && <MemoryDBPipeline liveState={liveState} resources={resources} theme={theme} />}
      {showReasoning && <><OvernightLearningCard theme={theme} /><SelfImprovementList theme={theme} /></>}
      {showOrgans && <OrganIntrospectionViewer theme={theme} />}
    </div>
  );
}
