import { useState, useEffect, useRef } from 'react';
import { ChevronRight, Check, Loader2, Sparkles, AlertTriangle } from 'lucide-react';

/**
 * THINKING STEPS -- the Claude-style panel.
 *
 * UK asked for this repeatedly: "jaise Claude step by step think and
 * command run karta hai aur task complete karke last me saare turns ka
 * conclusion bhi deta hai + saath me jo steps liye jo kaam kiya wo
 * dikhe".
 *
 * So: a collapsed summary line while working ("Thinking… 3 steps"),
 * expandable to see each stage as it arrives, and a conclusion line at
 * the end saying what was actually done.
 *
 * WHAT THIS WILL NOT DO
 * =====================
 * It renders ONLY stages the server actually sent. There is no
 * placeholder step, no invented "Analysing your request…" while
 * waiting, no fabricated step count. If a stage has not arrived, the
 * row shows a spinner and the stage NAME and nothing else.
 *
 * That restraint is the whole point. A thinking panel that shows
 * plausible reasoning the model never did is indistinguishable from one
 * that works, and this project has already had to tear out several
 * things that looked alive and were not. If JARVIS did one step, the
 * panel says one step.
 */

export interface ThinkingStep {
  stage: string;
  content: string;
  duration_ms?: number;
  ok?: boolean;
}

const STAGE_LABEL: Record<string, string> = {
  understand: 'Samajh raha hun',
  explore: 'Options dekh raha hun',
  critique: 'Apna reasoning check kar raha hun',
  answer: 'Jawab bana raha hun',
};

export default function ThinkingSteps({
  steps,
  currentStage,
  done,
  reason,
  error,
  isDark = true,
}: {
  steps: ThinkingStep[];
  currentStage?: string | null;
  done?: boolean;
  reason?: string;
  error?: string | null;
  isDark?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [elapsed, setElapsed] = useState(0);

  // Live timer while working. Stops on completion so the number settles
  // instead of ticking forever.
  useEffect(() => {
    if (done) return;
    const started = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - started) / 1000), 200);
    return () => clearInterval(id);
  }, [done]);

  useEffect(() => {
    if (open && !done) bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [steps.length, currentStage, open, done]);

  if (steps.length === 0 && !currentStage && !error) return null;

  const totalMs = steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const stepWord = steps.length === 1 ? 'step' : 'steps';

  const summary = error
    ? 'Thinking rukk gayi'
    : done
    ? `Socha — ${steps.length} ${stepWord}${totalMs ? `, ${(totalMs / 1000).toFixed(1)}s` : ''}`
    : `Soch raha hun… ${elapsed.toFixed(1)}s`;

  return (
    <div
      className={`mb-2 overflow-hidden rounded-2xl border text-left ${
        isDark ? 'border-white/10 bg-white/[0.03]' : 'border-slate-200 bg-slate-50'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full items-center gap-2 px-3 py-2 text-xs transition ${
          isDark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-500 hover:text-slate-800'
        }`}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
        />
        {error ? (
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
        ) : done ? (
          <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
        ) : (
          <Sparkles className="h-3.5 w-3.5 shrink-0 animate-pulse text-brand-400" />
        )}
        <span className="font-medium">{summary}</span>
        {reason && (
          <span className="ml-auto hidden truncate pl-3 text-[11px] opacity-60 sm:inline">
            {reason}
          </span>
        )}
      </button>

      {open && (
        <div
          className={`space-y-3 border-t px-3 py-3 ${
            isDark ? 'border-white/10' : 'border-slate-200'
          }`}
        >
          {steps.map((step, i) => (
            <div key={`${step.stage}-${i}`} className="relative pl-4">
              {/* Step rail */}
              <span
                className={`absolute left-0 top-1.5 h-1.5 w-1.5 rounded-full ${
                  step.ok === false ? 'bg-amber-400' : 'bg-brand-400'
                }`}
              />
              {i < steps.length - 1 && (
                <span
                  className={`absolute left-[2.5px] top-4 bottom-[-10px] w-px ${
                    isDark ? 'bg-white/10' : 'bg-slate-200'
                  }`}
                />
              )}

              <div className="flex items-baseline gap-2">
                <span
                  className={`text-[11px] font-medium uppercase tracking-wide ${
                    isDark ? 'text-brand-300/80' : 'text-brand-600'
                  }`}
                >
                  {STAGE_LABEL[step.stage] ?? step.stage}
                </span>
                {typeof step.duration_ms === 'number' && (
                  <span className="text-[10px] text-slate-500">
                    {Math.round(step.duration_ms)}ms
                  </span>
                )}
              </div>

              <p
                className={`mt-1 whitespace-pre-wrap text-xs leading-relaxed ${
                  isDark ? 'text-slate-400' : 'text-slate-600'
                }`}
              >
                {step.content}
              </p>
            </div>
          ))}

          {/* In-flight stage: spinner and the stage name ONLY. No
              placeholder reasoning -- see the component note above. */}
          {!done && currentStage && !steps.some((s) => s.stage === currentStage) && (
            <div className="flex items-center gap-2 pl-4 text-xs text-slate-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              {STAGE_LABEL[currentStage] ?? currentStage}
            </div>
          )}

          {error && (
            <p className="pl-4 text-xs text-amber-300">
              {error}
            </p>
          )}

          {/* Conclusion: what was actually done, counted from real
              steps -- not a generated summary of work that may not have
              happened. */}
          {done && steps.length > 0 && (
            <div
              className={`mt-1 border-t pt-2 pl-4 text-[11px] ${
                isDark ? 'border-white/10 text-slate-500' : 'border-slate-200 text-slate-500'
              }`}
            >
              {steps.length} {stepWord} chale
              {totalMs ? ` (${(totalMs / 1000).toFixed(1)}s)` : ''}
              {steps.some((s) => s.ok === false) && ' — kuch step fail hue'}
              . Jawab neeche hai.
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
