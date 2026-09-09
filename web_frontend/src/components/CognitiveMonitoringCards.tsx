import React from 'react';
import { Activity, Brain, Database, GraduationCap, Languages, Moon, Network, RefreshCw, Scissors, ShieldCheck, Sparkles, Target, TrendingDown, Workflow } from 'lucide-react';
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

function ago(timestamp: any) {
  if (!timestamp) return '—';
  const n = Number(timestamp);
  const ms = n > 1e12 ? n : n * 1000;
  const sec = Math.max(0, (Date.now() - ms) / 1000);
  if (sec < 60) return `${Math.floor(sec)}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

function Card({ title, subtitle, icon: Icon, accent, children, theme }: any) {
  const dark = theme === 'dark';
  return <section className={`rounded-xl border overflow-hidden ${dark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900'}`}>
    <div className="p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-lg border flex items-center justify-center shrink-0" style={{ background: `${accent}18`, borderColor: `${accent}35` }}><Icon className="w-4 h-4" style={{ color: accent }} /></div>
          <div className="min-w-0"><h2 className="font-bold text-sm uppercase tracking-wider truncate">{title}</h2>{subtitle && <div className="text-[10px] text-slate-500">{subtitle}</div>}</div>
        </div>
      </div>
      {children}
    </div>
  </section>;
}

function Field({ label, value, accent }: { label: string; value: any; accent?: string }) {
  return <div className="p-2.5 rounded-lg border bg-black/[.02] dark:bg-white/[.02] border-slate-200 dark:border-white/5"><div className="text-[9px] text-slate-500 uppercase mb-1">{label}</div><div className="font-bold text-[11px] break-words" style={accent ? { color: accent } : undefined}>{String(value)}</div></div>;
}

export function CognitiveMonitoringCards({ liveState, resources, theme }: Props) {
  const state: AnyRecord = liveState as AnyRecord || {};
  const detail: AnyRecord = state.stage_detail || {};
  const extraction = (state.extractions || [])[0] || {};
  const attempts = extraction.attempts || [];
  const learning = state.learning || {};
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
  const panel = dark ? 'bg-white/[.02] border-white/5' : 'bg-slate-50 border-slate-200';

  return <div className="space-y-4">
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="Recent Schema Extractions" subtitle="Perception contract and fallback chain" icon={Workflow} accent="#5b8def" theme={theme}>
        <div className={`rounded-lg border p-3 ${panel}`}>
          <div className="flex items-center justify-between gap-3 mb-2"><span className="text-[10px] text-slate-500 uppercase">[{extraction.schema || 'perception'}]</span><span className={`text-[9px] font-bold px-2 py-1 rounded-full border ${extraction.fallback_active || state.fallback_active ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'}`}>{extraction.fallback_active || state.fallback_active ? 'SAFE FALLBACK' : 'PRIMARY'}</span></div>
          <div className="font-mono text-[10px] break-words mb-3">used=<span className="text-[#5b8def]">{extraction.stage_used || (state.fallback_active ? 'safe_fallback' : 'primary')}</span> {attempts.map((a: any, i: number) => <React.Fragment key={i}> {a.stage}:{a.ok ? 'ok' : 'fail'}{i < attempts.length - 1 ? ' →' : ''}</React.Fragment>)}</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">{attempts.map((a: any) => <Field key={a.stage} label={a.stage} value={a.ok ? 'PASS' : 'FAIL'} accent={a.ok ? '#22c55e' : '#f59e0b'} />)}</div>
        </div>
      </Card>

      <Card title="Background Learning Queue" subtitle="Autonomous worker state" icon={GraduationCap} accent="#8b5cf6" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          <Field label="Worker" value={learning.alive ? 'ALIVE' : 'OFFLINE'} accent={learning.alive ? '#22c55e' : '#ef4444'} />
          <Field label="State" value={learning.active ? 'ACTIVE' : 'IDLE'} />
          <Field label="Pending" value={learning.pending ?? 0} accent="#f59e0b" />
          <Field label="Processed" value={learning.processed ?? 0} accent="#22c55e" />
          <Field label="Failed / Dropped" value={`${learning.failed ?? 0} / ${learning.dropped ?? 0}`} accent="#ef4444" />
        </div>
      </Card>
    </div>

    <Card title="Idle Loop Activity" subtitle="Autonomous no-op cycles while the organism is idle" icon={Moon} accent="#64748b" theme={theme}>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2"><Field label="Last cycle" value={pick(idle, ['last_cycle', 'lastCycle', 'message'], 'NO-OP — no pending goals')} /><Field label="Recorded cycles" value={pick(idle, ['cycles', 'cycle_count', 'count'], '—')} /><Field label="Last activity" value={ago(pick(idle, ['timestamp', 'last_cycle_at', 'lastCycleAt'], 0))} /></div>
    </Card>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="Memory Consolidation" subtitle="Episodic → semantic, idle-time" icon={Database} accent="#06b6d4" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2"><Field label="Run" value={pick(consolidation, ['run', 'run_number', 'runNumber'])} /><Field label="Examined" value={pick(consolidation, ['examined', 'examined_count'])} /><Field label="Candidates" value={pick(consolidation, ['candidates', 'candidate_count'])} /><Field label="Promoted" value={pick(consolidation, ['promoted_to_semantic', 'promoted'])} /></div>
        <div className="mt-2 text-[10px] text-slate-500">{pick(consolidation, ['message', 'summary'], 'No new semantic facts extracted in the latest idle consolidation.')}</div>
      </Card>

      <Card title="Native Response Learning" subtitle="Zero-LLM-cost templates" icon={Sparkles} accent="#8b5cf6" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2"><Field label="Templates learned" value={pick(native, ['templates_learned', 'templatesLearned'], 0)} /><Field label="LLM hits saved" value={pick(native, ['total_hits_saved_from_LLM', 'hits_saved'], 0)} /><Field label="Last scan" value={pick(native, ['last_scan', 'lastScan', 'message'], 'candidates=0')} /></div>
      </Card>

      <Card title="Procedural Memory" subtitle="Third memory type · learned habits" icon={RefreshCw} accent="#f59e0b" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2"><Field label="Procedures" value={pick(procedural, ['total_procedures', 'procedures'], 0)} /><Field label="Hits" value={pick(procedural, ['total_hits', 'hits'], 0)} /><Field label="By kind" value={pick(procedural, ['by_kind', 'byKind'], '(none learned yet)')} /></div>
      </Card>

      <Card title="Personal Typo Learning" subtitle="Idiolect correction model" icon={Languages} accent="#5b8def" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2"><Field label="Learned corrections" value={pick(typo, ['learned_corrections', 'corrections'], 0)} /><Field label="Pending pairs" value={pick(typo, ['pending_pairs_being_tracked', 'pending_pairs'], 0)} /><Field label="Promotion threshold" value={pick(typo, ['promotion_threshold', 'threshold'], 3)} /></div>
      </Card>

      <Card title="Memory Decay" subtitle="Unused personal facts fade over time" icon={TrendingDown} accent="#64748b" theme={theme}>
        <div className="grid grid-cols-2 gap-2"><Field label="Last cycle" value={pick(decay, ['last_cycle', 'message'], 'No decay cycle recorded')} /><Field label="Weakened facts" value={pick(decay, ['unused_facts_weakened', 'weakened'], 0)} /></div>
      </Card>

      <Card title="Metacognitive Calibration" subtitle="Confidence versus correctness" icon={Target} accent="#e24d6b" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2"><Field label="Calibration score" value={pick(meta, ['calibration_score', 'score'], 0)} accent="#e24d6b" /><Field label="Contradicted" value={pick(meta, ['contradicted_facts', 'contradicted'], 0)} /><Field label="Sample" value={pick(meta, ['sample', 'evaluations'], '—')} /></div>
      </Card>

      <Card title="Cognitive Self-Awareness" subtitle="Resolution, recall and training signals" icon={Brain} accent="#14b8a6" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Field label="Interactions" value={pick(awareness, ['total_interactions', 'interactions'], 0)} /><Field label="Native resolution" value={pick(awareness, ['native_resolution_rate'], 0)} /><Field label="LLM fallback" value={pick(awareness, ['llm_fallback_rate'], 0)} /><Field label="Direct recall" value={pick(awareness, ['direct_recall'], 0)} />
          <Field label="Identity" value={pick(awareness, ['identity'], 0)} /><Field label="Graph multi-hop" value={pick(awareness, ['graph_multi_hop'], 0)} /><Field label="SLM assisted" value={pick(awareness, ['slm_assisted'], 0)} /><Field label="Contradiction rate" value={pick(awareness, ['contradiction_rate'], 0)} />
        </div>
        <div className="mt-2 text-[10px] text-slate-500">training data collected: {pick(awareness, ['training_data_collected', 'training_examples'], '—')}</div>
      </Card>

      <Card title="Evolution & Self-Learning" subtitle="Proposals generated from organism feedback" icon={Network} accent="#a855f7" theme={theme}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2"><Field label="Proposals" value={pick(evolution, ['proposals', 'total'], 0)} /><Field label="Approved" value={pick(evolution, ['approved'], 0)} /><Field label="Applied" value={pick(evolution, ['applied'], 0)} /><Field label="Rejected" value={pick(evolution, ['rejected'], 0)} /></div>
      </Card>
    </div>

    <Card title="Organism Health" subtitle="Heartbeat, idle state, LLM readiness and organ attachment" icon={ShieldCheck} accent="#22c55e" theme={theme}>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2"><Field label="Heartbeat" value={state.heartbeat?.running ? 'ALIVE' : 'OFFLINE'} accent={state.heartbeat?.running ? '#22c55e' : '#ef4444'} /><Field label="Beats" value={state.heartbeat?.beats ?? 0} /><Field label="Idle" value={state.heartbeat?.idle ? 'TRUE' : 'FALSE'} /><Field label="LLM ready" value={state.llm_ready ? 'TRUE' : 'FALSE'} /><Field label="Organs" value={`${Object.values(state.organs || {}).filter((o: any) => o.attached).length}/${Object.keys(state.organs || {}).length || 0} online`} /></div>
    </Card>
  </div>;
}
