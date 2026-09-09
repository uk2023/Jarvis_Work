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
 const positions=['left-1/2 top-[18px] -translate-x-1/2','right-[30px] top-1/2 -translate-y-1/2','left-1/2 bottom-[18px] -translate-x-1/2','left-[30px] top-1/2 -translate-y-1/2'];
 return <section id="card-cognitive-pipeline" className={`trace-root ${dark?'trace-dark':'trace-light'} w-full overflow-hidden`}>
  <div className="px-3 py-3 sm:px-4">
   <div className="trace-flow-label !mb-1"><Activity size={13}/> COGNITIVE STATE <span>· LIVE SYSTEM POSITION</span></div>
   <div className="relative mx-auto mt-1 h-[252px] w-full max-w-[390px] overflow-hidden">
    <div className="absolute left-1/2 top-1/2 h-[190px] w-[190px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/5" />
    <div className="absolute left-1/2 top-1/2 h-[158px] w-[158px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed animate-[spin_16s_linear_infinite]" style={{borderColor:`${active.accent}18`}} />
    {inactive.map((s,i)=>{const Icon=s.icon;return <div key={s.key} className={`absolute ${positions[i]} flex h-[20px] w-[20px] items-center justify-center rounded-full border shadow-xl transition-all duration-700 ease-out animate-[pulse_2.2s_ease-in-out_infinite]`} style={{background:`radial-gradient(circle at 30% 25%, ${s.accent}55, ${s.accent}18 44%, ${s.accent}08 68%, transparent 78%)`,borderColor:`${s.accent}55`,boxShadow:`inset -3px -4px 7px rgba(0,0,0,.45), inset 2px 2px 5px rgba(255,255,255,.18), 0 5px 15px rgba(0,0,0,.32), 0 0 12px ${s.accent}30`}} title={s.key}><Icon size={7} style={{color:s.accent,opacity:.9,filter:`drop-shadow(0 0 3px ${s.accent})`}}/></div>})}
    <div className="absolute left-1/2 top-1/2 h-[68px] w-[68px] -translate-x-1/2 -translate-y-1/2 flex items-center justify-center rounded-full border transition-all duration-700 ease-out animate-[pulse_2.1s_ease-in-out_infinite]" style={{borderColor:`${active.accent}a0`,background:`radial-gradient(circle at 32% 28%, ${active.accent}70 0%, ${active.accent}30 38%, ${active.accent}10 65%, transparent 84%)`,boxShadow:`inset -8px -9px 18px rgba(0,0,0,.4), inset 5px 5px 13px rgba(255,255,255,.15), 0 8px 24px rgba(0,0,0,.38), 0 0 34px ${active.accent}65, 0 0 86px ${active.accent}30`}}>
      <div className="absolute -inset-[10px] rounded-full border animate-[spin_5s_linear_infinite]" style={{borderColor:`${active.accent}35`,borderTopColor:`${active.accent}c5`,borderRightColor:`${active.accent}70`,boxShadow:`0 0 18px ${active.accent}30`}}/>
      <div className="absolute -inset-[4px] rounded-full border animate-pulse" style={{borderColor:`${active.accent}30`}}/>
      <active.icon size={18} style={{color:active.accent,filter:`drop-shadow(0 0 8px ${active.accent})`}}/>
    </div>
   </div>
   <div className="mt-1 flex items-center justify-center gap-2 text-[9px] uppercase tracking-[.14em] text-slate-500"><span>CURRENT STATE:</span><b style={{color:active.accent}}>{current}</b></div>
  </div>
 </section>;
}
