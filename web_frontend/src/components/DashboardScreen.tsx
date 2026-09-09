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

const formatTime = (timestamp: number) => {
  if (!timestamp) return '—';
  return new Date(timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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
  const logSurface=isDark?'bg-black/30 border-white/5':'bg-slate-950 border-slate-200';
  const headerControls=<><span className="trace-tab-control">PID: {liveState?.pid||'—'}</span><select value={pollIntervalMs} onChange={e=>setPollIntervalMs(Number(e.target.value))} className="trace-tab-control cursor-pointer outline-none"><option value={1000}>POLL: 1s</option><option value={2000}>POLL: 2s</option><option value={5000}>POLL: 5s</option><option value={0}>POLL: PAUSED</option></select><button onClick={fetchDashboardData} disabled={isRefreshing} className="trace-action-btn flex items-center gap-1.5" title="Sync now" aria-label="Sync now"><RefreshCw className={`h-3 w-3 ${isRefreshing?'animate-spin':''}`}/>SYNC</button></>;
  return <div className={`h-full overflow-y-auto overflow-x-hidden p-3 sm:p-5 space-y-3 font-mono text-xs max-w-full ${isDark?'trace-dark':'trace-light'}`}>
   {showMonitor&&<>
    <TabHeader icon={Activity} category="JARVIS / OBSERVABILITY" title="COGNITIVE MONITOR" subtitle="Live organism runtime monitor" controls={headerControls}/>
    <CognitivePipelineCard liveState={liveState} theme={theme}/><CognitiveMonitoringCards liveState={liveState} resources={resources} theme={theme}/>

    <section id="card-activity-history" className={`trace-root overflow-hidden ${surface}`}>
      <div className="px-3 py-2 sm:px-3">
        <div className="flex items-center justify-between gap-3 mb-1.5">
          <div className="flex items-center gap-2 min-w-0"><BarChart3 className="w-3.5 h-3.5 text-[#5b8def] shrink-0"/><h2 className="font-bold text-[9px] uppercase tracking-wider truncate">Recent Activity History</h2></div>
          <span className="text-[7px] text-slate-500 uppercase shrink-0">Completed Turns</span>
        </div>
        <div className={`border rounded-md overflow-hidden ${logSurface}`}>
          <div className="grid grid-cols-[minmax(0,.7fr)_minmax(0,2.2fr)_auto] gap-2 px-2 py-1 border-b border-white/5 text-[7px] uppercase tracking-[.12em] text-slate-500">
            <span>Transaction</span><span>Content</span><span>Time</span>
          </div>
          <div className="max-h-44 overflow-y-auto p-1">
            {history.length===0?<div className="p-2 text-slate-500 text-[9px]">No activity history available.</div>:history.map(item=>{
              const running=item.endTime===null;
              const selected=selectedTurnId===item.turnId;
              return <div key={item.turnId} onClick={()=>{setSelectedTurnId(item.turnId);onSelectTurn(item.turnId);}} className={`group relative grid grid-cols-[minmax(0,.7fr)_minmax(0,2.2fr)_auto] items-center gap-2 px-2 py-1.5 cursor-pointer border-b last:border-0 border-white/5 text-[8px] transition ${selected?'bg-[#5b8def]/12 ring-1 ring-inset ring-[#5b8def]/45':isDark?'hover:bg-white/[.035]':'hover:bg-white/10'}`}>
                <span className="text-[#5b8def] font-bold truncate">{item.turnId}</span>
                <span className="min-w-0 truncate text-slate-300" title={item.query}>{item.query||'—'}</span>
                <span className={`${running?'text-amber-400':'text-slate-400'} shrink-0 tabular-nums`}>{formatTime(item.startTime)}</span>
                {selected&&<span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-[#5b8def]"/>}
                <button onClick={e=>{e.stopPropagation();setSelectedTurnId(item.turnId);onSelectTurn(item.turnId);}} className="absolute right-1.5 opacity-0 group-hover:opacity-100 text-[#5b8def] transition" title="Inspect transaction" aria-label="Inspect transaction"><ExternalLink className="w-2.5 h-2.5"/></button>
              </div>;
            })}
          </div>
        </div>
      </div>
    </section>

    <section id="card-internal-logs" className={`trace-root overflow-hidden ${surface}`}>
      <div className="px-3 py-2 sm:px-3">
        <div className="flex items-center justify-between gap-3 mb-1.5">
          <div className="flex items-center gap-2 min-w-0"><Terminal className="w-3.5 h-3.5 text-[#5b8def] shrink-0"/><h2 className="font-bold text-[9px] uppercase tracking-wider truncate">Internal Diagnostic Logs</h2></div>
          <button onClick={onNavigateToCLI} className={`px-2 py-1 border rounded-md flex items-center gap-1 text-[8px] font-bold shrink-0 ${isDark?'bg-white/5 hover:bg-white/10 border-white/10 text-[#5b8def]':'bg-slate-50 hover:bg-slate-100 border-slate-200 text-[#4f7ed8]'}`}><Terminal className="w-2.5 h-2.5"/>Open Virtual CLI</button>
        </div>
        <div className={`border rounded-md overflow-hidden ${logSurface}`}>
          <div className="grid grid-cols-[auto_auto_minmax(0,1fr)] gap-2 px-2 py-1 border-b border-white/5 text-[7px] uppercase tracking-[.12em] text-slate-500"><span>Time</span><span>Level</span><span>Diagnostic Message</span></div>
          <div className="max-h-44 overflow-y-auto p-1">
            {(liveState?.logs??[]).length===0?<div className="p-2 text-slate-500 text-[9px]">No diagnostic logs available.</div>:(liveState?.logs??[]).map((log,index)=>{
              const level=typeof log==='object'&&log!==null&&'level' in log?String((log as {level?:string}).level||'info').toLowerCase():'info';
              const message=typeof log==='string'?log:typeof log==='object'&&log!==null&&'message' in log?String((log as {message?:unknown}).message??''):String(log);
              const timestamp=typeof log==='object'&&log!==null&&'timestamp' in log?Number((log as {timestamp?:number}).timestamp||0):0;
              const warning=level==='warning'||level==='warn',error=level==='error';
              return <div key={index} className={`grid grid-cols-[auto_auto_minmax(0,1fr)] items-start gap-2 px-2 py-1.5 border-b last:border-0 border-white/5 text-[8px] leading-relaxed min-w-0 ${error?'text-rose-400':warning?'text-amber-300':isDark?'text-slate-400':'text-slate-300'}`}>
                <span className="text-slate-600 tabular-nums shrink-0">{formatTime(timestamp)}</span><span className={`font-bold uppercase shrink-0 ${error?'text-rose-400':warning?'text-amber-400':'text-[#5b8def]'}`}>{level}</span><span className="min-w-0 break-words">{message}</span>
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
