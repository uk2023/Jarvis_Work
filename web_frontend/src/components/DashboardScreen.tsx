import React, { useEffect, useState } from 'react';
import { Activity, BarChart3, ExternalLink, RefreshCw, Terminal } from 'lucide-react';
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

export function DashboardScreen({ onSelectTurn, onNavigateToCLI, theme, activeSection = 'monitor' }: DashboardScreenProps) {
  const [liveState, setLiveState] = useState<LiveStateResponse | null>(null);
  const [resources, setResources] = useState<SystemResourcesData | null>(null);
  const [history, setHistory] = useState<ActivityHistoryItem[]>([]);
  const [pollIntervalMs, setPollIntervalMs] = useState(2000);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [currentSection, setCurrentSection] = useState<'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'>(activeSection);
  const isDark = theme === 'dark';
  useEffect(() => setCurrentSection(activeSection), [activeSection]);
  const fetchDashboardData = async () => { try { setIsRefreshing(true); const [stateRes,resRes,histRes]=await Promise.all([api.getLiveState(),api.getResources(),api.getActivityHistory()]); setLiveState(stateRes);setResources(resRes);setHistory(histRes);} catch(err){console.error('Failed to load dashboard metrics:',err);} finally{setIsRefreshing(false);} };
  useEffect(() => { fetchDashboardData(); const interval=pollIntervalMs>0?setInterval(fetchDashboardData,pollIntervalMs):null; return()=>{if(interval)clearInterval(interval);}; },[pollIntervalMs]);
  const showMonitor=currentSection==='monitor'||currentSection==='all',showMemory=currentSection==='memory'||currentSection==='all',showReasoning=currentSection==='reasoning'||currentSection==='all',showOrgans=currentSection==='organs'||currentSection==='all';
  const surface=isDark?'bg-[#080b12] border-white/10 text-white':'bg-white border-slate-200 text-slate-900';
  const tableSurface=isDark?'bg-[#070a10] border-white/10':'bg-slate-50 border-slate-200';
  const rowBorder=isDark?'border-white/[.055]':'border-slate-200';
  const headerControls=<><span className="trace-tab-control">PID: {liveState?.pid||'—'}</span><select value={pollIntervalMs} onChange={e=>setPollIntervalMs(Number(e.target.value))} className="trace-tab-control cursor-pointer outline-none"><option value={1000}>POLL: 1s</option><option value={2000}>POLL: 2s</option><option value={5000}>POLL: 5s</option><option value={0}>POLL: PAUSED</option></select><button onClick={fetchDashboardData} disabled={isRefreshing} className="trace-action-btn flex items-center gap-1.5" title="Sync now" aria-label="Sync now"><RefreshCw className={`h-3 w-3 ${isRefreshing?'animate-spin':''}`}/>SYNC</button></>;
  return <div className={`h-full overflow-y-auto overflow-x-hidden p-3 sm:p-5 space-y-3 font-mono text-xs max-w-full ${isDark?'trace-dark':'trace-light'}`}>
   {showMonitor&&<>
    <TabHeader icon={Activity} category="JARVIS / OBSERVABILITY" title="COGNITIVE MONITOR" subtitle="Live organism runtime monitor" controls={headerControls}/>
    <CognitivePipelineCard liveState={liveState} theme={theme}/><CognitiveMonitoringCards liveState={liveState} resources={resources} theme={theme}/>

    <section id="card-activity-history" className={`trace-root overflow-hidden ${surface}`}>
      <div className="px-3 py-2.5 sm:px-4">
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 min-w-0"><BarChart3 className="w-3.5 h-3.5 text-[#5b8def] shrink-0"/><div className="min-w-0"><h2 className="font-bold text-[9px] uppercase tracking-wider truncate">Recent Activity History</h2><div className="text-[7px] text-slate-500 truncate">Transaction stream · select a row to inspect</div></div></div>
          <span className="text-[7px] text-slate-500 uppercase tracking-[.1em] shrink-0">{history.length} turns</span>
        </div>
        <div className={`border rounded-lg overflow-hidden ${tableSurface}`}>
          <div className={`grid grid-cols-[minmax(0,.72fr)_minmax(0,2.2fr)_auto] gap-2 px-2.5 py-1.5 border-b ${rowBorder} text-[7px] uppercase tracking-[.14em] text-slate-500`}>
            <span>Transaction</span><span>Content</span><span className="text-right">Timestamp</span>
          </div>
          <div className="max-h-44 overflow-y-auto">
            {history.length===0?<div className="px-2.5 py-3 text-slate-500 text-[9px]">No activity history available.</div>:history.map(item=>{
              const selected=selectedTurnId===item.turnId;
              return <div key={item.turnId} onClick={()=>{setSelectedTurnId(item.turnId);onSelectTurn(item.turnId);}} className={`group relative grid grid-cols-[minmax(0,.72fr)_minmax(0,2.2fr)_auto] items-center gap-2 px-2.5 py-2 cursor-pointer border-b last:border-0 ${rowBorder} text-[8px] transition-all ${selected?(isDark?'bg-[#5b8def]/12':'bg-[#5b8def]/[.08]'):(isDark?'hover:bg-white/[.035]':'hover:bg-slate-100')}`}>
                <span className="min-w-0 truncate font-bold text-[#5b8def]" title={item.turnId}>{item.turnId}</span>
                <span className="min-w-0 truncate text-slate-300" title={item.query}>{item.query||'—'}</span>
                <span className="shrink-0 text-right tabular-nums text-slate-500">{formatTime(item.startTime)}</span>
                {selected&&<span className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#5b8def]"/>}
                <button onClick={e=>{e.stopPropagation();setSelectedTurnId(item.turnId);onSelectTurn(item.turnId);}} className={`absolute right-1.5 p-1 rounded ${isDark?'bg-black/30':'bg-white'} opacity-0 group-hover:opacity-100 text-[#5b8def] transition`} title="Inspect transaction" aria-label="Inspect transaction"><ExternalLink className="w-2.5 h-2.5"/></button>
              </div>;
            })}
          </div>
        </div>
      </div>
    </section>

    <section id="card-internal-logs" className={`trace-root overflow-hidden ${surface}`}>
      <div className="px-3 py-2.5 sm:px-4">
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 min-w-0"><Terminal className="w-3.5 h-3.5 text-[#5b8def] shrink-0"/><div className="min-w-0"><h2 className="font-bold text-[9px] uppercase tracking-wider truncate">Internal Diagnostic Logs</h2><div className="text-[7px] text-slate-500 truncate">Runtime diagnostics · warnings and errors surfaced inline</div></div></div>
          <button onClick={onNavigateToCLI} className={`px-2 py-1 border rounded-md flex items-center gap-1 text-[8px] font-bold shrink-0 ${isDark?'bg-white/5 hover:bg-white/10 border-white/10 text-[#5b8def]':'bg-slate-50 hover:bg-slate-100 border-slate-200 text-[#4f7ed8]'}`}><Terminal className="w-2.5 h-2.5"/>Open Virtual CLI</button>
        </div>
        <div className={`border rounded-lg overflow-hidden ${tableSurface}`}>
          <div className={`grid grid-cols-[auto_auto_minmax(0,1fr)] gap-2 px-2.5 py-1.5 border-b ${rowBorder} text-[7px] uppercase tracking-[.14em] text-slate-500`}><span>Timestamp</span><span>Level</span><span>Diagnostic Message</span></div>
          <div className="max-h-44 overflow-y-auto">
            {(liveState?.logs??[]).length===0?<div className="px-2.5 py-3 text-slate-500 text-[9px]">No diagnostic logs available.</div>:(liveState?.logs??[]).map((log,index)=>{
              const level=typeof log==='object'&&log!==null&&'level' in log?String((log as {level?:string}).level||'info').toLowerCase():'info';
              const message=typeof log==='string'?log:typeof log==='object'&&log!==null&&'message' in log?String((log as {message?:unknown}).message??''):String(log);
              const timestamp=typeof log==='object'&&log!==null&&'timestamp' in log?Number((log as {timestamp?:number}).timestamp||0):0;
              const warning=level==='warning'||level==='warn',error=level==='error';
              return <div key={index} className={`grid grid-cols-[auto_auto_minmax(0,1fr)] items-start gap-2 px-2.5 py-2 border-b last:border-0 ${rowBorder} text-[8px] leading-relaxed min-w-0 ${error?(isDark?'text-rose-400':'text-rose-600'):warning?(isDark?'text-amber-300':'text-amber-600'):isDark?'text-slate-400':'text-slate-600'} ${isDark?'hover:bg-white/[.025]':'hover:bg-slate-100'}`}>
                <span className="text-slate-500 tabular-nums shrink-0">{formatTime(timestamp)}</span><span className={`font-bold uppercase shrink-0 ${error?'text-rose-400':warning?'text-amber-400':'text-[#5b8def]'}`}>{level}</span><span className="min-w-0 break-words">{message}</span>
              </div>;
            })}
          </div>
        </div>
      </div>
    </section>
   </>}
   {showMemory&&<MemoryDBPipeline liveState={liveState} resources={resources} theme={theme}/>} {showReasoning&&<><OvernightLearningCard theme={theme}/><SelfImprovementList theme={theme}/></>} {showOrgans&&<OrganIntrospectionViewer theme={theme}/>} 
  </div>;
}
