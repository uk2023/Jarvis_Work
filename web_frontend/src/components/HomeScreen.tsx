import React, { useState } from 'react';
import {
  Activity,
  Shield,
  Sparkles,
  ArrowUp,
  Mic,
  MicOff,
  Cpu,
  Brain,
  Zap,
} from 'lucide-react';
import { AppTheme } from '../types';

interface HomeScreenProps {
  theme: AppTheme;
  onNavigateToView: (view: 'user_chat' | 'dashboard' | 'cli' | 'inspector') => void;
  onStartChatWithPrompt: (prompt: string) => void;
  isAdmin: boolean;
  onOpenAuth: () => void;
}

const QUICK_PROMPTS = [
  { label: 'Check status', icon: Zap, query: 'Show me current organism vitals and CPU status' },
  { label: 'Memory recall', icon: Brain, query: 'Survey FAISS episodic memory for recent context' },
  { label: 'Overnight learning', icon: Cpu, query: 'What was discovered during overnight idle learning?' },
];

export function HomeScreen({
  theme,
  onNavigateToView,
  onStartChatWithPrompt,
  isAdmin,
  onOpenAuth,
}: HomeScreenProps) {
  const isDark = theme === 'dark';
  const [prompt, setPrompt] = useState('');
  const [isListening, setIsListening] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    onStartChatWithPrompt(prompt.trim());
    setPrompt('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const toggleMic = () => {
    if (!isListening) {
      setIsListening(true);
      setTimeout(() => {
        setPrompt('JARVIS, check system status');
        setIsListening(false);
      }, 1800);
    } else {
      setIsListening(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto flex flex-col" style={{ backgroundColor: 'var(--jarvis-bg)', color: 'var(--jarvis-text)' }}>
      {/* One restrained hero moment: a quiet mark, a plain greeting, one
          status line -- not a stack of decorative badges/chrome. */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-xl flex flex-col items-center text-center">
          <div className="relative w-16 h-16 mb-6 flex items-center justify-center rounded-full border" style={{ borderColor: 'var(--jarvis-border-strong)' }}>
            <span className="absolute inline-flex h-2.5 w-2.5 rounded-full animate-ping opacity-40" style={{ backgroundColor: 'var(--jarvis-accent)' }} />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ backgroundColor: 'var(--jarvis-accent)' }} />
          </div>

          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight mb-2">
            Hi, I'm JARVIS
          </h1>
          <p className="text-base mb-10" style={{ color: 'var(--jarvis-text-muted)' }}>
            Ask me anything -- Hinglish is fine too.
          </p>

          <form
            onSubmit={handleSubmit}
            className="w-full rounded-2xl border p-3 text-left transition-colors focus-within:border-[var(--jarvis-accent)]"
            style={{ backgroundColor: 'var(--jarvis-surface)', borderColor: 'var(--jarvis-border)' }}
          >
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              placeholder="Message JARVIS..."
              className="w-full bg-transparent resize-none outline-none text-base"
              style={{ color: 'var(--jarvis-text)' }}
            />
            <div className="flex items-center justify-between pt-2 mt-1 border-t" style={{ borderColor: 'var(--jarvis-border)' }}>
              <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--jarvis-text-muted)' }}>
                <Sparkles size={13} />
                Native-first
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={toggleMic}
                  aria-label={isListening ? 'Stop listening' : 'Voice input'}
                  className="w-9 h-9 rounded-full flex items-center justify-center transition-colors"
                  style={isListening
                    ? { backgroundColor: 'var(--jarvis-danger)', color: 'white' }
                    : { color: 'var(--jarvis-text-muted)' }}
                >
                  {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                </button>
                <button
                  type="submit"
                  disabled={!prompt.trim()}
                  aria-label="Send"
                  className="w-9 h-9 rounded-full flex items-center justify-center transition-transform disabled:cursor-not-allowed"
                  style={{
                    backgroundColor: prompt.trim() ? 'var(--jarvis-accent)' : 'var(--jarvis-border)',
                    color: prompt.trim() ? 'white' : 'var(--jarvis-text-muted)',
                  }}
                >
                  <ArrowUp size={16} />
                </button>
              </div>
            </div>
          </form>

          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            {QUICK_PROMPTS.map(item => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => onStartChatWithPrompt(item.query)}
                  className="px-3 py-1.5 rounded-full border text-sm transition-colors flex items-center gap-1.5"
                  style={{ borderColor: 'var(--jarvis-border)', backgroundColor: 'var(--jarvis-surface)', color: 'var(--jarvis-text-muted)' }}
                >
                  <Icon size={13} style={{ color: 'var(--jarvis-accent)' }} />
                  {item.label}
                </button>
              );
            })}
          </div>

          <div className="mt-8">
            {isAdmin ? (
              <button
                onClick={() => onNavigateToView('dashboard')}
                className="text-sm hover:underline flex items-center gap-1.5"
                style={{ color: 'var(--jarvis-accent)' }}
              >
                <Activity size={14} />
                Open systems dashboard
              </button>
            ) : (
              <button
                onClick={onOpenAuth}
                className="text-sm flex items-center gap-1.5 transition-colors"
                style={{ color: 'var(--jarvis-text-muted)' }}
              >
                <Shield size={14} />
                Operator sign in
              </button>
            )}
          </div>
        </div>
      </section>

      <footer className="py-4 px-6 text-center text-xs" style={{ color: 'var(--jarvis-text-muted)' }}>
        JARVIS Cognitive OS
      </footer>
    </div>
  );
}
