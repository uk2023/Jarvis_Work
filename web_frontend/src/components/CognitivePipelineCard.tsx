import React from 'react';
import { Activity, Brain, Database, Moon, Sparkles, Zap } from 'lucide-react';
import { AppTheme, LiveStateResponse } from '../types';

interface Props { liveState: LiveStateResponse | null; theme: AppTheme; }
type StateKey = 'IDLE' | 'PERCEIVING' | 'INDEXING' | 'CONSOLIDATING' | 'EXECUTING';
const STATES: Array<{key:StateKey; icon:React.ElementType; accent:string}> = [
 {key:'IDLE',icon:Moon,accent:'#64748b'}, {key:'PERCEIVING',icon:Activity,accent:'#5b8def'},
 {key:'INDEXING',icon:Database,accent:'#22c55e'}, {key:'CONSOLIDATING',icon:Brain,accent:'#06b6d4'},
 {key:'EXECUTING',icon:Zap,accent:'#a855f7'},
];

export function CognitivePipelineCard({liveState,theme}:Props){
 const dark=theme==='dark';
 const raw=String(liveState?.stage||'IDLE').toUpperCase();
 const current=(STATES.some(s=>s.key===raw)?raw:'IDLE') as StateKey;
 const active=STATES.find(s=>s.key===current)!;
 return <section id="card-cognitive-pipeline" className={`trace-root ${dark?'trace-dark':'trace-light'} w-full overflow-hidden`}>
  <div className="px-3 py-3 sm:px-4">
   <div className="trace-flow-label !mb-1"><Activity size={13}/> COGNITIVE STATE <span>· LIVE SYSTEM POSITION</span></div>
   <div className="relative mx-auto mt-1 h-[280px] w-full max-w-[430px] overflow-hidden">
    <div className="absolute left-1/2 top-1/2 h-[190px] w-[190px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/5 shadow-[0_0_55px_rgba(91,141,239,.08)]" />
    {STATES.filter(s=>s.key!==current).map((s,i)=>{
      const positions=['left-1/2 top-[18px] -translate-x-1/2','right-[12px] top-1/2 -translate-y-1/2','left-1/2 bottom-[18px] -translate-x-1/2','left-[12px] top-1/2 -translate-y-1/2'];
      const Icon=s.icon;
      return <div key={s.key} className={`absolute ${positions[i]} flex h-[54px] w-[54px] items-center justify-center rounded-full border shadow-lg transition-all duration-700 ease-out ${dark?'border-white/10 bg-slate-950/80':'border-slate-200 bg-white'}`} style={{boxShadow:`0 8px 24px ${s.accent}12`}} title={s.key}><Icon size={17} style={{color:s.accent,opacity:.72}}/></div>;
    })}
    <div className="absolute left-1/2 top-1/2 flex h-[124px] w-[124px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border transition-all duration-700 ease-out" style={{borderColor:`${active.accent}70`,background:`radial-gradient(circle, ${active.accent}22 0%, ${active.accent}09 48%, transparent 72%)`,boxShadow:`0 0 24px ${active.accent}35, 0 0 70px ${active.accent}18`}}>
      <div className="absolute inset-[10px] rounded-full border animate-pulse" style={{borderColor:`${active.accent}35`}}/>
      <div className="relative text-center"><active.icon size={22} className="mx-auto mb-1.5" style={{color:active.accent}}/><div className="text-[12px] font-black tracking-[.16em]" style={{color:active.accent}}>{current}</div><div className="mt-1 text-[8px] font-bold tracking-[.14em] text-slate-500">ACTIVE STATE</div></div>
    </div>
   </div>
   <div className="mt-1 flex items-center justify-center gap-2 text-[9px] uppercase tracking-[.14em] text-slate-500"><span>CURRENT STATE:</span><b style={{color:active.accent}}>{current}</b></div>
  </div>
 </section>;
}
