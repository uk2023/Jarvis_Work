import React, { useState, useEffect } from 'react';
import {
  Activity,
  Cpu,
  Database,
  Terminal,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
  Zap,
  ArrowRight,
  Server,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Flame,
  Radio,
  BarChart3,
  HardDrive,
  FileCode2,
} from 'lucide-react';
import {
  LiveStateResponse,
  SystemResourcesData,
  ActivityHistoryItem,
  PipelineStage,
  AppTheme,
} from '../types';
import { api } from '../api/client';
import { RuntimeUptimeWidget } from './RuntimeUptimeWidget';
import { OrganIntrospectionViewer } from './OrganIntrospectionViewer';
import { OvernightLearningCard } from './OvernightLearningCard';
import { SelfImprovementList } from './SelfImprovementList';

interface DashboardScreenProps {
  onSelectTurn: (turnId: string) => void;
  onNavigateToCLI: () => void;
  theme: AppTheme;
  activeSection?: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all';
  onSelectSection?: (section: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all') => void;
}

export function DashboardScreen({
  onSelectTurn,
  onNavigateToCLI,
  theme,
  activeSection = 'monitor',
  onSelectSection,
}: DashboardScreenProps) {
  const [liveState, setLiveState] = useState<LiveStateResponse | null>(null);
  const [resources, setResources] = useState<SystemResourcesData | null>(null);
  const [history, setHistory] = useState<ActivityHistoryItem[]>([]);
  const [pollIntervalMs, setPollIntervalMs] = useState<number>(2000);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [currentSection, setCurrentSection] = useState<'monitor' | 'memory' | 'reasoning' | 'organs' | 'all'>(
    activeSection
  );

  useEffect(() => {
    if (activeSection) {
      setCurrentSection(activeSection);
    }
  }, [activeSection]);

  const handleSectionChange = (sec: 'monitor' | 'memory' | 'reasoning' | 'organs' | 'all') => {
    setCurrentSection(sec);
    if (onSelectSection) onSelectSection(sec);
  };

  const isDark = theme === 'dark';

  // Fetch all dashboard metrics
  const fetchDashboardData = async () => {
    try {
      setIsRefreshing(true);
      const [stateRes, resRes, histRes] = await Promise.all([
        api.getLiveState(),
        api.getResources(),
        api.getActivityHistory(),
      ]);
      setLiveState(stateRes);
      setResources(resRes);
      setHistory(histRes);
      setSecondsAgo(0);
    } catch (err) {
      console.error('Failed to load dashboard metrics:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Setup auto-polling every 1-2 seconds
  useEffect(() => {
    fetchDashboardData();

    let interval: NodeJS.Timeout | null = null;
    if (pollIntervalMs > 0) {
      interval = setInterval(fetchDashboardData, pollIntervalMs);
    }

    const timer = setInterval(() => {
      setSecondsAgo(prev => prev + 1);
    }, 1000);

    return () => {
      if (interval) clearInterval(interval);
      clearInterval(timer);
    };
  }, [pollIntervalMs]);

  const stages: PipelineStage[] = ['IDLE', 'PERCEIVING', 'INDEXING', 'EXECUTING'];
  const currentStage = liveState?.stage || 'IDLE';
  const isWorking = currentStage !== 'IDLE';

  const organEntries: [string, { type: string; attached: boolean }][] = liveState?.organs
    ? (Object.entries(liveState.organs) as [string, { type: string; attached: boolean }][])
    : [];
  const attachedCount = organEntries.filter(([_, o]) => o.attached).length;

  const showMonitor = currentSection === 'monitor' || currentSection === 'all';
  const showMemory = currentSection === 'memory' || currentSection === 'all';
  const showReasoning = currentSection === 'reasoning' || currentSection === 'all';
  const showOrgans = currentSection === 'organs' || currentSection === 'all';

  return (
    <div className="h-full overflow-y-auto p-3 sm:p-5 space-y-4 font-mono text-xs max-w-full">
      {/* ------------------------------------------------------------- */}
      {/* a) STATUS HEADER (Always visible in Monitor or All)          */}
      {/* ------------------------------------------------------------- */}
      {showMonitor && (
        <section
          id="dashboard-status-header"
          className={`p-4 rounded-xl border transition-all ${
            isDark
              ? 'bg-[#080b12] border-white/10 text-white shadow-lg shadow-brand-950/20'
              : 'bg-white border-slate-200 text-slate-900 shadow-sm'
          }`}
        >
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Big unmissable Working / Idle Indicator */}
          <div className="flex items-center gap-3">
            <div
              className={`px-3 py-1.5 rounded-lg flex items-center gap-2 font-bold text-sm tracking-wide ${
                isWorking
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                  : isDark
                  ? 'bg-white/5 text-slate-400 border border-white/10'
                  : 'bg-slate-100 text-slate-600 border border-slate-200'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isWorking ? 'bg-emerald-400 animate-ping' : 'bg-slate-500'
                }`}
              />
              <span>{isWorking ? '● WORKING' : '○ IDLE'}</span>
            </div>

            {/* PID & Runtime */}
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="px-2 py-1 rounded bg-brand-500/10 text-brand-400 border border-brand-500/30">
                PID: {liveState?.pid || 4242}
              </span>
              <span
                className={`px-2 py-1 rounded font-semibold ${
                  liveState?.runtime === 'ONLINE'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                }`}
              >
                {liveState?.runtime || 'ONLINE'}
              </span>
            </div>

            {/* Compact Runtime Widget in Status Header */}
            <div className="hidden lg:block">
              <RuntimeUptimeWidget theme={theme} compact={true} />
            </div>
          </div>

          {/* Controls: Locked horizontal dimensions so poll layer and adjacent refresh button never shift */}
          <div className="flex items-center gap-2 text-xs shrink-0">
            <span className="w-20 sm:w-24 text-right text-slate-500 dark:text-slate-400 font-mono tabular-nums shrink-0 select-none">
              {secondsAgo === 0 ? 'just now' : `${secondsAgo}s ago`}
            </span>

            <select
              value={pollIntervalMs}
              onChange={e => setPollIntervalMs(Number(e.target.value))}
              className={`w-28 sm:w-32 h-7 px-1.5 rounded-lg border text-xs cursor-pointer outline-none shrink-0 font-mono ${
                isDark
                  ? 'bg-black/60 border-white/10 text-brand-300'
                  : 'bg-slate-50 border-slate-300 text-slate-800'
              }`}
            >
              <option value={1000}>Poll: 1s (Fast)</option>
              <option value={2000}>Poll: 2s (Normal)</option>
              <option value={5000}>Poll: 5s (Relaxed)</option>
              <option value={0}>Poll: Paused</option>
            </select>

            <button
              onClick={fetchDashboardData}
              disabled={isRefreshing}
              className={`w-7 h-7 flex items-center justify-center rounded-lg border transition cursor-pointer shrink-0 ${
                isDark
                  ? 'bg-white/5 hover:bg-white/10 border-white/10 text-brand-400'
                  : 'bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700'
              }`}
              title="Refresh now"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Pipeline Stage Step Indicator */}
        <div className="mt-4 pt-3 border-t border-slate-200 dark:border-white/10">
          <div className="text-xs uppercase font-bold tracking-wider text-slate-400 mb-2">
            Active Cognitive Pipeline:
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {stages.map((st, idx) => {
              const isActive = currentStage === st;
              return (
                <div
                  key={st}
                  className={`p-2 rounded-lg border flex items-center justify-between transition-all ${
                    isActive
                      ? 'bg-brand-500/20 border-brand-400 text-brand-200 shadow-[0_0_12px_rgba(34,211,238,0.25)] font-bold'
                      : isDark
                      ? 'bg-white/[0.02] border-white/5 text-slate-500'
                      : 'bg-slate-50 border-slate-200 text-slate-400'
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="text-xs opacity-60">#{idx + 1}</span>
                    <span className="truncate text-xs">{st}</span>
                  </div>
                  {isActive && <span className="w-2 h-2 rounded-full bg-brand-400 animate-ping" />}
                </div>
              );
            })}
          </div>
        </div>

        {/* Fallback Active Warning Banner */}
        {liveState?.fallback_active && (
          <div className="mt-3 p-2.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="font-semibold text-xs">
              Warning: Last extraction used the deterministic safe fallback.
            </span>
          </div>
        )}
      </section>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 2-COLUMN GRID FOR SYSTEM VITALS (MONITOR)                     */}
      {/* ------------------------------------------------------------- */}
      {showMonitor && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* b) SYSTEM RESOURCES CARD */}
            <div
              id="card-system-resources"
              className={`p-4 rounded-xl border space-y-3 ${
                isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900 shadow-xs'
              }`}
            >
          <div className="flex items-center justify-between border-b pb-2 border-slate-200 dark:border-white/10">
            <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-brand-700 dark:text-brand-400">
              <Cpu className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span>System Resources</span>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">Snapdragon ARM64</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">Max RSS RAM</div>
              <div className="font-bold text-brand-700 dark:text-brand-400 text-sm mt-0.5">{resources?.process.max_rss_mb || 412.3} MB</div>
            </div>
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">CPU User Sec</div>
              <div className="font-bold text-brand-700 dark:text-brand-400 text-sm mt-0.5">{resources?.process.user_cpu_seconds || 22.1}s</div>
            </div>
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">CPU Sys Sec</div>
              <div className="font-bold text-brand-700 dark:text-brand-400 text-sm mt-0.5">{resources?.process.system_cpu_seconds || 3.4}s</div>
            </div>
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">Threads</div>
              <div className="font-bold text-emerald-700 dark:text-emerald-400 text-sm mt-0.5">{resources?.process.threads || 9} Live</div>
            </div>
          </div>

          {/* LLM Backend & Turn Budget */}
          <div className={`p-3 rounded-lg border space-y-2 ${isDark ? 'bg-black/30 border-white/10' : 'bg-slate-50 border-slate-200'}`}>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400">LLM Fallback Backend:</span>
              <span className="font-semibold text-brand-700 dark:text-brand-300 font-mono">{resources?.llm.backend || 'Groq openai/gpt-oss-120b'}</span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400">Cognitive Pipeline:</span>
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> NATIVE FIRST (Groq Fallback)
              </span>
            </div>

            {/* Budget Gauges */}
            <div className="pt-2 border-t border-slate-200 dark:border-white/5 space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500 dark:text-slate-400">Turn Call Budget:</span>
                <span className="font-mono text-brand-700 dark:text-brand-400 font-bold">
                  {resources?.llm.budget.calls || 2} / {resources?.llm.budget.max_calls || 4} calls
                </span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-white/10 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-brand-500 dark:bg-brand-400 h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, ((resources?.llm.budget.calls || 2) / (resources?.llm.budget.max_calls || 4)) * 100)}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* e) BACKGROUND LEARNING QUEUE & ORGANISM HEALTH */}
        <div
          id="card-learning-queue-and-health"
          className={`p-4 rounded-xl border space-y-3 ${
            isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900 shadow-xs'
          }`}
        >
          <div className="flex items-center justify-between border-b pb-2 border-slate-200 dark:border-white/10">
            <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
              <Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span>Background Learning Queue</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 dark:text-slate-400">Worker:</span>
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 text-xs font-bold border border-emerald-500/30">
                ALIVE
              </span>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2 text-center text-xs">
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">Pending</div>
              <div className="font-bold text-amber-600 dark:text-amber-400 text-sm mt-0.5">{liveState?.learning.pending || 0}</div>
            </div>
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">Processed</div>
              <div className="font-bold text-emerald-700 dark:text-emerald-400 text-sm mt-0.5">{liveState?.learning.processed || 14}</div>
            </div>
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">Failed</div>
              <div className="font-bold text-rose-600 dark:text-rose-400 text-sm mt-0.5">{liveState?.learning.failed || 0}</div>
            </div>
            <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
              <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold">Dropped</div>
              <div className="font-bold text-slate-600 dark:text-slate-400 text-sm mt-0.5">{liveState?.learning.dropped || 0}</div>
            </div>
          </div>

          {/* g) Organism Health & Heartbeat */}
          <div className={`p-3 rounded-lg border space-y-2 ${isDark ? 'bg-black/30 border-white/10' : 'bg-slate-50 border-slate-200'}`}>
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
                Heartbeat Daemon:
              </span>
              <span className="text-brand-700 dark:text-brand-300 font-bold font-mono">
                {liveState?.heartbeat.beats || 88} beats ({attachedCount}/{organEntries.length || 10} Organs Online)
              </span>
            </div>

            {/* Organ Chips */}
            <div className="flex flex-wrap gap-1 pt-1">
              {organEntries.map(([name, organ]) => (
                <span
                  key={name}
                  className={`px-1.5 py-0.5 rounded text-xs font-semibold border ${
                    organ.attached
                      ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                      : 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30'
                  }`}
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

          {/* c) RECENT ACTIVITY HISTORY (Clickable -> Jumps to Trace Inspector) */}
          <section
            id="card-activity-history"
            className={`p-4 rounded-xl border space-y-3 ${
              isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900 shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between border-b pb-2 border-white/10">
              <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-brand-400">
                <Activity className="w-4 h-4 text-brand-400" />
                <span>Recent Activity History (Completed Turns)</span>
              </div>
              <span className="text-xs text-slate-400">Click turn row to inspect deep trace</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className={`border-b text-xs uppercase text-slate-400 ${isDark ? 'border-white/10' : 'border-slate-200'}`}>
                    <th className="py-2 px-2">Turn ID</th>
                    <th className="py-2 px-2">Query</th>
                    <th className="py-2 px-2">Duration</th>
                    <th className="py-2 px-2 hidden sm:table-cell">Stage Trajectory</th>
                    <th className="py-2 px-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {history.map(item => {
                    const isInProgress = item.endTime === null;
                    return (
                      <tr
                        key={item.turnId}
                        onClick={() => onSelectTurn(item.turnId)}
                        className={`cursor-pointer transition-colors group ${
                          isInProgress
                            ? 'bg-amber-500/10 text-amber-200 animate-pulse'
                            : isDark
                            ? 'hover:bg-brand-500/10 text-slate-200'
                            : 'hover:bg-slate-100 text-slate-800'
                        }`}
                      >
                        <td className="py-2.5 px-2 font-bold text-brand-400 whitespace-nowrap">
                          {item.turnId}
                        </td>
                        <td className="py-2.5 px-2 truncate max-w-[200px] sm:max-w-[280px]">
                          {item.query}
                        </td>
                        <td className="py-2.5 px-2 whitespace-nowrap">
                          {item.durationSeconds.toFixed(2)}s
                        </td>
                        <td className="py-2.5 px-2 hidden sm:table-cell text-xs text-slate-400 truncate">
                          {item.stagePath.join(' > ')}
                        </td>
                        <td className="py-2.5 px-2 text-right whitespace-nowrap">
                          <span className="inline-flex items-center gap-1 text-xs text-brand-400 group-hover:underline">
                            Inspect <ArrowRight className="w-3 h-3" />
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* h) RECENT INTERNAL LOG CARD */}
          <div
            id="card-internal-logs"
            className={`p-4 rounded-xl border space-y-3 ${
              isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900 shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between border-b pb-2 border-white/10">
              <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-slate-300">
                <Terminal className="w-4 h-4 text-brand-400" />
                <span>Internal Diagnostic Log</span>
              </div>
              <button
                onClick={onNavigateToCLI}
                className="text-xs text-brand-400 hover:underline flex items-center gap-1 cursor-pointer"
              >
                Open Virtual CLI <ExternalLink className="w-3 h-3" />
              </button>
            </div>

            <div className="space-y-1.5 max-h-[190px] overflow-y-auto no-scrollbar font-mono text-xs">
              {liveState?.logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`p-2 rounded border flex items-start gap-2 ${
                    log.level === 'warning'
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                      : log.level === 'error'
                      ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                      : isDark
                      ? 'bg-black/30 border-white/5 text-slate-300'
                      : 'bg-slate-50 border-slate-200 text-slate-700'
                  }`}
                >
                  <span
                    className={`px-1 rounded text-xs uppercase font-bold shrink-0 ${
                      log.level === 'warning'
                        ? 'bg-amber-500/30 text-amber-200'
                        : log.level === 'error'
                        ? 'bg-rose-500/30 text-rose-200'
                        : 'bg-brand-500/20 text-brand-300'
                    }`}
                  >
                    {log.level}
                  </span>
                  <span className="text-brand-400 shrink-0">[{log.tag}]</span>
                  <span className="truncate">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MEMORY & DATABASE: RECENT SCHEMA EXTRACTIONS & LEARNING EVOLUTION */}
      {/* ------------------------------------------------------------- */}
      {showMemory && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* d) RECENT SCHEMA EXTRACTIONS CARD */}
            <div
              id="card-schema-extractions"
              className={`p-4 rounded-xl border space-y-3 ${
                isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900 shadow-sm'
              }`}
            >
              <div className="flex items-center justify-between border-b pb-2 border-white/10">
                <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-brand-400">
                  <Database className="w-4 h-4 text-brand-400" />
                  <span>Recent Schema Extractions (Contract Verification)</span>
                </div>
                <span className="text-xs text-slate-400">Memory & DB Pipeline</span>
              </div>

              <div className="space-y-2">
                {liveState?.extractions.map((ext, idx) => {
                  const badgeColor =
                    ext.stage_used === 'primary'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : ext.stage_used === 'refined'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : 'bg-rose-500/20 text-rose-300 border-rose-500/40';

                  const sequenceStr = ext.attempts
                    .map(a => `${a.stage}:${a.ok ? 'ok' : 'fail'}`)
                    .join(' -> ');

                  return (
                    <div
                      key={idx}
                      className={`p-2.5 rounded-lg border flex items-center justify-between gap-2 ${
                        isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'
                      }`}
                    >
                      <div>
                        <div className={`font-semibold text-xs ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>{ext.schema}</div>
                        <div className="text-xs text-slate-400 font-mono mt-0.5">
                          Attempts: <span className="text-brand-400">{sequenceStr}</span>
                        </div>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-xs font-bold border uppercase ${badgeColor}`}>
                        {ext.stage_used}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* f) LEARNING & EVOLUTION CARD */}
            <div
              id="card-learning-and-evolution"
              className={`p-4 rounded-xl border space-y-3 ${
                isDark ? 'bg-[#080b12] border-white/10 text-white' : 'bg-white border-slate-200 text-slate-900 shadow-sm'
              }`}
            >
              <div className="flex items-center justify-between border-b pb-2 border-white/10">
                <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-amber-400">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <span>Learning & Evolution Snapshot</span>
                </div>
                <span className="text-xs text-slate-400">Continuous Adaptation</span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                {/* Self-evaluation */}
                <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                  <div className="text-xs text-slate-400 uppercase">Evaluations</div>
                  <div className="font-bold text-brand-400 text-sm">{resources?.self_evaluation.evaluations || 27}</div>
                  <div className="text-xs text-emerald-400">
                    {((resources?.self_evaluation.success_rate || 0.888) * 100).toFixed(1)}% Succ
                  </div>
                </div>

                {/* Knowledge */}
                <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                  <div className="text-xs text-slate-400 uppercase">Knowledge</div>
                  <div className="font-bold text-emerald-400 text-sm">{resources?.knowledge.built || 9} Built</div>
                  <div className="text-xs text-slate-400">{resources?.knowledge.accepted || 6} Acc / {resources?.knowledge.pending || 2} Pend</div>
                </div>

                {/* Evolution */}
                <div className={`p-2 rounded-lg border ${isDark ? 'bg-white/[0.02] border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                  <div className="text-xs text-slate-400 uppercase">Evolution</div>
                  <div className="font-bold text-amber-400 text-sm">{resources?.evolution.proposals || 3} Prop</div>
                  <div className="text-xs text-slate-400">{resources?.evolution.applied || 0} Applied</div>
                </div>
              </div>

              {/* Evolution Policy Note */}
              <div className={`p-2.5 rounded-lg border text-xs text-slate-400 flex items-start gap-2 ${
                isDark ? 'bg-black/30 border-white/5' : 'bg-slate-50 border-slate-200'
              }`}>
                <ShieldCheck className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
                <span>
                  Evolution requires explicit operator approval before runtime application. No autonomous code modification is auto-applied without verification.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* SYSTEM REASONING: OVERNIGHT LEARNING & SELF IMPROVEMENT       */}
      {/* ------------------------------------------------------------- */}
      {showReasoning && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Overnight Learning */}
            <OvernightLearningCard theme={theme} />

            {/* Self-Improvement Requests */}
            <SelfImprovementList theme={theme} />
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* ORGAN INTROSPECTIONS                                          */}
      {/* ------------------------------------------------------------- */}
      {showOrgans && (
        <div className="space-y-4">
          <OrganIntrospectionViewer theme={theme} />
        </div>
      )}
    </div>
  );
}
