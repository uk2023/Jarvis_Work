import React from 'react';
import { Activity, Brain, Cpu, Database, GraduationCap, Languages, Moon, Network, Radio, ShieldCheck, Sparkles, Target, TrendingDown, Workflow } from 'lucide-react';
import { AppTheme, LiveStateResponse, SystemResourcesData } from '../types';

interface Props { liveState: LiveStateResponse | null; resources: SystemResourcesData | null; theme: AppTheme; }
type AnyRecord = Record<string, any>;

function pick(root: any, paths: string[], fallback: any = '—') {
  for (const path of paths) {
    const value = path.split('.').reduce((v, k) => v == null ? undefined : v[k], root);
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return fallback;
}
function text(value: any) {
  if (value == null || value === '') return '—';
  if (typeof value === 'string') return value;
  try { return JSON.stringify(value); } catch { return String(value); }
}
function ago(timestamp: any) {
  if (!timestamp) return '—';
  const n = Number(timestamp); const ms = n > 1e12 ? n : n * 1000;
  const sec = Math.max(0, (Date.now() - ms) / 1000);
  if (sec < 60) return `${Math.floor(sec)}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

function Node({ label, value, icon: Icon, accent = '#5b8def', theme, wide = false }: { label: string; value: any; icon?: React.ElementType; accent?: string; theme: AppTheme; wide?: boolean }) {
  const dark = theme === 'dark';
  return (
    <div className={`min-w-0 ${wide ? 'sm:col-span-2' : ''}`}>
      <div className={`min-h-[58px] h-full flex items-center gap-2 px-2.5 py-2 border ${dark ? 'bg-white/[.018] border-white/6' : 'bg-slate-50 border-slate-200'}`}>
        {Icon && <span className="shrink-0 w-6 h-6 flex items-center justify-center border rounded" style={{ color: accent, background: `${accent}12`, borderColor: `${accent}25` }}><Icon size={12} /></span>}
        <div className="min-w-0 flex-1">
          <div className="text-[8px] uppercase tracking-[.13em] text-slate-500 truncate">{label}</div>
          <div className="mt-0.5 text-[10px] font-bold leading-tight break-words line-clamp-2" title={text(value)} style={{ color: accent }}>{text(value)}</div>
        </div>
      </div>
    </div>
  );
}

function Rail({ title, subtitle, icon: Icon, accent, theme, children }: { title: string; subtitle?: string; icon: React.ElementType; accent: string; theme: AppTheme; children: React.ReactNode }) {
  const dark = theme === 'dark';
  return (
    <section className={`trace-root overflow-hidden ${dark ? 'trace-dark' : 'trace-light'}`}>
      <div className="px-3 py-2.5 sm:px-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-6 h-6 shrink-0 flex items-center justify-center border rounded" style={{ color: accent, background: `${accent}12`, borderColor: `${accent}25` }}><Icon size={12} /></span>
          <div className="min-w-0"><div className="text-[10px] font-bold uppercase tracking-wider truncate">{title}</div>{subtitle && <div className="text-[8px] text-slate-500 truncate">{subtitle}</div>}</div>
        </div>
        {children}
      </div>
    </section>
  );
}

export function CognitiveMonitoringCards({ liveState, resources, theme }: Props) {
  const state: AnyRecord = liveState || {};
  const learning: AnyRecord = state.learning || {};
  const extraction: AnyRecord = (state.extractions || [])[0] || {};
  const attempts: any[] = extraction.attempts || [];
  const organs: AnyRecord = state.organs || {};
  const idle = pick(state, ['idle_loop', 'idleLoop', 'monitoring.idle_loop', 'cognition.idle_loop'], {});
  const consolidation = pick(state, ['memory_consolidation', 'memoryConsolidation', 'monitoring.memory_consolidation'], {});
  const native = pick(state, ['native_response_learning', 'nativeResponseLearning', 'monitoring.native_response_learning'], {});
  const procedural = pick(state, ['procedural_memory', 'proceduralMemory', 'monitoring.procedural_memory'], {});
  const typo = pick(state, ['personal_typo_learning', 'personalTypoLearning', 'monitoring.personal_typo_learning'], {});
  const decay = pick(state, ['memory_decay', 'memoryDecay', 'monitoring.memory_decay'], {});
  const meta = pick(state, ['metacognitive_calibration', 'metacognitiveCalibration', 'monitoring.metacognitive_calibration'], {});
  const awareness = pick(state, ['cognitive_self_awareness', 'cognitiveSelfAwareness', 'monitoring.cognitive_self_awareness'], {});
  const evolution = pick(state, ['evolution_self_learning', 'evolution', 'monitoring.evolution'], resources?.evolution || {});
  const dark = theme === 'dark';
  const online = Object.values(organs).filter((o: any) => o?.attached).length;
  const total = Object.keys(organs).length;

  return <div className="space-y-2.5">
    <Rail title="ORGANISM · HEALTH + LEARNING" subtitle="Unified liveness, organs and background worker telemetry" icon={ShieldCheck} accent="#22c55e" theme={theme}>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
        <Node label="Heartbeat" value={state.heartbeat?.running ? 'ALIVE' : 'OFFLINE'} icon={Radio} accent={state.heartbeat?.running ? '#22c55e' : '#ef4444'} theme={theme} />
        <Node label="Beats" value={state.heartbeat?.beats ?? 0} accent="#22c55e" theme={theme} />
        <Node label="Organs" value={`${online}/${total || 0} ONLINE`} accent="#22c55e" theme={theme} />
        <Node label="Learning worker" value={learning.alive ? 'ALIVE' : 'OFFLINE'} icon={GraduationCap} accent={learning.alive ? '#8b5cf6' : '#ef4444'} theme={theme} />
        <Node label="Queue" value={`${learning.pending ?? 0} pending`} accent="#f59e0b" theme={theme} />
        <Node label="Processed" value={learning.processed ?? 0} accent="#22c55e" theme={theme} />
        <Node label="Failed / dropped" value={`${learning.failed ?? 0} / ${learning.dropped ?? 0}`} accent="#ef4444" theme={theme} />
        <Node label="Idle" value={state.heartbeat?.idle ? 'TRUE' : 'FALSE'} icon={Moon} accent="#64748b" theme={theme} />
        <Node label="LLM ready" value={state.llm_ready ? 'TRUE' : 'FALSE'} accent="#5b8def" theme={theme} />
        <Node label="Worker state" value={learning.active ? 'ACTIVE' : 'IDLE'} accent="#8b5cf6" theme={theme} />
      </div>
      <div className="mt-2 overflow-x-auto overflow-y-hidden">
        <div className="flex gap-1.5 min-w-max pb-0.5">
          {Object.entries(organs).map(([name, organ]: any) => <div key={name} className={`w-[118px] h-[40px] shrink-0 flex items-center gap-1.5 px-2 border ${organ?.attached ? (dark ? 'bg-emerald-500/[.035] border-emerald-500/15' : 'bg-emerald-50 border-emerald-200') : (dark ? 'bg-rose-500/[.035] border-rose-500/15' : 'bg-rose-50 border-rose-200')}`} title={`${name} · ${organ?.type || 'unknown'}`}><span className={`w-1.5 h-1.5 rounded-full shrink-0 ${organ?.attached ? 'bg-emerald-400' : 'bg-rose-400'}`} /><div className="min-w-0"><div className="text-[9px] font-bold truncate">{name}</div><div className="text-[8px] text-slate-500 truncate">{organ?.type || 'unknown'} · {organ?.attached ? 'ONLINE' : 'OFFLINE'}</div></div></div>)}
        </div>
      </div>
    </Rail>

    <Rail title="SYSTEM RESOURCES" subtitle="Process and model telemetry · compact diagnostic nodes" icon={Cpu} accent="#5b8def" theme={theme}>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
        <Node label="Platform" value={pick(resources, ['platform'], 'Snapdragon ARM64')} icon={Cpu} accent="#5b8def" theme={theme} />
        <Node label="Max RSS RAM" value={`${resources?.process?.max_rss_mb ?? '—'} MB`} accent="#06b6d4" theme={theme} />
        <Node label="CPU" value={`${((resources?.process?.user_cpu_seconds ?? 0) + (resources?.process?.system_cpu_seconds ?? 0)).toFixed(2)} s`} accent="#5b8def" theme={theme} />
        <Node label="LLM backend" value={resources?.llm?.backend || '—'} wide theme={theme} />
        <Node label="Cognitive path" value={pick(resources, ['cognitive_pipeline', 'cognitive_path'], state.fallback_active ? 'NATIVE FIRST · GROQ FALLBACK' : 'NATIVE FIRST')} accent="#22c55e" theme={theme} />
      </div>
    </Rail>

    <Rail title="RECENT SCHEMA EXTRACTION" subtitle="Perception source and fallback contract" icon={Workflow} accent="#5b8def" theme={theme}>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
        <Node label="Schema" value={extraction.schema || 'perception'} accent="#5b8def" theme={theme} />
        <Node label="Used" value={extraction.stage_used || (state.fallback_active ? 'safe_fallback' : 'primary')} accent={state.fallback_active ? '#f59e0b' : '#22c55e'} theme={theme} />
        <Node label="Attempts" value={attempts.length ? attempts.map(a => `${a.stage}:${a.ok ? 'ok' : 'fail'}`).join(' → ') : '—'} wide accent="#f59e0b" theme={theme} />
        <Node label="Fallback" value={state.fallback_active ? 'ACTIVE' : 'CLEAR'} accent={state.fallback_active ? '#f59e0b' : '#22c55e'} theme={theme} />
      </div>
    </Rail>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
      <Rail title="IDLE LOOP" subtitle="Autonomous no-op activity" icon={Moon} accent="#64748b" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5"><Node label="Last cycle" value={pick(idle, ['last_cycle', 'lastCycle', 'message'], 'NO-OP — no pending goals')} wide theme={theme} /><Node label="Cycles" value={pick(idle, ['cycles', 'cycle_count', 'count'])} accent="#64748b" theme={theme} /><Node label="Last activity" value={ago(pick(idle, ['timestamp', 'last_cycle_at', 'lastCycleAt'], 0))} theme={theme} /></div></Rail>
      <Rail title="MEMORY CONSOLIDATION" subtitle="Episodic → semantic · idle-time" icon={Database} accent="#06b6d4" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5"><Node label="Run" value={pick(consolidation, ['run', 'run_number', 'runNumber'])} accent="#06b6d4" theme={theme} /><Node label="Examined" value={pick(consolidation, ['examined', 'examined_count'])} theme={theme} /><Node label="Candidates" value={pick(consolidation, ['candidates', 'candidate_count'])} theme={theme} /><Node label="Promoted" value={pick(consolidation, ['promoted_to_semantic', 'promoted'])} accent="#22c55e" theme={theme} /></div></Rail>
      <Rail title="NATIVE RESPONSE LEARNING" subtitle="Zero-LLM-cost templates" icon={Sparkles} accent="#8b5cf6" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5"><Node label="Templates" value={pick(native, ['templates_learned', 'templatesLearned'], 0)} accent="#8b5cf6" theme={theme} /><Node label="LLM hits saved" value={pick(native, ['total_hits_saved_from_LLM', 'hits_saved'], 0)} accent="#22c55e" theme={theme} /><Node label="Last scan" value={pick(native, ['last_scan', 'lastScan', 'message'], 'candidates=0')} wide theme={theme} /></div></Rail>
      <Rail title="PROCEDURAL MEMORY" subtitle="Learned habits" icon={Network} accent="#f59e0b" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5"><Node label="Procedures" value={pick(procedural, ['total_procedures', 'procedures'], 0)} accent="#f59e0b" theme={theme} /><Node label="Hits" value={pick(procedural, ['total_hits', 'hits'], 0)} theme={theme} /><Node label="By kind" value={pick(procedural, ['by_kind', 'byKind'], '(none learned yet)')} wide theme={theme} /></div></Rail>
      <Rail title="PERSONAL TYPO LEARNING" subtitle="Idiolect correction model" icon={Languages} accent="#5b8def" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5"><Node label="Corrections" value={pick(typo, ['learned_corrections', 'corrections'], 0)} accent="#5b8def" theme={theme} /><Node label="Pending pairs" value={pick(typo, ['pending_pairs_being_tracked', 'pending_pairs'], 0)} theme={theme} /><Node label="Threshold" value={pick(typo, ['promotion_threshold', 'threshold'], 3)} theme={theme} /></div></Rail>
      <Rail title="MEMORY DECAY" subtitle="Unused personal facts fade" icon={TrendingDown} accent="#64748b" theme={theme}><div className="grid grid-cols-2 gap-1.5"><Node label="Last cycle" value={pick(decay, ['last_cycle', 'message'], 'No decay cycle recorded')} wide theme={theme} /><Node label="Weakened facts" value={pick(decay, ['unused_facts_weakened', 'weakened'], 0)} accent="#64748b" theme={theme} /></div></Rail>
      <Rail title="METACOGNITIVE CALIBRATION" subtitle="Confidence versus correctness" icon={Target} accent="#e24d6b" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5"><Node label="Score" value={pick(meta, ['calibration_score', 'score'], 0)} accent="#e24d6b" theme={theme} /><Node label="Contradicted" value={pick(meta, ['contradicted_facts', 'contradicted'], 0)} theme={theme} /><Node label="Sample" value={pick(meta, ['sample', 'evaluations'], '—')} theme={theme} /></div></Rail>
      <Rail title="COGNITIVE SELF-AWARENESS" subtitle="Recall, resolution and training signals" icon={Brain} accent="#14b8a6" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5"><Node label="Interactions" value={pick(awareness, ['total_interactions', 'interactions'], 0)} theme={theme} /><Node label="Native rate" value={pick(awareness, ['native_resolution_rate'], 0)} accent="#14b8a6" theme={theme} /><Node label="LLM fallback" value={pick(awareness, ['llm_fallback_rate'], 0)} accent="#a855f7" theme={theme} /><Node label="Direct recall" value={pick(awareness, ['direct_recall'], 0)} theme={theme} /><Node label="Identity" value={pick(awareness, ['identity'], 0)} theme={theme} /><Node label="Graph multi-hop" value={pick(awareness, ['graph_multi_hop'], 0)} theme={theme} /><Node label="SLM assisted" value={pick(awareness, ['slm_assisted'], 0)} theme={theme} /><Node label="Contradiction" value={pick(awareness, ['contradiction_rate'], 0)} accent="#e24d6b" theme={theme} /></div></Rail>
      <Rail title="EVOLUTION & SELF-LEARNING" subtitle="Organism feedback and proposals" icon={Network} accent="#a855f7" theme={theme}><div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5"><Node label="Proposals" value={pick(evolution, ['proposals', 'total'], 0)} accent="#a855f7" theme={theme} /><Node label="Approved" value={pick(evolution, ['approved'], 0)} theme={theme} /><Node label="Applied" value={pick(evolution, ['applied'], 0)} accent="#22c55e" theme={theme} /><Node label="Rejected" value={pick(evolution, ['rejected'], 0)} accent="#ef4444" theme={theme} /></div></Rail>
    </div>
  </div>;
}
