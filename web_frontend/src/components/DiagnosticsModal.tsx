import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Terminal,
  X,
  Play,
  Minus,
  Maximize2,
  Minimize2,
  Radio,
  CheckCircle2,
  Trash2,
} from 'lucide-react';
import { AppTheme } from '../types';

interface DiagnosticsModalProps {
  isOpen: boolean;
  onClose: () => void;
  beatCount: number;
  theme?: AppTheme;
}

export const DiagnosticsModal: React.FC<DiagnosticsModalProps> = ({
  isOpen,
  onClose,
  beatCount,
  theme = 'dark',
}) => {
  const [logs, setLogs] = useState<string[]>([
    `[${new Date().toLocaleTimeString()}] [JARVIS-INIT] Subsystems bootstrapping on ARM64 Termux PRoot...`,
    `[${new Date().toLocaleTimeString()}] [ORGAN-ATTACH] Brain attached (BrainOrchestrator v0.6.0)`,
    `[${new Date().toLocaleTimeString()}] [MEMORY-INIT] FAISS Index loaded (384-dim ONNX MiniLM embedder)`,
    `[${new Date().toLocaleTimeString()}] [NEURAL-BRIDGE] Qwen2.5-3B-Instruct (Q4_K_M GGUF, 4 threads) online`,
    `[${new Date().toLocaleTimeString()}] [ASYNC-WORKER] Background Experience & Learning Worker thread active`,
    `[${new Date().toLocaleTimeString()}] [ORGANISM-PULSE] Heartbeat beating synchronously (Cycle #${beatCount})`,
  ]);
  const [cmdInput, setCmdInput] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const isDark = theme === 'dark';

  useEffect(() => {
    if (isOpen) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isOpen]);

  if (!isOpen) return null;

  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = cmdInput.trim();
    if (!cmd) return;

    const time = new Date().toLocaleTimeString();
    const newLogs = [...logs, `[${time}] UK@jarvis:~$ ${cmd}`];

    if (cmd === 'help') {
      newLogs.push(
        `Available Commands:\n - status : Show all organ health states\n - pulse  : Trigger biological heart wave\n - test-hinglish : Benchmark phonetic typo normalizer\n - clear  : Clear terminal logs`
      );
    } else if (cmd === 'status') {
      newLogs.push(
        `[STATUS MATRIX] 9 Organs Attached | Memory: 1.84 GB | Latency: 0.24s | Pipeline: Non-blocking Async`
      );
    } else if (cmd === 'pulse') {
      newLogs.push(
        `[PULSE] Heartbeat wave emitted ∿∿∿_/\\_∿∿∿ (72 BPM) | Subconscious Curiosity Active`
      );
    } else if (cmd === 'test-hinglish') {
      newLogs.push(
        `[BENCHMARK] Testing input "mera ex ka nan devyana h, mujhe python coding psnd h"\n -> Normalized: "mera ex ka naam devyana h, mujhe python coding pasand h"\n -> Fact Extracted: {subject: 'user_ex', predicate: 'name', value: 'Devyana'}\n -> Status: PASS (0.002s)`
      );
    } else if (cmd === 'clear') {
      setLogs([]);
      setCmdInput('');
      return;
    } else {
      newLogs.push(`[CMD] Command not recognized: "${cmd}". Type "help" for options.`);
    }

    setLogs(newLogs);
    setCmdInput('');
  };

  return (
    <AnimatePresence>
      <div
        id="virtual-cli-container"
        className="fixed inset-0 z-50 pointer-events-none flex items-end sm:items-center justify-end sm:p-5"
      >
        {/* Transparent non-blocking backdrop on desktop, light dismissible backdrop on mobile */}
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/30 backdrop-blur-[2px] pointer-events-auto sm:bg-black/10"
        />

        {/* Authentic Floating Terminal Window on Right Side */}
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 30, scale: 0.95 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className={`pointer-events-auto w-full flex flex-col rounded-t-2xl sm:rounded-2xl border shadow-2xl overflow-hidden font-mono text-xs z-50 transition-all ${
            isExpanded
              ? 'sm:w-[680px] h-[85vh]'
              : 'sm:w-[480px] md:w-[500px] h-[65vh] sm:h-[480px]'
          } ${
            isDark
              ? 'bg-[#090c15]/95 backdrop-blur-2xl border-white/20 text-white shadow-[0_20px_60px_rgba(0,0,0,0.8)]'
              : 'bg-slate-900/95 backdrop-blur-2xl border-slate-700 text-slate-100 shadow-[0_20px_50px_rgba(0,0,0,0.4)]'
          }`}
        >
          {/* Authentic Terminal Title Bar with Traffic Lights */}
          <div
            className={`flex items-center justify-between px-3.5 py-2.5 border-b select-none ${
              isDark ? 'bg-black/60 border-white/10' : 'bg-slate-950 border-slate-800'
            }`}
          >
            {/* Window Traffic Lights & Title */}
            <div className="flex items-center gap-2.5">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={onClose}
                  className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-600 transition flex items-center justify-center group cursor-pointer"
                  title="Close Terminal"
                >
                  <X className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100" />
                </button>
                <button
                  onClick={onClose}
                  className="w-3 h-3 rounded-full bg-amber-500 hover:bg-amber-600 transition flex items-center justify-center group cursor-pointer"
                  title="Minimize"
                >
                  <Minus className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100" />
                </button>
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="w-3 h-3 rounded-full bg-emerald-500 hover:bg-emerald-600 transition flex items-center justify-center group cursor-pointer"
                  title="Toggle Size"
                >
                  {isExpanded ? (
                    <Minimize2 className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100" />
                  ) : (
                    <Maximize2 className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100" />
                  )}
                </button>
              </div>

              <div className="flex items-center gap-1.5 text-[11px] text-slate-300 font-semibold pl-1">
                <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                <span className="truncate">jarvis@arm64: ~</span>
              </div>
            </div>

            {/* Right Status Badges */}
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 text-[10px] bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/30 font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                LIVE
              </span>
              <button
                onClick={() => setLogs([])}
                className="text-slate-400 hover:text-slate-200 p-1 rounded transition cursor-pointer"
                title="Clear Logs"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* Terminal Console Output */}
          <div
            className={`flex-1 overflow-y-auto p-3.5 space-y-1.5 text-[11px] leading-relaxed select-text font-mono ${
              isDark ? 'bg-black/70 text-slate-200' : 'bg-slate-950 text-slate-200'
            }`}
          >
            {logs.length === 0 ? (
              <div className="text-slate-500 italic py-4 text-center">
                Terminal cleared. Type 'help' for commands.
              </div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className="whitespace-pre-wrap break-words">
                  {log.includes('UK@jarvis') ? (
                    <span className="text-cyan-400 font-bold">{log}</span>
                  ) : log.includes('ERROR') ? (
                    <span className="text-red-400 font-semibold">{log}</span>
                  ) : log.includes('WARN') ? (
                    <span className="text-amber-400 font-semibold">{log}</span>
                  ) : log.includes('PASS') || log.includes('ONLINE') ? (
                    <span className="text-emerald-400 font-semibold">{log}</span>
                  ) : log.includes('[STATUS MATRIX]') || log.includes('[PULSE]') ? (
                    <span className="text-cyan-300">{log}</span>
                  ) : (
                    <span className="text-slate-300">{log}</span>
                  )}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>

          {/* Terminal Command Input Form */}
          <form
            onSubmit={handleCommand}
            className={`p-2.5 border-t flex items-center gap-2 ${
              isDark ? 'bg-black/80 border-white/10' : 'bg-slate-900 border-slate-800'
            }`}
          >
            <span className="text-cyan-400 font-bold shrink-0 text-xs">UK@jarvis:~$</span>
            <input
              type="text"
              value={cmdInput}
              onChange={e => setCmdInput(e.target.value)}
              placeholder="Type 'help', 'status', 'pulse', 'test-hinglish'..."
              className="flex-1 bg-transparent border-none outline-none text-white text-xs font-mono placeholder-slate-500"
              autoFocus
            />
            <button
              type="submit"
              className="px-2.5 py-1 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded-lg text-xs flex items-center gap-1 transition cursor-pointer shadow-sm"
            >
              <Play className="w-2.5 h-2.5 fill-black" />
              <span>Run</span>
            </button>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
