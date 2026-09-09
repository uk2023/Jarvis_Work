import React, { useEffect, useState } from 'react';
import { Activity, BarChart3, ExternalLink, Maximize2, RefreshCw, Terminal, X } from 'lucide-react';
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

const formatTime = (timestamp: number) => {
  if (!timestamp) return '—';
  const value = timestamp > 1e12 ? timestamp : timestamp * 1000;
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

export function DashboardScreen({ onSelectTurn, theme, activeSection = 'monitor' }: DashboardScreenProps) {
  const [liveState, setLiveState] = useState<LiveStateResponse | null>(null);
  const [resources, setResources] = useState<SystemResourcesData | null>(null);
  const [history, setHistory] = useState<ActivityHistoryItem[]>([]);
  const [pollIntervalMs, setPollIntervalMs] = useState(2000);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [currentSection, setCurrentSection] = useState<'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'>(activeSection);
  const [expandedTable, setExpandedTable] = useState<'activity' | 'logs' | null>(null);
  const isDark = theme === 'dark';
  useEffect(() => setCurrentSection(activeSection), [activeSection]);
  const fetchDashboardData = async () => { try { setIsRefreshing(true); const [stateRes,resRes,histRes]=await Promise.all([api.getLiveState(),api.getResources(),api.getActivityHistory()]); setLiveState(stateRes); setResources(resRes); setHistory(histRes); } catch(err) { console.error('Failed to load dashboard metrics:',err); } finally { setIsRefreshing(false); } };
  useEffect(() => { fetchDashboardData(); const interval=pollIntervalMs>0?setInterval(fetchDashboardData,pollIntervalMs):null; return()=>{if(interval)clearInterval(interval);}; },[pollIntervalMs]);
  const showMonitor=currentSection==='monitor'||currentSection==='all', showMemory=currentSection==='memory'||currentSection==='all', showReasoning=currentSection==='reasoning'||currentSection==='all', showOrgans=currentSection==='organs'||currentSection==='all';
  const surface=isDark?'bg-[#080b12] border-white/10 text-white':'bg-white border-slate-200 text-slate-900';
  const headerControls=<><span className="trace-tab-control">PID: {liveState?.pid||'—'}</span><select value={pollIntervalMs} onChange={e=>setPollIntervalMs(Number(e.target.value))} className="trace-tab-control cursor-pointer outline-none"><option value={1000}>POLL: 1s</option><option value={2000}>POLL: 2s</option><option value={5000}>POLL: 5s</option><option value={0}>POLL: PAUSED</option></select><button onClick={fetchDashboardData} disabled={isRefreshing} className="trace-action-btn flex items-center gap-1.5" title="Sync now" aria-label="Sync now"><RefreshCw className={`h-3 w-3 ${isRefreshing?'animate-spin':''}`}/>SYNC</button></>;
  const expandButton=(table:'activity'|'logs')=><button onClick={()=>setExpandedTable(table)} className={`px-2 py-1 border rounded-md flex items-center gap-1 text-[8px] font-bold shrink-0 ${isDark?'bg-white/5 hover:bg-white/10 border-white/10 text-[#8eb3ff]':'bg-slate-50 hover:bg-slate-100 border-slate-200 text-[#315fbe]'}`}><Maximize2 className="w-2.5 h-2.5"/>Expand</button>;
  const activityTable=(expanded=false)=><div className={`border rounded-lg overflow-hidden jarvis-table-surface ${expanded?'min-w-[760px]':''}`}><div className="grid grid-cols-[minmax(0,.72fr)_minmax(0,2.2fr)_minmax(120px,.55fr)] gap-2 px-2.5 py-1.5 border-b jarvis-table-header text-[7px] uppercase tracking-[.14em]"><span className="flex items-center justify-center text-center">Transaction</span><span className="flex items-center justify-center text-center">Content</span><span className="flex items-center justify-center text-center">Timestamp</span></div><div className={expanded?'':'max-h-44 overflow-y-auto'}>{history.length===0?<div className="px-2.5 py-3 jarvis-table-muted text-[9px]">No activity history available.</div>:history.map(item=>{const selected=selectedTurnId===item.turnId;return <div key={item.turnId} onClick={()=>{setSelectedTurnId(item.turnId);onSelectTurn(item.turnId);}} className={`group relative grid grid-cols-[minmax(0,.72fr)_minmax(0,2.2fr)_minmax(120px,.55fr)] items-center gap-2 px-2.5 py-2 cursor-pointer border-b last:border-0 jarvis-table-row text-[8px] transition-all ${selected?(isDark?'bg-[#5b8def]/12':'bg-[#5b8def]/[.08]'):''}`}><span className="min-w-0 truncate font-bold jarvis-table-accent" title={item.turnId}>{item.turnId}</span><span className="min-w-0 truncate" title={item.query}>{item.query||'—'}</span><span className="shrink-0 text-center tabular-nums jarvis-table-muted">{formatTime(item.startTime)}</span>{selected&&<span className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#5b8def]"/>}<button onClick={e=>{e.stopPropagation();setSelectedTurnId(item.turnId);onSelectTurn(item.turnId);}} className={`absolute right-1.5 p-1 rounded ${isDark?'bg-black/30':'bg-white'} opacity-0 group-hover:opacity-100 jarvis-table-accent transition`} title="Inspect transaction" aria-label="Inspect transaction"><ExternalLink className="w-2.5 h-2.5"/></button></div>;})}</div></div>;
  const logsTable=(expanded=false)=><div className={`border rounded-lg overflow-hidden jarvis-table-surface ${expanded?'min-w-[900px]':''}`}><div className="grid grid-cols-[minmax(110px,.35fr)_minmax(90px,.28fr)_minmax(0,1fr)] gap-2 px-2.5 py-1.5 border-b jarvis-table-header text-[7px] uppercase tracking-[.14em]"><span className="flex items-center justify-center text-center">Timestamp</span><span className="flex items-center justify-center text-center">Level</span><span className="flex items-center justify-center text-center">Diagnostic Message</span></div><div className={expanded?'':'max-h-44 overflow-y-auto'}>{(liveState?.logs??[]).length===0?<div className="px-2.5 py-3 jarvis-table-muted text-[9px]">No diagnostic logs available.</div>:(liveState?.logs??[]).map((log,index)=>{const level=typeof log==='object'&&log!==null&&'level' in log?String((log as {level?:string}).level||'info').toLowerCase():'info';const message=typeof log==='string'?log:typeof log==='object'&&log!==null&&'message' in log?String((log as {message?:unknown}).message??''):String(log);const timestamp=typeof log==='object'&&log!==null&&'timestamp' in log?Number((log as {timestamp?:number}).timestamp||0):0;const warning=level==='warning'||level==='warn',error=level==='error';return <div key={index} className={`grid grid-cols-[minmax(110px,.35fr)_minmax(90px,.28fr)_minmax(0,1fr)] items-start gap-2 px-2.5 py-2 border-b last:border-0 jarvis-table-row text-[8px] leading-relaxed min-w-0 ${error?'text-rose-500':warning?'text-amber-500':''}`}><span className="jarvis-table-muted tabular-nums shrink-0 text-center">{formatTime(timestamp)}</span><span className={`font-bold uppercase shrink-0 text-center ${error?'text-rose-500':warning?'text-amber-500':'jarvis-table-accent'}`}>{level}</span><span className="min-w-0 break-words">{message}</span></div>;})}</div></div>;
  return <div className={`h-full overflow-y-auto overflow-x-hidden p-3 sm:p-5 space-y-3 font-mono text-xs max-w-full ${isDark?'trace-dark':'trace-light'}`}>
   {showMonitor&&<>
    <TabHeader icon={Activity} category="JARVIS / OBSERVABILITY" title="COGNITIVE MONITOR" subtitle="Live organism runtime monitor" controls={headerControls}/>
    <CognitivePipelineCard liveState={liveState} theme={theme}/><CognitiveMonitoringCards liveState={liveState} resources={resources} theme={theme}/>
    <section id="card-activity-history" className={`trace-root overflow-hidden ${surface}`}><div className="px-3 py-2.5 sm:px-4"><div className="flex items-center justify-between gap-3 mb-2"><div className="flex items-center gap-2 min-w-0"><BarChart3 className="w-3.5 h-3.5 text-[#5b8def] shrink-0"/><div className="min-w-0"><h2 className="font-bold text-[9px] uppercase tracking-wider truncate">Recent Activity History</h2><div className="text-[7px] text-slate-500 truncate">Transaction stream · select a row to inspect</div></div></div><div className="flex items-center gap-2 shrink-0"><span className="text-[7px] text-slate-500 uppercase tracking-[.1em]">{history.length} turns</span>{expandButton('activity')}</div></div>{activityTable()}</div></section>
    <section id="card-internal-logs" className={`trace-root overflow-hidden ${surface}`}><div className="px-3 py-2.5 sm:px-4"><div className="flex items-center justify-between gap-3 mb-2"><div className="flex items-center gap-2 min-w-0"><Terminal className="w-3.5 h-3.5 text-[#5b8def] shrink-0"/><div className="min-w-0"><h2 className="font-bold text-[9px] uppercase tracking-wider truncate">Internal Diagnostic Logs</h2><div className="text-[7px] text-slate-500 truncate">Runtime diagnostics · warnings and errors surfaced inline</div></div></div>{expandButton('logs')}</div>{logsTable()}</div></section>
   </>}
   {showMemory&&<MemoryDBPipeline liveState={liveState} resources={resources} theme={theme}/>} {showReasoning&&<><OvernightLearningCard theme={theme}/><SelfImprovementList theme={theme}/></>} {showOrgans&&<OrganIntrospectionViewer theme={theme}/>} 
   {expandedTable&&<div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm p-2 sm:p-5 flex items-center justify-center"><div className="w-full h-full max-w-[1500px] flex flex-col rounded-xl border shadow-2xl overflow-hidden jarvis-table-modal"><div className="flex items-center justify-between gap-3 px-3 sm:px-5 py-3 border-b jarvis-table-modal-head shrink-0"><div><h2 className="font-black text-[10px] sm:text-xs uppercase tracking-[.14em]">{expandedTable==='activity'?'Recent Activity History':'Internal Diagnostic Logs'}</h2><p className="mt-1 text-[8px] jarvis-table-muted">Full-window diagnostic table · spreadsheet view</p></div><button onClick={()=>setExpandedTable(null)} className="p-2 rounded-lg border jarvis-table-modal-head hover:opacity-80" title="Close" aria-label="Close expanded table"><X className="w-4 h-4"/></button></div><div className="flex-1 overflow-auto p-3 sm:p-5">{expandedTable==='activity'?activityTable(true):logsTable(true)}</div></div></div>}
  </div>;
}
