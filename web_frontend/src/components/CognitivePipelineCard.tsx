import React from 'react';
import { Activity, Brain, CheckCircle2, Clock3, Database, Moon, Sparkles, Zap } from 'lucide-react';
import { AppTheme, LiveStateResponse, StageTransition } from '../types';

interface Props { liveState: LiveStateResponse | null; theme: AppTheme; }

type StateKey = 'IDLE' | 'PERCEIVING' | 'INDEXING' | 'CONSOLIDATING' | 'EXECUTING';

const STATES: Array<{ key: StateKey; icon: React.ElementType; accent: string }> = [
  { key: 'IDLE', icon: Moon, accent: '#64748b' },
  { key: 'PERCEIVING', icon: Activity, accent: '#5b8def' },
  { key: 'INDEXING', icon: Database, accent: '#22c55e' },
  { key: 'CONSOLIDATING', icon: Brain, accent: '#06b6d4' },
  { key: 'EXECUTING', icon: Zap, accent: '#a855f7' },
];

function duration(value?: number) { return `${Number(value ?? 0).toFixed(3)}s`; }
function ago(timestamp?: number) {
  if (!timestamp) return '—';
  const seconds = Math.max(0, (Date.now() - timestamp * 1000) / 1000);
  if (seconds < 60) return `${seconds.toFixed(1)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export function CognitivePipelineCard({ liveState, theme }: Props) {
  const current = String(liveState?.stage || 'IDLE').toUpperCase() as StateKey;
  const trace = [...(liveState?.pipeline_trace ?? [])].sort((a, b) => a.timestamp - b.timestamp).slice(-8);
  const dark = theme === 'dark';

  return (
    <section id="card-cognitive-pipeline" className={`trace-root ${dark ? 'trace-dark' : 'trace-light'} overflow-hidden`}>
      <div className="px-3 py-3 sm:px-4">
        <div className="flex items-center justify-between gap-3 mb-2.5">
          <div className="trace-flow-label !mb-0"><Activity size={13} /> COGNITIVE STATE <span>· LIVE SYSTEM POSITION</span></div>
          <div className="trace-live shrink-0"><span /> {current}</div>
        </div>

        <div className="w-full overflow-x-auto overflow-y-hidden pb-1">
          <div className="flex items-stretch justify-center gap-1.5 sm:gap-2 min-w-[760px] mx-auto">
            {STATES.map(({ key, icon: Icon, accent }) => {
              const active = key === current;
              return (
                <div key={key} className="relative flex-1 min-w-[140px] max-w-[220px] min-h-[64px]">
                  <div
                    className={`h-full flex items-center gap-2 px-2.5 py-2 border-b-2 transition-all ${active ? 'bg-white/[.045]' : 'bg-transparent'} ${dark ? 'border-white/10' : 'border-slate-200'}`}
                    style={active ? { borderBottomColor: accent, boxShadow: `inset 0 -1px 12px ${accent}18` } : undefined}
                  >
                    <span className="shrink-0 w-7 h-7 flex items-center justify-center border rounded-md" style={{ color: active ? accent : undefined, background: active ? `${accent}16` : undefined, borderColor: active ? `${accent}35` : undefined }}>
                      <Icon size={14} />
                    </span>
                    <div className="min-w-0">
                      <div className={`text-[10px] font-bold tracking-[.12em] truncate ${active ? '' : 'text-slate-500'}`} style={active ? { color: accent } : undefined}>{key}</div>
                      <div className="text-[9px] uppercase text-slate-500 truncate">{active ? 'CURRENT STATE' : 'STANDBY'}</div>
                    </div>
                    {active && <CheckCircle2 className="ml-auto shrink-0" size={13} style={{ color: accent }} />}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] uppercase tracking-wider text-slate-500">
          <span>CURRENT: <b style={{ color: STATES.find(s => s.key === current)?.accent }}>{current}</b></span>
          <span>•</span><span>TRANSITIONS: {trace.length}</span>
          <span>•</span><span>FALLBACK: <b className={liveState?.fallback_active ? 'text-amber-400' : 'text-emerald-400'}>{liveState?.fallback_active ? 'ACTIVE' : 'CLEAR'}</b></span>
        </div>
      </div>

      {trace.length > 0 && (
        <div className={`border-t px-3 py-2.5 sm:px-4 ${dark ? 'border-white/5' : 'border-slate-200'}`}>
          <div className="flex items-center gap-2 mb-1.5 text-[9px] font-bold uppercase tracking-wider text-slate-500"><Clock3 size={11} /> Recent transitions</div>
          <div className="overflow-x-auto overflow-y-hidden">
            <div className="flex gap-1.5 min-w-max">
              {trace.map((item: StageTransition, index) => (
                <div key={`${item.timestamp}-${index}`} className={`shrink-0 max-w-[210px] px-2 py-1.5 border ${dark ? 'border-white/8 bg-white/[.018]' : 'border-slate-200 bg-slate-50'}`}>
                  <div className="flex items-center gap-1.5 text-[9px] font-bold">
                    <span className="text-slate-500">{item.previous_stage}</span><span>→</span><span className="text-[#5b8def]">{item.stage}</span>
                    <span className="text-slate-500">{duration(item.duration_in_previous)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-[8px] text-slate-500" title={item.detail?.message ?? item.detail?.reason ?? ''}>{item.detail?.message ?? item.detail?.reason ?? ago(item.timestamp)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
