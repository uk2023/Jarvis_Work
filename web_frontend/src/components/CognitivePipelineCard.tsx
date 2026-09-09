import React from 'react';
import { Activity, CheckCircle2, Clock3, GitBranch, Database, Brain, Gauge, Zap, MessageSquare, GraduationCap, AlertTriangle } from 'lucide-react';
import { AppTheme, LiveStateResponse, StageTransition } from '../types';

interface Props { liveState: LiveStateResponse | null; theme: AppTheme; }

const stageMeta: Record<string, { color: string; soft: string; icon: React.ElementType }> = {
  IDLE: { color: '#64748b', soft: 'rgba(100,116,139,.10)', icon: CheckCircle2 },
  PERCEIVING: { color: '#5b8def', soft: 'rgba(91,141,239,.11)', icon: Activity },
  INDEXING: { color: '#22c55e', soft: 'rgba(34,197,94,.10)', icon: Database },
  EXECUTING: { color: '#a855f7', soft: 'rgba(168,85,247,.10)', icon: Zap },
};

function age(timestamp?: number) {
  if (!timestamp) return '—';
  const seconds = Math.max(0, (Date.now() - timestamp * 1000) / 1000);
  if (seconds < 60) return `${seconds.toFixed(1)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m${Math.floor(seconds % 60)}s ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function duration(value?: number) { return `${Number(value ?? 0).toFixed(3)}s`; }

export function CognitivePipelineCard({ liveState, theme }: Props) {
  const isDark = theme === 'dark';
  const trace = [...(liveState?.pipeline_trace ?? [])].sort((a, b) => a.timestamp - b.timestamp).slice(-12);
  const current = liveState?.stage ?? 'IDLE';

  return (
    <section id="card-cognitive-pipeline" className="trace-root overflow-hidden">
      <div className="trace-hero !rounded-none !border-0">
        <div className="trace-hero-top">
          <div className="trace-kicker"><GitBranch size={15} /> COGNITIVE PIPELINE</div>
          <div className="trace-live"><span /> {current}</div>
        </div>
        <div className="trace-hero-title">
          <div>
            <h2>WORKFLOW TRACE</h2>
            <p>Most recent last · live state transitions and stage timing</p>
          </div>
        </div>
        <div className="trace-overview" style={{ gridTemplateColumns: 'repeat(3,minmax(0,1fr))' }}>
          <div className="trace-metric"><span className="trace-metric-label">CURRENT STAGE</span><strong style={{ color: stageMeta[current]?.color ?? '#5b8def' }}>{current}</strong></div>
          <div className="trace-metric"><span className="trace-metric-label">TRANSITIONS</span><strong>{trace.length}</strong></div>
          <div className="trace-metric"><span className="trace-metric-label">FALLBACK</span><strong style={{ color: liveState?.fallback_active ? '#f59e0b' : '#22c55e' }}>{liveState?.fallback_active ? 'ACTIVE' : 'CLEAR'}</strong></div>
        </div>
      </div>
      <div className="trace-flow">
        <div className="trace-flow-label"><GitBranch size={13} /> WORKFLOW PIPELINE TRACE <span>· most recent last</span></div>
        {trace.length === 0 ? (
          <div className={`p-5 rounded-xl border text-slate-500 ${isDark ? 'bg-white/[.02] border-white/10' : 'bg-slate-50 border-slate-200'}`}>No pipeline transitions recorded yet.</div>
        ) : trace.map((item: StageTransition, index) => {
          const meta = stageMeta[item.stage] ?? stageMeta.IDLE;
          const Icon = meta.icon;
          const isCurrent = index === trace.length - 1;
          return (
            <div className="trace-node" key={`${item.timestamp}-${index}`} style={{ '--trace-accent': meta.color, '--trace-soft': meta.soft } as React.CSSProperties}>
              <div className="trace-node-rail" aria-hidden="true"><span className="trace-node-dot" /></div>
              <div className="trace-stage">
                <div className="trace-stage-head" style={{ cursor: 'default' }}>
                  <span className="trace-stage-index">{String(index + 1).padStart(2, '0')}</span>
                  <span className="trace-stage-icon"><Icon size={16} /></span>
                  <span className="trace-stage-title">{item.previous_stage} → {item.stage}</span>
                  <span className="trace-stage-time"><Clock3 size={12} /> {duration(item.duration_in_previous)}</span>
                  <span className="trace-stage-summary">{item.detail?.message ?? item.detail?.reason ?? `transition ${index + 1}`}</span>
                  <span className="trace-stage-status" style={isCurrent ? undefined : { color: meta.color }}><span /> {isCurrent ? 'CURRENT' : 'COMPLETED'}</span>
                  <span className="trace-chevron"><CheckCircle2 size={15} /></span>
                </div>
                <div className="trace-stage-body" style={{ overflow: 'visible' }}>
                  <div className="trace-stage-content">
                    <div className="trace-grid">
                      <div className="trace-field"><span className="trace-field-label">FROM</span><span className="trace-field-value trace-mono">{item.previous_stage}</span></div>
                      <div className="trace-field"><span className="trace-field-label">TO</span><span className="trace-field-value trace-mono" style={{ color: meta.color }}>{item.stage}</span></div>
                      <div className="trace-field"><span className="trace-field-label">TIME IN PREVIOUS</span><span className="trace-field-value trace-mono">{duration(item.duration_in_previous)}</span></div>
                      <div className="trace-field"><span className="trace-field-label">LAST ACTIVITY</span><span className="trace-field-value trace-mono">{age(item.timestamp)}</span></div>
                    </div>
                    {item.detail && Object.keys(item.detail).length > 0 && (
                      <div className="trace-callout" style={{ marginTop: 8, '--trace-accent': meta.color } as React.CSSProperties}>
                        <Brain size={14} />
                        <div><strong>STAGE DETAIL</strong><p>{JSON.stringify(item.detail)}</p></div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
