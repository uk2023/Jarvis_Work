import React from 'react';
import { motion } from 'motion/react';
import {
  Sparkles,
  Compass,
  Zap,
  CheckCircle2,
  Clock,
  Cpu,
  RefreshCw,
  GitPullRequest,
  ShieldCheck,
  Flame,
  Radio,
} from 'lucide-react';
import { CuriosityGoal, EvolutionProposal, AppTheme } from '../types';

interface AutonomyCuriosityProps {
  goals: CuriosityGoal[];
  proposals: EvolutionProposal[];
  onTriggerCuriosity: () => void;
  theme?: AppTheme;
}

export const AutonomyCuriosity: React.FC<AutonomyCuriosityProps> = ({
  goals,
  proposals,
  onTriggerCuriosity,
  theme = 'dark',
}) => {
  const isDark = theme === 'dark';

  return (
    <div
      id="autonomy-curiosity-view"
      className="h-full overflow-y-auto p-4 sm:p-6 max-w-5xl mx-auto space-y-6 select-text"
    >
      {/* Hero Banner */}
      <div
        className={`border rounded-2xl p-5 shadow-sm relative overflow-hidden transition-colors ${
          isDark
            ? 'bg-[#0b0e17]/80 backdrop-blur-2xl border-white/10 shadow-2xl'
            : 'bg-white border-slate-200/90 shadow-sm'
        }`}
      >
        <div
          className={`absolute top-0 right-0 w-64 h-64 rounded-full blur-3xl pointer-events-none ${
            isDark ? 'bg-cyan-500/10' : 'bg-cyan-500/5'
          }`}
        />
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-500 animate-pulse shadow-[0_0_8px_#22d3ee]"></div>
              <h2
                className={`text-sm sm:text-base font-bold tracking-widest uppercase font-mono ${
                  isDark ? 'text-cyan-50' : 'text-slate-900'
                }`}
              >
                SUBCONSCIOUS CURIOSITY & EVOLUTION CHAMBER
              </h2>
            </div>
            <p className={`text-xs font-mono ${isDark ? 'text-white/60' : 'text-slate-500'}`}>
              Autonomous Idle Loop, Safe Goal Decomposition & Controlled Self-Improvement Patches
            </p>
          </div>

          <button
            onClick={onTriggerCuriosity}
            className={`px-4 py-2 rounded-xl text-xs font-semibold font-mono flex items-center gap-2 transition cursor-pointer ${
              isDark
                ? 'bg-cyan-400/15 hover:bg-cyan-400/25 text-cyan-200 border border-cyan-400/40 shadow-[0_0_12px_rgba(34,211,238,0.2)]'
                : 'bg-cyan-50 hover:bg-cyan-100 text-cyan-700 border border-cyan-300 shadow-sm'
            }`}
          >
            <Sparkles className="w-4 h-4 text-cyan-500 dark:text-cyan-400 animate-spin" style={{ animationDuration: '4s' }} />
            <span>Trigger Idle Curiosity Cycle</span>
          </button>
        </div>
      </div>

      {/* Subconscious Goals Section */}
      <div
        className={`border rounded-2xl p-5 shadow-sm space-y-4 transition-colors ${
          isDark
            ? 'bg-[#0f121d]/80 backdrop-blur-2xl border-white/10 shadow-2xl'
            : 'bg-white border-slate-200/90 shadow-sm'
        }`}
      >
        <div className="flex items-center justify-between">
          <h3
            className={`text-xs font-bold font-mono flex items-center gap-2 uppercase tracking-wider ${
              isDark ? 'text-cyan-300' : 'text-cyan-700'
            }`}
          >
            <Compass className="w-4 h-4 text-cyan-500 dark:text-cyan-400" /> Active Curiosity & Learning Goals
          </h3>
          <span className={`text-[10px] font-mono ${isDark ? 'text-white/40' : 'text-slate-400'}`}>
            {goals.filter(g => g.status === 'active').length} Active &bull;{' '}
            {goals.filter(g => g.status === 'completed').length} Completed
          </span>
        </div>

        <div className="space-y-3">
          {goals.map(goal => (
            <motion.div
              key={goal.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`border p-4 rounded-2xl font-mono text-xs space-y-2.5 transition ${
                isDark
                  ? 'bg-black/40 backdrop-blur-xl border-white/10 hover:border-cyan-400/40 shadow-xl'
                  : 'bg-slate-50 border-slate-200 hover:border-cyan-400 shadow-sm'
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`font-semibold text-xs flex items-center gap-2 ${
                    isDark ? 'text-white' : 'text-slate-900'
                  }`}
                >
                  <Flame className="w-3.5 h-3.5 text-orange-500" />
                  {goal.text}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[10px] uppercase font-bold border ${
                    goal.status === 'active'
                      ? isDark
                        ? 'bg-cyan-400/10 text-cyan-300 border-cyan-400/30'
                        : 'bg-cyan-50 text-cyan-700 border-cyan-200'
                      : isDark
                      ? 'bg-green-400/10 text-green-400 border-green-400/30'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}
                >
                  {goal.status}
                </span>
              </div>

              {/* Progress Milestones */}
              <div className="pl-3 border-l-2 border-cyan-500/30 space-y-1">
                {goal.progress.map((prog, idx) => (
                  <div
                    key={idx}
                    className={`text-[11px] flex items-center gap-2 ${
                      isDark ? 'text-slate-300' : 'text-slate-600'
                    }`}
                  >
                    <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />
                    <span>{prog}</span>
                  </div>
                ))}
              </div>

              <div
                className={`flex items-center justify-between text-[10px] pt-1 border-t ${
                  isDark ? 'text-white/40 border-white/5' : 'text-slate-400 border-slate-200'
                }`}
              >
                <span>Origin: {goal.origin.toUpperCase()}</span>
                <span>Priority: {(goal.priority * 100).toFixed(0)}%</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Evolution Proposals Section */}
      <div
        className={`border rounded-2xl p-5 shadow-sm space-y-4 transition-colors ${
          isDark
            ? 'bg-[#0f121d]/80 backdrop-blur-2xl border-white/10 shadow-2xl'
            : 'bg-white border-slate-200/90 shadow-sm'
        }`}
      >
        <div className="flex items-center justify-between">
          <h3
            className={`text-xs font-bold font-mono flex items-center gap-2 uppercase tracking-wider ${
              isDark ? 'text-cyan-300' : 'text-cyan-700'
            }`}
          >
            <GitPullRequest className="w-4 h-4 text-cyan-500 dark:text-cyan-400" /> Controlled Evolution & Runtime Patches
          </h3>
          <span className={`text-[10px] font-mono ${isDark ? 'text-white/40' : 'text-slate-400'}`}>
            {proposals.length} Self-Improvement Probes
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          {proposals.map(evo => (
            <div
              key={evo.id}
              className={`border p-4 rounded-2xl font-mono text-xs space-y-2 transition ${
                isDark
                  ? 'bg-black/40 backdrop-blur-xl border-white/10 hover:border-cyan-400/40 shadow-xl'
                  : 'bg-slate-50 border-slate-200 hover:border-cyan-400 shadow-sm'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`font-bold text-xs capitalize ${isDark ? 'text-cyan-300' : 'text-cyan-700'}`}>
                  {evo.target.replace(/_/g, ' ')}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-lg text-[10px] font-bold border ${
                    isDark
                      ? 'bg-green-400/10 text-green-400 border-green-400/30'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}
                >
                  {evo.status}
                </span>
              </div>

              <p className={`text-[11px] leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                {evo.reason}
              </p>

              <div
                className={`pt-2 border-t flex items-center justify-between text-[10px] ${
                  isDark ? 'text-white/40 border-white/5' : 'text-slate-400 border-slate-200'
                }`}
              >
                <span>Validation Score: {(evo.score * 100).toFixed(0)}%</span>
                <span className="text-emerald-600 dark:text-green-400 flex items-center gap-1 font-bold">
                  <ShieldCheck className="w-3 h-3" /> Structure Verified
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
