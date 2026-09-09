import React from 'react';
import { Activity, Brain, Database, Moon, Sparkles, Zap } from 'lucide-react';
import { motion } from 'motion/react';
import { AppTheme, LiveStateResponse } from '../types';

interface Props { liveState: LiveStateResponse | null; theme: AppTheme; }
type StateKey = 'IDLE' | 'PERCEIVING' | 'INDEXING' | 'CONSOLIDATING' | 'EXECUTING';
const STATES: Array<{key:StateKey;icon:React.ElementType;accent:string}> = [
 {key:'IDLE',icon:Moon,accent:'#64748b'}, {key:'PERCEIVING',icon:Activity,accent:'#5b8def'},
 {key:'INDEXING',icon:Database,accent:'#22c55e'}, {key:'CONSOLIDATING',icon:Brain,accent:'#06b6d4'}, {key:'EXECUTING',icon:Zap,accent:'#a855f7'}
];
const positions = [[50,50],[50,12],[84,36],[72,82],[28,82]];
export function CognitivePipelineCard({liveState,theme}:Props){
 const current=String(liveState?.stage||'IDLE').toUpperCase() as StateKey;
 const safeCurrent=STATES.some(s=>s.key===current)?current:'IDLE';
 const dark=theme==='dark';
 const activeIndex=Math.max(0,STATES.findIndex(s=>s.key===safeCurrent));
 return <section id="card-cognitive-pipeline" className={`trace-root ${dark?'trace-dark':'trace-light'} overflow-hidden`}>
  <div className="px-3 py-3 sm:px-4">
   <div className="flex items-center justify-between gap-3 mb-1"><div className="trace-flow-label !mb-0"><Activity size={13}/> COGNITIVE STATE <span>· LIVE SYSTEM POSITION</span></div><div className="trace-live shrink-0"><span/> LIVE</div></div>
   <div className="relative mx-auto mt-1 h-[250px] w-full max-w-[430px] overflow-hidden rounded-xl border bg-black/[.015] dark:bg-white/[.01]" aria-label={`Current cognitive state ${safeCurrent}`}>
    <div className="absolute inset-[18%] rounded-full border border-slate-400/10 dark:border-white/5"/>
    <div className="absolute inset-[31%] rounded-full border border-slate-400/8 dark:border-white/5"/>
    {STATES.map(({key,icon:Icon,accent},index)=>{const active=index===activeIndex; const [x,y]=positions[index]; return <motion.div key={key} className="absolute" animate={{left:`${x}%`,top:`${y}%`,scale:active?1.45:.72,opacity:active?1:.62}} transition={{type:'spring',stiffness:110,damping:16,mass:.7}} style={{transform:'translate(-50%,-50%)'}}>
      <motion.div animate={{boxShadow:active?`0 0 28px ${accent}55, 0 0 8px ${accent}35`:'0 4px 14px rgba(0,0,0,.16)'}} transition={{duration:.35}} className="relative flex h-[54px] w-[54px] items-center justify-center rounded-full border backdrop-blur-md" style={{borderColor:active?`${accent}85`:`${accent}30`,background:dark?'rgba(15,23,42,.82)':'rgba(255,255,255,.88)'}}>
       {active&&<motion.span className="absolute inset-[-8px] rounded-full border" style={{borderColor:`${accent}45`}} animate={{scale:[1,1.12,1],opacity:[.7,.15,.7]}} transition={{duration:2,repeat:Infinity,ease:'easeInOut'}}/>}
       <Icon size={active?18:15} style={{color:accent}}/>
       <span className={`absolute top-[calc(100%+7px)] whitespace-nowrap text-[8px] font-bold tracking-[.1em] ${active?'text-slate-900 dark:text-slate-100':'text-slate-500'}`}>{key}</span>
      </motion.div>
    </motion.div>})}
    <motion.div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none" animate={{opacity:[.35,.65,.35],scale:[.92,1.04,.92]}} transition={{duration:2.6,repeat:Infinity,ease:'easeInOut'}}><Sparkles size={14} className="text-slate-400"/></motion.div>
   </div>
   <div className="mt-2 flex items-center justify-center gap-x-3 text-[9px] uppercase tracking-wider text-slate-500"><span>CURRENT: <b style={{color:STATES[activeIndex].accent}}>{safeCurrent}</b></span><span>•</span><span>FALLBACK: <b className={liveState?.fallback_active?'text-amber-400':'text-emerald-400'}>{liveState?.fallback_active?'ACTIVE':'CLEAR'}</b></span></div>
  </div>
 </section>;
}
