import React from 'react';
import { Activity, Brain, Database, Moon, Zap } from 'lucide-react';
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
 const positions=['left-1/2 top-[12px] -translate-x-1/2','right-[18px] top-1/2 -translate-y-1/2','left-1/2 bottom-[12px] -translate-x-1/2','left-[18px] top-1/2 -translate-y-1/2'];
 return <section id="card-cognitive-pipeline" className={`trace-root ${dark?'trace-dark':'trace-light'} w-full overflow-hidden`}>
  <div className="px-3 py-3 sm:px-4">
   <div className="trace-flow-label !mb-1"><Activity size={13}/> COGNITIVE STATE <span>· LIVE SYSTEM POSITION</span></div>
   <div className="relative mx-auto mt-1 h-[252px] w-full max-w-[390px] overflow-hidden">
    <div className="absolute left-1/2 top-1/2 h-[172px] w-[172px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/5" />
    {inactive.map((s,i)=>{const Icon=s.icon;return <div key={s.key} className={`absolute ${positions[i]} flex h-[24px] w-[24px] items-center justify-center rounded-full border shadow-xl transition-all duration-700 ease-out animate-[pulse_2.8s_ease-in-out_infinite] ${dark?'border-white/10 bg-slate-950/90':'border-slate-200 bg-white'}`} style={{background:`radial-gradient(circle at 32% 28%, ${s.accent}48, ${s.accent}14 48%, transparent 76%)`,boxShadow:`inset -2px -3px 6px rgba(0,0,0,.38), inset 2px 2px 5px rgba(255,255,255,.12), 0 5px 14px rgba(0,0,0,.28), 0 0 14px ${s.accent}20`}} title={s.key}><Icon size={8} style={{color:s.accent,opacity:.88}}/></div>})}
    <div className="absolute left-1/2 top-1/2 flex h-[76px] w-[108px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[38%] border transition-all duration-700 ease-out" style={{borderColor:`${active.accent}85`,background:`radial-gradient(circle at 34% 28%, ${active.accent}55 0%, ${active.accent}25 35%, ${active.accent}0d 64%, transparent 82%)`,boxShadow:`inset -7px -8px 18px rgba(0,0,0,.38), inset 5px 5px 13px rgba(255,255,255,.13), 0 8px 24px rgba(0,0,0,.38), 0 0 30px ${active.accent}55, 0 0 76px ${active.accent}28`}}>
      <div className="absolute -inset-[10px] rounded-[44%] border animate-[spin_7s_linear_infinite]" style={{borderColor:`${active.accent}35`,borderTopColor:`${active.accent}b0`,boxShadow:`0 0 18px ${active.accent}22`}}/>
      <div className="absolute -inset-[4px] rounded-[42%] border animate-pulse" style={{borderColor:`${active.accent}24`}}/>
      <active.icon size={17} style={{color:active.accent,filter:`drop-shadow(0 0 7px ${active.accent})`}}/>
    </div>
   </div>
   <div className="mt-1 flex items-center justify-center gap-2 text-[9px] uppercase tracking-[.14em] text-slate-500"><span>CURRENT STATE:</span><b style={{color:active.accent}}>{current}</b></div>
  </div>
 </section>;
}
