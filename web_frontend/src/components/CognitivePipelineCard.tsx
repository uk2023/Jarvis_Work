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
 const inactive=STATES.filter(s=>s.key!==current);
 const positions=['left-1/2 top-[10px] -translate-x-1/2','right-[8px] top-1/2 -translate-y-1/2','left-1/2 bottom-[10px] -translate-x-1/2','left-[8px] top-1/2 -translate-y-1/2'];
 return <section id="card-cognitive-pipeline" className={`trace-root ${dark?'trace-dark':'trace-light'} w-full overflow-hidden`}>
  <div className="px-3 py-3 sm:px-4">
   <div className="trace-flow-label !mb-1"><Activity size={13}/> COGNITIVE STATE <span>· LIVE SYSTEM POSITION</span></div>
   <div className="relative mx-auto mt-1 h-[252px] w-full max-w-[390px] overflow-hidden">
    <div className="absolute left-1/2 top-1/2 h-[164px] w-[164px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/5" />
    {inactive.map((s,i)=>{const Icon=s.icon;return <div key={s.key} className={`absolute ${positions[i]} flex h-[30px] w-[30px] items-center justify-center rounded-md border shadow-lg transition-all duration-700 ease-out animate-pulse ${dark?'border-white/10 bg-slate-950/80':'border-slate-200 bg-white'}`} style={{boxShadow:`0 0 18px ${s.accent}18`}} title={s.key}><Icon size={11} style={{color:s.accent,opacity:.78}}/></div>})}
    <div className="absolute left-1/2 top-1/2 flex h-[92px] w-[124px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-2xl border transition-all duration-700 ease-out" style={{borderColor:`${active.accent}75`,background:`radial-gradient(circle, ${active.accent}25 0%, ${active.accent}09 55%, transparent 78%)`,boxShadow:`0 0 26px ${active.accent}45, 0 0 72px ${active.accent}22`}}>
      <div className="absolute -inset-[9px] rounded-[22px] border animate-pulse" style={{borderColor:`${active.accent}30`,boxShadow:`0 0 20px ${active.accent}18`}}/>
      <active.icon size={18} style={{color:active.accent}}/>
    </div>
   </div>
   <div className="mt-1 flex items-center justify-center gap-2 text-[9px] uppercase tracking-[.14em] text-slate-500"><span>CURRENT STATE:</span><b style={{color:active.accent}}>{current}</b></div>
  </div>
 </section>;
}
