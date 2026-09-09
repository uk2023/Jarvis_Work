import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface TabHeaderProps {
  icon: LucideIcon;
  category: string;
  title: string;
  statusBadge?: React.ReactNode;
  controls?: React.ReactNode;
}

export const TabHeader: React.FC<TabHeaderProps> = ({ icon: Icon, category, title, statusBadge, controls }) => (
  <header className="bg-white/80 backdrop-blur-md rounded-2xl p-3 border border-slate-200/80 shadow-sm mb-4 w-full dark:bg-slate-900/80 dark:border-slate-700/70">
    <div className="flex items-center justify-between w-full gap-2">
      <div className="flex items-center gap-2 min-w-0 flex-1">
        <div className="w-8 h-8 rounded-xl bg-blue-50/80 border border-blue-200/50 flex items-center justify-center shrink-0 dark:bg-blue-500/10 dark:border-blue-400/20">
          <Icon size={15} />
        </div>
        <div className="flex items-baseline gap-2 min-w-0">
          <div className="text-[10px] font-mono text-slate-400 uppercase whitespace-nowrap">{category}</div>
          <h2 className="text-xs font-bold text-slate-800 uppercase tracking-tight leading-tight whitespace-nowrap dark:text-slate-100">{title}</h2>
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0 whitespace-nowrap" aria-label="Live">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-2 w-2 rounded-full bg-emerald-400 animate-ping opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="text-[10px] font-bold tracking-wider text-emerald-600 font-mono dark:text-emerald-400">LIVE</span>
      </div>
    </div>
    {controls && (
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-100/60 overflow-x-auto no-scrollbar whitespace-nowrap w-full dark:border-slate-700/60">
        {controls}
      </div>
    )}
  </header>
);
